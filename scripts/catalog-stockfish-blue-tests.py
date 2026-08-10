#!/usr/bin/env python3
"""Catalog accepted blue/non-regression Fishtest runs for 2025-2026.

The official Fishtest UI renders an accepted SPRT in blue when the midpoint of
its Elo bounds is negative.  Those tests are deliberately separated from
gain-bound (green) tests here because accepting non-regression does not prove a
positive Elo gain.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path


COMMON_PATH = Path(__file__).with_name("catalog-stockfish-positive-tests.py")
COMMON_SPEC = importlib.util.spec_from_file_location("xfish_positive_catalog", COMMON_PATH)
if COMMON_SPEC is None or COMMON_SPEC.loader is None:
    raise RuntimeError("could not load the common Fishtest catalog module")
common = importlib.util.module_from_spec(COMMON_SPEC)
COMMON_SPEC.loader.exec_module(common)

RELEVANT_RE = re.compile(
    r"\b(?:search|prun\w*|reduc\w*|history|extension|cut\w*|move ordering|"
    r"ttmove|transposition|singular|probcut|futil\w*|razor\w*|lmr|lmp|"
    r"null move|nullmove|qsearch|quiescence|correction|see|capture|quiet|"
    r"prefetch|simd|avx2|speed\w*|optimi[sz]\w*|nps|node\w*|cache|branch|"
    r"inline|continuation|stat bonus|stat_bonus|cutoff|fail high|fail-high|"
    r"aspiration|iterative|countermove|killer)\b",
    re.IGNORECASE,
)
OBVIOUSLY_INAPPLICABLE_RE = re.compile(
    r"\b(?:castl\w*|en[ -]?passant|chess960|promotion|syzygy|tablebase|"
    r"rule\s*50|50[ -]?move|wasm|android|ios|avx512|sve|neon)\b",
    re.IGNORECASE,
)


def git(repo: Path, *args: str, check: bool = True) -> str:
    environment = dict(os.environ)
    environment["GIT_NO_LAZY_FETCH"] = "1"
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )
    return completed.stdout.strip()


def object_exists(repo: Path, revision: str) -> bool:
    try:
        git(repo, "cat-file", "-e", revision + "^{commit}")
        return True
    except subprocess.CalledProcessError:
        return False


def is_blue(run: dict[str, object]) -> bool:
    sprt = dict(run.get("sprt", {}))
    return (
        sprt.get("state") == "accepted"
        and float(sprt.get("elo0", 0.0)) + float(sprt.get("elo1", 0.0)) < 0.0
    )


def source_snapshot(repo: Path, run: dict[str, object]) -> dict[str, object]:
    base = str(run.get("resolved_base", ""))
    new = str(run.get("resolved_new", ""))
    available = bool(base and new and object_exists(repo, base) and object_exists(repo, new))
    if not available:
        return {"available": False, "files": [], "shortstat": ""}
    try:
        files = git(repo, "diff", "--name-only", base, new).splitlines()
    except subprocess.CalledProcessError:
        files = []
    try:
        shortstat = git(repo, "diff", "--shortstat", base, new)
    except subprocess.CalledProcessError:
        shortstat = ""
    return {
        "available": True,
        "files": files,
        "shortstat": shortstat,
    }


def markdown_report(payload: dict[str, object]) -> str:
    summary = dict(payload["summary"])
    official = [item for item in payload["official_commits"] if item["needs_manual_review"]]
    experimental = [
        item for item in payload["experimental_sources"] if item["needs_source_review"]
    ]
    lines = [
        "# Stockfish blue Fishtest inventory (2025-2026)",
        "",
        "Source: [Stockfish Finished Tests](https://tests.stockfishchess.org/tests/finished)",
        "through the official public `/api/finished_runs` endpoint.",
        "",
        "A blue result is an accepted SPRT whose bound midpoint is negative,",
        "for example normalized-Elo `[-1.75, +0.25]`. It proves the configured",
        "non-regression condition, not that the patch gained Elo.",
        "",
        "## Coverage",
        "",
        f"- Window: `{payload['window']['start']}` through `{payload['window']['end']}`.",
        f"- Successful finished runs read: {summary['successful_runs']}.",
        f"- Blue accepted runs: {summary['blue_runs']}.",
        f"- Blue runs with positive observed W/L: {summary['positive_blue_runs']}.",
        f"- Blue runs with non-positive observed W/L: {summary['nonpositive_blue_runs']}.",
        f"- Official commits directly citing a blue run: {summary['official_commits']}.",
        f"- Official commits left for manual review: {summary['official_manual_review']}.",
        f"- Distinct uncited source objects: {summary['experimental_sources']}.",
        f"- Heuristic source-review rows: {summary['experimental_source_review']}.",
        "",
        "## Official manual review",
        "",
        "| Date | Commit | Subject | Blue tests | Flags |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for item in official:
        lines.append(
            f"| {item['date']} | [`{item['commit'][:8]}`](https://github.com/official-stockfish/Stockfish/commit/{item['commit']}) "
            f"| {str(item['subject']).replace('|', '\\|')} | {len(item['blue_tests'])} "
            f"| {', '.join(item['flags']) or '-'} |"
        )
    if not official:
        lines.append("| - | - | No unreviewed official commit | - | - |")
    lines.extend(
        [
            "",
            "## Experimental source-review pool",
            "",
            "This is an intentionally broad reproducible pool, not the execution",
            "queue. Source-level Xiangqi decisions belong in the accompanying port",
            "plan; rejected rows remain in the JSON ledger to prevent rediscovery.",
            "",
            "| Date | Source | Tag | Tests | W-L delta | Files |",
            "| --- | --- | --- | ---: | ---: | --- |",
        ]
    )
    for item in experimental:
        primary = item["primary_test"]
        source_url = str(item["tests_repo"]).rstrip("/") + "/commit/" + item["resolved_new"]
        files = ", ".join(item["source_snapshot"]["files"]) or "source object not cached"
        lines.append(
            f"| {str(primary['last_updated'])[:10]} | [`{item['resolved_new'][:8]}`]({source_url}) "
            f"| {str(primary['new_tag']).replace('|', '\\|')} | {len(item['blue_tests'])} "
            f"| {item['score_delta']:+d} | {files.replace('|', '\\|')} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stockfish-repo", type=Path, required=True)
    parser.add_argument("--xfish-repo", type=Path, default=Path.cwd())
    parser.add_argument("--revision", default="origin/master")
    parser.add_argument("--start", default="2025-01-01T00:00:00+00:00")
    parser.add_argument("--end", default="2027-01-01T00:00:00+00:00")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--audit-log", action="append", type=Path)
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("build/audit/stockfish-blue-tests-2025-2026.json"),
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=Path("docs/stockfish-blue-tests-2025-2026.md"),
    )
    args = parser.parse_args()

    root = Path.cwd()
    start = common.parse_datetime(args.start)
    end = common.parse_datetime(args.end)
    if end <= start:
        parser.error("--end must be after --start")

    last_page, cache = common.find_last_page(
        start_timestamp=start.timestamp(), successful_only=True
    )
    missing = [page for page in range(1, last_page + 1) if page not in cache]
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(
                common.fetch_page,
                page,
                start_timestamp=start.timestamp(),
                successful_only=True,
            ): page
            for page in missing
        }
        for future in as_completed(futures):
            cache[futures[future]] = future.result()

    by_id: dict[str, dict[str, object]] = {}
    for page in range(1, last_page + 1):
        for raw in cache.get(page, []):
            updated = common.parse_datetime(str(raw["last_updated"]))
            if start <= updated < end:
                compact = common.compact_run(raw)
                by_id[str(compact["test_id"])] = compact
    successful = sorted(
        by_id.values(), key=lambda item: str(item["last_updated"]), reverse=True
    )
    blue = [run for run in successful if is_blue(run)]
    blue_by_id = {str(run["test_id"]): run for run in blue}

    stockfish_repo = args.stockfish_repo.resolve()
    xfish_repo = args.xfish_repo.resolve()
    commits = common.stockfish_commits(stockfish_repo, args.revision)
    audits = args.audit_log or [
        Path("docs/stockfish-port-log.md"),
        Path("docs/stockfish-17-18-strength-decisions.md"),
        Path("docs/stockfish-fishtest-2025-2026-plan.md"),
    ]
    audit_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace").casefold()
        for raw_path in audits
        for path in [raw_path if raw_path.is_absolute() else root / raw_path]
        if path.exists()
    )
    xfish_subjects = {
        subject.casefold()
        for subject in git(xfish_repo, "log", "HEAD", "--format=%s").splitlines()
    }
    xfish_origins = set()
    for record in git(xfish_repo, "log", "HEAD", "--format=%aI%x1f%ae").splitlines():
        if "\x1f" in record:
            author_date, author_email = record.split("\x1f", 1)
            xfish_origins.add((author_date.strip(), author_email.strip().casefold()))

    cited_ids: set[str] = set()
    official_commits = []
    for commit, metadata in commits.items():
        tests = [blue_by_id[test_id] for test_id in metadata["test_ids"] if test_id in blue_by_id]
        if not tests:
            continue
        cited_ids.update(str(test["test_id"]) for test in tests)
        files = list(metadata["files"])
        searchable = f"{metadata['subject']}\n{metadata['body']}"
        flags = []
        if common.NNUE_ARCH_OR_NET_RE.search(searchable) or any(
            path.endswith(".nnue") for path in files
        ):
            flags.append("nnue-architecture-or-network")
        if common.infrastructure_only(files):
            flags.append("infrastructure-only")
        if metadata["subject"].casefold().startswith("revert "):
            flags.append("revert")
        if metadata["subject"].casefold() in xfish_subjects:
            flags.append("already-xfish-subject")
        if (metadata["author_date"], metadata["author_email"].casefold()) in xfish_origins:
            flags.append("already-xfish-author-origin")
        if commit[:8].casefold() in audit_text:
            flags.append("already-reviewed")
        if any(test["base_nets"] != test["new_nets"] for test in tests):
            flags.append("test-changed-network")
        blockers = {
            "nnue-architecture-or-network",
            "infrastructure-only",
            "revert",
            "already-xfish-subject",
            "already-xfish-author-origin",
            "already-reviewed",
            "test-changed-network",
        }
        official_commits.append(
            {
                "commit": commit,
                "date": metadata["date"],
                "subject": metadata["subject"],
                "files": files,
                "flags": flags,
                "needs_manual_review": not blockers.intersection(flags),
                "blue_tests": tests,
            }
        )
    official_commits.sort(
        key=lambda item: (str(item["date"]), str(item["commit"])), reverse=True
    )

    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for run in blue:
        if str(run["test_id"]) not in cited_ids:
            grouped[(str(run["tests_repo"]), str(run["resolved_new"]))].append(run)

    experimental_sources = []
    for (tests_repo, resolved_new), tests in grouped.items():
        primary = max(
            tests, key=lambda item: (int(item["games"]), str(item["last_updated"]))
        )
        searchable = "\n".join(
            str(test.get(key, ""))
            for test in tests
            for key in ("new_tag", "msg_new", "info")
        )
        flags = []
        if resolved_new in commits:
            flags.append("official-object-without-direct-citation")
        if any(test["base_nets"] != test["new_nets"] for test in tests):
            flags.append("test-changed-network")
        if common.NNUE_ARCH_OR_NET_RE.search(searchable):
            flags.append("nnue-architecture-or-network")
        if OBVIOUSLY_INAPPLICABLE_RE.search(searchable):
            flags.append("obviously-chess-or-platform-specific")
        if not RELEVANT_RE.search(searchable):
            flags.append("no-port-relevance-keyword")
        if not tests_repo.startswith("https://github.com/"):
            flags.append("source-not-github")
        if resolved_new[:8].casefold() in audit_text:
            flags.append("already-reviewed")
        snapshot = source_snapshot(stockfish_repo, primary)
        if snapshot["files"] and common.infrastructure_only(snapshot["files"]):
            flags.append("infrastructure-only")
        blockers = {
            "official-object-without-direct-citation",
            "test-changed-network",
            "nnue-architecture-or-network",
            "obviously-chess-or-platform-specific",
            "no-port-relevance-keyword",
            "source-not-github",
            "already-reviewed",
            "infrastructure-only",
        }
        experimental_sources.append(
            {
                "tests_repo": tests_repo,
                "resolved_new": resolved_new,
                "flags": flags,
                "needs_source_review": not blockers.intersection(flags),
                "score_delta": sum(int(test["wins"]) - int(test["losses"]) for test in tests),
                "source_snapshot": snapshot,
                "primary_test": primary,
                "blue_tests": tests,
            }
        )
    experimental_sources.sort(
        key=lambda item: (
            str(item["primary_test"]["last_updated"]),
            str(item["resolved_new"]),
        ),
        reverse=True,
    )

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": common.API_URL,
        "definition": "accepted SPRT with elo0 + elo1 < 0",
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "stockfish_revision": git(stockfish_repo, "rev-parse", args.revision),
        "xfish_revision": git(xfish_repo, "rev-parse", "HEAD"),
        "summary": {
            "api_pages": last_page,
            "successful_runs": len(successful),
            "blue_runs": len(blue),
            "positive_blue_runs": sum(int(run["wins"]) > int(run["losses"]) for run in blue),
            "nonpositive_blue_runs": sum(int(run["wins"]) <= int(run["losses"]) for run in blue),
            "official_commits": len(official_commits),
            "official_manual_review": sum(item["needs_manual_review"] for item in official_commits),
            "experimental_sources": len(experimental_sources),
            "experimental_source_review": sum(
                item["needs_source_review"] for item in experimental_sources
            ),
        },
        "blue_runs": blue,
        "official_commits": official_commits,
        "experimental_sources": experimental_sources,
    }
    json_path = args.json if args.json.is_absolute() else root / args.json
    markdown_path = args.markdown if args.markdown.is_absolute() else root / args.markdown
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    markdown_path.write_text(markdown_report(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    print(f"wrote {json_path}")
    print(f"wrote {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
