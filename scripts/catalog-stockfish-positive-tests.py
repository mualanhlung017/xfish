#!/usr/bin/env python3
"""Catalog positive-Elo Stockfish Fishtest runs for a date window.

The public Fishtest API is the authoritative source. By default this script
reads the successful (green) Finished Tests tab, then retains runs whose score
point estimate is positive (wins > losses). It cross-references test IDs cited
by official Stockfish commit messages so unrelated progression tests whose
``resolved_new`` merely happened to be master are not attributed to that commit.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = "https://tests.stockfishchess.org/api/finished_runs"
TEST_ID_RE = re.compile(
    r"tests\.stockfishchess\.org/tests/(?:view|live_elo)/([0-9a-f]{24})",
    re.IGNORECASE,
)
NNUE_ARCH_OR_NET_RE = re.compile(
    r"(?:NNUE\s+architecture|architecture\s+to\s+SFNN|SFNNv\d+|"
    r"network\s+architecture|update\s+(?:the\s+)?(?:(?:default|main|small)\s+)*"
    r"(?:network|net)\b|new\s+(?:main\s+|small\s+)?(?:network|net)\b|"
    r"\bnet\s+nn-[0-9a-f]+\.nnue)",
    re.IGNORECASE,
)
CHESS_SPECIFIC_RE = re.compile(
    r"\b(?:castling|chess960|en[ -]?passant|promotion|stalemate|syzygy|"
    r"tablebase|rule\s*50|50[ -]?move|bishop|queen)\b",
    re.IGNORECASE,
)
INFRA_PREFIXES = (".github/", "scripts/", "tests/", "src/nnue/benchmark/")
INFRA_FILES = {
    ".gitignore",
    ".gitattributes",
    ".gitmodules",
    "AUTHORS",
    "CITATION.cff",
    "CONTRIBUTING.md",
    "Copying.txt",
    "README.md",
    "Top CPU Contributors.txt",
}


def git(repo: Path, *args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def fetch_page(
    page: int,
    *,
    start_timestamp: float,
    successful_only: bool,
    retries: int = 5,
) -> list[dict[str, object]]:
    params: dict[str, str | int] = {
        "page": page,
        "timestamp": f"{start_timestamp:.6f}",
    }
    if successful_only:
        params["success_only"] = 1
    url = f"{API_URL}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "xfish-fishtest-audit/1.0"})
    for attempt in range(retries):
        try:
            with urlopen(request, timeout=45) as response:
                payload = json.load(response)
            return list(payload.values())
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            if attempt + 1 == retries:
                raise
            time.sleep(0.5 * (2**attempt))
    raise AssertionError("unreachable")


def find_last_page(
    *, start_timestamp: float, successful_only: bool
) -> tuple[int, dict[int, list[dict[str, object]]]]:
    """Find the final non-empty API page with exponential then binary search."""

    cache: dict[int, list[dict[str, object]]] = {}

    def get(page: int) -> list[dict[str, object]]:
        if page not in cache:
            cache[page] = fetch_page(
                page,
                start_timestamp=start_timestamp,
                successful_only=successful_only,
            )
        return cache[page]

    if not get(1):
        return 0, cache
    low, high = 1, 2
    while get(high):
        low, high = high, high * 2
    while high - low > 1:
        middle = (low + high) // 2
        if get(middle):
            low = middle
        else:
            high = middle
    return low, cache


def stockfish_commits(repo: Path, revision: str) -> dict[str, dict[str, object]]:
    raw = git(
        repo,
        "log",
        revision,
        "--name-only",
        "--format=%x1e%H%x1f%cs%x1f%aI%x1f%ae%x1f%s%x1f%B%x1d",
    )
    commits: dict[str, dict[str, object]] = {}
    for record in raw.split("\x1e"):
        if "\x1d" not in record:
            continue
        metadata, file_text = record.split("\x1d", 1)
        values = metadata.strip().split("\x1f", 5)
        if len(values) != 6:
            continue
        commit, date, author_date, author_email, subject, body = values
        files = [line.strip().replace("\\", "/") for line in file_text.splitlines() if line.strip()]
        commits[commit] = {
            "date": date,
            "author_date": author_date,
            "author_email": author_email,
            "subject": subject,
            "body": body,
            "files": files,
            "test_ids": sorted(set(TEST_ID_RE.findall(body))),
        }
    return commits


def infrastructure_only(files: list[str]) -> bool:
    return bool(files) and all(
        path in INFRA_FILES
        or path.startswith(INFRA_PREFIXES)
        or path.endswith((".md", ".yml", ".yaml"))
        for path in files
    )


def score_elo(wins: int, losses: int, draws: int) -> float:
    games = wins + losses + draws
    if games == 0:
        return 0.0
    score = (wins + draws / 2.0) / games
    score = min(max(score, 1e-12), 1.0 - 1e-12)
    return 400.0 * math.log10(score / (1.0 - score))


def compact_run(run: dict[str, object]) -> dict[str, object]:
    args = dict(run.get("args", {}))
    results = dict(run.get("results", {}))
    wins = int(results.get("wins", 0))
    losses = int(results.get("losses", 0))
    draws = int(results.get("draws", 0))
    sprt = dict(args.get("sprt", {}))
    return {
        "test_id": str(run.get("_id", "")),
        "start_time": str(run.get("start_time", "")),
        "last_updated": str(run.get("last_updated", "")),
        "resolved_base": str(args.get("resolved_base", "")),
        "resolved_new": str(args.get("resolved_new", "")),
        "base_tag": str(args.get("base_tag", "")),
        "new_tag": str(args.get("new_tag", "")),
        "msg_new": str(args.get("msg_new", "")),
        "info": str(args.get("info", "")),
        "username": str(args.get("username", "")),
        "tests_repo": str(args.get("tests_repo", "")),
        "tc": str(args.get("tc", "")),
        "threads": int(args.get("threads", 0) or 0),
        "book": str(args.get("book", "")),
        "base_nets": list(args.get("base_nets", [])),
        "new_nets": list(args.get("new_nets", [])),
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "games": wins + losses + draws,
        "score_elo": score_elo(wins, losses, draws),
        "pentanomial": list(results.get("pentanomial", [])),
        "crashes": int(results.get("crashes", 0)),
        "time_losses": int(results.get("time_losses", 0)),
        "sprt": {
            key: sprt.get(key)
            for key in ("elo0", "elo1", "elo_model", "state", "llr")
            if key in sprt
        },
        "is_green": bool(run.get("is_green", False)),
        "is_yellow": bool(run.get("is_yellow", False)),
        "failed": bool(run.get("failed", False)),
    }


def markdown_report(payload: dict[str, object]) -> str:
    summary = dict(payload["summary"])
    candidates = list(payload["official_commits"])
    lines = [
        "# Stockfish Finished Tests positive-Elo inventory (2025-2026)",
        "",
        "Source: [Stockfish Finished Tests](https://tests.stockfishchess.org/tests/finished)",
        "through its public `/api/finished_runs` endpoint. The catalog uses the",
        "finished timestamp and retains successful runs whose score point estimate",
        "is positive (`wins > losses`). `score_elo` is the logistic conversion of",
        "W/L/D and is used only for sign/ranking; the original SPRT model and LLR",
        "remain in the JSON artifact.",
        "",
        "## Coverage",
        "",
        f"- Window: `{payload['window']['start']}` through `{payload['window']['end']}`.",
        f"- API mode: `{'successful/green only' if payload['successful_only'] else 'all finished'}`.",
        f"- Finished runs read: {summary['finished_runs_in_window']}.",
        f"- Positive point-estimate runs: {summary['positive_runs']}.",
        f"- Positive runs cited by official Stockfish commit messages: {summary['official_linked_runs']}.",
        f"- Distinct official commits represented: {summary['official_linked_commits']}.",
        f"- Diagnostic only: {summary['exact_resolved_new_runs']} runs had an exact `resolved_new` on master; these are not used for attribution.",
        f"- New automatic manual-review queue after durable xfish ledgers: {summary['manual_review_commits']}.",
        "",
        "A green SPRT result and a positive W/L/D point estimate are separate",
        "conditions. Requiring both avoids treating a non-regression test with a",
        "slightly negative observed score as an Elo-gain candidate.",
        "",
        "## Official-commit review queue",
        "",
        "| Date | Commit | Subject | Best positive test | W-L-D | Elo | Flags |",
        "| --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for item in candidates:
        if not item["needs_manual_review"]:
            continue
        primary = item["primary_test"]
        commit = item["commit"]
        subject = str(item["subject"]).replace("|", "\\|")
        flags = ", ".join(item["flags"]) or "-"
        lines.append(
            f"| {item['date']} | [`{commit[:8]}`](https://github.com/official-stockfish/Stockfish/commit/{commit}) "
            f"| {subject} | [`{primary['test_id'][:8]}`](https://tests.stockfishchess.org/tests/view/{primary['test_id']}) "
            f"| {primary['wins']}-{primary['losses']}-{primary['draws']} "
            f"| {primary['score_elo']:+.3f} | {flags} |"
        )
    lines.extend(
        [
            "",
            "Automatic exclusions are intentionally conservative. A row reaching",
            "this queue still needs a source-level Xiangqi applicability review; it",
            "is not authorization to apply several patches together.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stockfish-repo", type=Path, required=True)
    parser.add_argument("--xfish-repo", type=Path, default=Path.cwd())
    parser.add_argument("--revision", default="origin/master")
    parser.add_argument("--start", default="2025-01-01T00:00:00+00:00")
    parser.add_argument("--end", default="2027-01-01T00:00:00+00:00")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument(
        "--all-finished",
        action="store_true",
        help="read every finished run instead of the successful/green tab",
    )
    parser.add_argument(
        "--audit-log",
        action="append",
        type=Path,
        help="durable xfish decision log to exclude (repeatable)",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("build/audit/stockfish-positive-tests-2025-2026.json"),
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=Path("docs/stockfish-positive-tests-2025-2026.md"),
    )
    args = parser.parse_args()

    start = parse_datetime(args.start)
    end = parse_datetime(args.end)
    if end <= start:
        parser.error("--end must be after --start")
    successful_only = not args.all_finished
    last_page, cache = find_last_page(
        start_timestamp=start.timestamp(), successful_only=successful_only
    )

    missing = [page for page in range(1, last_page + 1) if page not in cache]
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(
                fetch_page,
                page,
                start_timestamp=start.timestamp(),
                successful_only=successful_only,
            ): page
            for page in missing
        }
        for future in as_completed(futures):
            cache[futures[future]] = future.result()

    by_id: dict[str, dict[str, object]] = {}
    for page in range(1, last_page + 1):
        for run in cache.get(page, []):
            run_id = str(run.get("_id", ""))
            if not run_id:
                continue
            updated = parse_datetime(str(run["last_updated"]))
            if start <= updated < end:
                by_id[run_id] = compact_run(run)

    finished = sorted(by_id.values(), key=lambda item: str(item["last_updated"]), reverse=True)
    positive = [item for item in finished if int(item["wins"]) > int(item["losses"])]

    sf_repo = args.stockfish_repo.resolve()
    commits = stockfish_commits(sf_repo, args.revision)
    sf18_descendants = set(
        git(sf_repo, "rev-list", f"sf_18..{args.revision}").splitlines()
    )
    audits = args.audit_log or [
        Path("docs/stockfish-port-log.md"),
        Path("docs/stockfish-17-18-strength-decisions.md"),
    ]
    root = Path.cwd()
    xfish_repo = args.xfish_repo.resolve()
    xfish_subjects = {
        subject.casefold()
        for subject in git(xfish_repo, "log", "HEAD", "--format=%s").splitlines()
    }
    xfish_origins = set()
    for record in git(
        xfish_repo, "log", "HEAD", "--format=%aI%x1f%ae"
    ).splitlines():
        if "\x1f" in record:
            author_date, author_email = record.split("\x1f", 1)
            xfish_origins.add((author_date.strip(), author_email.strip().casefold()))
    audit_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace").casefold()
        for raw_path in audits
        for path in [raw_path if raw_path.is_absolute() else root / raw_path]
        if path.exists()
    )

    positive_by_id = {str(item["test_id"]): item for item in positive}
    exact_resolved_new: dict[str, list[dict[str, object]]] = {}
    for run in positive:
        commit = str(run["resolved_new"])
        if commit in commits:
            exact_resolved_new.setdefault(commit, []).append(run)

    grouped: dict[str, list[dict[str, object]]] = {}
    for commit, metadata in commits.items():
        linked = [
            positive_by_id[test_id]
            for test_id in metadata["test_ids"]
            if test_id in positive_by_id
        ]
        if linked:
            grouped[commit] = linked

    official_commits: list[dict[str, object]] = []
    for commit, tests in grouped.items():
        metadata = commits[commit]
        files = list(metadata["files"])
        searchable = f"{metadata['subject']}\n{metadata['body']}"
        flags: list[str] = []
        if commit in sf18_descendants:
            flags.append("post-sf18")
        else:
            flags.append("sf18-or-earlier")
        if NNUE_ARCH_OR_NET_RE.search(searchable) or any(
            path.endswith(".nnue") for path in files
        ):
            flags.append("nnue-architecture-or-network")
        if CHESS_SPECIFIC_RE.search(searchable):
            flags.append("chess-specific-review")
        if infrastructure_only(files):
            flags.append("infrastructure-only")
        if metadata["subject"].casefold().startswith("revert "):
            flags.append("revert")
        if metadata["subject"].casefold() in xfish_subjects:
            flags.append("already-xfish-subject")
        if (
            str(metadata["author_date"]),
            str(metadata["author_email"]).casefold(),
        ) in xfish_origins:
            flags.append("already-xfish-author-origin")
        if commit[:8].casefold() in audit_text:
            flags.append("already-reviewed")
        if any(test["base_nets"] != test["new_nets"] for test in tests):
            flags.append("test-changed-network")
        primary = max(tests, key=lambda item: (int(item["games"]), float(item["score_elo"])))
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
                "upstream_test_ids": metadata["test_ids"],
                "flags": flags,
                "needs_manual_review": not blockers.intersection(flags),
                "positive_tests": tests,
                "primary_test": primary,
            }
        )
    official_commits.sort(key=lambda item: (str(item["date"]), str(item["commit"])), reverse=True)

    payload: dict[str, object] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": API_URL,
        "successful_only": successful_only,
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "stockfish": {
            "repository": str(sf_repo),
            "revision": args.revision,
            "resolved_revision": git(sf_repo, "rev-parse", args.revision).strip(),
        },
        "xfish": {
            "repository": str(xfish_repo),
            "resolved_revision": git(xfish_repo, "rev-parse", "HEAD").strip(),
        },
        "summary": {
            "api_pages": last_page,
            "finished_runs_in_window": len(finished),
            "positive_runs": len(positive),
            "official_linked_runs": len(
                {
                    str(test["test_id"])
                    for tests in grouped.values()
                    for test in tests
                }
            ),
            "official_linked_commits": len(official_commits),
            "exact_resolved_new_runs": sum(
                len(tests) for tests in exact_resolved_new.values()
            ),
            "exact_resolved_new_commits": len(exact_resolved_new),
            "manual_review_commits": sum(
                bool(item["needs_manual_review"]) for item in official_commits
            ),
        },
        "positive_runs": positive,
        "official_commits": official_commits,
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
