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
        book="xfish-uho-3mvs-w65-85-v1.epd",
        book_sha256="a" * 64,
        book_positions=100000,
        opening_seed="ltc-independent-seed",
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
        self.assertAlmostEqual(config["upper_bound"], math.log(19), places=12)
        self.assertAlmostEqual(config["lower_bound"], -math.log(19), places=12)
        self.assertEqual(config["current_pentanomial"], [0, 0, 0, 0, 0])

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

    def test_terminal_results_info_is_complete_for_finished_list(self):
        aggregate = results(20, 16, 164, [0, 8, 80, 12, 0])
        current = {
            "stage": "stc",
            "state": "",
            "llr": math.log(19),
            "lower_bound": -math.log(19),
            "upper_bound": math.log(19),
            "elo0": 0.0,
            "elo1": 2.0,
        }
        info = admin.results_info_for_sprt(aggregate, current, state="accepted")
        self.assertEqual(info["style"], "#44EB44")
        self.assertEqual(info["llr"], math.log(19))
        self.assertIn("STC accepted", info["info"][0])
        self.assertIn("0, 8, 80, 12, 0", info["info"][1])
        self.assertIn("Total: 200 W: 20 L: 16 D: 164", info["info"][2])

    def test_inconclusive_results_info_is_yellow(self):
        current = {
            "stage": "ltc",
            "state": "",
            "llr": 0.0,
            "lower_bound": -math.log(19),
            "upper_bound": math.log(19),
            "elo0": 0.5,
            "elo1": 2.5,
        }
        info = admin.results_info_for_sprt(
            results(0, 0, 0, [0, 0, 0, 0, 0]),
            current,
            state="inconclusive",
        )
        self.assertEqual(info["style"], "yellow")
        self.assertIn("LTC inconclusive", info["info"][0])

    def test_manual_retirement_preserves_results_and_reason(self):
        aggregate = results(20, 16, 164, [0, 8, 80, 12, 0])
        current = {
            "stage": "stc",
            "state": "",
            "llr": 0.125,
            "lower_bound": -math.log(19),
            "upper_bound": math.log(19),
            "elo0": 0.0,
            "elo1": 2.0,
        }
        fields = admin.retirement_update_fields(
            aggregate,
            current,
            "invalid",
            "opening_book_superseded_high_draw_rate",
        )
        prefix = "args.%s" % admin.SPRT_KEY
        self.assertEqual(fields["%s.state" % prefix], "invalid")
        self.assertEqual(fields["%s.finished_games" % prefix], 200)
        self.assertEqual(fields["%s.finished_pairs" % prefix], 100)
        self.assertEqual(
            fields["%s.current_pentanomial" % prefix], aggregate["pentanomial"]
        )
        self.assertTrue(fields["finished"])
        self.assertFalse(fields["tasks.$[].active"])
        self.assertIn(
            "opening_book_superseded_high_draw_rate",
            fields["results_info"]["info"][-1],
        )

    def test_manual_retirement_rejects_empty_reason(self):
        current = {
            "stage": "stc",
            "state": "",
            "llr": 0.0,
            "lower_bound": -math.log(19),
            "upper_bound": math.log(19),
            "elo0": 0.0,
            "elo1": 2.0,
        }
        with self.assertRaisesRegex(ValueError, "reason"):
            admin.retirement_update_fields(
                results(0, 0, 0, [0, 0, 0, 0, 0]),
                current,
                "invalid",
                "   ",
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
                "book": "xfish-uho-3mvs-w65-85-v1.epd",
                "book_sha256": "a" * 64,
                "book_positions": 100000,
                "opening_seed": "stc-seed",
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
                "book": "xfish-uho-3mvs-w65-85-v1.epd",
                "book_sha256": "a" * 64,
                "book_positions": 100000,
                "opening_seed": "stc-seed",
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

    def test_ltc_requires_an_independent_opening_seed(self):
        run_id = str(ObjectId())
        parent = {
            "args": {
                "resolved_base": BASE_SHA,
                "resolved_new": NEW_SHA,
                "book": "xfish-uho-3mvs-w65-85-v1.epd",
                "book_sha256": "a" * 64,
                "book_positions": 100000,
                "opening_seed": "same-seed",
                admin.SPRT_KEY: {
                    "stage": "stc",
                    "elo0": 0.0,
                    "elo1": 2.0,
                    "state": "accepted",
                },
            }
        }
        child_args = args("ltc", run_id)
        child_args.opening_seed = "same-seed"
        with self.assertRaisesRegex(ValueError, "independent"):
            admin.sprt_for_run(child_args, FakeRunDb(parent))


if __name__ == "__main__":
    unittest.main()
