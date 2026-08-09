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


class SprtPolicyTests(unittest.TestCase):
    def test_stc_parameters_and_bounds(self):
        config = admin.sprt_for_run(args("stc"), FakeRunDb())
        self.assertEqual(config["stage"], "stc")
        self.assertEqual((config["elo0"], config["elo1"]), (0.0, 2.0))
        self.assertEqual((config["alpha"], config["beta"]), (0.05, 0.05))

        run = {"args": {"sprt": config}}
        status = admin.sprt_status(run, {"wins": 1, "losses": 1, "draws": 10})
        self.assertAlmostEqual(status["upper_bound"], math.log(19), places=12)
        self.assertAlmostEqual(status["lower_bound"], -math.log(19), places=12)

    def test_ltc_requires_parent(self):
        with self.assertRaisesRegex(ValueError, "parent-run-id"):
            admin.sprt_for_run(args("ltc"), FakeRunDb())

    def test_ltc_requires_accepted_stc(self):
        run_id = str(ObjectId())
        parent = {
            "args": {
                "resolved_base": BASE_SHA,
                "resolved_new": NEW_SHA,
                "sprt": {
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
                "sprt": {
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
