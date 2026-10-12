#!/usr/bin/env python3
"""Count open issues in a design review file. Exit 0 only when none remain."""

import argparse
import re
import sys
import tempfile
from pathlib import Path

ISSUE = re.compile(r"^### Issue\b", re.MULTILINE)
STATUS = re.compile(r"^[-*] Status:\s*(\S+)\s*$", re.MULTILINE)


def count_open(text):
    if re.search(r"^No open issues\.\s*$", text, re.MULTILINE):
        return 0, 0
    blocks = re.split(r"(?=^### Issue\b)", text, flags=re.MULTILINE)
    total = 0
    open_count = 0
    for block in blocks:
        if not block.strip().startswith("### Issue"):
            continue
        total += 1
        match = STATUS.search(block)
        if not match:
            open_count += 1
            continue
        if match.group(1).lower() == "open":
            open_count += 1
    return open_count, total


def self_test():
    closed = "### Issue 1\n- Severity: nit\n- Status: addressed\n"
    opened = "### Issue 1\n- Status: open\n### Issue 2\n- Status: wontfix\n"
    if count_open(closed) != (0, 1):
        raise SystemExit(count_open(closed))
    if count_open(opened) != (1, 2):
        raise SystemExit(count_open(opened))
    if count_open("No open issues.\n") != (0, 0):
        raise SystemExit("empty review")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "review.md"
        path.write_text(opened, encoding="utf-8")
    print("self-test ok")


def main(argv):
    if argv == ["--self-test"]:
        self_test()
        return 0
    parser = argparse.ArgumentParser()
    parser.add_argument("review")
    args = parser.parse_args(argv)
    text = Path(args.review).read_text(encoding="utf-8")
    open_count, total = count_open(text)
    print("open=%d total=%d" % (open_count, total))
    return 0 if open_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
