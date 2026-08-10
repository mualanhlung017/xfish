#!/usr/bin/env python3
"""Cross-platform Xiangqi adapter for the variant fishtest server."""

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import platform
import random
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path


REFERENCE_NPS = 628000.0
STOP = threading.Event()
PRINT_LOCK = threading.Lock()
BENCH_RE = re.compile(r"^(Total time \(ms\)|Nodes searched)\s*:\s*(\d+)\s*$", re.M)


def parallel_pair_count(core_budget, engine_threads):
    if core_budget < 1:
        raise ValueError("worker core budget must be positive")
    if engine_threads < 1:
        raise ValueError("run thread count must be positive")
    count = core_budget // engine_threads
    if count < 1:
        raise ValueError(
            "run needs %d engine threads but worker advertises only %d cores"
            % (engine_threads, core_budget)
        )
    return count


def log(message):
    with PRINT_LOCK:
        stamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        print("[%s] %s" % (stamp, message), flush=True)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(str(temporary), str(path))


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def acquire_instance_lock(state_root):
    """Keep one worker process per persistent state directory."""
    lock_path = Path(state_root) / "worker.lock"
    handle = open(lock_path, "a+b")
    try:
        if os.name == "nt":
            import msvcrt

            if lock_path.stat().st_size == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        handle.close()
        raise RuntimeError(
            "another worker process is already using state_root %s" % state_root
        ) from error
    return handle


def post_json(server, endpoint, payload, retries=6):
    body = json.dumps(payload).encode("utf-8")
    url = server.rstrip("/") + endpoint
    delay = 1
    last_error = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
            if "error" in result:
                raise RuntimeError(result["error"])
            return result
        except (OSError, ValueError, urllib.error.URLError, RuntimeError) as error:
            last_error = error
            if attempt + 1 < retries:
                time.sleep(delay)
                delay = min(delay * 2, 15)
    raise RuntimeError("POST %s failed: %s" % (url, last_error))


def parse_options(option_text):
    options = {}
    for token in shlex.split(option_text or ""):
        if "=" not in token:
            raise ValueError("invalid engine option: %s" % token)
        key, value = token.split("=", 1)
        options[key] = value
    return options


def parse_tc(tc):
    match = re.fullmatch(r"(?:(\d+)/)?([0-9]+(?:\.[0-9]+)?)(?:\+([0-9]+(?:\.[0-9]+)?))?", tc)
    if not match or match.group(1):
        raise ValueError("only sudden-death base+increment time controls are supported: %s" % tc)
    return float(match.group(2)), float(match.group(3) or 0.0)


def run_process(command, cwd, output_path, env=None, timeout=None):
    creationflags = 0
    kwargs = {}
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    with open(output_path, "w", encoding="utf-8", errors="replace") as output:
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            stdout=output,
            stderr=subprocess.STDOUT,
            env=env,
            creationflags=creationflags,
            **kwargs
        )
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise


