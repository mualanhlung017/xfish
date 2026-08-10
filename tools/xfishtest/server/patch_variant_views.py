#!/usr/bin/env python3
"""Teach the pinned variant-fishtest UI how to render xfish SPRT runs."""

from pathlib import Path


VIEWS = Path("/opt/fishtest-src/server/fishtest/views.py")
MARKER = '''    # win/loss/draw count
    WLD = [run_results["wins"], run_results["losses"], run_results["draws"]]
'''
INSERT = MARKER + '''
    # xfish uses the current official paired-pentanomial normalized-Elo SPRT.
    # The pinned variant server only knows its legacy trinomial SPRT, so the
    # external watcher stores a display snapshot in args.xfish_sprt.
    if "xfish_sprt" in run["args"]:
        sprt = run["args"]["xfish_sprt"]
        state = sprt.get("state", "")
        label = state or "running"
        stage = str(sprt.get("stage", "sprt")).upper()
        llr = float(sprt.get("llr", 0.0))
        lower = float(sprt.get("lower_bound", -2.9444389791664403))
        upper = float(sprt.get("upper_bound", 2.9444389791664403))
        penta = sprt.get("current_pentanomial", [0, 0, 0, 0, 0])
        result["llr"] = llr
        result["info"].append(
            "%s %s: LLR %.3f (%.3f, %.3f) [%.2f, %.2f]"
            % (stage, label, llr, lower, upper, sprt["elo0"], sprt["elo1"])
        )
        result["info"].append("Ptnml(0-2): " + ", ".join(str(value) for value in penta))
        result["info"].append(
            "Total: %d W: %d L: %d D: %d" % (sum(WLD), WLD[0], WLD[1], WLD[2])
        )
        if state == "accepted":
            result["style"] = "#44EB44"
        elif state in ("rejected", "invalid"):
            result["style"] = "#FF6A6A"
        elif state == "inconclusive":
            result["style"] = "yellow"
        return result
'''


def main():
    source = VIEWS.read_text(encoding="utf-8")
    if "# xfish uses the current official paired-pentanomial" in source:
        return
    if source.count(MARKER) != 1:
        raise RuntimeError("pinned variant views.py marker did not match exactly once")
    VIEWS.write_text(source.replace(MARKER, INSERT), encoding="utf-8")


if __name__ == "__main__":
    main()
