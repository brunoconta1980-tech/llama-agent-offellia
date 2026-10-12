#!/usr/bin/env python3
"""Read llama-agent session logs and report repeated requests. Does not edit skills."""

import argparse
import json
import os
import re
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def session_root(explicit):
    if explicit:
        return Path(explicit)
    return Path.home() / ".llama-agent" / "sessions"


def iter_jsonl(root):
    if not root.is_dir():
        return
    for path in sorted(root.rglob("*.jsonl")):
        if path.is_file():
            yield path


def message_text(message):
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "\n".join(parts)
    return ""


def normalize(text):
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def scan(root):
    prompts = Counter()
    tools = Counter()
    files = 0
    user_turns = 0
    for path in iter_jsonl(root):
        files += 1
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            message = record.get("message") if record.get("type") == "message" else record
            if not isinstance(message, dict):
                continue
            if message.get("role") == "user":
                text = normalize(message_text(message))
                if len(text) >= 20:
                    prompts[text] += 1
                    user_turns += 1
            for call in message.get("tool_calls") or []:
                if not isinstance(call, dict):
                    continue
                fn = call.get("function") if isinstance(call.get("function"), dict) else call
                name = fn.get("name") if isinstance(fn, dict) else None
                if isinstance(name, str) and name:
                    tools[name] += 1
    return {
        "files": files,
        "user_turns": user_turns,
        "prompts": prompts,
        "tools": tools,
    }


def skill_name(text):
    words = re.findall(r"[a-z0-9]+", text)[:4]
    name = "-".join(words) or "repeated-request"
    name = name.strip("-")[:40].strip("-")
    return name or "repeated-request"


def write_report(stats, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    repeated = [(text, count) for text, count in stats["prompts"].most_common() if count >= 2]
    actions = []
    for index, (text, count) in enumerate(repeated, start=1):
        actions.append({
            "id": "A%d" % index,
            "action": "propose-skill",
            "name": skill_name(text),
            "count": count,
            "evidence": text[:240],
            "apply": False,
        })
    report = [
        "# Session report",
        "",
        "files: %d" % stats["files"],
        "user_turns: %d" % stats["user_turns"],
        "",
        "## Tools",
        "",
    ]
    if stats["tools"]:
        for name, count in stats["tools"].most_common():
            report.append("- %s: %d" % (name, count))
    else:
        report.append("No tool calls recorded.")
    report.extend(["", "## Repeated requests", ""])
    if repeated:
        for text, count in repeated:
            report.append("- %d times: %s" % (count, text[:240]))
    else:
        report.append("No request was repeated often enough to propose a skill.")
    report.extend([
        "",
        "Nothing was created or deleted. Apply a proposal only after the user accepts that action id.",
        "",
    ])
    (out / "report.md").write_text("\n".join(report), encoding="utf-8")
    (out / "actions.json").write_text(json.dumps(actions, indent=2) + "\n", encoding="utf-8")
    return out


def self_test():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "sessions"
        root.mkdir()
        line = json.dumps({
            "type": "message",
            "message": {"role": "user", "content": "Please add a retry helper around the client call."},
        })
        tool = json.dumps({
            "type": "message",
            "message": {"role": "assistant", "tool_calls": [{"function": {"name": "read"}}]},
        })
        (root / "one.jsonl").write_text(line + "\n" + tool + "\n" + line + "\n", encoding="utf-8")
        stats = scan(root)
        if stats["prompts"].most_common(1)[0][1] != 2:
            raise SystemExit(stats)
        if stats["tools"]["read"] != 1:
            raise SystemExit(stats["tools"])
        out = write_report(stats, Path(tmp) / "run")
        actions = json.loads((out / "actions.json").read_text(encoding="utf-8"))
        if not actions or actions[0]["apply"] is not False:
            raise SystemExit(actions)
    print("self-test ok")


def main(argv):
    if argv == ["--self-test"]:
        self_test()
        return 0
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    root = session_root(args.sessions)
    stats = scan(root)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = Path(args.out) if args.out else Path.home() / ".llama-agent" / "learn" / "runs" / stamp
    written = write_report(stats, out)
    print("files=%d user_turns=%d" % (stats["files"], stats["user_turns"]))
    print("report=%s" % (written / "report.md"))
    print("actions=%s" % (written / "actions.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