def bench_once(engine, network_dir, depth):
    command = [str(engine), "bench", "16", "1", str(depth), "default", "depth"]
    completed = subprocess.run(
        command,
        cwd=str(network_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )
    values = {name: int(value) for name, value in BENCH_RE.findall(completed.stdout)}
    if completed.returncode != 0 or "Total time (ms)" not in values or "Nodes searched" not in values:
        raise RuntimeError("bench failed for %s (exit %s)" % (engine, completed.returncode))
    return values["Total time (ms)"], values["Nodes searched"]


def loaded_bench_nps(engine, network_dir, concurrency):
    def many(depth):
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [pool.submit(bench_once, engine, network_dir, depth) for _ in range(concurrency)]
            return [future.result() for future in futures]

    log("warming baseline bench with %d concurrent processes" % concurrency)
    many(11)
    log("measuring loaded baseline bench at depth 13")
    measured = many(13)
    nps_values = [1000.0 * nodes / elapsed for elapsed, nodes in measured]
    mean = sum(nps_values) / len(nps_values)
    spread = 0.0
    if len(nps_values) > 1:
        spread = math.sqrt(sum((value - mean) ** 2 for value in nps_values) / (len(nps_values) - 1))
    log(
        "loaded baseline bench: mean %.0f nps/thread, min %.0f, max %.0f, stdev %.1f%%"
        % (mean, min(nps_values), max(nps_values), 100.0 * spread / mean)
    )
    return mean


class Worker:
    def __init__(self, config_path):
        self.config_path = Path(config_path).resolve()
        self.config = read_json(self.config_path)
        if not isinstance(self.config, dict):
            raise ValueError("invalid config")
        self.root = self.config_path.parent
        self.server = self.config["server"]
        self.username = self.config.get("username", "gr17")
        self.password = Path(self.config["password_file"]).read_text(encoding="utf-8").strip()
        self.concurrency = int(self.config["concurrency"])
        if self.concurrency < 1:
            raise ValueError("concurrency must be positive")
        self.book = Path(self.config["book"]).resolve()
        self.network = Path(self.config["network"]).resolve()
        self.upstream = Path(self.config["variantfishtest"]).resolve()
        self.result_root = Path(self.config["result_root"]).resolve()
        self.state_root = Path(self.config["state_root"]).resolve()
        self.runner = Path(__file__).with_name("xiangqi_match.py").resolve()
        self.result_root.mkdir(parents=True, exist_ok=True)
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.instance_lock = acquire_instance_lock(self.state_root)
        self.verify_static_inputs()
        self.openings = self.load_openings()
        self.worker_info = self.make_worker_info()

    def verify_static_inputs(self):
        expected_book = self.config["book_sha256"].lower()
        expected_network = self.config["network_sha256"].lower()
        if sha256_file(self.book) != expected_book:
            raise ValueError("opening book checksum mismatch")
        if sha256_file(self.network) != expected_network:
            raise ValueError("NNUE checksum mismatch")
        required = [self.upstream / "variantfishtest.py", self.upstream / "stat_util.py"]
        if not all(path.is_file() for path in required):
            raise ValueError("variantfishtest checkout is incomplete")

    def load_openings(self):
        lines = []
        seen = set()
        for raw in self.book.read_text(encoding="utf-8").splitlines():
            line = raw.rstrip(";").strip()
            if line and line not in seen:
                seen.add(line)
                lines.append(line)
        seed = str(self.config.get("opening_seed", "xfish-xiangqi-v1")).encode("utf-8")
        lines.sort(key=lambda line: hashlib.sha256(seed + b"\0" + line.encode("utf-8")).digest())
        log("loaded %d unique deterministic Xiangqi openings" % len(lines))
        return lines

    def make_worker_info(self):
        identity_path = self.state_root / "worker-id"
        if identity_path.exists():
            unique_key = identity_path.read_text(encoding="utf-8").strip()
        else:
            unique_key = str(uuid.uuid4())
            identity_path.write_text(unique_key + "\n", encoding="utf-8")
        uname = platform.uname()
        label = self.config.get("label", uname.node)
        return {
            "uname": "%s | %s %s" % (label, uname.system, uname.release),
            "architecture": list(platform.architecture()),
            "concurrency": self.concurrency,
            "username": self.username,
            "version": "xfish-xiangqi-1.0:py%d.%d.%d" % sys.version_info[:3],
            "unique_key": unique_key,
        }

    def auth_payload(self):
        return {"worker_info": self.worker_info, "password": self.password}

    def engine_for(self, commit):
        item = self.config.get("engines", {}).get(commit)
        if not item:
            raise ValueError("no AVX2 engine registered for revision %s" % commit)
        path = Path(item["path"]).resolve()
        if not path.is_file():
            raise ValueError("engine does not exist: %s" % path)
        actual = sha256_file(path)
        if actual.lower() != item["sha256"].lower():
            raise ValueError("engine checksum mismatch for commit %s" % commit)
        network = Path(item.get("network", self.network)).resolve()
        if not network.is_file():
            raise ValueError("NNUE does not exist for commit %s: %s" % (commit, network))
        expected_network = item.get("network_sha256", self.config["network_sha256"])
        actual_network = sha256_file(network)
        if actual_network.lower() != expected_network.lower():
            raise ValueError("NNUE checksum mismatch for commit %s" % commit)
        return path, actual, network, actual_network

    def verify_and_scale(
        self,
        run,
        new_engine,
        base_engine,
        new_digest,
        base_digest,
        new_network,
        base_network,
        new_network_digest,
        base_network_digest,
    ):
        cache_path = self.state_root / "bench-cache.json"
        cache = read_json(cache_path, {}) or {}
        key = "%s:%s:%d" % (base_digest, base_network_digest, self.concurrency)
        cached = cache.get(key)
        base_signature = int(run["args"]["base_signature"])
        new_signature = int(run["args"]["new_signature"])
        if cached and int(cached.get("signature", -1)) == base_signature:
            base_nps = float(cached["nps"])
            log("using cached loaded baseline bench: %.0f nps/thread" % base_nps)
        else:
            _, nodes = bench_once(base_engine, base_network.parent, 13)
            if nodes != base_signature:
                raise ValueError("baseline signature mismatch: expected %d, got %d" % (base_signature, nodes))
            base_nps = loaded_bench_nps(base_engine, base_network.parent, self.concurrency)
            cache[key] = {"signature": nodes, "nps": base_nps, "created": time.time()}
            atomic_json(cache_path, cache)

        new_key = "signature:%s:%s" % (new_digest, new_network_digest)
        if int(cache.get(new_key, -1)) != new_signature:
            _, nodes = bench_once(new_engine, new_network.parent, 13)
            if nodes != new_signature:
                raise ValueError("candidate signature mismatch: expected %d, got %d" % (new_signature, nodes))
            cache[new_key] = nodes
            atomic_json(cache_path, cache)

        factor = REFERENCE_NPS / base_nps
        base_seconds, increment_seconds = parse_tc(run["args"]["tc"])
        base_ms = max(1, int(round(1000.0 * base_seconds * factor)))
        increment_ms = max(0, int(round(1000.0 * increment_seconds * factor)))
        self.worker_info["nps"] = base_nps
        self.worker_info["ARCH"] = "x86-64-avx2"
        log("CPU factor %.4f; %s scaled to %.3f+%.3f" % (factor, run["args"]["tc"], base_ms / 1000.0, increment_ms / 1000.0))
        return base_nps, base_ms, increment_ms

    def pair_paths(self, run_id, task_id, global_pair):
        task_root = self.result_root / run_id / ("task-%03d" % task_id)
        task_root.mkdir(parents=True, exist_ok=True)
        stem = "pair-%06d" % global_pair
        return task_root, task_root / (stem + ".json"), task_root / (stem + ".log"), task_root / (stem + ".epd")

    def valid_pair_result(self, payload, run_id, global_pair, fen_digest):
        return (
            isinstance(payload, dict)
            and payload.get("run_id") == run_id
            and payload.get("global_pair") == global_pair
            and payload.get("fen_sha256") == fen_digest
            and sum(payload.get("scores", [])) == 2
            and sum(payload.get("pentanomial", [])) == 1
        )

    def run_pair(
        self,
        run,
        task_id,
        local_pair,
        global_pair,
        new_engine,
        base_engine,
        new_digest,
        base_digest,
        new_network,
        base_network,
        new_network_digest,
        base_network_digest,
        base_ms,
        increment_ms,
    ):
        run_id = str(run["_id"])
        fen = self.openings[global_pair]
        fen_digest = hashlib.sha256(fen.encode("utf-8")).hexdigest()
        task_root, summary_path, log_path, opening_path = self.pair_paths(run_id, task_id, global_pair)
        existing = read_json(summary_path)
        if self.valid_pair_result(existing, run_id, global_pair, fen_digest):
            return local_pair, existing

        opening_path.write_text(fen + "\n", encoding="utf-8")
        new_options = parse_options(run["args"].get("new_options", ""))
        base_options = parse_options(run["args"].get("base_options", ""))
        for options in (new_options, base_options):
            options["Threads"] = str(run["args"].get("threads", 1))
        new_options["EvalFile"] = str(new_network)
        base_options["EvalFile"] = str(base_network)

        command = [
            sys.executable,
            "-u",
            str(self.runner),
            str(new_engine),
            str(base_engine),
            "--alias",
            "1:%s" % run["args"]["new_tag"],
            "--alias",
            "2:%s" % run["args"]["base_tag"],
            "-v",
            "xiangqi",
            "-n",
            "2",
            "-T",
            "1",
            "-t",
            str(base_ms),
            "-i",
            str(increment_ms),
            "-b",
            str(opening_path),
            "--verbosity",
            "2",
        ]
        for key, value in sorted(new_options.items()):
            command.extend(["--e1-options", "%s=%s" % (key, value)])
        for key, value in sorted(base_options.items()):
            command.extend(["--e2-options", "%s=%s" % (key, value)])

        base_seconds = (base_ms + 200 * increment_ms) / 1000.0
        timeout = max(120, int(2 * (3 * base_ms + 200 * increment_ms) / 1000.0 + 60))
        env = os.environ.copy()
        env["XFISHTEST_VARIANTFISHTEST"] = str(self.upstream)
        env["XFISHTEST_SUMMARY"] = str(summary_path)

        last_error = None
        for attempt in range(1, 4):
            try:
                code = run_process(command, self.network.parent, log_path, env=env, timeout=timeout)
                if code != 0:
                    raise RuntimeError("runner exited with code %d" % code)
                payload = read_json(summary_path)
                if not isinstance(payload, dict):
                    raise RuntimeError("runner did not create a summary")
                payload.update(
                    {
                        "run_id": run_id,
                        "task_id": task_id,
                        "local_pair": local_pair,
                        "global_pair": global_pair,
                        "fen_sha256": fen_digest,
                        "new_sha": run["args"]["resolved_new"],
                        "base_sha": run["args"]["resolved_base"],
                        "new_engine_sha256": new_digest,
                        "base_engine_sha256": base_digest,
                        "new_network_sha256": new_network_digest,
                        "base_network_sha256": base_network_digest,
                        "base_ms": base_ms,
                        "increment_ms": increment_ms,
                        "nominal_tc": run["args"]["tc"],
                        "completed_utc": datetime.now(timezone.utc).isoformat(),
                        "estimated_pair_limit_seconds": base_seconds,
                    }
                )
                if not self.valid_pair_result(payload, run_id, global_pair, fen_digest):
                    raise RuntimeError("invalid pair summary")
                atomic_json(summary_path, payload)
                return local_pair, payload
            except Exception as error:
                last_error = error
                log("pair %d attempt %d failed: %s" % (global_pair, attempt, error))
                try:
                    summary_path.unlink()
                except FileNotFoundError:
                    pass
        raise RuntimeError("pair %d failed after retries: %s" % (global_pair, last_error))

    def update_task(self, run_id, task_id, stats, nps):
        payload = {
            "username": self.username,
            "password": self.password,
            "run_id": run_id,
            "task_id": task_id,
            "stats": stats,
            "nps": nps,
        }
        return post_json(self.server, "/api/update_task", payload)

    def play_task(self, response):
        run = response["run"]
        task_id = int(response["task_id"])
        run_id = str(run["_id"])
        engine_threads = int(run["args"].get("threads", 1))
        pair_concurrency = parallel_pair_count(self.concurrency, engine_threads)
        task = run["tasks"][task_id]
        task_games = int(task["num_games"])
        if task_games % 2:
            raise ValueError("task game count is not pair-aligned")
        old_stats = task.get(
            "stats",
            {
                "wins": 0,
                "losses": 0,
                "draws": 0,
                "crashes": 0,
                "time_losses": 0,
                "pentanomial": [0, 0, 0, 0, 0],
            },
        )
        for key in ("wins", "losses", "draws", "crashes", "time_losses"):
            old_stats.setdefault(key, 0)
        old_games = old_stats["wins"] + old_stats["losses"] + old_stats["draws"]
        if old_games % 2 or old_games > task_games:
            raise ValueError("server task progress is not pair-aligned")
        if "pentanomial" not in old_stats:
            if old_games and "xfish_sprt" in run.get("args", {}):
                raise ValueError("SPRT task progress is missing pentanomial statistics")
            old_stats["pentanomial"] = [0, 0, 0, 0, 0]
        if len(old_stats["pentanomial"]) != 5:
            raise ValueError("server task has an invalid pentanomial vector")
        if 2 * sum(old_stats["pentanomial"]) != old_games:
            raise ValueError("server W/L/D and pentanomial progress disagree")
        old_pairs = old_games // 2
        total_pairs = task_games // 2
        opening_offset = sum(int(item["num_games"]) // 2 for item in run["tasks"][:task_id])
        if opening_offset + total_pairs > len(self.openings):
            raise ValueError("opening book is too small")

        new_engine, new_digest, new_network, new_network_digest = self.engine_for(
            run["args"]["resolved_new"]
        )
        base_engine, base_digest, base_network, base_network_digest = self.engine_for(
            run["args"]["resolved_base"]
        )
        nps, base_ms, increment_ms = self.verify_and_scale(
            run,
            new_engine,
            base_engine,
            new_digest,
            base_digest,
            new_network,
            base_network,
            new_network_digest,
            base_network_digest,
        )
        log(
            "run %s task %d: %d/%d games already complete; openings %d..%d; "
            "%d engine threads, %d parallel pairs on %d cores"
            % (
                run_id,
                task_id,
                old_games,
                task_games,
                opening_offset,
                opening_offset + total_pairs - 1,
                engine_threads,
                pair_concurrency,
                self.concurrency,
            )
        )

        aggregate = dict(old_stats)
        aggregate["pentanomial"] = list(old_stats["pentanomial"])
        completed = {}
        next_local = old_pairs
        task_root = self.result_root / run_id / ("task-%03d" % task_id)
        with concurrent.futures.ThreadPoolExecutor(max_workers=pair_concurrency) as pool:
            futures = {}

            remaining = iter(range(old_pairs, total_pairs))

            def submit_next():
                try:
                    local_pair = next(remaining)
                except StopIteration:
                    return False
                global_pair = opening_offset + local_pair
                future = pool.submit(
                    self.run_pair,
                    run,
                    task_id,
                    local_pair,
                    global_pair,
                    new_engine,
                    base_engine,
                    new_digest,
                    base_digest,
                    new_network,
                    base_network,
                    new_network_digest,
                    base_network_digest,
                    base_ms,
                    increment_ms,
                )
                futures[future] = local_pair
                return True

            for _ in range(pair_concurrency):
                if not submit_next():
                    break

            while futures:
                done, _pending = concurrent.futures.wait(
                    futures, return_when=concurrent.futures.FIRST_COMPLETED
                )
                for future in done:
                    futures.pop(future)
                    local_pair, pair = future.result()
                    completed[local_pair] = pair
                    changed = False
                    while next_local in completed:
                        item = completed.pop(next_local)
                        aggregate["wins"] += item["scores"][0]
                        aggregate["losses"] += item["scores"][1]
                        aggregate["draws"] += item["scores"][2]
                        aggregate["time_losses"] += sum(item.get("time_losses", []))
                        for index, value in enumerate(item["pentanomial"]):
                            aggregate["pentanomial"][index] += value
                        next_local += 1
                        changed = True
                    if changed:
                        games = aggregate["wins"] + aggregate["losses"] + aggregate["draws"]
                        if 2 * sum(aggregate["pentanomial"]) != games:
                            raise RuntimeError("W/L/D and pentanomial aggregate disagree")
                        result = self.update_task(run_id, task_id, aggregate, nps)
                        atomic_json(
                            task_root / "aggregate.json",
                            {
                                "run_id": run_id,
                                "task_id": task_id,
                                "stats": aggregate,
                                "contiguous_pairs": next_local,
                                "nps": nps,
                                "base_ms": base_ms,
                                "increment_ms": increment_ms,
                            },
                        )
                        log(
                            "run %s task %d progress: %d/%d games"
                            % (run_id, task_id, games, task_games)
                        )
                        if not result.get("task_alive", False) and games < task_games:
                            for pending in futures:
                                pending.cancel()
                            log(
                                "run %s task %d stopped cleanly by server after %d games"
                                % (run_id, task_id, games)
                            )
                            return
                    submit_next()

        games = aggregate["wins"] + aggregate["losses"] + aggregate["draws"]
        if games != task_games or next_local != total_pairs:
            raise RuntimeError("task completed with a non-contiguous result set")
        log("run %s task %d complete: W/L/D %d/%d/%d" % (run_id, task_id, aggregate["wins"], aggregate["losses"], aggregate["draws"]))

    def fail_task(self, response):
        if not response or "run" not in response:
            return
        payload = {
            "username": self.username,
            "password": self.password,
            "run_id": str(response["run"]["_id"]),
            "task_id": int(response["task_id"]),
        }
        try:
            post_json(self.server, "/api/failed_task", payload, retries=2)
        except Exception as error:
            log("could not release failed task: %s" % error)

    def run_forever(self):
        log(
            "worker %s connecting to %s with %d advertised physical cores"
            % (self.worker_info["uname"], self.server, self.concurrency)
        )
        while not STOP.is_set():
            response = None
            try:
                response = post_json(self.server, "/api/request_task", self.auth_payload())
                if response.get("task_waiting") is not None:
                    STOP.wait(float(self.config.get("poll_seconds", 10)))
                    continue
                self.play_task(response)
            except Exception as error:
                log("worker task error: %s" % error)
                self.fail_task(response)
                if STOP.wait(float(self.config.get("error_backoff_seconds", 30))):
                    break


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="path to the machine-local JSON configuration")
    arguments = parser.parse_args()

    def stop_handler(_signum, _frame):
        STOP.set()

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)
    Worker(arguments.config).run_forever()


if __name__ == "__main__":
    main()
