import importlib.util
from pathlib import Path
import sys
import unittest


SCRIPT = Path(__file__).with_name("generate-xiangqi-uho.py")
SPEC = importlib.util.spec_from_file_location("generate_xiangqi_uho", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ParseSearchTests(unittest.TestCase):
    def test_latest_completed_exact_iteration_wins_over_final_bounds(self):
        records, bestmove = MODULE.parse_search(
            [
                "info depth 10 multipv 1 score cp 140 wdl 800 200 0 pv a0a1",
                "info depth 10 multipv 2 score cp 125 wdl 720 280 0 pv b0b1",
                "info depth 11 multipv 1 score cp 151 lowerbound wdl 850 150 0 pv a0a2",
                "info depth 11 multipv 2 score cp 117 upperbound wdl 680 320 0 pv b0b2",
                "bestmove a0a2",
            ]
        )

        self.assertEqual(bestmove, "a0a2")
        self.assertEqual([record.depth for record in records], [10, 10])
        self.assertEqual([record.move for record in records], ["a0a1", "b0b1"])
        self.assertTrue(all(record.bound == "" for record in records))

    def test_bound_is_retained_when_no_exact_iteration_exists(self):
        records, _bestmove = MODULE.parse_search(
            [
                "info depth 1 multipv 1 score cp 20 lowerbound wdl 550 450 0 pv a0a1",
                "bestmove a0a1",
            ]
        )

        self.assertEqual(records[0].bound, "lowerbound")


if __name__ == "__main__":
    unittest.main()
