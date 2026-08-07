#!/usr/bin/env python3
"""Summarize paired xfish A/B benchmark CSV files.

The benchmark launchers alternate AB/BA order inside each pair.  This script
uses the per-pair candidate/baseline ratio, which removes most slow clock and
load drift, and bootstraps the median ratio with a deterministic seed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot calculate a percentile of an empty sample")
    position = (len(ordered) - 1) * probability
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    fraction = position - low
    return ordered[low] * (1.0 - fraction) + ordered[high] * fraction


def bootstrap_median_ci(values: list[float], samples: int = 50_000) -> tuple[float, float]:
    seed_material = ",".join(f"{value:.12f}" for value in values).encode()
    seed = int.from_bytes(hashlib.sha256(seed_material).digest()[:8], "little")
    rng = random.Random(seed)
    n = len(values)
    medians = [statistics.median(rng.choices(values, k=n)) for _ in range(samples)]
    return percentile(medians, 0.025), percentile(medians, 0.975)


def load_rows(paths: Iterable[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        with path.open(newline="", encoding="utf-8-sig") as stream:
            rows.extend(csv.DictReader(stream))
    return rows


def summarize(rows: list[dict[str, str]]) -> dict[str, object]:
    signatures: dict[str, dict[str, int]] = defaultdict(dict)
    performance: dict[str, dict[int, dict[str, float]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    raw_nps: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for row in rows:
        platform = row["platform"].strip().lower()
        label = row["label"].strip().lower()
        kind = row["kind"].strip().lower()
        if label not in {"baseline", "candidate"}:
            continue
        if kind == "signature":
            signatures[platform][label] = int(row["nodes"])
        elif kind == "performance":
            pair = int(row["pair"])
            nps = float(row["nps"])
            performance[platform][pair][label] = nps
            raw_nps[platform][label].append(nps)

    platform_results: dict[str, dict[str, object]] = {}
    correctness = True
    for platform in sorted(performance):
        ratios: list[float] = []
        for pair in sorted(performance[platform]):
            values = performance[platform][pair]
            if set(values) != {"baseline", "candidate"}:
                raise ValueError(f"{platform} pair {pair} is incomplete")
            ratios.append(values["candidate"] / values["baseline"])

        if len(ratios) < 3:
            raise ValueError(f"{platform} has only {len(ratios)} complete pairs; need at least 3")

        signature = signatures.get(platform, {})
        signature_match = (
            set(signature) == {"baseline", "candidate"}
            and signature["baseline"] == signature["candidate"]
        )
        correctness = correctness and signature_match
        lower, upper = bootstrap_median_ci(ratios)
        baseline_nps = raw_nps[platform]["baseline"]
        candidate_nps = raw_nps[platform]["candidate"]
        platform_results[platform] = {
            "pairs": len(ratios),
            "signature_nodes": signature,
            "signature_match": signature_match,
            "baseline_median_nps": statistics.median(baseline_nps),
            "candidate_median_nps": statistics.median(candidate_nps),
            "median_paired_ratio": statistics.median(ratios),
            "median_paired_gain_percent": (statistics.median(ratios) - 1.0) * 100.0,
            "mean_paired_gain_percent": (statistics.mean(ratios) - 1.0) * 100.0,
            "bootstrap_95_percent": [lower, upper],
            "baseline_cv_percent": (
                statistics.stdev(baseline_nps) / statistics.mean(baseline_nps) * 100.0
                if len(baseline_nps) > 1
                else 0.0
            ),
            "candidate_cv_percent": (
                statistics.stdev(candidate_nps) / statistics.mean(candidate_nps) * 100.0
                if len(candidate_nps) > 1
                else 0.0
            ),
        }

    if not platform_results:
        raise ValueError("no performance rows found")

    ratios = [float(result["median_paired_ratio"]) for result in platform_results.values()]
    combined_ratio = math.exp(sum(math.log(ratio) for ratio in ratios) / len(ratios))
    no_regression = all(ratio >= 0.997 for ratio in ratios)
    enough_pairs = all(int(result["pairs"]) >= 9 for result in platform_results.values())
    statistically_positive = all(
        float(result["bootstrap_95_percent"][0]) >= 0.997
        for result in platform_results.values()
    )
    required_platforms = {"windows", "linux"}
    has_both_platforms = required_platforms.issubset(platform_results)
    accepted = (
        correctness
        and has_both_platforms
        and enough_pairs
        and no_regression
        and statistically_positive
        and combined_ratio >= 1.01
    )

    return {
        "platforms": platform_results,
        "combined_geometric_ratio": combined_ratio,
        "combined_gain_percent": (combined_ratio - 1.0) * 100.0,
        "gate": {
            "correctness": correctness,
            "windows_and_linux": has_both_platforms,
            "at_least_9_pairs_each": enough_pairs,
            "no_platform_below_minus_0_3_percent": no_regression,
            "per_platform_ci_lower_at_least_minus_0_3_percent": statistically_positive,
            "combined_gain_at_least_1_percent": combined_ratio >= 1.01,
            "accepted": accepted,
        },
    }


def print_markdown(summary: dict[str, object]) -> None:
    print("| Platform | Pairs | Baseline median | Candidate median | Paired gain | 95% CI | Signature |")
    print("|---|---:|---:|---:|---:|---:|:---:|")
    platforms = summary["platforms"]
    assert isinstance(platforms, dict)
    for platform, result in platforms.items():
        assert isinstance(result, dict)
        lower, upper = result["bootstrap_95_percent"]
        print(
            f"| {platform} | {result['pairs']} | {result['baseline_median_nps']:,.0f} | "
            f"{result['candidate_median_nps']:,.0f} | "
            f"{result['median_paired_gain_percent']:+.3f}% | "
            f"{(lower - 1.0) * 100:+.3f}%..{(upper - 1.0) * 100:+.3f}% | "
            f"{'match' if result['signature_match'] else 'MISMATCH'} |"
        )
    print()
    print(f"Combined geometric gain: {summary['combined_gain_percent']:+.3f}%")
    print(f"Promotion gate: {'PASS' if summary['gate']['accepted'] else 'FAIL'}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", nargs="+", type=Path, help="one or more benchmark CSV files")
    parser.add_argument("--json", type=Path, help="also write the complete summary as JSON")
    args = parser.parse_args()
    try:
        summary = summarize(load_rows(args.csv))
    except (OSError, KeyError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print_markdown(summary)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
