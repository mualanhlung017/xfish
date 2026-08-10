#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("audit-xiangqi-uho.py")
SPEC = importlib.util.spec_from_file_location("audit_xiangqi_uho", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


FENS = (
    "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1",
    "rnbakabnr/9/1c5c1/p1p1p1p1p/9/P8/2P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1",
)
PATHS = (
    "a0a1 a9a8 b0b1 b9b8 c0c1 c9c8",
    "i0i1 i9i8 h0h1 h9h8 g0g1 g9g8",
)


def write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="ascii", newline="\n")


def search_record(score: int, wdl: list[int]) -> dict[str, object]:
    return {
        "multipv": 1,
        "move": "a0a1",
        "score_type": "cp",
        "score": score,
        "bound": "",
        "wdl": wdl,
        "depth": 12,
    }


class CorpusFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.seed = "audit-unit-test"
        ordered = sorted(FENS, key=lambda fen: AUDIT.stable_key(self.seed, fen))
        path_by_fen = dict(zip(FENS, PATHS))
        self.candidates = ordered
        self.paths = [path_by_fen[fen] for fen in ordered]
        self.accepted = ordered[0]
        write_text(root / "depth-06.paths", "\n".join(self.paths) + "\n")
        positions = [
            {"path": path, "fen": fen, "checkers": ""}
            for path, fen in zip(self.paths, ordered)
        ]
        self.write_jsonl(root / "positions.jsonl", positions)
        write_text(root / "candidates.epd", "\n".join(ordered) + "\n")
        write_text(root / "unit-book.epd", self.accepted + "\n")
        scores = [
            {
                "fen": ordered[0],
                "accepted": True,
                "reason": "accepted",
                "best": search_record(10, [300, 500, 200]),
                "second": search_record(0, [290, 500, 210]),
            },
            {
                "fen": ordered[1],
                "accepted": False,
                "reason": "wdl_draw_outside_band",
                "best": search_record(20, [100, 600, 300]),
                "second": search_record(0, [100, 600, 300]),
            },
        ]
        self.write_jsonl(root / "scores.jsonl", scores)
        self.config = {
            "schema": 2,
            "plies": 6,
            "seed": self.seed,
            "wdl_component": "draw",
            "wdl_min": 481,
            "wdl_max": 519,
            "second_move_window_cp": 150,
        }
        self.write_json(root / "generation-config.json", self.config)
        self.manifest = {
            "schema": 2,
            "status": "passed",
            "parameters": self.config,
            "book": {
                "name": "unit-book.epd",
                "path": str(root / "unit-book.epd"),
                "positions": 1,
                "sha256": AUDIT.sha256_file(root / "unit-book.epd"),
            },
            "counts": {
                "leaf_paths": 2,
                "checked_positions": 0,
                "duplicate_fens": 0,
                "unique_noncheck_fens": 2,
                "scored_fens": 2,
                "accepted_fens": 1,
                "minimum_positions": 1,
            },
            "rejection_reasons": {"accepted": 1, "wdl_draw_outside_band": 1},
            "accepted_wdl_histograms": {
                "draw": {"500-504": 1},
                "loss": {"200-224": 1},
                "win": {"300-324": 1},
            },
            "artifacts": {},
        }
        self.refresh_hashes()

    @staticmethod
    def write_json(path: Path, value: object) -> None:
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @staticmethod
    def write_jsonl(path: Path, values: list[dict[str, object]]) -> None:
        path.write_text(
            "".join(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n" for value in values),
            encoding="utf-8",
            newline="\n",
        )

    def refresh_hashes(self) -> None:
        self.manifest["book"]["sha256"] = AUDIT.sha256_file(self.root / "unit-book.epd")
        self.manifest["artifacts"] = {
            "generation_config_sha256": AUDIT.sha256_file(self.root / "generation-config.json"),
            "final_paths_sha256": AUDIT.sha256_file(self.root / "depth-06.paths"),
            "positions_jsonl_sha256": AUDIT.sha256_file(self.root / "positions.jsonl"),
            "candidates_epd_sha256": AUDIT.sha256_file(self.root / "candidates.epd"),
            "scores_jsonl_sha256": AUDIT.sha256_file(self.root / "scores.jsonl"),
        }
        self.write_json(self.root / "manifest.json", self.manifest)


class AuditCorpusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.fixture = CorpusFixture(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_valid_corpus_passes(self) -> None:
        result = AUDIT.audit_corpus(self.root, minimum_positions=1)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["positions"], 1)
        self.assertEqual(result["candidates"], 2)

    def test_accepted_wdl_outside_band_fails(self) -> None:
        rows = [value for _line, value in AUDIT.json_lines(self.root / "scores.jsonl")]
        rows[0]["best"]["wdl"] = [100, 600, 300]
        self.fixture.write_jsonl(self.root / "scores.jsonl", rows)
        self.fixture.refresh_hashes()
        with self.assertRaisesRegex(AUDIT.AuditError, "outside 481..519"):
            AUDIT.audit_corpus(self.root, minimum_positions=1)

    def test_position_path_mismatch_fails(self) -> None:
        rows = [value for _line, value in AUDIT.json_lines(self.root / "positions.jsonl")]
        rows[0]["path"] = "a0a1 a9a8 b0b1 b9b8 d0d1 d9d8"
        self.fixture.write_jsonl(self.root / "positions.jsonl", rows)
        self.fixture.refresh_hashes()
        with self.assertRaisesRegex(AUDIT.AuditError, "position path"):
            AUDIT.audit_corpus(self.root, minimum_positions=1)

    def test_book_duplicate_fails(self) -> None:
        write_text(self.root / "unit-book.epd", self.fixture.accepted + "\n" + self.fixture.accepted + "\n")
        self.fixture.manifest["book"]["positions"] = 2
        self.fixture.manifest["counts"]["accepted_fens"] = 2
        self.fixture.refresh_hashes()
        with self.assertRaisesRegex(AUDIT.AuditError, "duplicate FENs"):
            AUDIT.audit_corpus(self.root, minimum_positions=1)


if __name__ == "__main__":
    unittest.main()
