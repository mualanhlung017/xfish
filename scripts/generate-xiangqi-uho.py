#!/usr/bin/env python3
"""Generate an immutable Xiangqi UHO opening book with xfish.

The generator deliberately uses an accepted xfish baseline for every move-tree
decision and for the final WDL filter.  It does not consume an existing book.
The resulting positions are suitable for paired, color-reversed fishtest runs:

* Red chooses a small set of near-best moves;
* Black receives a wider MultiPV window, creating controlled Red advantages;
* positions are taken after an even number of plies so Red is to move;
* checked positions, malformed FENs, duplicates, mates, and one-move tactical
  positions are excluded;
* the final Red win probability must be inside an inclusive WDL band;
* inputs, parameters, intermediate paths, scores, counts, and hashes are saved
  for reproducibility and audit.

The script checkpoints after each tree depth and appends position/score JSONL
records as it works.  Re-running with the exact same configuration resumes the
same corpus; a configuration mismatch is rejected.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Sequence


MOVE_RE = re.compile(r"^[a-i][0-9][a-i][0-9]$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FEN_RE = re.compile(r"^Fen:\s+(.+?)\s*$")
CHECKERS_RE = re.compile(r"^Checkers:\s*(.*?)\s*$")
PIECE_SYMBOLS = frozenset("rnbakcpRNBAKCP")
START_FEN = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"


class BookGenerationError(RuntimeError):
    """Raised when an input, UCI response, or reproducibility check fails."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value, encoding="utf-8", newline="\n")
    temporary.replace(path)


def atomic_json(path: Path, value: object) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def stable_key(seed: str, value: str) -> bytes:
    return hashlib.sha256(
        seed.encode("utf-8") + b"\0" + value.encode("utf-8")
    ).digest()


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be nonnegative")
    return parsed


def probability_per_mille(value: str) -> int:
    parsed = int(value)
    if not 0 <= parsed <= 1000:
        raise argparse.ArgumentTypeError("must be between 0 and 1000")
    return parsed


def expected_sha256(value: str) -> str:
    parsed = value.lower()
    if not SHA256_RE.fullmatch(parsed):
        raise argparse.ArgumentTypeError("must be a 64-digit SHA-256")
    return parsed


def path_text(moves: Sequence[str]) -> str:
    return " ".join(moves)


def position_command(moves: Sequence[str]) -> str:
    if not moves:
        return "position startpos"
    return "position startpos moves " + path_text(moves)


def validate_fen(fen: str, expected_side: str) -> None:
    fields = fen.split()
    if len(fields) != 6:
        raise BookGenerationError(f"malformed Xiangqi FEN field count: {fen}")
    board, side, castling, en_passant, halfmove, fullmove = fields
    if side != expected_side:
        raise BookGenerationError(
            f"unexpected side to move {side!r}, expected {expected_side!r}: {fen}"
        )
    if castling != "-" or en_passant != "-":
        raise BookGenerationError(f"unexpected Xiangqi FEN flags: {fen}")
    if not halfmove.isdigit() or not fullmove.isdigit():
        raise BookGenerationError(f"invalid Xiangqi FEN counters: {fen}")

    ranks = board.split("/")
    if len(ranks) != 10:
        raise BookGenerationError(f"Xiangqi FEN must contain 10 ranks: {fen}")
    pieces: Counter[str] = Counter()
    for rank in ranks:
        width = 0
        for symbol in rank:
            if symbol.isdigit():
                width += int(symbol)
            elif symbol in PIECE_SYMBOLS:
                width += 1
                pieces[symbol] += 1
            else:
                raise BookGenerationError(
                    f"unexpected Xiangqi FEN symbol {symbol!r}: {fen}"
                )
        if width != 9:
            raise BookGenerationError(f"Xiangqi FEN rank width is not 9: {fen}")
    if pieces["K"] != 1 or pieces["k"] != 1:
        raise BookGenerationError(f"Xiangqi FEN must contain both kings: {fen}")


@dataclass(frozen=True)
class SearchMove:
    multipv: int
    move: str
    score_type: str
    score: int
    bound: str
    wdl: tuple[int, int, int] | None
    depth: int | None


def token_after(tokens: Sequence[str], name: str) -> str | None:
    try:
        return tokens[tokens.index(name) + 1]
    except (ValueError, IndexError):
        return None


