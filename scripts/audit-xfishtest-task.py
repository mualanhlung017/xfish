#!/usr/bin/env python3
"""Audit one completed paired-xfishtest task from immutable worker artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task-id", required=True, type=int)
    parser.add_argument("--opening-offset", required=True, type=int)
    parser.add_argument("--expected-pairs", type=int, default=100)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--new-sha", required=True)
    parser.add_argument("--base-engine-sha256", required=True)
    parser.add_argument("--new-engine-sha256", required=True)
    parser.add_argument("--network-sha256", required=True)
    parser.add_argument("--nominal-tc", default="10+0.1")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    task_dir = args.task_dir.resolve()
    summaries = sorted(task_dir.glob("pair-*.json"))
    require(task_dir.is_dir(), f"task directory does not exist: {task_dir}")
    require(
        len(summaries) == args.expected_pairs,
        f"JSON count {len(summaries)} != {args.expected_pairs}",
    )

    aggregate_scores = [0, 0, 0]
    aggregate_pentanomial = [0, 0, 0, 0, 0]
    aggregate_time_losses = [0, 0]
    global_pairs: list[int] = []
    local_pairs: list[int] = []
    fen_hashes: list[str] = []
    manifest_entries: list[tuple[str, str]] = []

    for summary_path in summaries:
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception as error:  # preserve all remaining audit evidence
            errors.append(f"{summary_path.name}: invalid JSON: {error}")
            continue

        global_pair = payload.get("global_pair")
        local_pair = payload.get("local_pair")
        stem = f"pair-{global_pair:06d}" if isinstance(global_pair, int) else summary_path.stem
        epd_path = task_dir / f"{stem}.epd"
        log_path = task_dir / f"{stem}.log"

        require(summary_path.name == f"{stem}.json", f"{summary_path.name}: filename/index mismatch")
        require(epd_path.is_file(), f"{stem}: missing EPD")
        require(log_path.is_file(), f"{stem}: missing log")
        require(payload.get("schema") == 1, f"{stem}: schema is not 1")
        require(payload.get("run_id") == args.run_id, f"{stem}: wrong run_id")
        require(payload.get("task_id") == args.task_id, f"{stem}: wrong task_id")
        require(isinstance(global_pair, int), f"{stem}: invalid global_pair")
        require(isinstance(local_pair, int), f"{stem}: invalid local_pair")

        if isinstance(global_pair, int):
            global_pairs.append(global_pair)
        if isinstance(local_pair, int):
            local_pairs.append(local_pair)

        expected_identity = {
            "base_sha": args.base_sha,
            "new_sha": args.new_sha,
            "base_engine_sha256": args.base_engine_sha256,
            "new_engine_sha256": args.new_engine_sha256,
            "base_network_sha256": args.network_sha256,
            "new_network_sha256": args.network_sha256,
            "nominal_tc": args.nominal_tc,
        }
        for key, expected in expected_identity.items():
            require(payload.get(key) == expected, f"{stem}: {key} mismatch")

        scores = payload.get("scores")
        penta = payload.get("pentanomial")
        time_losses = payload.get("time_losses")
        require(
            isinstance(scores, list)
            and len(scores) == 3
            and all(isinstance(value, int) and value >= 0 for value in scores)
            and sum(scores) == 2,
            f"{stem}: invalid W/L/D score vector",
        )
        require(
            isinstance(penta, list)
            and len(penta) == 5
            and all(isinstance(value, int) and value >= 0 for value in penta)
            and sum(penta) == 1,
            f"{stem}: invalid pentanomial vector",
        )
        if isinstance(scores, list) and len(scores) == 3 and all(isinstance(v, int) for v in scores):
            for index, value in enumerate(scores):
                aggregate_scores[index] += value
            penta_index = 2 * scores[0] + scores[2]
            require(
                isinstance(penta, list)
                and len(penta) == 5
                and penta[penta_index] == 1,
                f"{stem}: pentanomial does not encode candidate score",
            )
        if isinstance(penta, list) and len(penta) == 5 and all(isinstance(v, int) for v in penta):
            for index, value in enumerate(penta):
                aggregate_pentanomial[index] += value

        require(
            payload.get("white_wins", 0)
            + payload.get("black_wins", 0)
            + payload.get("draw_games", 0)
            == 2,
            f"{stem}: color-result totals do not equal two games",
        )
        require(
            isinstance(time_losses, list)
            and len(time_losses) == 2
            and all(isinstance(value, int) and value == 0 for value in time_losses),
            f"{stem}: time loss detected or malformed",
        )
        if isinstance(time_losses, list) and len(time_losses) == 2 and all(
            isinstance(value, int) for value in time_losses
        ):
            for index, value in enumerate(time_losses):
                aggregate_time_losses[index] += value

        if epd_path.is_file():
            fen = epd_path.read_text(encoding="utf-8").strip()
            fen_sha = sha256_bytes(fen.encode("utf-8"))
            require(payload.get("fen_sha256") == fen_sha, f"{stem}: FEN SHA-256 mismatch")
            fen_hashes.append(fen_sha)

        if log_path.is_file():
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
            require(log_text.count("Game (xiangqi):") == 2, f"{stem}: log does not contain two Xiangqi games")
            require("# of games: 2" in log_text, f"{stem}: log game count mismatch")
            require("'Hash': '16'" in log_text, f"{stem}: Hash=16 missing from log")
            require("'Threads': '1'" in log_text, f"{stem}: Threads=1 missing from log")
            require(
                re.search(r"time losses engine1:\s*0", log_text) is not None
                and re.search(r"time losses engine2:\s*0", log_text) is not None,
                f"{stem}: nonzero or missing time-loss summary",
            )
            require("Traceback" not in log_text, f"{stem}: traceback in match log")

        for artifact in (summary_path, epd_path, log_path):
            if artifact.is_file():
                manifest_entries.append((artifact.name, sha256_file(artifact)))

    expected_local = list(range(args.expected_pairs))
    expected_global = list(range(args.opening_offset, args.opening_offset + args.expected_pairs))
    require(sorted(local_pairs) == expected_local, "local-pair range is not contiguous and complete")
    require(sorted(global_pairs) == expected_global, "global-pair range is not contiguous and complete")
    require(len(set(global_pairs)) == len(global_pairs), "duplicate global pair")
    require(len(set(fen_hashes)) == len(fen_hashes), "duplicate FEN in task")
    require(
        sum(aggregate_scores) == 2 * len(summaries),
        "aggregate W/L/D game count mismatch",
    )
    require(
        sum(aggregate_pentanomial) == len(summaries),
        "aggregate pentanomial pair count mismatch",
    )
    require(sum(aggregate_time_losses) == 0, "aggregate time loss is nonzero")

    manifest_text = "".join(
        f"{name}\0{digest}\n" for name, digest in sorted(manifest_entries)
    ).encode("utf-8")
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "passed": not errors,
        "task_dir": str(task_dir),
        "run_id": args.run_id,
        "task_id": args.task_id,
        "expected_pairs": args.expected_pairs,
        "opening_offset": args.opening_offset,
        "pairs_audited": len(summaries),
        "games_audited": sum(aggregate_scores),
        "scores_wld": aggregate_scores,
        "pentanomial": aggregate_pentanomial,
        "time_losses": aggregate_time_losses,
        "fen_count": len(fen_hashes),
        "unique_fen_count": len(set(fen_hashes)),
        "artifact_count": len(manifest_entries),
        "artifact_manifest_sha256": sha256_bytes(manifest_text),
        "errors": errors,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
