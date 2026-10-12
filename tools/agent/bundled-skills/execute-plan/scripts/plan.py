#!/usr/bin/env python3
"""Parse a design PR Plan, order it, and record local git branch state."""

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

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


def slug(title):
    text = title.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return (text or "unnamed")[:50].strip("-")


def parse_plan(text):
    body = section(text, "## PR Plan")
    if body is None:
        raise SystemExit("design document has no ## PR Plan")
    nodes = []
    for part in re.split(r"(?=^### PR \d+:)", body, flags=re.MULTILINE):
        part = part.strip()
        if not part.startswith("### PR"):
            continue
        match = PR_HEADING.match(part.splitlines()[0])
        if not match:
            continue
        number = int(match.group(1))
        deps_raw = field(part, "Dependencies") or "None"
        deps = [] if deps_raw.lower() == "none" else ["pr-%s" % item for item in re.findall(r"PR\s+(\d+)", deps_raw)]
        nodes.append({
            "id": "pr-%d" % number,
            "number": number,
            "title": match.group(2).strip(),
            "slug": slug(match.group(2)),
            "files": [item.strip() for item in field(part, "Files").split(",") if item.strip()],
            "dependencies": deps,
            "description": field(part, "Description"),
            "status": "pending",
            "commit": "",
        })
    if not nodes:
        raise SystemExit("PR Plan has no entries")
    ids = {node["id"] for node in nodes}
    for node in nodes:
        for dep in node["dependencies"]:
            if dep not in ids:
                raise SystemExit("%s depends on unknown %s" % (node["id"], dep))
    return nodes


def order_nodes(nodes):
    by_id = {node["id"]: node for node in nodes}
    memo = {}
    visiting = set()

    def level(node_id):
        if node_id in visiting:
            raise SystemExit("cycle at %s" % node_id)
        if node_id in memo:
            return memo[node_id]
        visiting.add(node_id)
        deps = by_id[node_id]["dependencies"]
        value = 0 if not deps else 1 + max(level(dep) for dep in deps)
        visiting.remove(node_id)
        memo[node_id] = value
        return value

    for node in nodes:
        node["level"] = level(node["id"])
    return sorted(nodes, key=lambda item: (item["level"], item["number"]))


def git(repo, *args, check=True):
    result = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    if check and result.returncode != 0:
        raise SystemExit(result.stderr.strip() or "git failed")
    return result


def load_state(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_state(path, state):
    Path(path).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def cmd_parse(args):
    text = Path(args.design).read_text(encoding="utf-8")
    nodes = order_nodes(parse_plan(text))
    plan_id = hashlib.sha256(Path(args.design).read_bytes()).hexdigest()[:8]
    for node in nodes:
        node["branch"] = "execute-plan/%s-%s-%s" % (plan_id, node["id"], node["slug"])
    state = {
        "plan_id": plan_id,
        "design": str(Path(args.design).resolve()),
        "original_branch": "",
        "nodes": nodes,
    }
    save_state(args.out, state)
    print("plan_id=%s prs=%d" % (plan_id, len(nodes)))
    for node in nodes:
        print("%s level=%d branch=%s" % (node["id"], node["level"], node["branch"]))


def ready(state):
    done = {node["id"] for node in state["nodes"] if node["status"] == "completed"}
    for node in state["nodes"]:
        if node["status"] != "pending":
            continue
        if all(dep in done for dep in node["dependencies"]):
            return node
    return None


def cmd_next(args):
    state = load_state(args.state)
    node = ready(state)
    if node is None:
        pending = [item["id"] for item in state["nodes"] if item["status"] != "completed"]
        if pending:
            print("blocked " + " ".join(pending))
            return 2
        print("complete")
        return 0
    print(json.dumps(node, indent=2))
    return 0


def cmd_mark(args):
    state = load_state(args.state)
    for node in state["nodes"]:
        if node["id"] == args.pr:
            node["status"] = args.status
            if args.commit:
                node["commit"] = args.commit
            save_state(args.state, state)
            print("%s %s" % (args.pr, args.status))
            return 0
    raise SystemExit("unknown pr %s" % args.pr)


def cmd_prepare(args):
    state = load_state(args.state)
    repo = args.repo
    inside = git(repo, "rev-parse", "--is-inside-work-tree", check=False)
    if inside.returncode != 0:
        raise SystemExit("not a git repository; implement in the working tree and use mark")
    porcelain = git(repo, "status", "--porcelain").stdout
    if porcelain.strip():
        raise SystemExit("working tree is dirty; commit or stash before prepare")
    if not state.get("original_branch"):
        state["original_branch"] = git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    node = ready(state)
    if node is None:
        raise SystemExit("no PR is ready")
    if node["dependencies"]:
        dep = next(item for item in state["nodes"] if item["id"] == node["dependencies"][0])
        base = dep["commit"] or "HEAD"
    else:
        base = "HEAD"
    exists = git(repo, "show-ref", "--verify", "--quiet", "refs/heads/%s" % node["branch"], check=False)
    if exists.returncode != 0:
        git(repo, "branch", node["branch"], base)
    if args.checkout:
        git(repo, "checkout", node["branch"])
    save_state(args.state, state)
    print("branch=%s" % node["branch"])
    print("pr=%s" % node["id"])


def self_test():
    design = """# Demo

## PR Plan

### PR 1: Add parser
- Files: src/a.py
- Dependencies: None
- Description: Add it.

### PR 2: Use parser
- Files: src/b.py
- Dependencies: PR 1
- Description: Use it.
"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        doc = root / "design.md"
        doc.write_text(design, encoding="utf-8")
        state = root / "state.json"
        cmd_parse(argparse.Namespace(design=str(doc), out=str(state)))
        repo = root / "repo"
        repo.mkdir()
        git(str(repo), "init", "-b", "main")
        git(str(repo), "config", "user.email", "plan@local")
        git(str(repo), "config", "user.name", "plan")
        (repo / "README").write_text("base\n", encoding="utf-8")
        git(str(repo), "add", "README")
        git(str(repo), "commit", "-m", "base")
        cmd_prepare(argparse.Namespace(state=str(state), repo=str(repo), checkout=True))
        (repo / "src").mkdir()
        (repo / "src" / "a.py").write_text("print(1)\n", encoding="utf-8")
        git(str(repo), "add", "src/a.py")
        git(str(repo), "commit", "-m", "pr 1")
        commit = git(str(repo), "rev-parse", "HEAD").stdout.strip()
        cmd_mark(argparse.Namespace(state=str(state), pr="pr-1", status="completed", commit=commit))
        nxt = ready(load_state(state))
        if nxt["id"] != "pr-2":
            raise SystemExit(nxt)
    print("self-test ok")


def main(argv):
    if argv == ["--self-test"]:
        self_test()
        return 0
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    parse = sub.add_parser("parse")
    parse.add_argument("design")
    parse.add_argument("--out", required=True)
    nxt = sub.add_parser("next")
    nxt.add_argument("state")
    mark = sub.add_parser("mark")
    mark.add_argument("state")
    mark.add_argument("pr")
    mark.add_argument("status")
    mark.add_argument("--commit", default="")
    prepare = sub.add_parser("prepare")
    prepare.add_argument("state")
    prepare.add_argument("--repo", default=".")
    prepare.add_argument("--checkout", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "parse":
        cmd_parse(args)
    elif args.command == "next":
        return cmd_next(args)
    elif args.command == "mark":
        return cmd_mark(args)
    else:
        cmd_prepare(args)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