def parse_search(output: Sequence[str]) -> tuple[list[SearchMove], str]:
    records: dict[int, SearchMove] = {}
    exact_records: dict[int, SearchMove] = {}
    bestmove = ""
    for line in output:
        if line.startswith("bestmove "):
            fields = line.split()
            if len(fields) >= 2:
                bestmove = fields[1]
            continue
        if not line.startswith("info "):
            continue
        tokens = line.split()
        if "score" not in tokens or "pv" not in tokens:
            continue
        try:
            score_index = tokens.index("score")
            score_type = tokens[score_index + 1]
            score = int(tokens[score_index + 2])
            pv_index = tokens.index("pv")
            move = tokens[pv_index + 1]
            multipv = int(token_after(tokens, "multipv") or "1")
        except (ValueError, IndexError):
            continue
        if not MOVE_RE.fullmatch(move):
            continue
        bound = ""
        if score_index + 3 < len(tokens) and tokens[score_index + 3] in (
            "lowerbound",
            "upperbound",
        ):
            bound = tokens[score_index + 3]
        wdl: tuple[int, int, int] | None = None
        if "wdl" in tokens:
            try:
                index = tokens.index("wdl")
                wdl = tuple(int(item) for item in tokens[index + 1 : index + 4])
                if len(wdl) != 3 or sum(wdl) != 1000 or min(wdl) < 0:
                    wdl = None
            except (ValueError, IndexError):
                wdl = None
        try:
            depth = int(token_after(tokens, "depth") or "")
        except ValueError:
            depth = None
        record = SearchMove(
            multipv=multipv,
            move=move,
            score_type=score_type,
            score=score,
            bound=bound,
            wdl=wdl,
            depth=depth,
        )
        records[multipv] = record
        # A fixed-node search may stop during an aspiration-window re-search.
        # In that case the last line for a PV is only a lower/upper bound even
        # though the engine emitted an exact result at the previous completed
        # iteration.  Preserve the deepest completed exact record instead of
        # silently treating the final bound as an exact WDL estimate.
        if not bound:
            exact_records[multipv] = record
    if not bestmove or bestmove in ("(none)", "0000"):
        raise BookGenerationError("search returned no legal best move")
    ordered = [
        exact_records.get(index, records[index]) for index in sorted(records)
    ]
    if not ordered or ordered[0].multipv != 1:
        raise BookGenerationError("search returned no parseable principal variation")
    return ordered, bestmove


