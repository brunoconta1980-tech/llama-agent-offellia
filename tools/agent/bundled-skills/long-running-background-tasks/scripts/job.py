#!/usr/bin/env python3
"""Start, watch, and stop a background job. watch prints nothing until the job ends."""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

WRAPPER = r"""
import subprocess, sys
from pathlib import Path
root = Path(sys.argv[1])
cmd = sys.argv[2:]
log = open(root / "job.log", "ab", buffering=0)
try:
    result = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
    code = result.returncode
except Exception as exc:
    log.write(str(exc).encode() + b"\n")
    code = 1
finally:
    log.close()
(root / "exit.code").write_text(str(code))
"""


def jobs_root(path):
    if path:
        return Path(path)
    home = Path.home()
    return home / ".llama-agent" / "jobs"


def job_dir(root, name):
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise SystemExit("job name must be a single path segment")
    return root / name


def read_pid(directory):
    pid_path = directory / "job.pid"
    if not pid_path.is_file():
        return None
    try:
        return int(pid_path.read_text().strip())
    except ValueError:
        return None


def alive(pid):
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def cmd_start(args):
    if not args.cmd:
        raise SystemExit("pass the command after --")
    root = jobs_root(args.dir)
    directory = job_dir(root, args.name)
    directory.mkdir(parents=True, exist_ok=True)
    if (directory / "exit.code").exists():
        (directory / "exit.code").unlink()
    (directory / "job.log").write_bytes(b"")
    (directory / "job.cmd").write_text(json.dumps(args.cmd), encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-c", WRAPPER, str(directory), *args.cmd],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    (directory / "job.pid").write_text(str(proc.pid))
    print("pid=%s" % proc.pid)
    print("log=%s" % (directory / "job.log"))
    print("dir=%s" % directory)


def cmd_status(args):
    directory = job_dir(jobs_root(args.dir), args.name)
    if not directory.is_dir():
        raise SystemExit("no job %s" % args.name)
    pid = read_pid(directory)
    exit_path = directory / "exit.code"
    if exit_path.is_file():
        state = "exited %s" % exit_path.read_text().strip()
    elif alive(pid):
        state = "running"
    else:
        state = "not-running"
    print("name=%s" % args.name)
    print("state=%s" % state)
    print("pid=%s" % (pid if pid is not None else ""))
    print("log=%s" % (directory / "job.log"))


def cmd_stop(args):
    directory = job_dir(jobs_root(args.dir), args.name)
    pid = read_pid(directory)
    if not alive(pid):
        print("already stopped")
        return
    os.killpg(pid, signal.SIGTERM)
    deadline = time.time() + 5
    while time.time() < deadline and alive(pid):
        time.sleep(0.05)
    if alive(pid):
        os.killpg(pid, signal.SIGKILL)
    if not (directory / "exit.code").is_file():
        (directory / "exit.code").write_text("143")
    print("stopped pid=%s" % pid)


def cmd_watch(args):
    directory = job_dir(jobs_root(args.dir), args.name)
    exit_path = directory / "exit.code"
    deadline = time.time() + args.timeout
    while not exit_path.is_file():
        if time.time() > deadline:
            print("ACTION_REQUIRED timeout waiting for %s" % args.name)
            return 2
        time.sleep(args.interval)
    code = exit_path.read_text().strip()
    if code == "0":
        print("DONE %s" % args.name)
        return 0
    print("FAILED %s exit=%s" % (args.name, code))
    log = directory / "job.log"
    if log.is_file():
        data = log.read_bytes()[-2000:]
        sys.stdout.buffer.write(data)
        if not data.endswith(b"\n"):
            sys.stdout.write("\n")
    return 1


def self_test():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        base = ["--dir", tmp]
        start = argparse.Namespace(dir=tmp, name="nap", cmd=[sys.executable, "-c", "print('hello-job')"])
        cmd_start(start)
        code = cmd_watch(argparse.Namespace(dir=tmp, name="nap", timeout=10, interval=0.05))
        if code != 0:
            raise SystemExit("watch failed")
        log = (Path(tmp) / "nap" / "job.log").read_text(encoding="utf-8")
        if "hello-job" not in log:
            raise SystemExit("log missing output: %r" % log)
        cmd_status(argparse.Namespace(dir=tmp, name="nap"))
    print("self-test ok")


def main(argv):
    if argv == ["--self-test"]:
        self_test()
        return 0
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start")
    start.add_argument("--name", required=True)
    start.add_argument("cmd", nargs=argparse.REMAINDER)
    status = sub.add_parser("status")
    status.add_argument("--name", required=True)
    stop = sub.add_parser("stop")
    stop.add_argument("--name", required=True)
    watch = sub.add_parser("watch")
    watch.add_argument("--name", required=True)
    watch.add_argument("--timeout", type=float, default=86400)
    watch.add_argument("--interval", type=float, default=0.5)
    args = parser.parse_args(argv)
    if args.command == "start":
        cmd = args.cmd
        if cmd and cmd[0] == "--":
            cmd = cmd[1:]
        args.cmd = cmd
        cmd_start(args)
        return 0
    if args.command == "status":
        cmd_status(args)
        return 0
    if args.command == "stop":
        cmd_stop(args)
        return 0
    return cmd_watch(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
