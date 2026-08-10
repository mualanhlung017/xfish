#!/usr/bin/env python3
import argparse
import importlib.util
import json
import math
from pathlib import Path
import re
import time

from bson.objectid import ObjectId
from fishtest import stat_util
from fishtest.rundb import RunDb


SPRT_ALPHA = 0.05
SPRT_BETA = 0.05
SPRT_KEY = "xfish_sprt"
SPRT_ELO_MODEL = "normalized"
OFFICIAL_FISHTEST_COMMIT = "b571c90db880f973a7eea57bd344600fe89a7e8e"
OFFICIAL_LLR_PATH = Path(
    "/opt/fishtest-official/server/fishtest/stats/LLRcalc.py"
)
SPRT_STAGES = {
    "stc": {"elo0": 0.0, "elo1": 2.0, "tc": "10+0.1"},
    "ltc": {"elo0": 0.5, "elo1": 2.5, "tc": "60+0.6"},
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def load_official_llrcalc(path=OFFICIAL_LLR_PATH):
    spec = importlib.util.spec_from_file_location("xfish_official_llrcalc", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load official fishtest LLR calculator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OFFICIAL_LLRCALC = load_official_llrcalc()


def positive_int(value):
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer") from error
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def positive_float(value):
    try:
        parsed = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a number") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def sha256_digest(value):
    parsed = value.lower()
    if not SHA256_RE.fullmatch(parsed):
        raise argparse.ArgumentTypeError("must be a 64-digit SHA-256")
    return parsed


def password_from(path):
    value = Path(path).read_text(encoding="utf-8").strip()
    if not value:
        raise ValueError("password file is empty")
    return value


def sprt_for_run(args, rundb):
    if args.sprt_stage is None:
        if args.parent_run_id is not None:
            raise ValueError("--parent-run-id requires --sprt-stage ltc")
        return None

    stage = SPRT_STAGES[args.sprt_stage]
    sprt = {
        "stage": args.sprt_stage,
        "elo0": stage["elo0"],
        "elo1": stage["elo1"],
        "alpha": SPRT_ALPHA,
        "beta": SPRT_BETA,
        "elo_model": SPRT_ELO_MODEL,
        "statistic": "pentanomial",
        "official_fishtest_commit": OFFICIAL_FISHTEST_COMMIT,
        "llr": 0.0,
        "lower_bound": math.log(SPRT_BETA / (1 - SPRT_ALPHA)),
        "upper_bound": math.log((1 - SPRT_BETA) / SPRT_ALPHA),
        "current_games": 0,
        "current_pentanomial": [0, 0, 0, 0, 0],
        "state": "",
    }

    if args.sprt_stage == "stc":
        if args.parent_run_id is not None:
            raise ValueError("STC is the first SPRT stage and cannot have a parent run")
        return sprt

    if args.parent_run_id is None:
        raise ValueError("LTC requires --parent-run-id for an accepted STC run")
    if not ObjectId.is_valid(args.parent_run_id):
        raise ValueError("parent run id is invalid")

    parent = rundb.get_run(ObjectId(args.parent_run_id))
    if parent is None:
        raise ValueError("parent STC run was not found")
    parent_args = parent.get("args", {})
    parent_sprt = parent_args.get(SPRT_KEY, parent_args.get("sprt", {}))
    parent_is_stc = (
        parent_sprt.get("stage") == "stc"
        or (
            float(parent_sprt.get("elo0", math.nan)) == SPRT_STAGES["stc"]["elo0"]
            and float(parent_sprt.get("elo1", math.nan)) == SPRT_STAGES["stc"]["elo1"]
        )
    )
    if not parent_is_stc or parent_sprt.get("state") != "accepted":
        raise ValueError("parent run has not passed STC SPRT(0.0, 2.0)")
    parent_results = aggregate_results(parent)
    if parent_results["crashes"] or parent_results["time_losses"]:
        raise ValueError("parent STC run contains a crash or time loss")
    if parent_args.get("resolved_base") != args.base_sha:
        raise ValueError("LTC baseline SHA does not match its parent STC run")
    if parent_args.get("resolved_new") != args.new_sha:
        raise ValueError("LTC candidate SHA does not match its parent STC run")
    if parent_args.get("book") != args.book:
        raise ValueError("LTC opening book ID does not match its parent STC run")
    if parent_args.get("book_sha256") != args.book_sha256:
        raise ValueError("LTC opening book SHA-256 does not match its parent STC run")
    if int(parent_args.get("book_positions", 0)) != args.book_positions:
        raise ValueError("LTC opening book size does not match its parent STC run")
    if parent_args.get("opening_seed") == args.opening_seed:
        raise ValueError("LTC requires an opening seed independent from STC")

    sprt["parent_run_id"] = args.parent_run_id
    return sprt


def aggregate_results(run):
    results = {
        "wins": 0,
        "losses": 0,
        "draws": 0,
        "crashes": 0,
        "time_losses": 0,
        "pentanomial": [0, 0, 0, 0, 0],
        "missing_pentanomial_games": 0,
    }
    for task in run.get("tasks", []):
        stats = task.get("stats", {})
        games = sum(int(stats.get(key, 0)) for key in ("wins", "losses", "draws"))
        for key in ("wins", "losses", "draws", "crashes", "time_losses"):
            results[key] += int(stats.get(key, 0))
        penta = stats.get("pentanomial")
        if penta is None:
            results["missing_pentanomial_games"] += games
            continue
        if len(penta) != 5 or any(int(value) < 0 for value in penta):
            raise ValueError("task has an invalid pentanomial vector")
        for index, value in enumerate(penta):
            results["pentanomial"][index] += int(value)
    return results


def sprt_status(run, results):
    run_args = run.get("args", {})
    sprt = run_args.get(SPRT_KEY)
    if sprt is not None:
        games = results["wins"] + results["losses"] + results["draws"]
        pairs = sum(results["pentanomial"])
        if results["missing_pentanomial_games"] or games != 2 * pairs:
            raise ValueError(
                "paired SPRT statistics are incomplete: games=%d pairs=%d missing=%d"
                % (games, pairs, results["missing_pentanomial_games"])
            )
        game_score_twice = 2 * results["wins"] + results["draws"]
        pair_score_twice = sum(
            index * count for index, count in enumerate(results["pentanomial"])
        )
        if game_score_twice != pair_score_twice:
            raise ValueError(
                "W/L/D and pentanomial scores disagree: games=%d pairs=%d"
                % (game_score_twice, pair_score_twice)
            )
        llr = (
            0.0
            if pairs == 0
            else OFFICIAL_LLRCALC.LLR_normalized(
                sprt["elo0"], sprt["elo1"], results["pentanomial"]
            )
        )
        lower_bound = math.log(sprt["beta"] / (1 - sprt["alpha"]))
        upper_bound = math.log((1 - sprt["beta"]) / sprt["alpha"])
        state = sprt.get("state", "")
        if not state and llr <= lower_bound:
            state = "rejected"
        elif not state and llr >= upper_bound:
            state = "accepted"
        return {
            "finished": bool(state),
            "state": state,
            "llr": llr,
            "lower_bound": lower_bound,
            "upper_bound": upper_bound,
            "stage": sprt.get("stage"),
            "elo0": sprt["elo0"],
            "elo1": sprt["elo1"],
            "alpha": sprt["alpha"],
            "beta": sprt["beta"],
            "elo_model": sprt["elo_model"],
            "statistic": sprt["statistic"],
            "pairs": pairs,
            "parent_run_id": sprt.get("parent_run_id"),
            "official_fishtest_commit": sprt["official_fishtest_commit"],
        }

    # Preserve read-only status support for historical runs created with the
    # variant-fishtest server's legacy trinomial BayesElo implementation.
    sprt = run_args.get("sprt")
    if sprt is None:
        return None
    current = stat_util.SPRT(
        results,
        elo0=sprt["elo0"],
        alpha=sprt["alpha"],
        elo1=sprt["elo1"],
        beta=sprt["beta"],
        drawelo=sprt["drawelo"],
    )
    current.update(
        {
            "stage": sprt.get("stage"),
            "elo0": sprt["elo0"],
            "elo1": sprt["elo1"],
            "alpha": sprt["alpha"],
            "beta": sprt["beta"],
            "parent_run_id": sprt.get("parent_run_id"),
            "elo_model": "BayesElo",
            "statistic": "trinomial-legacy",
        }
    )
    return current


def create_user(args):
    rundb = RunDb()
    rundb.userdb.init_collection()
    password = password_from(args.password_file)
    user = rundb.userdb.get_user(args.username)
    if user is None:
        if not rundb.userdb.create_user(args.username, password, args.email):
            raise RuntimeError("could not create user")
        user = rundb.userdb.get_user(args.username)
    else:
        user["password"] = password
    groups = list(user.get("groups", []))
    if args.worker_only:
        groups = [group for group in groups if group != "group:admins"]
    elif "group:admins" not in groups:
        groups.append("group:admins")
    user["groups"] = groups
    user["machine_limit"] = args.machine_limit
    user["tests_repo"] = args.tests_repo
    rundb.userdb.save_user(user)
    print(
        json.dumps(
            {
                "username": args.username,
                "created": True,
                "worker_only": args.worker_only,
            }
        )
    )


def create_run(args):
    rundb = RunDb()
    existing = rundb.runs.find_one({"args.info": args.info})
    if existing is not None:
        print(json.dumps({"run_id": str(existing["_id"]), "existing": True}))
        return

    sprt = sprt_for_run(args, rundb)
    games = args.games if args.games is not None else (100000 if sprt else 2000)
    chunk_size = args.chunk_size if args.chunk_size is not None else (40 if args.sprt_stage == "ltc" else 200)
    tc = args.tc if args.tc is not None else (
        SPRT_STAGES[args.sprt_stage]["tc"] if args.sprt_stage else "10+0.1"
    )

    if games < 2 or games % 2:
        raise ValueError("games must be a positive even number")
    if chunk_size < 2 or chunk_size % 2:
        raise ValueError("chunk size must be a positive even number")
    if args.threads < 1:
        raise ValueError("threads must be positive")
    if args.hash_mb < 1:
        raise ValueError("hash size must be positive")
    if games // 2 > args.book_positions:
        raise ValueError(
            "opening book has %d positions but the run can assign %d unique pairs"
            % (args.book_positions, games // 2)
        )
    rundb.chunk_size = chunk_size

    run_id = rundb.new_run(
        variant="xiangqi",
        base_tag=args.base_tag,
        new_tag=args.new_tag,
        num_games=games,
        tc=tc,
        book=args.book,
        book_depth=0,
        threads=args.threads,
        base_options="Hash=%d" % args.hash_mb,
        new_options="Hash=%d" % args.hash_mb,
        info=args.info,
        resolved_base=args.base_sha,
        resolved_new=args.new_sha,
        msg_base=args.base_tag,
        msg_new=args.new_tag,
        base_signature=args.base_signature,
        new_signature=args.new_signature,
        regression_test=True,
        # The pinned Xiangqi server only implements legacy trinomial SPRT.
        # Keep its built-in stopper disabled and let the xfish watcher below
        # evaluate official Stockfish-style pentanomial normalized-Elo LLR.
        sprt=None,
        username=args.username,
        tests_repo=args.tests_repo,
        auto_purge=False,
        throughput=1000,
        priority=0,
    )
    run_fields = {
        "args.book_sha256": args.book_sha256,
        "args.book_positions": args.book_positions,
        "args.opening_seed": args.opening_seed,
    }
    if sprt is not None:
        run_fields["args.%s" % SPRT_KEY] = sprt
    rundb.runs.update_one({"_id": run_id}, {"$set": run_fields})
    rundb.approve_run(run_id, args.username)
    print(json.dumps({"run_id": str(run_id), "existing": False}))


def terminal_decision(run, results, current_sprt):
    if results["crashes"] or results["time_losses"]:
        return "invalid", "runtime_error"
    if current_sprt["state"]:
        return current_sprt["state"], "llr_boundary"
    games = results["wins"] + results["losses"] + results["draws"]
    if games >= int(run.get("args", {}).get("num_games", 0)):
        return "inconclusive", "safety_cap"
    return "", ""


def results_info_for_sprt(results, current_sprt, state=None):
    effective_state = state if state is not None else current_sprt.get("state", "")
    stage = str(current_sprt.get("stage") or "sprt").upper()
    label = effective_state or "running"
    info = {
        "style": "",
        "llr": current_sprt["llr"],
        "info": [
            "%s %s: LLR %.3f (%.3f, %.3f) [%.2f, %.2f]"
            % (
                stage,
                label,
                current_sprt["llr"],
                current_sprt["lower_bound"],
                current_sprt["upper_bound"],
                current_sprt["elo0"],
                current_sprt["elo1"],
            ),
            "Ptnml(0-2): " + ", ".join(str(value) for value in results["pentanomial"]),
            "Total: %d W: %d L: %d D: %d"
            % (
                results["wins"] + results["losses"] + results["draws"],
                results["wins"],
                results["losses"],
                results["draws"],
            ),
        ],
    }
    if effective_state == "accepted":
        info["style"] = "#44EB44"
    elif effective_state in ("rejected", "invalid"):
        info["style"] = "#FF6A6A"
    elif effective_state == "inconclusive":
        info["style"] = "yellow"
    return info


def evaluate_and_stop(rundb, run):
    results = aggregate_results(run)
    current_sprt = sprt_status(run, results)
    config = run.get("args", {}).get(SPRT_KEY)
    if config is None or config.get("state"):
        return results, current_sprt, False

    games = results["wins"] + results["losses"] + results["draws"]
    state, stop_reason = terminal_decision(run, results, current_sprt)
    if not state:
        prefix = "args.%s" % SPRT_KEY
        rundb.runs.update_one(
            {"_id": run["_id"], "%s.state" % prefix: ""},
            {
                "$set": {
                    "%s.llr" % prefix: current_sprt["llr"],
                    "%s.lower_bound" % prefix: current_sprt["lower_bound"],
                    "%s.upper_bound" % prefix: current_sprt["upper_bound"],
                    "%s.current_games" % prefix: games,
                    "%s.current_pentanomial" % prefix: results["pentanomial"],
                }
            },
        )
        return results, current_sprt, False

    # Re-read immediately before committing the decision so a concurrent
    # worker update cannot be overwritten by a stale full Mongo document.
    fresh = rundb.get_run(run["_id"])
    results = aggregate_results(fresh)
    current_sprt = sprt_status(fresh, results)
    games = results["wins"] + results["losses"] + results["draws"]
    state, stop_reason = terminal_decision(fresh, results, current_sprt)
    if not state:
        return results, current_sprt, False

    prefix = "args.%s" % SPRT_KEY
    decision = rundb.runs.update_one(
        {"_id": fresh["_id"], "%s.state" % prefix: ""},
        {
            "$set": {
                "%s.state" % prefix: state,
                "%s.llr" % prefix: current_sprt["llr"],
                "%s.stop_reason" % prefix: stop_reason,
                "%s.finished_games" % prefix: games,
                "%s.finished_pairs" % prefix: sum(results["pentanomial"]),
                "%s.current_games" % prefix: games,
                "%s.current_pentanomial" % prefix: results["pentanomial"],
                "%s.lower_bound" % prefix: current_sprt["lower_bound"],
                "%s.upper_bound" % prefix: current_sprt["upper_bound"],
                "results_info": results_info_for_sprt(
                    results, current_sprt, state=state
                ),
                "tasks.$[].active": False,
                "tasks.$[].pending": False,
                "finished": True,
            }
        },
    )
    if not decision.modified_count:
        return results, sprt_status(rundb.get_run(fresh["_id"]), results), False
    current_sprt["state"] = state
    current_sprt["finished"] = True
    return results, current_sprt, True


def status(args):
    rundb = RunDb()
    run = rundb.get_run(ObjectId(args.run_id))
    if run is None:
        raise ValueError("run not found")
    results, current_sprt, _ = evaluate_and_stop(rundb, run)
    run = rundb.get_run(ObjectId(args.run_id))
    tasks = []
    for index, task in enumerate(run["tasks"]):
        tasks.append(
            {
                "task_id": index,
                "num_games": task["num_games"],
                "active": task["active"],
                "pending": task["pending"],
                "stats": task.get("stats", {}),
                "worker": task.get("worker_info", {}).get("uname", ""),
                "nps": task.get("nps", 0),
            }
        )
    print(
        json.dumps(
            {
                "run_id": args.run_id,
                "finished": run.get("finished", False),
                "results": results,
                "sprt": current_sprt,
                "tasks": tasks,
            },
            sort_keys=True,
        )
    )


def list_runs(args):
    rundb = RunDb()
    query = {} if args.all else {"finished": {"$ne": True}}
    cursor = rundb.runs.find(query).sort([("_id", -1)]).limit(args.limit)
    runs = []
    for run in cursor:
        results, current_sprt, _ = evaluate_and_stop(rundb, run)
        completed_games = sum(
            sum(int(task.get("stats", {}).get(key, 0)) for key in ("wins", "losses", "draws"))
            for task in run.get("tasks", [])
        )
        runs.append(
            {
                "run_id": str(run["_id"]),
                "info": run.get("args", {}).get("info", ""),
                "base_tag": run.get("args", {}).get("base_tag", ""),
                "new_tag": run.get("args", {}).get("new_tag", ""),
                "num_games": int(run.get("args", {}).get("num_games", 0)),
                "completed_games": completed_games,
                "finished": bool(run.get("finished", False)),
                "results": results,
                "sprt": current_sprt,
            }
        )
    print(json.dumps({"runs": runs}, sort_keys=True))


def watch_sprt(args):
    rundb = RunDb()
    while True:
        query = {"finished": {"$ne": True}, "args.%s" % SPRT_KEY: {"$exists": True}}
        for run in list(rundb.runs.find(query)):
            try:
                results, current, stopped = evaluate_and_stop(rundb, run)
                if stopped:
                    print(
                        json.dumps(
                            {
                                "event": "sprt_stopped",
                                "run_id": str(run["_id"]),
                                "games": results["wins"]
                                + results["losses"]
                                + results["draws"],
                                "pentanomial": results["pentanomial"],
                                "llr": current["llr"],
                                "state": current["state"],
                            },
                            sort_keys=True,
                        ),
                        flush=True,
                    )
            except Exception as error:
                print(
                    json.dumps(
                        {
                            "event": "sprt_watch_error",
                            "run_id": str(run.get("_id", "")),
                            "error": str(error),
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
        if args.once:
            return
        time.sleep(args.poll_seconds)


def stop_run(args):
    rundb = RunDb()
    run_id = ObjectId(args.run_id)
    run = rundb.get_run(run_id)
    if run is None:
        raise ValueError("run not found")
    rundb.stop_run(run_id)
    print(json.dumps({"run_id": args.run_id, "stopped": True}))


def retirement_update_fields(results, current_sprt, state, reason):
    if state not in ("invalid", "inconclusive"):
        raise ValueError("manual terminal state must be invalid or inconclusive")
    reason = reason.strip()
    if not reason:
        raise ValueError("manual terminal reason must not be empty")

    games = results["wins"] + results["losses"] + results["draws"]
    prefix = "args.%s" % SPRT_KEY
    info = results_info_for_sprt(results, current_sprt, state=state)
    info["info"].append("Stopped: %s" % reason)
    return {
        "%s.state" % prefix: state,
        "%s.llr" % prefix: current_sprt["llr"],
        "%s.stop_reason" % prefix: reason,
        "%s.finished_games" % prefix: games,
        "%s.finished_pairs" % prefix: sum(results["pentanomial"]),
        "%s.current_games" % prefix: games,
        "%s.current_pentanomial" % prefix: results["pentanomial"],
        "%s.lower_bound" % prefix: current_sprt["lower_bound"],
        "%s.upper_bound" % prefix: current_sprt["upper_bound"],
        "results_info": info,
        "tasks.$[].active": False,
        "tasks.$[].pending": False,
        "finished": True,
    }


def retire_run(args):
    if not ObjectId.is_valid(args.run_id):
        raise ValueError("run id is invalid")
    rundb = RunDb()
    run_id = ObjectId(args.run_id)
    run = rundb.get_run(run_id)
    if run is None:
        raise ValueError("run not found")

    config = run.get("args", {}).get(SPRT_KEY)
    if config is None:
        raise ValueError("run is not an xfish pentanomial SPRT run")
    existing_state = config.get("state", "")
    if existing_state:
        if existing_state == args.state and config.get("stop_reason") == args.reason:
            print(
                json.dumps(
                    {
                        "run_id": args.run_id,
                        "state": existing_state,
                        "reason": config.get("stop_reason"),
                        "existing": True,
                    },
                    sort_keys=True,
                )
            )
            return
        raise ValueError("run already has terminal state %s" % existing_state)

    results = aggregate_results(run)
    current_sprt = sprt_status(run, results)
    if current_sprt["state"]:
        raise ValueError(
            "run already reached the %s LLR boundary" % current_sprt["state"]
        )
    fields = retirement_update_fields(
        results, current_sprt, args.state, args.reason
    )
    decision = rundb.runs.update_one(
        {
            "_id": run_id,
            "args.%s.state" % SPRT_KEY: "",
            "finished": {"$ne": True},
        },
        {"$set": fields},
    )
    if not decision.modified_count:
        raise RuntimeError("run changed concurrently; no terminal update was written")
    print(
        json.dumps(
            {
                "run_id": args.run_id,
                "state": args.state,
                "reason": args.reason,
                "games": fields["args.%s.finished_games" % SPRT_KEY],
                "pentanomial": results["pentanomial"],
                "llr": current_sprt["llr"],
                "existing": False,
            },
            sort_keys=True,
        )
    )


def parser():
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)

    user = commands.add_parser("create-user")
    user.add_argument("--username", default="gr17")
    user.add_argument("--password-file", required=True)
    user.add_argument("--email", default="gr17@localhost")
    user.add_argument("--machine-limit", type=int, default=8)
    user.add_argument("--tests-repo", default="https://github.com/mualanhlung017/xfish")
    user.add_argument(
        "--worker-only",
        action="store_true",
        help="create/update an API worker account without the admin group",
    )
    user.set_defaults(func=create_user)

    run = commands.add_parser("create-run")
    run.add_argument("--username", default="gr17")
    run.add_argument("--games", type=positive_int)
    run.add_argument("--chunk-size", type=positive_int)
    run.add_argument("--tc")
    run.add_argument("--threads", type=positive_int, default=1)
    run.add_argument("--hash-mb", type=positive_int, default=16)
    run.add_argument("--book", required=True)
    run.add_argument("--book-sha256", type=sha256_digest, required=True)
    run.add_argument("--book-positions", type=positive_int, required=True)
    run.add_argument("--opening-seed", required=True)
    run.add_argument("--base-tag", required=True)
    run.add_argument("--new-tag", required=True)
    run.add_argument("--base-sha", required=True)
    run.add_argument("--new-sha", required=True)
    run.add_argument("--base-signature", required=True)
    run.add_argument("--new-signature", required=True)
    run.add_argument("--info", required=True)
    run.add_argument("--sprt-stage", choices=tuple(SPRT_STAGES))
    run.add_argument("--parent-run-id")
    run.add_argument("--tests-repo", default="https://github.com/mualanhlung017/xfish")
    run.set_defaults(func=create_run)

    show = commands.add_parser("status")
    show.add_argument("run_id")
    show.set_defaults(func=status)

    listing = commands.add_parser("list-runs")
    listing.add_argument("--all", action="store_true")
    listing.add_argument("--limit", type=positive_int, default=20)
    listing.set_defaults(func=list_runs)

    watcher = commands.add_parser("watch-sprt")
    watcher.add_argument("--poll-seconds", type=positive_float, default=2.0)
    watcher.add_argument("--once", action="store_true")
    watcher.set_defaults(func=watch_sprt)

    stop = commands.add_parser("stop-run")
    stop.add_argument("run_id")
    stop.set_defaults(func=stop_run)

    retire = commands.add_parser("retire-run")
    retire.add_argument("run_id")
    retire.add_argument("--state", choices=("invalid", "inconclusive"), required=True)
    retire.add_argument("--reason", required=True)
    retire.set_defaults(func=retire_run)
    return root


if __name__ == "__main__":
    arguments = parser().parse_args()
    arguments.func(arguments)
