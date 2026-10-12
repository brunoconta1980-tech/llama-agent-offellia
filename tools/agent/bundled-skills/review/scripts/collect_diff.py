#!/usr/bin/env python3
"""Collect a git diff for review. Color is off. The diff is the evidence."""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


def git(repo, *args):
    result = subprocess.run(
        ["git", "-C", repo, "-c", "color.ui=false", *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or "git failed")
    return result.stdout


def collect(repo, base):
    status = git(repo, "status", "--porcelain")
    if base:
        diff = git(repo, "diff", "--find-renames", "%s...HEAD" % base)
        kind = "branch"
    elif status.strip():
        diff = git(repo, "diff", "--find-renames", "HEAD")
        kind = "working-tree"
    else:
        diff = git(repo, "diff", "--find-renames", "HEAD~1...HEAD") if _has_parent(repo) else ""
        untracked = []
        kind = "last-commit" if diff.strip() else "empty"
        return kind, status, diff, untracked
    untracked = [
        line[3:] for line in status.splitlines()
        if line.startswith("?? ")
    ]
    return kind, status, diff, untracked


def _has_parent(repo):
    result = subprocess.run(
        ["git", "-C", repo, "rev-parse", "--verify", "HEAD~1"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def render(repo, base):
    kind, status, diff, untracked = collect(repo, base)
    lines = ["# Review packet", "", "kind: %s" % kind, "", "## Status", "", "```", status.rstrip(), "```", ""]
    if untracked:
        lines.append("## Untracked")
        lines.append("")
        for path in untracked:
            lines.append("- %s" % path)
            file_path = Path(repo) / path
            if file_path.is_file() and file_path.stat().st_size <= 20000:
                lines.append("")
                lines.append("```")
                lines.append(file_path.read_text(encoding="utf-8", errors="replace"))
                lines.append("```")
        lines.append("")
    lines.append("## Diff")
    lines.append("")
    lines.append("```diff")
    lines.append(diff.rstrip())
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def self_test():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        subprocess.check_call(["git", "init", "-b", "main"], cwd=repo, stdout=subprocess.DEVNULL)
        subprocess.check_call(["git", "config", "user.email", "review@local"], cwd=repo)
        subprocess.check_call(["git", "config", "user.name", "review"], cwd=repo)
        (repo / "a.txt").write_text("one\n", encoding="utf-8")
        subprocess.check_call(["git", "add", "a.txt"], cwd=repo)
        subprocess.check_call(["git", "commit", "-m", "base"], cwd=repo, stdout=subprocess.DEVNULL)
        (repo / "a.txt").write_text("one\ntwo\n", encoding="utf-8")
        packet = render(str(repo), None)
        if "kind: working-tree" not in packet or "+two" not in packet:
            raise SystemExit(packet)
    print("self-test ok")


def main(argv):
    if argv == ["--self-test"]:
        self_test()
        return 0
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--base", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    packet = render(args.repo, args.base)
    if args.out:
        Path(args.out).write_text(packet, encoding="utf-8")
        print("wrote %s" % args.out)
    else:
        sys.stdout.write(packet)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
