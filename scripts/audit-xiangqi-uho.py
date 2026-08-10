#!/usr/bin/env python3
"""Independently audit an Xfish-generated Xiangqi UHO corpus.

The generator writes enough provenance to reconstruct every filtering
decision.  This tool deliberately re-reads those artifacts instead of using
generator internals, so a generator or manifest bug cannot silently bless its
own output.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable, Iterator


MOVE_RE = re.compile(r"^[a-i][0-9][a-i][0-9]$")
PIECE_SYMBOLS = frozenset("rnbakcpRNBAKCP")
WDL_COMPONENT_INDEX = {"win": 0, "draw": 1, "loss": 2}


class AuditError(RuntimeError):
    """Raised when an artifact violates the frozen corpus contract."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_key(seed: str, fen: str) -> bytes:
    return hashlib.sha256(seed.encode() + b"\0" + fen.encode()).digest()


def validate_fen(fen: str) -> None:
    fields = fen.split()
    if len(fields) != 6:
        raise AuditError(f"malformed FEN field count: {fen}")
    board, side, castling, en_passant, halfmove, fullmove = fields
    if side != "w":
        raise AuditError(f"book FEN does not leave Red to move: {fen}")
    if castling != "-" or en_passant != "-":
        raise AuditError(f"unexpected Xiangqi FEN flags: {fen}")
    if not halfmove.isdigit() or not fullmove.isdigit():
        raise AuditError(f"invalid Xiangqi FEN counters: {fen}")
    ranks = board.split("/")
    if len(ranks) != 10:
        raise AuditError(f"Xiangqi FEN does not contain ten ranks: {fen}")
    kings = Counter()
    for rank in ranks:
        width = 0
        for symbol in rank:
            if symbol.isdigit():
                width += int(symbol)
            elif symbol in PIECE_SYMBOLS:
                width += 1
                if symbol in "Kk":
                    kings[symbol] += 1
            else:
                raise AuditError(f"unexpected Xiangqi FEN symbol {symbol!r}: {fen}")
        if width != 9:
            raise AuditError(f"Xiangqi FEN rank width is not nine: {fen}")
    if kings != Counter({"K": 1, "k": 1}):
        raise AuditError(f"Xiangqi FEN must contain exactly two kings: {fen}")


def text_lines(path: Path) -> list[str]:
    data = path.read_bytes()
    if not data or not data.endswith(b"\n"):
        raise AuditError(f"{path.name} is empty or lacks a final LF")
    if b"\r" in data:
        raise AuditError(f"{path.name} is not LF-normalized")
    try:
        lines = data.decode("ascii").splitlines()
    except UnicodeDecodeError as error:
        raise AuditError(f"{path.name} is not ASCII") from error
    if any(not line for line in lines):
        raise AuditError(f"{path.name} contains an empty line")
    return lines


