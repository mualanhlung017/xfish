#!/usr/bin/env python3
"""Run exactly one color-reversed Xiangqi pair and emit a JSON summary."""

import json
import os
import sys
from pathlib import Path


UPSTREAM = os.environ.get("XFISHTEST_VARIANTFISHTEST")
SUMMARY = os.environ.get("XFISHTEST_SUMMARY")
if not UPSTREAM or not SUMMARY:
    raise SystemExit("XFISHTEST_VARIANTFISHTEST and XFISHTEST_SUMMARY are required")

sys.path.insert(0, str(Path(UPSTREAM).resolve()))

import chess.uci  # noqa: E402
import variantfishtest  # noqa: E402


_original_setoption = chess.uci.Engine.setoption


def _xiangqi_compatible_setoption(self, options, async_callback=None):
    filtered = dict(options)
    for key in list(filtered):
        if key.lower() == "uci_variant" and "UCI_Variant" not in self.options:
            del filtered[key]
    if not filtered:
        return None
    return _original_setoption(self, filtered, async_callback)


chess.uci.Engine.setoption = _xiangqi_compatible_setoption


class XiangqiMatch(variantfishtest.EngineMatch):
    def __init__(self):
        super(XiangqiMatch, self).__init__()
        if self.num_engines != 2 or self.is_tournament:
            raise ValueError("this wrapper requires exactly two engines")
        if self.variants != ["xiangqi"]:
            raise ValueError("this compatibility wrapper is Xiangqi-only")
        if self.max_games != 2 or self.threads != 1:
            raise ValueError("one wrapper process must run exactly two games on one thread")

    def validate_engine_variants(self):
        for engine_idx, engine_path in enumerate(self.engine_paths):
            engine = None
            try:
                engine = chess.uci.popen_engine(engine_path)
                engine.uci()
                if self.config:
                    engine.setoption({"VariantPath": self.config})
                    engine.uci()
                if "UCI_Variant" in engine.options:
                    supported = engine.options["UCI_Variant"].var or []
                    if "xiangqi" not in supported:
                        raise ValueError(
                            "engine %d does not advertise xiangqi" % (engine_idx + 1)
                        )
            finally:
                if engine is not None:
                    engine.quit()
        if self.verbosity >= 1:
            self.out.write("Variant validation passed (fixed Xiangqi engines accepted)\n")
            self.out.flush()

    def worker(self):
        # The upstream worker retries exceptions forever.  A distributed worker
        # needs a hard failure so it can record the log and retry the pair cleanly.
        res1, res2, tl1, tl2, _ = self.play_match_instance()
        with self.lock:
            if res1 == variantfishtest.DRAW:
                self.scores[variantfishtest.DRAW] += 1
                self.draw_games += 1
            else:
                self.scores[res1] += 1
                if res1 == variantfishtest.WIN:
                    self.white_wins += 1
                else:
                    self.black_wins += 1
            score1 = variantfishtest.SCORES[res1]

            if res2 == variantfishtest.DRAW:
                self.scores[variantfishtest.DRAW] += 1
                self.draw_games += 1
            else:
                self.scores[1 - res2] += 1
                if res2 == variantfishtest.WIN:
                    self.white_wins += 1
                else:
                    self.black_wins += 1
            score2 = 1 - variantfishtest.SCORES[res2]

            self.r.extend([score1, score2])
            self.time_losses[0] += tl1
            self.time_losses[1] += tl2
            self.pentanomial[int(round(2 * (score1 + score2)))] += 1


def write_summary(match):
    payload = {
        "schema": 1,
        "scores": list(match.scores),
        "pentanomial": list(match.pentanomial),
        "time_losses": list(match.time_losses),
        "white_wins": match.white_wins,
        "black_wins": match.black_wins,
        "draw_games": match.draw_games,
    }
    if sum(payload["scores"]) != 2 or sum(payload["pentanomial"]) != 1:
        raise RuntimeError("incomplete pair result: %r" % payload)
    target = Path(SUMMARY)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(str(temporary), str(target))


if __name__ == "__main__":
    engine_match = XiangqiMatch()
    engine_match.run()
    write_summary(engine_match)