class EngineSession:
    def __init__(
        self,
        executable: Path,
        network: Path,
        hash_mb: int,
        timeout: float,
        label: str,
    ) -> None:
        self.executable = executable
        self.network = network
        self.timeout = timeout
        self.label = label
        self.lines: queue.Queue[str | None] = queue.Queue()
        self.identification = ""
        self.current_multipv: int | None = None

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
            cwd=str(network.parent),
        )
        if self.process.stdin is None or self.process.stdout is None:
            raise BookGenerationError(f"{label}: failed to open UCI pipes")
        self.reader = threading.Thread(target=self._read_output, daemon=True)
        self.reader.start()

        self.send("uci")
        startup = self.read_until(lambda line: line == "uciok")
        for line in startup:
            if line.startswith("id name "):
                self.identification = line[len("id name ") :].strip()
        if not self.identification:
            raise BookGenerationError(f"{label}: engine did not identify itself")
        self.send("setoption name Threads value 1")
        self.send(f"setoption name Hash value {hash_mb}")
        self.send(f"setoption name EvalFile value {network}")
        self.send("setoption name UCI_ShowWDL value true")
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
            raise BookGenerationError(
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
                raise BookGenerationError(
                    f"{self.label}: UCI timeout; tail={output[-20:]}"
                )
            try:
                line = self.lines.get(timeout=remaining)
            except queue.Empty as error:
                raise BookGenerationError(f"{self.label}: UCI timeout") from error
            if line is None:
                raise BookGenerationError(
                    f"{self.label}: unexpected engine EOF; tail={output[-20:]}"
                )
            output.append(line)
            if predicate(line):
                return output

    def ready(self) -> None:
        self.send("isready")
        self.read_until(lambda line: line == "readyok")

    def prepare_search(self, multipv: int) -> None:
        self.send("ucinewgame")
        self.send("setoption name Clear Hash")
        if self.current_multipv != multipv:
            self.send(f"setoption name MultiPV value {multipv}")
            self.current_multipv = multipv
        self.ready()

    def search_path(
        self, moves: Sequence[str], nodes: int, multipv: int
    ) -> list[SearchMove]:
        self.prepare_search(multipv)
        self.send(position_command(moves))
        self.send(f"go nodes {nodes}")
        output = self.read_until(lambda line: line.startswith("bestmove "))
        records, _bestmove = parse_search(output)
        return records

    def search_fen(self, fen: str, nodes: int, multipv: int) -> list[SearchMove]:
        self.prepare_search(multipv)
        self.send("position fen " + fen)
        self.send(f"go nodes {nodes}")
        output = self.read_until(lambda line: line.startswith("bestmove "))
        records, _bestmove = parse_search(output)
        return records

    def dump_path(self, moves: Sequence[str]) -> tuple[str, str]:
        self.send(position_command(moves))
        self.send("d")
        output = self.read_until(lambda line: CHECKERS_RE.match(line) is not None)
        fen = ""
        checkers = ""
        for line in output:
            fen_match = FEN_RE.match(line)
            if fen_match:
                fen = fen_match.group(1).strip()
            checkers_match = CHECKERS_RE.match(line)
            if checkers_match:
                checkers = checkers_match.group(1).strip()
        if not fen:
            raise BookGenerationError(f"{self.label}: d command returned no FEN")
        return fen, checkers

    def close(self) -> None:
        if self.process.poll() is None:
            try:
                self.send("quit")
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()
                self.process.wait(timeout=5)


class EnginePool:
    def __init__(
        self,
        executable: Path,
        network: Path,
        hash_mb: int,
        timeout: float,
    ) -> None:
        self.executable = executable
        self.network = network
        self.hash_mb = hash_mb
        self.timeout = timeout
        self.local = threading.local()
        self.lock = threading.Lock()
        self.sessions: list[EngineSession] = []

    def session(self) -> EngineSession:
        session = getattr(self.local, "session", None)
        if session is not None:
            return session
        with self.lock:
            label = f"xfish-generator-{len(self.sessions):02d}"
        session = EngineSession(
            self.executable, self.network, self.hash_mb, self.timeout, label
        )
        with self.lock:
            self.sessions.append(session)
        self.local.session = session
        return session

    def identities(self) -> list[str]:
        return sorted({session.identification for session in self.sessions})

    def close(self) -> None:
        for session in self.sessions:
            session.close()


def read_paths(path: Path) -> list[tuple[str, ...]]:
    moves: list[tuple[str, ...]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        fields = raw.split()
        if any(not MOVE_RE.fullmatch(move) for move in fields):
            raise BookGenerationError(f"invalid move in {path}:{line_number}")
        moves.append(tuple(fields))
    return moves


def write_paths(path: Path, paths: Iterable[Sequence[str]]) -> None:
    atomic_text(path, "".join(path_text(item) + "\n" for item in paths))


def load_jsonl(path: Path, key: str) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    if not path.exists():
        return records
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as error:
            raise BookGenerationError(f"invalid JSON in {path}:{line_number}") from error
        value = item.get(key)
        if not isinstance(value, str) or not value:
            raise BookGenerationError(f"missing {key!r} in {path}:{line_number}")
        if value in records:
            raise BookGenerationError(f"duplicate {key!r} in {path}: {value}")
        records[value] = item
    return records


def append_jsonl(path: Path, records: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
            stream.write("\n")
        stream.flush()


def batched(values: Sequence[object], size: int) -> Iterable[Sequence[object]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def generation_config(args: argparse.Namespace, engine_sha: str, network_sha: str) -> dict[str, object]:
    return {
        "schema": 1,
        "generator": "scripts/generate-xiangqi-uho.py",
        "engine_sha256": engine_sha,
        "network_sha256": network_sha,
        "start_fen": START_FEN,
        "plies": args.plies,
        "generation_nodes": args.generation_nodes,
        "scoring_nodes": args.scoring_nodes,
        "red_branch": args.red_branch,
        "black_branch": args.black_branch,
        "final_black_branch": args.final_black_branch,
        "red_move_window_cp": args.red_move_window_cp,
        "black_move_window_cp": args.black_move_window_cp,
        "final_black_move_window_cp": args.final_black_move_window_cp,
        "final_black_wdl_margin": args.final_black_wdl_margin,
        "second_move_window_cp": args.second_move_window_cp,
        "wdl_win_min": args.wdl_win_min,
        "wdl_win_max": args.wdl_win_max,
        "seed": args.seed,
    }


def ensure_configuration(path: Path, config: dict[str, object]) -> None:
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing != config:
            raise BookGenerationError(
                f"refusing to resume {path.parent}: generation configuration changed"
            )
        return
    atomic_json(path, config)


def generate_tree(
    args: argparse.Namespace,
    engine_pool: EnginePool,
    executor: concurrent.futures.ThreadPoolExecutor,
) -> list[tuple[str, ...]]:
    output_root: Path = args.output_dir
    paths: list[tuple[str, ...]] = [tuple()]
    start_depth = 0
    for depth in range(args.plies, 0, -1):
        checkpoint = output_root / f"depth-{depth:02d}.paths"
        if checkpoint.exists():
            paths = read_paths(checkpoint)
            if any(len(item) != depth for item in paths):
                raise BookGenerationError(f"invalid path depth in {checkpoint}")
            start_depth = depth
            break

    for ply in range(start_depth, args.plies):
        red_to_move = ply % 2 == 0
        final_black_ply = not red_to_move and ply == args.plies - 1
        if red_to_move:
            branch = args.red_branch
            window = args.red_move_window_cp
        elif final_black_ply:
            branch = args.final_black_branch
            window = args.final_black_move_window_cp
        else:
            branch = args.black_branch
            window = args.black_move_window_cp

        def expand(item: tuple[str, ...]) -> list[tuple[str, ...]]:
            records = engine_pool.session().search_path(
                item, args.generation_nodes, branch
            )
            best = records[0]
            if best.score_type != "cp" or best.bound:
                return []
            children: list[tuple[str, ...]] = []
            seen: set[str] = set()
            for record in records:
                if len(children) >= branch:
                    break
                if record.score_type != "cp" or record.bound or record.move in seen:
                    continue
                if best.score - record.score > window:
                    continue
                if final_black_ply:
                    if record.wdl is None:
                        continue
                    # Scores and WDL at this node are from Black's point of
                    # view.  Black's modeled loss probability is therefore
                    # Red's modeled win probability after the candidate move.
                    lower = max(0, args.wdl_win_min - args.final_black_wdl_margin)
                    upper = min(1000, args.wdl_win_max + args.final_black_wdl_margin)
                    if not lower <= record.wdl[2] <= upper:
                        continue
                seen.add(record.move)
                children.append(item + (record.move,))
            return children

        next_paths: list[tuple[str, ...]] = []
        completed = 0
        for children in executor.map(expand, paths):
            next_paths.extend(children)
            completed += 1
            if completed % 1000 == 0 or completed == len(paths):
                print(
                    f"generation ply {ply + 1}/{args.plies}: "
                    f"parents={completed}/{len(paths)} children={len(next_paths)}",
                    flush=True,
                )
        if not next_paths:
            raise BookGenerationError(f"generation produced no paths at ply {ply + 1}")
        if len(set(next_paths)) != len(next_paths):
            raise BookGenerationError("generator produced duplicate move paths")
        paths = next_paths
        write_paths(output_root / f"depth-{ply + 1:02d}.paths", paths)
    return paths


def collect_positions(
    args: argparse.Namespace,
    paths: Sequence[tuple[str, ...]],
    engine_pool: EnginePool,
    executor: concurrent.futures.ThreadPoolExecutor,
) -> tuple[list[str], dict[str, str], dict[str, int]]:
    output = args.output_dir / "positions.jsonl"
    existing = load_jsonl(output, "path")
    wanted = {path_text(item): item for item in paths}
    unknown = set(existing) - set(wanted)
    if unknown:
        raise BookGenerationError(
            f"position checkpoint contains {len(unknown)} paths outside the final tree"
        )
    missing = [item for item in paths if path_text(item) not in existing]

    def inspect(item: tuple[str, ...]) -> dict[str, object]:
        fen, checkers = engine_pool.session().dump_path(item)
        expected_side = "w" if len(item) % 2 == 0 else "b"
        validate_fen(fen, expected_side)
        return {"path": path_text(item), "fen": fen, "checkers": checkers}

    completed = len(existing)
    for chunk in batched(missing, args.checkpoint_interval):
        records = list(executor.map(inspect, chunk))
        append_jsonl(output, records)
        completed += len(records)
        print(
            f"position audit: {completed}/{len(paths)} paths",
            flush=True,
        )

    records = load_jsonl(output, "path")
    unique: dict[str, str] = {}
    checked = 0
    for item in paths:
        record = records[path_text(item)]
        fen = str(record["fen"])
        checkers = str(record.get("checkers", ""))
        if checkers:
            checked += 1
            continue
        unique.setdefault(fen, path_text(item))
    ordered = sorted(unique, key=lambda fen: stable_key(args.seed, fen))
    atomic_text(args.output_dir / "candidates.epd", "".join(fen + "\n" for fen in ordered))
    return ordered, unique, {
        "leaf_paths": len(paths),
        "checked_positions": checked,
        "duplicate_fens": len(paths) - checked - len(unique),
        "unique_noncheck_fens": len(unique),
    }


def score_positions(
    args: argparse.Namespace,
    fens: Sequence[str],
    engine_pool: EnginePool,
    executor: concurrent.futures.ThreadPoolExecutor,
) -> tuple[list[str], Counter[str], Counter[str]]:
    output = args.output_dir / "scores.jsonl"
    existing = load_jsonl(output, "fen")
    unknown = set(existing) - set(fens)
    if unknown:
        raise BookGenerationError(
            f"score checkpoint contains {len(unknown)} positions outside candidates.epd"
        )
    missing = [fen for fen in fens if fen not in existing]

    def score_one(fen: str) -> dict[str, object]:
        records = engine_pool.session().search_fen(fen, args.scoring_nodes, 2)
        reason = "accepted"
        if len(records) < 2:
            reason = "missing_second_move"
        elif records[0].bound or records[1].bound:
            reason = "bounded_score"
        elif records[0].score_type != "cp" or records[1].score_type != "cp":
            reason = "mate_or_non_cp_score"
        elif records[0].wdl is None:
            reason = "missing_wdl"
        elif not args.wdl_win_min <= records[0].wdl[0] <= args.wdl_win_max:
            reason = "wdl_outside_band"
        elif records[0].score - records[1].score > args.second_move_window_cp:
            reason = "forced_or_one_move"
        return {
            "fen": fen,
            "accepted": reason == "accepted",
            "reason": reason,
            "best": asdict(records[0]),
            "second": asdict(records[1]) if len(records) >= 2 else None,
        }

    completed = len(existing)
    for chunk in batched(missing, args.checkpoint_interval):
        records = list(executor.map(score_one, chunk))
        append_jsonl(output, records)
        completed += len(records)
        print(f"WDL scoring: {completed}/{len(fens)} positions", flush=True)

    scores = load_jsonl(output, "fen")
    accepted: list[str] = []
    reasons: Counter[str] = Counter()
    histogram: Counter[str] = Counter()
    for fen in fens:
        item = scores[fen]
        reason = str(item["reason"])
        reasons[reason] += 1
        if not item.get("accepted"):
            continue
        accepted.append(fen)
        best = item["best"]
        assert isinstance(best, dict)
        wdl = best["wdl"]
        assert isinstance(wdl, list)
        win = int(wdl[0])
        lower = (win // 25) * 25
        histogram[f"{lower:03d}-{lower + 24:03d}"] += 1
    return accepted, reasons, histogram


def build_book(args: argparse.Namespace) -> dict[str, object]:
    args.engine = args.engine.resolve()
    args.network = args.network.resolve()
    args.output_dir = args.output_dir.resolve()
    if not args.engine.is_file() or not args.network.is_file():
        raise BookGenerationError("xfish executable or NNUE network does not exist")
    if args.plies % 2:
        raise BookGenerationError("plies must be even so Red is to move in the book")
    if args.wdl_win_min > args.wdl_win_max:
        raise BookGenerationError("WDL lower bound exceeds upper bound")
    engine_sha = sha256_file(args.engine)
    network_sha = sha256_file(args.network)
    if engine_sha != args.engine_sha256:
        raise BookGenerationError(
            f"xfish SHA-256 mismatch: expected {args.engine_sha256}, got {engine_sha}"
        )
    if network_sha != args.network_sha256:
        raise BookGenerationError(
            f"NNUE SHA-256 mismatch: expected {args.network_sha256}, got {network_sha}"
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    config = generation_config(args, engine_sha, network_sha)
    ensure_configuration(args.output_dir / "generation-config.json", config)

    engine_pool = EnginePool(
        args.engine, args.network, args.hash_mb, args.uci_timeout_seconds
    )
    started = time.monotonic()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
            paths = generate_tree(args, engine_pool, executor)
            fens, _provenance, position_counts = collect_positions(
                args, paths, engine_pool, executor
            )
            accepted, reasons, histogram = score_positions(
                args, fens, engine_pool, executor
            )
        identities = engine_pool.identities()
    finally:
        engine_pool.close()

    book_path = args.output_dir / args.book_name
    atomic_text(book_path, "".join(fen + "\n" for fen in accepted))
    book_sha = sha256_file(book_path)
    status = "passed" if len(accepted) >= args.minimum_positions else "insufficient"
    manifest = {
        "schema": 1,
        "status": status,
        "created_utc": utc_now(),
        "elapsed_seconds": time.monotonic() - started,
        "book": {
            "name": args.book_name,
            "path": str(book_path),
            "sha256": book_sha,
            "positions": len(accepted),
        },
        "generator": {
            "engine": str(args.engine),
            "engine_identification": identities,
            "engine_sha256": engine_sha,
            "network": str(args.network),
            "network_sha256": network_sha,
            "implementation": "scripts/generate-xiangqi-uho.py",
        },
        "parameters": config,
        "counts": {
            **position_counts,
            "scored_fens": len(fens),
            "accepted_fens": len(accepted),
            "minimum_positions": args.minimum_positions,
        },
        "rejection_reasons": dict(sorted(reasons.items())),
        "accepted_wdl_win_histogram": dict(sorted(histogram.items())),
        "artifacts": {
            "generation_config_sha256": sha256_file(
                args.output_dir / "generation-config.json"
            ),
            "final_paths_sha256": sha256_file(
                args.output_dir / f"depth-{args.plies:02d}.paths"
            ),
            "positions_jsonl_sha256": sha256_file(
                args.output_dir / "positions.jsonl"
            ),
            "candidates_epd_sha256": sha256_file(
                args.output_dir / "candidates.epd"
            ),
            "scores_jsonl_sha256": sha256_file(args.output_dir / "scores.jsonl"),
        },
    }
    atomic_json(args.output_dir / "manifest.json", manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True), flush=True)
    if status != "passed":
        raise BookGenerationError(
            f"only {len(accepted)} positions passed; need {args.minimum_positions}"
        )
    return manifest


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Generate a deterministic Xiangqi UHO EPD using xfish only"
    )
    root.add_argument("--engine", type=Path, required=True)
    root.add_argument("--network", type=Path, required=True)
    root.add_argument("--engine-sha256", type=expected_sha256, required=True)
    root.add_argument("--network-sha256", type=expected_sha256, required=True)
    root.add_argument("--output-dir", type=Path, required=True)
    root.add_argument("--book-name", default="xfish-uho-3mvs-w65-85-v1.epd")
    root.add_argument("--seed", default="xfish-uho-xiangqi-3mvs-w65-85-v1")
    root.add_argument("--plies", type=positive_int, default=6)
    root.add_argument("--workers", type=positive_int, default=1)
    root.add_argument("--hash-mb", type=positive_int, default=16)
    root.add_argument("--generation-nodes", type=positive_int, default=50000)
    root.add_argument("--scoring-nodes", type=positive_int, default=100000)
    root.add_argument("--red-branch", type=positive_int, default=6)
    root.add_argument("--black-branch", type=positive_int, default=16)
    root.add_argument("--final-black-branch", type=positive_int, default=48)
    root.add_argument("--red-move-window-cp", type=nonnegative_int, default=100)
    root.add_argument("--black-move-window-cp", type=nonnegative_int, default=300)
    root.add_argument(
        "--final-black-move-window-cp", type=nonnegative_int, default=800
    )
    root.add_argument("--final-black-wdl-margin", type=nonnegative_int, default=100)
    root.add_argument("--second-move-window-cp", type=nonnegative_int, default=150)
    root.add_argument("--wdl-win-min", type=probability_per_mille, default=650)
    root.add_argument("--wdl-win-max", type=probability_per_mille, default=850)
    root.add_argument("--minimum-positions", type=positive_int, default=100000)
    root.add_argument("--checkpoint-interval", type=positive_int, default=1000)
    root.add_argument("--uci-timeout-seconds", type=float, default=120.0)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        build_book(args)
    except (BookGenerationError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
