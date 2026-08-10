#!/usr/bin/env python3
"""Compare Xiangqi rule and NNUE invariants across xfish binaries.

The verifier deliberately separates invariants from playing-strength changes:

* legal root moves and deeper perft counts must always match;
* the raw NNUE result and loaded network architecture must always match;
* every searched best move must be legal;
* for a claimed "No functional change" patch, deterministic search results must
  also match the current baseline exactly.

The same NNUE file is loaded by every engine.  A JSON report containing hashes,
inputs, results, and any mismatch is written for later audit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import random
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable


MOVE_RE = re.compile(r"^([a-i][0-9][a-i][0-9]):\s+([0-9]+)\s*$")
NODES_RE = re.compile(r"^Nodes searched:\s*([0-9]+)\s*$")
RAW_NNUE_RE = re.compile(
    r"^NNUE evaluation\s+([+-]?[0-9]+)\s+\(side to move, internal units\)\s*$"
)
FINAL_EVAL_RE = re.compile(
    r"^Final evaluation\s+([+-]?[0-9]+(?:\.[0-9]+)?)\s+\((white|black) side\)"
)
NO_EVAL_RE = re.compile(r"^Final evaluation:\s+none\s+\(([^)]+)\)\s*$")
ARCH_RE = re.compile(
    r"NNUE evaluation using .*\([0-9]+MiB,\s*\(([0-9]+(?:,\s*[0-9]+)+)\)\)"
)
INFO_DEPTH_RE = re.compile(r"^info\s+depth\s+")


class VerificationError(RuntimeError):
    """Raised for a UCI protocol failure or an invalid verifier input."""


@dataclass(frozen=True)
class PositionCase:
    label: str
    command: str
    source: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EngineSession:
    def __init__(
        self,
        label: str,
        executable: Path,
        network: Path,
        hash_mb: int,
        timeout: float,
    ) -> None:
        self.label = label
        self.executable = executable
        self.network = network
        self.timeout = timeout
        self.lines: queue.Queue[str | None] = queue.Queue()
        self.identification = ""
        self.network_architecture: str | None = None

        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        self.process = subprocess.Popen(
            [str(executable)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=creationflags,
        )
        if self.process.stdin is None or self.process.stdout is None:
            raise VerificationError(f"{label}: failed to open UCI pipes")

        self.reader = threading.Thread(target=self._read_output, daemon=True)
        self.reader.start()

        self.send("uci")
        startup = self.read_until(lambda line: line == "uciok")
        for line in startup:
            if line.startswith("id name "):
                self.identification = line[len("id name ") :].strip()

        self.send(f"setoption name Threads value 1")
        self.send(f"setoption name Hash value {hash_mb}")
        self.send(f"setoption name EvalFile value {network}")
        self.ready()

    def _read_output(self) -> None:
        assert self.process.stdout is not None
        try:
            for line in self.process.stdout:
                self.lines.put(line.rstrip("\r\n"))
        finally:
            self.lines.put(None)

    def send(self, command: str) -> None:
        if self.process.poll() is not None:
            raise VerificationError(
                f"{self.label}: engine exited with code {self.process.returncode}"
            )
        assert self.process.stdin is not None
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()

    def read_until(self, predicate: Callable[[str], bool]) -> list[str]:
        deadline = time.monotonic() + self.timeout
        output: list[str] = []
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                tail = "\n".join(output[-20:])
                raise VerificationError(
                    f"{self.label}: UCI timeout after {self.timeout:.1f}s\n{tail}"
                )
            try:
                line = self.lines.get(timeout=remaining)
            except queue.Empty as exc:
                raise VerificationError(f"{self.label}: UCI timeout") from exc
            if line is None:
                tail = "\n".join(output[-20:])
                raise VerificationError(
                    f"{self.label}: unexpected EOF (exit={self.process.poll()})\n{tail}"
                )
            output.append(line)
            architecture = ARCH_RE.search(line)
            if architecture:
                self.network_architecture = ",".join(
                    part.strip() for part in architecture.group(1).split(",")
                )
            if predicate(line):
                return output

    def ready(self) -> list[str]:
        self.send("isready")
        return self.read_until(lambda line: line == "readyok")

    def set_position(self, position_command: str) -> None:
        self.send(position_command)

    def perft(self, position_command: str, depth: int) -> dict[str, object]:
        self.set_position(position_command)
        self.send(f"go perft {depth}")
        output = self.read_until(lambda line: NODES_RE.match(line) is not None)
        moves: dict[str, int] = {}
        nodes: int | None = None
        for line in output:
            move_match = MOVE_RE.match(line)
            if move_match:
                moves[move_match.group(1)] = int(move_match.group(2))
            nodes_match = NODES_RE.match(line)
            if nodes_match:
                nodes = int(nodes_match.group(1))
        if nodes is None:
            raise VerificationError(f"{self.label}: missing perft total")
        return {"nodes": nodes, "moves": dict(sorted(moves.items()))}

    def evaluate(self, position_command: str) -> dict[str, object]:
        self.set_position(position_command)
        self.send("eval")
        output = self.ready()
        raw: int | None = None
        final: str | None = None
        unavailable: str | None = None
        for line in output:
            raw_match = RAW_NNUE_RE.match(line)
            if raw_match:
                raw = int(raw_match.group(1))
            final_match = FINAL_EVAL_RE.match(line)
            if final_match:
                final = f"{final_match.group(1)} {final_match.group(2)}"
            unavailable_match = NO_EVAL_RE.match(line)
            if unavailable_match:
                unavailable = unavailable_match.group(1)
        if unavailable is None and (raw is None or final is None):
            tail = "\n".join(output[-30:])
            raise VerificationError(
                f"{self.label}: unable to parse NNUE evaluation\n{tail}"
            )
        return {
            "status": unavailable or "evaluated",
            "raw_internal": raw,
            "final": final,
            "network_architecture": self.network_architecture,
        }

    def search(self, position_command: str, depth: int) -> dict[str, object]:
        self.send("ucinewgame")
        self.ready()
        self.set_position(position_command)
        self.send(f"go depth {depth}")
        output = self.read_until(lambda line: line.startswith("bestmove "))

        bestmove_line = output[-1].split()
        if len(bestmove_line) < 2:
            raise VerificationError(f"{self.label}: malformed bestmove output")
        bestmove = bestmove_line[1]
        ponder = None
        if len(bestmove_line) >= 4 and bestmove_line[2] == "ponder":
            ponder = bestmove_line[3]

        final_info = next((line for line in reversed(output) if INFO_DEPTH_RE.match(line)), "")
        tokens = final_info.split()

        def token_value(name: str) -> str | None:
            try:
                return tokens[tokens.index(name) + 1]
            except (ValueError, IndexError):
                return None

        score: list[str] | None = None
        if "score" in tokens:
            index = tokens.index("score")
            if index + 2 < len(tokens):
                score = tokens[index + 1 : index + 3]

        pv: list[str] = []
        if "pv" in tokens:
            pv = tokens[tokens.index("pv") + 1 :]

        return {
            "bestmove": bestmove,
            "ponder": ponder,
            "depth": token_value("depth"),
            "seldepth": token_value("seldepth"),
            "score": score,
            "nodes": token_value("nodes"),
            "pv": pv,
        }

    def close(self) -> None:
        if self.process.poll() is None:
            try:
                self.send("quit")
                self.process.wait(timeout=5)
            except (BrokenPipeError, OSError, subprocess.TimeoutExpired):
                self.process.kill()
                self.process.wait(timeout=5)

    def __enter__(self) -> "EngineSession":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
        self.close()


def read_book(book: Path) -> list[str]:
    positions: list[str] = []
    seen: set[str] = set()
    with book.open("r", encoding="utf-8-sig", errors="replace") as stream:
        for raw_line in stream:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split()
            if len(fields) < 6:
                continue
            fen = " ".join(fields[:6])
            if fen not in seen:
                seen.add(fen)
                positions.append(fen)
    if not positions:
        raise VerificationError(f"No six-field FEN positions found in {book}")
    return positions


def select_root_cases(book: Path, count: int, seed: int) -> list[PositionCase]:
    book_positions = read_book(book)
    rng = random.Random(seed)
    count = min(count, len(book_positions))
    indices = sorted(rng.sample(range(len(book_positions)), count))

    cases = [PositionCase("startpos", "position startpos", "built-in")]
    cases.extend(
        PositionCase(
            f"book-{index:06d}",
            f"position fen {book_positions[index]}",
            f"{book.name}:{index + 1}",
        )
        for index in indices
    )
    return cases


def add_playout_cases(
    reference: EngineSession,
    roots: list[PositionCase],
    root_count: int,
    plies: int,
    seed: int,
) -> list[PositionCase]:
    derived: list[PositionCase] = []
    for root_index, root in enumerate(roots[:root_count]):
        moves: list[str] = []
        for ply in range(plies):
            command = root.command
            if moves:
                command += " moves " + " ".join(moves)
            legal = sorted(reference.perft(command, 1)["moves"])
            if not legal:
                break
            selector = hashlib.sha256(
                f"{seed}:{root.label}:{ply}".encode("utf-8")
            ).digest()
            move_index = int.from_bytes(selector[:8], "little") % len(legal)
            moves.append(legal[move_index])
            derived.append(
                PositionCase(
                    f"playout-{root_index:02d}-ply-{ply + 1:02d}",
                    root.command + " moves " + " ".join(moves),
                    root.source,
                )
            )
    return derived


def repetition_cases() -> list[PositionCase]:
    cycle = ["a0a1", "a9a8", "a1a0", "a8a9"]
    return [
        PositionCase(
            f"quiet-repetition-{repeats}x",
            "position startpos moves " + " ".join(cycle * repeats),
            "built-in reversible rook cycle",
        )
        for repeats in (1, 2, 3)
    ]


def unique_cases(cases: Iterable[PositionCase]) -> list[PositionCase]:
    result: list[PositionCase] = []
    seen: set[str] = set()
    for case in cases:
        if case.command not in seen:
            seen.add(case.command)
            result.append(case)
    return result


def normalized_search(result: dict[str, object]) -> dict[str, object]:
    return {
        key: result[key]
        for key in ("bestmove", "ponder", "depth", "seldepth", "score", "nodes", "pv")
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path, help="v1.0.0 engine")
    parser.add_argument("--baseline", required=True, type=Path, help="latest accepted baseline")
    parser.add_argument("--candidate", required=True, type=Path, help="candidate engine")
    parser.add_argument("--network", required=True, type=Path, help="common NNUE file")
    parser.add_argument("--book", required=True, type=Path, help="Xiangqi EPD opening book")
    parser.add_argument("--output", type=Path, help="JSON report path")
    parser.add_argument("--positions", type=int, default=64, help="sampled book roots")
    parser.add_argument("--playout-roots", type=int, default=8)
    parser.add_argument("--playout-plies", type=int, default=8)
    parser.add_argument("--perft-depth", type=int, default=3)
    parser.add_argument("--search-depth", type=int, default=6)
    parser.add_argument("--search-positions", type=int, default=24)
    parser.add_argument("--hash", type=int, default=16, dest="hash_mb")
    parser.add_argument("--seed", type=int, default=20260808)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--expect-search-identical",
        action="store_true",
        help="require candidate deterministic search to equal latest baseline",
    )
    args = parser.parse_args()

    for name in ("reference", "baseline", "candidate", "network", "book"):
        path = getattr(args, name).expanduser().resolve()
        if not path.is_file():
            parser.error(f"--{name} is not a file: {path}")
        setattr(args, name, path)
    if args.positions < 1 or args.perft_depth < 1 or args.search_depth < 1:
        parser.error("position counts and depths must be positive")
    if args.playout_roots < 0 or args.playout_plies < 0 or args.search_positions < 0:
        parser.error("playout/search counts cannot be negative")
    if args.output:
        args.output = args.output.expanduser().resolve()
    return args


def main() -> int:
    args = parse_args()
    output = args.output
    if output is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output = Path.cwd() / "verification" / f"gameplay-{stamp}.json"
    output.parent.mkdir(parents=True, exist_ok=True)

    engine_paths = {
        "reference-v1.0.0": args.reference,
        "baseline": args.baseline,
        "candidate": args.candidate,
    }
    report: dict[str, object] = {
        "generated_utc": utc_now(),
        "passed": False,
        "configuration": {
            "book": str(args.book),
            "book_sha256": sha256_file(args.book),
            "network": str(args.network),
            "network_sha256": sha256_file(args.network),
            "positions": args.positions,
            "playout_roots": args.playout_roots,
            "playout_plies": args.playout_plies,
            "perft_depth": args.perft_depth,
            "search_depth": args.search_depth,
            "search_positions": args.search_positions,
            "hash_mb": args.hash_mb,
            "seed": args.seed,
            "expect_search_identical": args.expect_search_identical,
        },
        "engines": {
            label: {"path": str(path), "sha256": sha256_file(path)}
            for label, path in engine_paths.items()
        },
        "cases": [],
        "failures": [],
    }

    sessions: dict[str, EngineSession] = {}
    failures: list[str] = report["failures"]  # type: ignore[assignment]
    case_reports: list[dict[str, object]] = report["cases"]  # type: ignore[assignment]

    try:
        for label, path in engine_paths.items():
            print(f"Starting {label}: {path}", flush=True)
            sessions[label] = EngineSession(
                label, path, args.network, args.hash_mb, args.timeout
            )
            report["engines"][label]["id"] = sessions[label].identification  # type: ignore[index]

        roots = select_root_cases(args.book, args.positions, args.seed)
        derived = add_playout_cases(
            sessions["reference-v1.0.0"],
            roots,
            min(args.playout_roots, len(roots)),
            args.playout_plies,
            args.seed,
        )
        cases = unique_cases([*roots, *derived, *repetition_cases()])
        repetition_labels = {case.label for case in repetition_cases()}
        search_labels = {case.label for case in cases[: args.search_positions]}
        search_labels.update(repetition_labels)

        for case_index, case in enumerate(cases, start=1):
            print(
                f"[{case_index:03d}/{len(cases):03d}] {case.label}",
                flush=True,
            )
            entry: dict[str, object] = {
                "label": case.label,
                "source": case.source,
                "position_sha256": hashlib.sha256(
                    case.command.encode("utf-8")
                ).hexdigest(),
                "position": case.command,
                "engines": {},
            }
            perft_results: dict[str, dict[str, object]] = {}
            eval_results: dict[str, dict[str, object]] = {}
            search_results: dict[str, dict[str, object]] = {}

            for label, session in sessions.items():
                perft_results[label] = session.perft(case.command, args.perft_depth)
                eval_results[label] = session.evaluate(case.command)
                engine_result: dict[str, object] = {
                    "perft": perft_results[label],
                    "evaluation": eval_results[label],
                }
                if case.label in search_labels:
                    search_results[label] = session.search(case.command, args.search_depth)
                    engine_result["search"] = search_results[label]
                entry["engines"][label] = engine_result  # type: ignore[index]

            reference_perft = perft_results["reference-v1.0.0"]
            reference_eval = eval_results["reference-v1.0.0"]
            for label in ("baseline", "candidate"):
                if perft_results[label] != reference_perft:
                    failures.append(f"{case.label}: perft mismatch for {label}")
                comparable_eval = {
                    key: eval_results[label][key]
                    for key in ("status", "raw_internal", "final", "network_architecture")
                }
                expected_eval = {
                    key: reference_eval[key]
                    for key in ("status", "raw_internal", "final", "network_architecture")
                }
                if comparable_eval != expected_eval:
                    failures.append(f"{case.label}: NNUE mismatch for {label}")

            if case.label in search_labels:
                legal_moves = set(reference_perft["moves"])
                for label, search_result in search_results.items():
                    bestmove = str(search_result["bestmove"])
                    if legal_moves and bestmove not in legal_moves:
                        failures.append(
                            f"{case.label}: illegal bestmove {bestmove} from {label}"
                        )
                    if not legal_moves and bestmove not in {"(none)", "0000"}:
                        failures.append(
                            f"{case.label}: expected no bestmove from {label}, got {bestmove}"
                        )
                if args.expect_search_identical:
                    baseline_search = normalized_search(search_results["baseline"])
                    candidate_search = normalized_search(search_results["candidate"])
                    if candidate_search != baseline_search:
                        failures.append(
                            f"{case.label}: deterministic search mismatch for candidate"
                        )

            case_reports.append(entry)

        architectures = {
            label: session.network_architecture for label, session in sessions.items()
        }
        report["network_architectures"] = architectures
        if None in architectures.values() or len(set(architectures.values())) != 1:
            failures.append(f"loaded network architecture mismatch: {architectures}")

    except Exception as exc:
        failures.append(f"verifier error: {type(exc).__name__}: {exc}")
        raise
    finally:
        for session in sessions.values():
            session.close()
        report["passed"] = not failures
        report["completed_utc"] = utc_now()
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Report: {output}", flush=True)

    if failures:
        print(f"FAILED: {len(failures)} mismatch(es)", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print(
        f"PASSED: {len(case_reports)} positions; legal moves, perft, NNUE, and search checks",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
