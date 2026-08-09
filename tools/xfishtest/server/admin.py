#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path

from bson.objectid import ObjectId
from fishtest import stat_util
from fishtest.rundb import RunDb


SPRT_ALPHA = 0.05
SPRT_BETA = 0.05
SPRT_DRAWELO = 240.0
SPRT_STAGES = {
    "stc": {"elo0": 0.0, "elo1": 2.0, "tc": "10+0.1"},
    "ltc": {"elo0": 0.5, "elo1": 2.5, "tc": "60+0.6"},
}


def positive_int(value):
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer") from error
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be positive")
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
        "drawelo": SPRT_DRAWELO,
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
    parent_sprt = parent_args.get("sprt", {})
    parent_is_stc = (
        parent_sprt.get("stage") == "stc"
        or (
            float(parent_sprt.get("elo0", math.nan)) == SPRT_STAGES["stc"]["elo0"]
            and float(parent_sprt.get("elo1", math.nan)) == SPRT_STAGES["stc"]["elo1"]
        )
    )
    if not parent_is_stc or parent_sprt.get("state") != "accepted":
        raise ValueError("parent run has not passed STC SPRT(0.0, 2.0)")
    if parent_args.get("resolved_base") != args.base_sha:
        raise ValueError("LTC baseline SHA does not match its parent STC run")
    if parent_args.get("resolved_new") != args.new_sha:
        raise ValueError("LTC candidate SHA does not match its parent STC run")

    sprt["parent_run_id"] = args.parent_run_id
    return sprt


def sprt_status(run, results):
    sprt = run.get("args", {}).get("sprt")
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
        sprt=sprt,
        username=args.username,
        tests_repo=args.tests_repo,
        auto_purge=False,
        throughput=1000,
        priority=0,
    )
    rundb.approve_run(run_id, args.username)
    print(json.dumps({"run_id": str(run_id), "existing": False}))


def status(args):
    rundb = RunDb()
    run = rundb.get_run(ObjectId(args.run_id))
    if run is None:
        raise ValueError("run not found")
    results = rundb.get_results(run)
    current_sprt = sprt_status(run, results)
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
        results = rundb.get_results(run)
        current_sprt = sprt_status(run, results)
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


def stop_run(args):
    rundb = RunDb()
    run_id = ObjectId(args.run_id)
    run = rundb.get_run(run_id)
    if run is None:
        raise ValueError("run not found")
    rundb.stop_run(run_id)
    print(json.dumps({"run_id": args.run_id, "stopped": True}))


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
    run.add_argument("--book", default="xiangqi.epd")
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

    stop = commands.add_parser("stop-run")
    stop.add_argument("run_id")
    stop.set_defaults(func=stop_run)
    return root


if __name__ == "__main__":
    arguments = parser().parse_args()
    arguments.func(arguments)