def json_lines(path: Path) -> Iterator[tuple[int, dict[str, object]]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        for line_number, raw in enumerate(stream, 1):
            if "\r" in raw:
                raise AuditError(f"{path.name}:{line_number} contains CR")
            if not raw.endswith("\n"):
                raise AuditError(f"{path.name}:{line_number} lacks LF")
            try:
                value = json.loads(raw)
            except json.JSONDecodeError as error:
                raise AuditError(f"invalid JSON in {path.name}:{line_number}") from error
            if not isinstance(value, dict):
                raise AuditError(f"non-object JSON in {path.name}:{line_number}")
            yield line_number, value


def validate_exact_record(record: object, label: str) -> dict[str, object]:
    if not isinstance(record, dict):
        raise AuditError(f"{label} is not a search record")
    if record.get("score_type") != "cp":
        raise AuditError(f"{label} is not a centipawn score")
    if record.get("bound") not in ("", None):
        raise AuditError(f"{label} is a bounded score")
    score = record.get("score")
    if not isinstance(score, int) or isinstance(score, bool):
        raise AuditError(f"{label} has an invalid score")
    wdl = record.get("wdl")
    if (
        not isinstance(wdl, list)
        or len(wdl) != 3
        or any(not isinstance(value, int) or isinstance(value, bool) for value in wdl)
        or min(wdl) < 0
        or sum(wdl) != 1000
    ):
        raise AuditError(f"{label} has an invalid WDL triplet")
    return record


def histogram_bucket(component: str, value: int) -> str:
    width = 5 if component == "draw" else 25
    lower = value // width * width
    return f"{lower:03d}-{lower + width - 1:03d}"


def require_equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise AuditError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def audit_positions(
    output_dir: Path,
    plies: int,
    seed: str,
    candidates: list[str],
) -> dict[str, int]:
    paths_file = output_dir / f"depth-{plies:02d}.paths"
    positions_file = output_dir / "positions.jsonl"
    unique_noncheck: set[str] = set()
    leaf_paths = checked = duplicates = 0
    sentinel = object()
    with paths_file.open("r", encoding="ascii", newline="") as paths_stream:
        pairs = itertools.zip_longest(
            paths_stream,
            json_lines(positions_file),
            fillvalue=sentinel,
        )
        for leaf_paths, pair in enumerate(pairs, 1):
            raw_path, numbered = pair
            if raw_path is sentinel or numbered is sentinel:
                raise AuditError("final paths and positions.jsonl have different lengths")
            assert isinstance(raw_path, str)
            if "\r" in raw_path or not raw_path.endswith("\n"):
                raise AuditError(f"final path {leaf_paths} is not LF-normalized")
            path_text = raw_path[:-1]
            moves = path_text.split()
            if len(moves) != plies or any(
                not MOVE_RE.fullmatch(move) for move in moves
            ):
                raise AuditError(f"invalid final move path at line {leaf_paths}")
            line_number, record = numbered
            require_equal(line_number, leaf_paths, "position line number")
            require_equal(record.get("path"), path_text, f"position path {leaf_paths}")
            fen = record.get("fen")
            if not isinstance(fen, str):
                raise AuditError(f"positions.jsonl:{leaf_paths} lacks FEN")
            validate_fen(fen)
            checkers = record.get("checkers", "")
            if not isinstance(checkers, str):
                raise AuditError(f"positions.jsonl:{leaf_paths} has invalid checkers")
            if checkers:
                checked += 1
            elif fen in unique_noncheck:
                duplicates += 1
            else:
                unique_noncheck.add(fen)

    previous_key: bytes | None = None
    candidate_seen: set[str] = set()
    for line_number, fen in enumerate(candidates, 1):
        validate_fen(fen)
        if fen in candidate_seen:
            raise AuditError(f"duplicate candidate FEN at line {line_number}")
        candidate_seen.add(fen)
        if fen not in unique_noncheck:
            raise AuditError(f"candidate FEN {line_number} is absent from positions.jsonl")
        key = stable_key(seed, fen)
        if previous_key is not None and key <= previous_key:
            raise AuditError(f"candidate order is not deterministic at line {line_number}")
        previous_key = key
    require_equal(candidate_seen, unique_noncheck, "candidate FEN set")
    return {
        "leaf_paths": leaf_paths,
        "checked_positions": checked,
        "duplicate_fens": duplicates,
        "unique_noncheck_fens": len(unique_noncheck),
    }


def audit_scores(
    output_dir: Path,
    candidates: list[str],
    book: list[str],
    component: str,
    lower: int,
    upper: int,
    second_move_window: int,
) -> tuple[Counter[str], dict[str, Counter[str]]]:
    reasons: Counter[str] = Counter()
    histograms = {name: Counter() for name in WDL_COMPONENT_INDEX}
    accepted_index = 0
    sentinel = object()
    score_rows = json_lines(output_dir / "scores.jsonl")
    for index, pair in enumerate(
        itertools.zip_longest(candidates, score_rows, fillvalue=sentinel), 1
    ):
        fen, numbered = pair
        if fen is sentinel or numbered is sentinel:
            raise AuditError("candidates.epd and scores.jsonl have different lengths")
        assert isinstance(fen, str)
        line_number, record = numbered
        require_equal(line_number, index, "score line number")
        require_equal(record.get("fen"), fen, f"score FEN {index}")
        accepted = record.get("accepted")
        reason = record.get("reason")
        if not isinstance(accepted, bool) or not isinstance(reason, str):
            raise AuditError(f"scores.jsonl:{index} has invalid decision fields")
        if accepted != (reason == "accepted"):
            raise AuditError(f"scores.jsonl:{index} has inconsistent decision fields")
        reasons[reason] += 1
        if not accepted:
            continue
        if accepted_index >= len(book) or book[accepted_index] != fen:
            raise AuditError(f"book does not reproduce accepted score {index}")
        accepted_index += 1
        best = validate_exact_record(record.get("best"), f"score {index} best")
        second = validate_exact_record(record.get("second"), f"score {index} second")
        best_wdl = best["wdl"]
        assert isinstance(best_wdl, list)
        value = best_wdl[WDL_COMPONENT_INDEX[component]]
        if not lower <= value <= upper:
            raise AuditError(
                f"accepted score {index} has {component}={value}, outside {lower}..{upper}"
            )
        best_score = best["score"]
        second_score = second["score"]
        assert isinstance(best_score, int) and isinstance(second_score, int)
        if best_score - second_score > second_move_window:
            raise AuditError(f"accepted score {index} violates second-move window")
        for name, wdl_value in zip(("win", "draw", "loss"), best_wdl):
            histograms[name][histogram_bucket(name, wdl_value)] += 1
    require_equal(accepted_index, len(book), "accepted book length")
    return reasons, histograms


def audit_corpus(
    output_dir: Path,
    *,
    expected_component: str = "draw",
    expected_min: int = 481,
    expected_max: int = 519,
    minimum_positions: int = 50000,
) -> dict[str, object]:
    output_dir = output_dir.resolve()
    manifest_path = output_dir / "manifest.json"
    config_path = output_dir / "generation-config.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(config, dict):
        raise AuditError("manifest or generation config is not a JSON object")
    require_equal(manifest.get("status"), "passed", "manifest status")
    require_equal(manifest.get("schema"), 2, "manifest schema")
    require_equal(config.get("schema"), 2, "generation config schema")
    require_equal(manifest.get("parameters"), config, "manifest parameters")
    require_equal(config.get("wdl_component"), expected_component, "WDL component")
    require_equal(config.get("wdl_min"), expected_min, "WDL lower bound")
    require_equal(config.get("wdl_max"), expected_max, "WDL upper bound")
    plies = config.get("plies")
    seed = config.get("seed")
    second_move_window = config.get("second_move_window_cp")
    if not isinstance(plies, int) or plies < 1 or plies % 2:
        raise AuditError("invalid even ply count")
    if not isinstance(seed, str) or not seed:
        raise AuditError("invalid generation seed")
    if not isinstance(second_move_window, int) or second_move_window < 0:
        raise AuditError("invalid second-move window")

    book_section = manifest.get("book")
    counts_section = manifest.get("counts")
    artifacts = manifest.get("artifacts")
    if not all(isinstance(value, dict) for value in (book_section, counts_section, artifacts)):
        raise AuditError("manifest lacks book, counts, or artifacts section")
    assert isinstance(book_section, dict)
    assert isinstance(counts_section, dict)
    assert isinstance(artifacts, dict)
    book_name = book_section.get("name")
    if not isinstance(book_name, str) or Path(book_name).name != book_name:
        raise AuditError("manifest book name is unsafe")
    book_path = output_dir / book_name
    candidates_path = output_dir / "candidates.epd"
    book = text_lines(book_path)
    candidates = text_lines(candidates_path)
    if len(book) < minimum_positions:
        raise AuditError(f"book contains only {len(book)} positions")
    if len(set(book)) != len(book):
        raise AuditError("book contains duplicate FENs")
    for fen in book:
        validate_fen(fen)

    expected_hashes = {
        "generation_config_sha256": config_path,
        "final_paths_sha256": output_dir / f"depth-{plies:02d}.paths",
        "positions_jsonl_sha256": output_dir / "positions.jsonl",
        "candidates_epd_sha256": candidates_path,
        "scores_jsonl_sha256": output_dir / "scores.jsonl",
    }
    for field, path in expected_hashes.items():
        require_equal(sha256_file(path), artifacts.get(field), field)
    require_equal(sha256_file(book_path), book_section.get("sha256"), "book SHA-256")

    position_counts = audit_positions(output_dir, plies, seed, candidates)
    reasons, histograms = audit_scores(
        output_dir,
        candidates,
        book,
        expected_component,
        expected_min,
        expected_max,
        second_move_window,
    )
    expected_counts = {
        **position_counts,
        "scored_fens": len(candidates),
        "accepted_fens": len(book),
        "minimum_positions": counts_section.get("minimum_positions"),
    }
    for field, value in expected_counts.items():
        require_equal(counts_section.get(field), value, f"count {field}")
    require_equal(book_section.get("positions"), len(book), "book position count")
    require_equal(manifest.get("rejection_reasons"), dict(sorted(reasons.items())), "rejections")
    normalized_histograms = {
        name: dict(sorted(histogram.items()))
        for name, histogram in sorted(histograms.items())
    }
    require_equal(
        manifest.get("accepted_wdl_histograms"),
        normalized_histograms,
        "accepted WDL histograms",
    )
    return {
        "status": "passed",
        "output_dir": str(output_dir),
        "book": book_name,
        "book_sha256": sha256_file(book_path),
        "manifest_sha256": sha256_file(manifest_path),
        "positions": len(book),
        "candidates": len(candidates),
        "wdl_component": expected_component,
        "wdl_min": expected_min,
        "wdl_max": expected_max,
        "counts": expected_counts,
        "rejection_reasons": dict(sorted(reasons.items())),
        "accepted_wdl_histograms": normalized_histograms,
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--output-dir", type=Path, required=True)
    root.add_argument("--report", type=Path)
    root.add_argument("--expected-component", choices=tuple(WDL_COMPONENT_INDEX), default="draw")
    root.add_argument("--expected-min", type=int, default=481)
    root.add_argument("--expected-max", type=int, default=519)
    root.add_argument("--minimum-positions", type=int, default=50000)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        result = audit_corpus(
            args.output_dir,
            expected_component=args.expected_component,
            expected_min=args.expected_min,
            expected_max=args.expected_max,
            minimum_positions=args.minimum_positions,
        )
    except (AuditError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"audit failed: {error}", file=sys.stderr)
        return 2
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
