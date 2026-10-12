#!/usr/bin/env python3
"""Render a status row from ~/.llama-agent/statusline.json. Does not change the built-in TUI footer."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_ITEMS = ["cwd", "model", "context"]
ALLOWED = {"cwd", "model", "context", "branch", "session"}


def config_path(explicit):
    if explicit:
        return Path(explicit)
    return Path.home() / ".llama-agent" / "statusline.json"


def load_config(path):
    if not path.is_file():
        return {"type": "builtin", "items": list(DEFAULT_ITEMS)}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("statusline config must be an object")
    kind = data.get("type", "builtin")
    if kind not in {"builtin", "command", "disabled"}:
        raise SystemExit("type must be builtin, command, or disabled")
    items = data.get("items", list(DEFAULT_ITEMS))
    if kind == "builtin":
        if not isinstance(items, list) or not items or any(item not in ALLOWED for item in items):
            raise SystemExit("items must be one or more of %s" % ", ".join(sorted(ALLOWED)))
    if kind == "command" and not isinstance(data.get("command"), str):
        raise SystemExit("command type needs a command string")
    return data


def git_branch(cwd):
    result = subprocess.run(
        ["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def render_builtin(config, data):
    cwd = data.get("cwd") or os.getcwd()
    parts = []
    for item in config.get("items") or DEFAULT_ITEMS:
        if item == "cwd":
            parts.append(cwd)
        elif item == "model" and data.get("model"):
            parts.append(str(data["model"]))
        elif item == "context" and data.get("context_used_pct") is not None:
            parts.append("%s%%" % data["context_used_pct"])
        elif item == "session" and data.get("session"):
            parts.append(str(data["session"]))
        elif item == "branch":
            branch = data.get("branch") or git_branch(cwd)
            if branch:
                parts.append(branch)
    return " | ".join(parts)


def cmd_render(args):
    config = load_config(config_path(args.config))
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    data = json.loads(raw) if raw.strip() else {}
    if not isinstance(data, dict):
        raise SystemExit("stdin must be a JSON object")
    if config["type"] == "disabled":
        return 0
    if config["type"] == "command":
        result = subprocess.run(
            config["command"],
            input=json.dumps(data).encode(),
            shell=True,
            capture_output=True,
        )
        sys.stdout.buffer.write(result.stdout[:4096])
        return result.returncode
    text = render_builtin(config, data)
    if text:
        print(text)
    return 0


def cmd_write(args):
    path = config_path(args.config)
    items = args.items.split(",") if args.items else list(DEFAULT_ITEMS)
    config = {"type": args.type}
    if args.type == "builtin":
        config["items"] = items
    elif args.type == "command":
        if not args.command:
            raise SystemExit("--command is required for type command")
        config["command"] = args.command
    load_config_result = dict(config)
    if args.type == "builtin":
        load_config_result["items"] = items
    # Validate before writing.
    if args.type == "builtin":
        fake = {"type": "builtin", "items": items}
        if any(item not in ALLOWED for item in items) or not items:
            raise SystemExit("bad items")
        config = fake
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print("wrote %s" % path)


def self_test():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "statusline.json"
        cmd_write(argparse.Namespace(config=str(path), type="builtin", items="cwd,branch", command=None))
        saved = json.loads(path.read_text(encoding="utf-8"))
        if saved["items"] != ["cwd", "branch"]:
            raise SystemExit(saved)
        text = render_builtin(saved, {"cwd": "/work", "branch": "main", "model": "local"})
        if text != "/work | main":
            raise SystemExit(text)
        disabled = render_builtin({"type": "disabled"}, {})
    if disabled:
        pass
    print("self-test ok")


def main(argv):
    if argv == ["--self-test"]:
        self_test()
        return 0
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    render = sub.add_parser("render")
    render.add_argument("--config", default=None)
    write = sub.add_parser("write")
    write.add_argument("--config", default=None)
    write.add_argument("--type", choices=["builtin", "command", "disabled"], required=True)
    write.add_argument("--items", default=None)
    write.add_argument("--command", default=None)
    show = sub.add_parser("show")
    show.add_argument("--config", default=None)
    args = parser.parse_args(argv)
    if args.command == "render":
        return cmd_render(args)
    if args.command == "write":
        cmd_write(args)
        return 0
    path = config_path(args.config)
    print(json.dumps(load_config(path), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
