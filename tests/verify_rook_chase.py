"""Verify both rule variants through complete histories and production movegen."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def probe(executable: Path, cases):
    data = "".join(f"{fen}\n{' '.join(moves)}\n" for _, fen, moves in cases)
    result = subprocess.run([str(executable)], input=data, text=True,
                            capture_output=True, check=True, timeout=120)
    rows = result.stdout.splitlines()
    if len(rows) != len(cases):
        raise RuntimeError(f"incomplete probe: {result.stdout[-2000:]} {result.stderr}")
    parsed = []
    for case, line in zip(cases, rows):
        if not line.startswith("RESULT "):
            raise RuntimeError(f"{case[0]}: {line}")
        head, fen, legal, search = line.split("|")
        judged, score, restored = map(int, head.split()[1:])
        search_judged, search_score = map(int, search.split())
        assert restored == 1, (executable, line)
        parsed.append({"judged": bool(judged), "score": score,
                       "restored": True, "fen": fen, "legal": sorted(legal.split()),
                       "search_judged": bool(search_judged), "search_score": search_score})
    return parsed


def colour_reverse(fen, moves):
    fields = fen.split()
    ranks = fields[0].split("/")
    fields[0] = "/".join(rank[::-1].swapcase() for rank in ranks[::-1])
    fields[1] = "b" if fields[1] == "w" else "w"
    def sq(s):
        return chr(ord('i') - (ord(s[0]) - ord('a'))) + str(9 - int(s[1]))
    return " ".join(fields), [sq(m[:2]) + sq(m[2:]) for m in moves]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--off-probe", type=Path, required=True)
    parser.add_argument("--on-probe", type=Path, required=True)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--network", type=Path, required=True)
    parser.add_argument("--replay-module", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    replay = load_module(args.replay_module or root / "tests/chinese_xiangqi_notation.py", "rook_replay")
    gameplay = load_module(root / "scripts/verify-gameplay.py", "rook_gameplay")
    session = gameplay.EngineSession("notation", args.engine.resolve(), args.network.resolve(), 16, 30)
    game, games = [], []
    try:
        for filename, label, expected in (("huashan-rook-chase.pgn", "huashan-rook", 153),
                                           ("huashan-rook-cannon-chase.pgn", "huashan-cannon", 194)):
            path = root / "tests/data" / filename
            text = path.read_text(encoding="utf-8")
            fen = re.search(r'\[FEN "([^"]+)"\]', text)[1]
            tokens = re.findall(r'[^\s]+', "\n".join(l for l in text.splitlines() if not l.startswith('[')))
            tokens = [t for t in tokens if t != '*' and not re.fullmatch(r'\d+\.', t)]
            moves = []
            game.append((f"{label}-ply-0", fen, []))
            current = fen
            for ply, token in enumerate(tokens, 1):
                command = f"position fen {fen}" + (" moves " + " ".join(moves) if moves else "")
                legal = list(session.perft(command, 1)["moves"])
                wanted = replay.normalize_chinese_token(token)
                matches = []
                for candidate in legal:
                    notation = replay.move_as_wxf(current, candidate)
                    # File-named advisors can share a file in this source.
                    if wanted[1].isdigit():
                        file_index = ord(candidate[0]) - ord('a')
                        file_number = 9 - file_index if current.split()[1] == 'w' else file_index + 1
                        notation = notation[0] + str(file_number) + notation[2:]
                    if notation == wanted:
                        matches.append(candidate)
                if len(matches) != 1:
                    raise RuntimeError(f"{label} ply {ply}: {token} resolves to {matches} in {current}")
                moves.append(matches[0])
                command = f"position fen {fen} moves {' '.join(moves)}"
                session.send(command)
                session.send("d")
                lines = session.read_until(lambda line: line.startswith("Checkers:"))
                current = next(line[5:] for line in lines if line.startswith("Fen: "))
                game.append((f"{label}-ply-{ply}", fen, moves.copy()))
            assert len(moves) == expected, len(moves)
            games.append({"label": label, "plies": len(moves), "initial_fen": fen,
                          "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "moves": moves})
    finally:
        session.close()
    pinned = ("pinned-rook", "4k4/9/9/9/4r4/R8/9/9/4R4/3K5 w - - 0 1",
              "a4a5 e5e4 a5a4 e4e5".split() * 2)
    symmetric = ("symmetric-rook", "4k4/9/9/9/4r4/R8/9/9/9/3K5 w - - 0 1",
                 "a4a5 e5e4 a5a4 e4e5".split() * 2)
    knight = ("rook-chases-knight", "4k4/9/9/9/4n4/R8/9/9/9/3K5 w - - 0 1",
              "a4a5 e5f7".split() + "a5a7 f7e5 a7a5 e5f7".split() * 2)
    quiet = ("quiet-repetition", replay.START_FEN,
             "a0a1 a9a8 a1a0 a8a9".split() * 2)
    checking = ("perpetual-check", "4k4/9/3R5/9/9/9/9/9/9/5K3 w - - 0 1",
                "d7e7 e9d9 e7d7 d9e9".split() * 2)
    knight_rook = ("knight-chases-rook", "3k5/9/5N3/9/9/4r4/9/9/9/5K3 w - - 0 1",
                   "f7d6 e4e5 d6f7 e5e4".split() * 2)
    protected = ("protected-rook", "3k5/9/9/9/4rr3/R8/9/9/4A4/4K4 w - - 0 1",
                 "a4a5 e5e4 a5a4 e4e5".split() * 2)
    cannon = ("protected-cannon", "4k4/9/9/9/4cr3/R8/9/9/9/3K5 w - - 0 1",
              "a4a5 e5e4 a5a4 e4e5".split() * 2)
    king = ("king-chases-cannon", "5k3/9/9/9/9/9/9/9/3c5/4K4 w - - 0 1",
            "e0d0 d1e1 d0e0 e1d1".split() * 2)
    pawn = ("pawn-chases-cannon", "4k4/9/9/3c5/4P4/9/9/9/9/5K3 w - - 0 1",
            "e5d5 d6e6 d5e5 e6d6".split() * 2)
    fixtures = [pinned, symmetric, knight, quiet, checking, knight_rook, protected, cannon, king, pawn]
    cases = list(game)
    for name, f, ms in game:
        rf, rm = colour_reverse(f, ms)
        cases.append((name.replace('huashan-', 'huashan-reversed-'), rf, rm))
    for name, f, ms in fixtures:
        for n in range(len(ms) + 1):
            cases.append((f"{name}-ply-{n}", f, ms[:n]))
        rf, rm = colour_reverse(f, ms)
        for n in range(len(rm) + 1):
            cases.append((f"{name}-reversed-ply-{n}", rf, rm[:n]))
    off = probe(args.off_probe.resolve(), cases)
    on = probe(args.on_probe.resolve(), cases)
    differences = []
    for (name, f, ms), a, b in zip(cases, off, on):
        assert a["fen"] == b["fen"] and a["legal"] == b["legal"], name
        if (a["judged"], a["score"], a["search_judged"], a["search_score"]) != (b["judged"], b["score"], b["search_judged"], b["search_score"]):
            differences.append({"case": name, "fen": a["fen"], "moves": ms, "off": a, "on": b})
            assert name.startswith(("symmetric-rook", "huashan")), name
    for prefix in ("pinned-rook", "pinned-rook-reversed"):
        index = next(i for i, c in enumerate(cases) if c[0] == f"{prefix}-ply-8")
        assert off[index]["judged"] and off[index]["score"] < -30000, off[index]
        assert off[index] == on[index], on[index]
    for prefix in ("symmetric-rook", "symmetric-rook-reversed"):
        index = next(i for i, c in enumerate(cases) if c[0] == f"{prefix}-ply-8")
        assert off[index]["judged"] and off[index]["score"] == 0, off[index]
        assert on[index]["judged"] and on[index]["score"] < -30000, on[index]
    for prefix in ("king-chases-cannon", "king-chases-cannon-reversed", "pawn-chases-cannon", "pawn-chases-cannon-reversed"):
        index = next(i for i, c in enumerate(cases) if c[0] == f"{prefix}-ply-8")
        assert off[index] == on[index] and on[index]["score"] == 0, on[index]
    for prefix in ("protected-rook", "protected-rook-reversed", "protected-cannon", "protected-cannon-reversed"):
        index = next(i for i, c in enumerate(cases) if c[0] == f"{prefix}-ply-8")
        assert off[index] == on[index] and on[index]["score"] == 0, on[index]
    for prefix in ("rook-chases-knight", "rook-chases-knight-reversed"):
        index = next(i for i, c in enumerate(cases) if c[0] == f"{prefix}-ply-10")
        assert off[index] == on[index] and off[index]["score"] < -30000, off[index]
    for prefix in ("perpetual-check", "perpetual-check-reversed"):
        index = next(i for i, c in enumerate(cases) if c[0] == f"{prefix}-ply-8")
        assert off[index] == on[index] and off[index]["score"] < -30000, off[index]
    for prefix in ("huashan-rook", "huashan-reversed-rook"):
        for ply in (146, 150, 152):
            index = next(i for i, c in enumerate(cases) if c[0] == f"{prefix}-ply-{ply}")
            assert off[index]["judged"] and off[index]["score"] == 0, off[index]
            assert on[index]["judged"] and on[index]["score"] > 30000, on[index]
    for index, case in enumerate(cases):
        if case[0].startswith(("huashan-cannon-", "huashan-reversed-cannon-")):
            assert off[index] == on[index], case[0]
    report = {"passed": True, "game_plies": [g['plies'] for g in games], "game_positions": len(game),
              "cases": len(cases), "differences": differences, "games": games,
              "records": [{"name": c[0], "initial_fen": c[1], "moves": c[2], "off": a, "on": b}
                          for c, a, b in zip(cases, off, on)]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("passed", "game_plies", "game_positions", "cases")}, indent=2))
    print(f"Rule differences: {len(differences)}; report: {args.output}")


if __name__ == "__main__":
    main()
