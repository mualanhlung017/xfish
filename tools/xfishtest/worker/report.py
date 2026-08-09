#!/usr/bin/env python3
"""Aggregate worker pair summaries with pentanomial-aware uncertainty."""

import argparse
import hashlib
import json
import math
from pathlib import Path


def normal_cdf(value):
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def logistic_elo(score):
    score = min(max(score, 0.001), 0.999)
    return -400.0 * math.log10(1.0 / score - 1.0)


def paired_elo(pentanomial):
    # This matches current fishtest's get_elo calculation for five-bin paired
    # results, apart from its immaterial 0.001 prior on empty bins.
    regularized = [float(value) if value else 0.001 for value in pentanomial]
    pairs = sum(regularized)
    games = 2.0 * pairs
    mu = sum(regularized[index] * (index / 2.0) for index in range(5)) / games
    pair_scale_mu = 2.0 * mu
    variance = sum(
        regularized[index] * (index / 2.0 - pair_scale_mu) ** 2
        for index in range(5)
    ) / games
    standard_error = math.sqrt(variance) / math.sqrt(games)
    low = mu - 1.959963984540054 * standard_error
    high = mu + 1.959963984540054 * standard_error
    elo = logistic_elo(mu)
    elo95 = (logistic_elo(high) - logistic_elo(low)) / 2.0
    los = normal_cdf((mu - 0.5) / standard_error) if standard_error else (1.0 if mu > 0.5 else 0.0)
    normalized_elo = 800.0 / math.log(10.0) * (mu - 0.5) / math.sqrt(variance) if variance else 0.0
    return {
        "score": mu,
        "elo": elo,
        "elo95": elo95,
        "los": los,
        "normalized_elo": normalized_elo,
    }


def collect(paths, run_id=None):
    pairs = {}
    conflicts = []
    for root in paths:
        for path in Path(root).rglob("pair-*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if run_id and payload.get("run_id") != run_id:
                continue
            key = (payload.get("run_id"), int(payload["global_pair"]))
            fingerprint = hashlib.sha256(
                json.dumps(
                    {
                        "fen": payload.get("fen_sha256"),
                        "scores": payload.get("scores"),
                        "pentanomial": payload.get("pentanomial"),
                        "new_sha": payload.get("new_sha"),
                        "base_sha": payload.get("base_sha"),
                        "new_engine_sha256": payload.get("new_engine_sha256"),
                        "base_engine_sha256": payload.get("base_engine_sha256"),
                        "new_network_sha256": payload.get("new_network_sha256"),
                        "base_network_sha256": payload.get("base_network_sha256"),
                    },
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()
            if key in pairs and pairs[key][0] != fingerprint:
                conflicts.append({"key": key, "paths": [pairs[key][2], str(path)]})
            else:
                pairs[key] = (fingerprint, payload, str(path))
    if conflicts:
        raise RuntimeError("conflicting duplicate pair summaries: %r" % conflicts)
    return [value[1] for _, value in sorted(pairs.items())]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--run-id")
    parser.add_argument("--expect-pairs", type=int)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    pairs = collect(args.paths, args.run_id)
    if args.expect_pairs is not None and len(pairs) != args.expect_pairs:
        raise RuntimeError("expected %d pairs, found %d" % (args.expect_pairs, len(pairs)))
    indices = sorted(int(pair["global_pair"]) for pair in pairs)
    if args.expect_pairs is not None and indices != list(range(args.expect_pairs)):
        raise RuntimeError("pair index set is not the expected contiguous range")
    fen_hashes = [pair.get("fen_sha256") for pair in pairs]
    if len(set(fen_hashes)) != len(fen_hashes):
        raise RuntimeError("duplicate opening FEN detected")
    new_shas = {pair.get("new_sha") for pair in pairs}
    base_shas = {pair.get("base_sha") for pair in pairs}
    new_engine_hashes = {pair.get("new_engine_sha256") for pair in pairs}
    base_engine_hashes = {pair.get("base_engine_sha256") for pair in pairs}
    new_network_hashes = {pair.get("new_network_sha256") for pair in pairs}
    base_network_hashes = {pair.get("base_network_sha256") for pair in pairs}
    time_controls = {
        (pair.get("nominal_tc"), pair.get("base_ms"), pair.get("increment_ms"))
        for pair in pairs
    }
    if len(new_shas) != 1 or len(base_shas) != 1:
        raise RuntimeError("mixed engine revisions detected")
    # Windows and Linux executables legitimately have different hashes.  The
    # NNUE assigned to each side, however, must be identical on every worker.
    for label, values in (
        ("new NNUE files", new_network_hashes),
        ("base NNUE files", base_network_hashes),
    ):
        if len(values) != 1:
            raise RuntimeError("mixed %s detected" % label)

    scores = [sum(pair["scores"][index] for pair in pairs) for index in range(3)]
    penta = [sum(pair["pentanomial"][index] for pair in pairs) for index in range(5)]
    time_losses = sum(sum(pair.get("time_losses", [])) for pair in pairs)
    report = {
        "pairs": len(pairs),
        "unique_openings": len(set(fen_hashes)),
        "pair_index_min": min(indices) if indices else None,
        "pair_index_max": max(indices) if indices else None,
        "games": sum(scores),
        "wins": scores[0],
        "losses": scores[1],
        "draws": scores[2],
        "pentanomial": penta,
        "time_losses": time_losses,
        "new_sha": next(iter(new_shas), None),
        "base_sha": next(iter(base_shas), None),
        "new_engine_sha256s": sorted(value for value in new_engine_hashes if value),
        "base_engine_sha256s": sorted(value for value in base_engine_hashes if value),
        "new_network_sha256": next(iter(new_network_hashes), None),
        "base_network_sha256": next(iter(base_network_hashes), None),
        "worker_time_controls": [list(tc) for tc in sorted(time_controls)],
    }
    report.update(paired_elo(penta))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("Games: %(games)d (%(pairs)d paired openings)" % report)
        print("Unique opening indices: %(pair_index_min)d..%(pair_index_max)d" % report)
        print("W/L/D: %(wins)d/%(losses)d/%(draws)d" % report)
        print("Pentanomial [LL,LD,DD/WL,WD,WW]: %s" % report["pentanomial"])
        print("Elo: %.2f +/- %.2f (95%%), LOS: %.1f%%" % (report["elo"], report["elo95"], 100.0 * report["los"]))
        print("Normalized Elo: %.2f" % report["normalized_elo"])
        print("Time losses: %d" % report["time_losses"])


if __name__ == "__main__":
    main()
