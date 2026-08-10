import math
import unittest
from types import SimpleNamespace

from bson.objectid import ObjectId

import admin


BASE_SHA = "1" * 40
NEW_SHA = "2" * 40


class FakeRunDb:
    def __init__(self, parent=None):
        self.parent = parent

    def get_run(self, _run_id):
        return self.parent


def args(stage, parent_run_id=None):
    return SimpleNamespace(
        sprt_stage=stage,
        parent_run_id=parent_run_id,
        base_sha=BASE_SHA,
        new_sha=NEW_SHA,
    )


def results(wins, losses, draws, pentanomial):
    return {
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "crashes": 0,
        "time_losses": 0,
        "pentanomial": pentanomial,
        "missing_pentanomial_games": 0,
    }


class SprtPolicyTests(unittest.TestCase):
    def test_stc_parameters_and_bounds(self):
        config = admin.sprt_for_run(args("stc"), FakeRunDb())
        self.assertEqual(config["stage"], "stc")
        self.assertEqual((config["elo0"], config["elo1"]), (0.0, 2.0))
        self.assertEqual((config["alpha"], config["beta"]), (0.05, 0.05))
        self.assertEqual(config["elo_model"], "normalized")
        self.assertEqual(config["statistic"], "pentanomial")

        run = {"args": {admin.SPRT_KEY: config}}
        status = admin.sprt_status(run, results(0, 0, 2, [0, 0, 1, 0, 0]))
        self.assertAlmostEqual(status["upper_bound"], math.log(19), places=12)
        self.assertAlmostEqual(status["lower_bound"], -math.log(19), places=12)
        self.assertEqual(status["pairs"], 1)

    def test_pentanomial_is_required_for_played_games(self):
        config = admin.sprt_for_run(args("stc"), FakeRunDb())
        run = {"args": {admin.SPRT_KEY: config}}
        bad = results(1, 1, 0, [0, 0, 0, 0, 0])
        bad["missing_pentanomial_games"] = 2
        with self.assertRaisesRegex(ValueError, "incomplete"):
            admin.sprt_status(run, bad)

    def test_wld_score_must_match_pentanomial_score(self):
        config = admin.sprt_for_run(args("stc"), FakeRunDb())
        run = {"args": {admin.SPRT_KEY: config}}
        with self.assertRaisesRegex(ValueError, "scores disagree"):
            admin.sprt_status(run, results(2, 0, 0, [1, 0, 0, 0, 0]))

    def test_llr_matches_pinned_official_fishtest_reference(self):
        config = admin.sprt_for_run(args("stc"), FakeRunDb())
        run = {"args": {admin.SPRT_KEY: config}}
        status = admin.sprt_status(
            run,
            results(20, 16, 164, [0, 8, 80, 12, 0]),
        )
        self.assertAlmostEqual(status["llr"], 0.069511760895660, places=14)

    def test_both_llr_boundaries_are_detected(self):
        config = admin.sprt_for_run(args("stc"), FakeRunDb())
        run = {"args": {admin.SPRT_KEY: config}}
        accepted = admin.sprt_status(
            run,
            results(2000, 0, 0, [0, 0, 0, 0, 1000]),
        )
        rejected = admin.sprt_status(
            run,
            results(0, 2000, 0, [1000, 0, 0, 0, 0]),
        )
        self.assertEqual(accepted["state"], "accepted")
        self.assertGreaterEqual(accepted["llr"], accepted["upper_bound"])
        self.assertEqual(rejected["state"], "rejected")
        self.assertLessEqual(rejected["llr"], rejected["lower_bound"])

    def test_runtime_failure_invalidates_a_gate(self):
        run = {"args": {"num_games": 100000}}
        current = {"state": "", "llr": 0.0}
        failed = results(0, 0, 0, [0, 0, 0, 0, 0])
        failed["crashes"] = 1
        self.assertEqual(
            admin.terminal_decision(run, failed, current),
            ("invalid", "runtime_error"),
        )

    def test_aggregate_results_keeps_pair_frequencies(self):
        run = {
            "tasks": [
                {
                    "stats": {
                        "wins": 1,
                        "losses": 0,
                        "draws": 1,
                        "crashes": 0,
                        "time_losses": 0,
                        "pentanomial": [0, 0, 0, 1, 0],
                    }
                },
                {
                    "stats": {
                        "wins": 0,
                        "losses": 0,
                        "draws": 2,
                        "crashes": 0,
                        "time_losses": 0,
                        "pentanomial": [0, 0, 1, 0, 0],
                    }
                },
            ]
        }
        aggregate = admin.aggregate_results(run)
        self.assertEqual(aggregate["pentanomial"], [0, 0, 1, 1, 0])
        self.assertEqual(aggregate["missing_pentanomial_games"], 0)

    def test_ltc_requires_parent(self):
        with self.assertRaisesRegex(ValueError, "parent-run-id"):
            admin.sprt_for_run(args("ltc"), FakeRunDb())

    def test_ltc_requires_accepted_stc(self):
        run_id = str(ObjectId())
        parent = {
            "args": {
                "resolved_base": BASE_SHA,
                "resolved_new": NEW_SHA,
                admin.SPRT_KEY: {
                    "stage": "stc",
                    "elo0": 0.0,
                    "elo1": 2.0,
                    "state": "rejected",
                },
            }
        }
        with self.assertRaisesRegex(ValueError, "has not passed"):
            admin.sprt_for_run(args("ltc", run_id), FakeRunDb(parent))

    def test_ltc_inherits_accepted_stc_identity(self):
        run_id = str(ObjectId())
        parent = {
            "args": {
                "resolved_base": BASE_SHA,
                "resolved_new": NEW_SHA,
                admin.SPRT_KEY: {
                    "stage": "stc",
                    "elo0": 0.0,
                    "elo1": 2.0,
                    "state": "accepted",
                },
            }
        }
        config = admin.sprt_for_run(args("ltc", run_id), FakeRunDb(parent))
        self.assertEqual(config["stage"], "ltc")
        self.assertEqual((config["elo0"], config["elo1"]), (0.5, 2.5))
        self.assertEqual(config["parent_run_id"], run_id)


if __name__ == "__main__":
    unittest.main()
