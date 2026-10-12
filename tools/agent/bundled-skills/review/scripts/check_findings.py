#!/usr/bin/env python3
"""Check that a review file cites files that appear in the collected diff."""

import argparse
import re
import sys
import tempfile
from pathlib import Path

ISSUE = re.compile(r"(?=^### Issue\b)", re.MULTILINE)
FILE_LINE = re.compile(r"^[-*] File:\s*(\S+)", re.MULTILINE)
SEVERITY = re.compile(r"^[-*] Severity:\s*(bug|suggestion|nit)\s*$", re.MULTILINE)


def changed_paths(packet):
    paths = set()
    for match in re.finditer(r"^\+\+\+ b/(.+)$", packet, re.MULTILINE):
        paths.add(match.group(1).strip())
    for match in re.finditer(r"^--- a/(.+)$", packet, re.MULTILINE):
        paths.add(match.group(1).strip())
    for match in re.finditer(r"^\?\? (.+)$", packet, re.MULTILINE):
        paths.add(match.group(1).strip())
    return paths


def check(findings, packet):
    if re.search(r"^No issues found\.\s*$", findings, re.MULTILINE):
        return []
    paths = changed_paths(packet)
    errors = []
    blocks = [block for block in ISSUE.split(findings) if block.strip().startswith("### Issue")]
    if not blocks:
        errors.append("review has neither issues nor 'No issues found.'")
    for index, block in enumerate(blocks, start=1):
        file_match = FILE_LINE.search(block)
        if not file_match:
            errors.append("issue %d missing File" % index)
        else:
            cited = file_match.group(1).split(":")[0]
            if paths and cited not in paths:
                errors.append("issue %d cites %s which is not in the diff" % (index, cited))
        if not SEVERITY.search(block):
            errors.append("issue %d missing Severity bug|suggestion|nit" % index)
        if "- Description:" not in block and "* Description:" not in block:
            errors.append("issue %d missing Description" % index)
    return errors


def self_test():
    packet = "## Diff\n\n```diff\n--- a/src/a.py\n+++ b/src/a.py\n+two\n```\n"
    good = "### Issue 1\n- Severity: bug\n- File: src/a.py:2\n- Description: Missing check.\n"
    if check(good, packet):
        raise SystemExit(check(good, packet))
    bad = "### Issue 1\n- Severity: bug\n- File: src/missing.py:1\n- Description: No.\n"
    if not check(bad, packet):
        raise SystemExit("bad citation accepted")
    if check("No issues found.\n", packet):
        raise SystemExit("clean review rejected")
    with tempfile.TemporaryDirectory():
        pass
    print("self-test ok")


def main(argv):
    if argv == ["--self-test"]:
        self_test()
        return 0
    parser = argparse.ArgumentParser()
    parser.add_argument("findings")
    parser.add_argument("packet")
    args = parser.parse_args(argv)
    errors = check(
        Path(args.findings).read_text(encoding="utf-8"),
        Path(args.packet).read_text(encoding="utf-8"),
    )
    if errors:
        for item in errors:
            print(item, file=sys.stderr)
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
