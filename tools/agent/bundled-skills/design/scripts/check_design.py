#!/usr/bin/env python3
"""Check a design document and parse its PR Plan."""

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

REQUIRED = ("## Key Decisions", "## Open Questions", "## PR Plan")
PR_HEADING = re.compile(r"^### PR (\d+): (.+)$")


def section(text, heading):
    match = re.search(r"^%s\s*$" % re.escape(heading), text, re.MULTILINE)
    if not match:
        return None
    rest = text[match.end():]
    nxt = re.search(r"^## ", rest, re.MULTILINE)
    return rest[: nxt.start()] if nxt else rest


def field(block, label):
    match = re.search(r"^[-*] %s:\s*(.+)$" % re.escape(label), block, re.MULTILINE)
    return match.group(1).strip() if match else ""


def parse_plan(text):
    body = section(text, "## PR Plan")
    if body is None:
        return [], ["missing ## PR Plan"]
    parts = re.split(r"(?=^### PR \d+:)", body, flags=re.MULTILINE)
    nodes = []
    errors = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        first = part.splitlines()[0]
        match = PR_HEADING.match(first)
        if not match:
            continue
        number = int(match.group(1))
        deps_raw = field(part, "Dependencies")
        files_raw = field(part, "Files")
        description = field(part, "Description")
        if not files_raw:
            errors.append("PR %d missing Files" % number)
        if not description:
            errors.append("PR %d missing Description" % number)
        if not deps_raw:
            errors.append("PR %d missing Dependencies" % number)
            deps = []
        elif deps_raw.lower() == "none":
            deps = []
        else:
            deps = []
            for token in re.findall(r"PR\s+(\d+)", deps_raw):
                deps.append("pr-%s" % token)
            if not deps:
                errors.append("PR %d has unreadable Dependencies" % number)
        nodes.append({
            "id": "pr-%d" % number,
            "number": number,
            "title": match.group(2).strip(),
            "files": [item.strip() for item in files_raw.split(",") if item.strip()],
            "dependencies": deps,
            "description": description,
        })
    if not nodes:
        errors.append("PR Plan has no ### PR entries")
    ids = {node["id"] for node in nodes}
    if len(ids) != len(nodes):
        errors.append("duplicate PR numbers")
    for node in nodes:
        for dep in node["dependencies"]:
            if dep not in ids:
                errors.append("%s depends on unknown %s" % (node["id"], dep))
    visiting = set()
    visited = set()

    def walk(node_id):
        if node_id in visited:
            return
        if node_id in visiting:
            errors.append("cycle at %s" % node_id)
            return
        visiting.add(node_id)
        node = next(item for item in nodes if item["id"] == node_id)
        for dep in node["dependencies"]:
            if dep in ids:
                walk(dep)
        visiting.remove(node_id)
        visited.add(node_id)

    for node in nodes:
        walk(node["id"])
    return nodes, errors


def levels(nodes):
    by_id = {node["id"]: node for node in nodes}
    memo = {}

    def level(node_id):
        if node_id in memo:
            return memo[node_id]
        deps = by_id[node_id]["dependencies"]
        value = 0 if not deps else 1 + max(level(dep) for dep in deps)
        memo[node_id] = value
        return value

    for node in nodes:
        node["level"] = level(node["id"])
    return sorted(nodes, key=lambda item: (item["level"], item["number"]))


def check(text):
    errors = []
    for heading in REQUIRED:
        if section(text, heading) is None:
            errors.append("missing %s" % heading)
    nodes, plan_errors = parse_plan(text)
    errors.extend(plan_errors)
    if not errors:
        ordered = levels(nodes)
        return ordered, errors
    return nodes, errors


def self_test():
    good = """# Feature

## Design

Use one parser.

## Key Decisions

- One parser.

## Open Questions

None.

## PR Plan

### PR 1: Add parser
- Files: src/parser.py
- Dependencies: None
- Description: Parse the plan.

### PR 2: Call parser
- Files: src/main.py
- Dependencies: PR 1
- Description: Call it from main.
"""
    ordered, errors = check(good)
    if errors or [node["id"] for node in ordered] != ["pr-1", "pr-2"]:
        raise SystemExit((errors, ordered))
    bad = good.replace("Dependencies: PR 1", "Dependencies: PR 2", 1).replace(
        "### PR 2: Call parser\n- Files: src/main.py\n- Dependencies: PR 2",
        "### PR 2: Call parser\n- Files: src/main.py\n- Dependencies: PR 1",
    )
    # Build a real cycle.
    cycle = good.replace("Dependencies: None", "Dependencies: PR 2")
    _nodes, errors = check(cycle)
    if not any("cycle" in item for item in errors):
        raise SystemExit("cycle not detected: %s" % errors)
    with tempfile.TemporaryDirectory():
        pass
    print("self-test ok")


def main(argv):
    if argv == ["--self-test"]:
        self_test()
        return 0
    parser = argparse.ArgumentParser()
    parser.add_argument("design")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    text = Path(args.design).read_text(encoding="utf-8")
    ordered, errors = check(text)
    if errors:
        for item in errors:
            print(item, file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(ordered, indent=2))
    else:
        print("ok prs=%d" % len(ordered))
        for node in ordered:
            print("%s level=%d %s" % (node["id"], node["level"], node["title"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
