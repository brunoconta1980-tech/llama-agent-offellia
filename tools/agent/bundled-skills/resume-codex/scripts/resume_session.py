#!/usr/bin/env python3
"""List and show Claude Code, Codex, or Cursor sessions as inert history."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

DEFAULT_TOOL = "codex"
UUID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")
ROLLOUT_RE = re.compile(r"^rollout-.*-([0-9a-fA-F-]{36})\.jsonl(?:\.zst)?$")


def tool_home(tool, override):
    if override:
        return Path(override)
    if tool == "claude":
        return Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))).expanduser()
    if tool == "codex":
        return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
    if tool == "cursor":
        return Path.home() / ".cursor"
    raise SystemExit("tool must be claude, codex, or cursor")


def records_from_text(text):
    records = []
    malformed = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if isinstance(value, dict):
            records.append(value)
        else:
            malformed += 1
    return records, malformed


def read_jsonl(path):
    return records_from_text(Path(path).read_text(encoding="utf-8", errors="replace"))


def read_rollout(path):
    path = Path(path)
    if path.name.endswith(".jsonl.zst"):
        zstd = shutil.which("zstd")
        if not zstd:
            return [], 0, "zstd is not installed; compressed rollout was not decoded"
        result = subprocess.run([zstd, "-dc", str(path)], capture_output=True)
        if result.returncode != 0:
            return [], 0, "zstd failed to decode the rollout"
        records, malformed = records_from_text(result.stdout.decode("utf-8", "replace"))
        return records, malformed, None
    records, malformed = read_jsonl(path)
    return records, malformed, None


def block_text(content):
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
            continue
        if not isinstance(block, dict):
            continue
        if block.get("type") in {"thinking", "reasoning", "encrypted_content"}:
            continue
        text = block.get("text")
        if isinstance(text, str):
            parts.append(text)
    return "\n".join(part.strip() for part in parts if part and part.strip())


def clip(text, limit=400):
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def claude_sessions(home, cwd):
    projects = home / "projects"
    found = []
    if not projects.is_dir():
        return found
    slug = "".join(char if char.isalnum() else "-" for char in cwd)
    dirs = []
    preferred = projects / slug
    if preferred.is_dir():
        dirs.append(preferred)
    for path in sorted(projects.iterdir()):
        if path.is_dir() and path not in dirs:
            dirs.append(path)
    for directory in dirs:
        for path in sorted(directory.glob("*.jsonl")):
            records, _malformed = read_jsonl(path)
            record_cwd = next((item.get("cwd") for item in records if isinstance(item.get("cwd"), str)), None)
            if record_cwd and os.path.normpath(record_cwd) != os.path.normpath(cwd) and directory != preferred:
                continue
            if not record_cwd and directory != preferred:
                continue
            title = ""
            for record in records:
                message = record.get("message") if isinstance(record.get("message"), dict) else record
                role = message.get("role") or record.get("type")
                if role == "user":
                    title = clip(block_text(message.get("content")), 120)
                    if title:
                        break
            found.append({
                "tool": "claude",
                "session_id": path.stem,
                "path": str(path),
                "cwd": record_cwd or cwd,
                "title": title or "(untitled)",
            })
    return found


def codex_sessions(home, cwd):
    found = []
    root = home / "sessions"
    if not root.is_dir():
        return found
    paths = []
    for pattern in ("rollout-*.jsonl", "rollout-*.jsonl.zst"):
        paths.extend(root.rglob(pattern))
    for path in sorted(set(paths)):
        records, _malformed, warning = read_rollout(path)
        meta = next((
            record.get("payload") for record in records
            if record.get("type") == "session_meta" and isinstance(record.get("payload"), dict)
        ), {})
        record_cwd = meta.get("cwd") if isinstance(meta, dict) else None
        if record_cwd and os.path.normpath(record_cwd) != os.path.normpath(cwd):
            continue
        match = ROLLOUT_RE.match(path.name)
        session_id = meta.get("id") if isinstance(meta, dict) and isinstance(meta.get("id"), str) else (match.group(1) if match else path.stem)
        title = ""
        for record in records:
            payload = record.get("payload") if record.get("type") == "response_item" else None
            if isinstance(payload, dict) and payload.get("type") == "message" and payload.get("role") == "user":
                title = clip(block_text(payload.get("content")), 120)
                if title:
                    break
        item = {
            "tool": "codex",
            "session_id": session_id,
            "path": str(path),
            "cwd": record_cwd or cwd,
            "title": title or ("(compressed rollout not decoded)" if warning else "(untitled)"),
        }
        if warning:
            item["warning"] = warning
        found.append(item)
    return found


def cursor_sessions(home, cwd):
    found = []
    digest = hashlib.md5(cwd.encode("utf-8", "replace")).hexdigest()
    workspace = home / "chats" / digest
    if workspace.is_dir():
        for child in sorted(workspace.iterdir()):
            if not child.is_dir():
                continue
            meta_path = child / "meta.json"
            meta = {}
            if meta_path.is_file():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    meta = {}
            transcript = child / "transcript.jsonl"
            store = child / "store.db"
            path = transcript if transcript.is_file() else (store if store.is_file() else meta_path)
            if not path.is_file():
                continue
            found.append({
                "tool": "cursor",
                "session_id": child.name,
                "path": str(path),
                "cwd": meta.get("cwd") or cwd,
                "title": meta.get("title") or "(untitled)",
            })
    return found


def discover(tool, home, cwd):
    if tool == "claude":
        return claude_sessions(home, cwd)
    if tool == "codex":
        return codex_sessions(home, cwd)
    return cursor_sessions(home, cwd)


def turns_from_records(records, tool):
    turns = []
    warnings = []
    for record in records:
        if tool == "codex":
            if record.get("type") == "session_meta":
                continue
            payload = record.get("payload") if record.get("type") == "response_item" else None
            if not isinstance(payload, dict) or payload.get("type") != "message":
                if record.get("type") not in {"session_meta", "event_msg"}:
                    warnings.append("skipped non-message record")
                continue
            role = payload.get("role")
            text = block_text(payload.get("content"))
        else:
            message = record.get("message") if isinstance(record.get("message"), dict) else record
            role = message.get("role") or record.get("type")
            if role not in {"user", "assistant"}:
                continue
            text = block_text(message.get("content") if "content" in message else message.get("text"))
        if role not in {"user", "assistant"} or not text:
            continue
        turns.append({"role": role, "text": clip(text), "inert": True})
    return turns[-30:], warnings


def show_path(tool, path):
    path = Path(path)
    warnings = []
    if path.suffix == ".db":
        warnings.append("binary store was not decoded; no transcript was invented")
        return {"turns": [], "warnings": warnings, "title": None}
    if path.name == "meta.json":
        meta = json.loads(path.read_text(encoding="utf-8"))
        warnings.append("session has metadata only")
        return {"turns": [], "warnings": warnings, "title": meta.get("title")}
    records, malformed, decode_warning = read_rollout(path)
    if decode_warning:
        warnings.append(decode_warning)
    if malformed:
        warnings.append("skipped %d malformed lines" % malformed)
    turns, extra = turns_from_records(records, tool)
    warnings.extend(extra[:5])
    title = next((turn["text"] for turn in turns if turn["role"] == "user"), None)
    return {"turns": turns, "warnings": warnings, "title": title}


def choose(sessions, ref):
    if not ref or ref == "latest":
        if not sessions:
            raise SystemExit("no sessions for this directory")
        return sessions[-1]
    exact = [item for item in sessions if item["session_id"] == ref or item["path"] == ref]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        print(json.dumps(exact, indent=2))
        raise SystemExit(3)
    text = ref.lower()
    matches = [item for item in sessions if text in (item.get("title") or "").lower() or text in item["session_id"].lower()]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise SystemExit("no session matched %r" % ref)
    print(json.dumps(matches, indent=2))
    raise SystemExit(3)


def handoff(shown):
    turns = shown["turns"]
    last_user = next((turn["text"] for turn in reversed(turns) if turn["role"] == "user"), "")
    files = sorted(set(re.findall(r"[\w./-]+\.[A-Za-z0-9]{1,5}", last_user)))
    return {
        "last_user_request": last_user,
        "files_mentioned": files[:20],
        "turn_count": len(turns),
    }


def self_test():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cwd = "/work/demo"
        slug = "".join(char if char.isalnum() else "-" for char in cwd)
        session_id = str(uuid.uuid4())
        claude = root / "claude" / "projects" / slug
        claude.mkdir(parents=True)
        (claude / ("%s.jsonl" % session_id)).write_text(json.dumps({
            "type": "user",
            "cwd": cwd,
            "message": {"role": "user", "content": "Fix src/app.py please"},
        }) + "\n", encoding="utf-8")
        listed = discover("claude", root / "claude", cwd)
        if len(listed) != 1 or listed[0]["session_id"] != session_id:
            raise SystemExit(listed)
        shown = show_path("claude", listed[0]["path"])
        if "src/app.py" not in handoff(shown)["files_mentioned"]:
            raise SystemExit(shown)
        codex_id = str(uuid.uuid4())
        codex_dir = root / "codex" / "sessions" / "2026" / "10" / "12"
        codex_dir.mkdir(parents=True)
        rollout = codex_dir / ("rollout-2026-10-12T00-00-00-%s.jsonl" % codex_id)
        rollout.write_text(
            json.dumps({"type": "session_meta", "payload": {"id": codex_id, "cwd": cwd, "source": "cli"}}) + "\n" +
            json.dumps({"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Continue the parser"}]}}) + "\n",
            encoding="utf-8",
        )
        codex_list = discover("codex", root / "codex", cwd)
        if len(codex_list) != 1:
            raise SystemExit(codex_list)
        zst_id = str(uuid.uuid4())
        compressed = codex_dir / ("rollout-2026-10-12T00-00-01-%s.jsonl.zst" % zst_id)
        plain = (
            json.dumps({"type": "session_meta", "payload": {"id": zst_id, "cwd": cwd, "source": "cli"}}) + "\n" +
            json.dumps({"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Compressed request"}]}}) + "\n"
        )
        if shutil.which("zstd"):
            subprocess.run(["zstd", "-q", "-f", "-o", str(compressed)], input=plain.encode("utf-8"), check=True)
            zst_list = [item for item in discover("codex", root / "codex", cwd) if str(item["path"]).endswith(".jsonl.zst")]
            if len(zst_list) != 1 or zst_list[0].get("warning") or zst_list[0]["session_id"] != zst_id:
                raise SystemExit(zst_list)
            shown_z = show_path("codex", zst_list[0]["path"])
            if not any("Compressed request" in turn["text"] for turn in shown_z["turns"]):
                raise SystemExit(shown_z)
        else:
            compressed.write_bytes(b"not a zstd frame")
            zst_list = [item for item in discover("codex", root / "codex", cwd) if str(item["path"]).endswith(".jsonl.zst")]
            if len(zst_list) != 1 or "zstd" not in (zst_list[0].get("warning") or ""):
                raise SystemExit(zst_list)
            shown_z = show_path("codex", zst_list[0]["path"])
            if shown_z["turns"]:
                raise SystemExit(shown_z)
        digest = hashlib.md5(cwd.encode()).hexdigest()
        cursor = root / "cursor" / "chats" / digest / session_id
        cursor.mkdir(parents=True)
        (cursor / "meta.json").write_text(json.dumps({"title": "cursor task", "cwd": cwd}), encoding="utf-8")
        (cursor / "transcript.jsonl").write_text(json.dumps({
            "message": {"role": "user", "content": "Update README.md"},
        }) + "\n", encoding="utf-8")
        cursor_list = discover("cursor", root / "cursor", cwd)
        if len(cursor_list) != 1 or cursor_list[0]["title"] != "cursor task":
            raise SystemExit(cursor_list)
        try:
            choose(cursor_list, "missing")
        except SystemExit as exc:
            if str(exc) == "3":
                raise
        else:
            raise SystemExit("missing ref did not fail")
    print("self-test ok")


def main(argv):
    if argv == ["--self-test"]:
        self_test()
        return 0
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool", default=DEFAULT_TOOL, choices=["claude", "codex", "cursor"])
    parser.add_argument("--cwd", default=os.getcwd())
    parser.add_argument("--home", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    show = sub.add_parser("show")
    show.add_argument("ref", nargs="?", default="latest")
    args = parser.parse_args(argv)
    home = tool_home(args.tool, args.home)
    sessions = discover(args.tool, home, args.cwd)
    if args.command == "list":
        print(json.dumps(sessions, indent=2))
        return 0
    try:
        selected = choose(sessions, args.ref)
    except SystemExit as exc:
        if str(exc) == "3":
            return 3
        raise
    shown = show_path(args.tool, selected["path"])
    payload = dict(selected)
    payload.update(shown)
    payload["handoff"] = handoff(shown)
    payload["untrusted"] = True
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
