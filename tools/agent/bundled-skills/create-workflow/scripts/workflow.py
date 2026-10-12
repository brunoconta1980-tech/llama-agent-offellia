#!/usr/bin/env python3
"""Check a local workflow file and walk its phases. The running model does the phase work."""

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate(doc, filename=None):
    errors = []
    name = doc.get("name")
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        errors.append("name must be lowercase letters, digits, and single hyphens")
    if filename and Path(filename).stem != name:
        errors.append("file stem must equal name")
    description = doc.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append("description is required")
    artifact = doc.get("artifact")
    if not isinstance(artifact, str) or not artifact.strip() or "/" in artifact or "\\" in artifact:
        errors.append("artifact must be a single file name")
    phases = doc.get("phases")
    if not isinstance(phases, list) or not phases:
        errors.append("phases must be a non-empty list")
    else:
        titles = []
        for index, phase in enumerate(phases, start=1):
            if not isinstance(phase, dict):
                errors.append("phase %d is not an object" % index)
                continue
            title = phase.get("title")
            prompt = phase.get("prompt")
            if not isinstance(title, str) or not title.strip():
                errors.append("phase %d needs a title" % index)
            elif title in titles:
                errors.append("duplicate phase title %s" % title)
            else:
                titles.append(title)
            if not isinstance(prompt, str) or not prompt.strip():
                errors.append("phase %d needs a prompt" % index)
    return errors


def empty_state(workflow_path):
    return {"workflow": str(Path(workflow_path).resolve()), "outputs": [], "done": False}


def cmd_check(args):
    doc = load(args.workflow)
    errors = validate(doc, args.workflow)
    if errors:
        for item in errors:
            print(item, file=sys.stderr)
        return 1
    print("ok %s phases=%d artifact=%s" % (doc["name"], len(doc["phases"]), doc["artifact"]))
    return 0


def cmd_next(args):
    doc = load(args.workflow)
    errors = validate(doc, args.workflow)
    if errors:
        for item in errors:
            print(item, file=sys.stderr)
        return 1
    state_path = Path(args.state)
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    else:
        state = empty_state(args.workflow)
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    done = state.get("outputs") or []
    if len(done) >= len(doc["phases"]):
        state["done"] = True
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        print("complete")
        print("artifact=%s" % doc["artifact"])
        return 0
    phase = doc["phases"][len(done)]
    print("phase=%d" % (len(done) + 1))
    print("title=%s" % phase["title"])
    print("--- prompt ---")
    print(phase["prompt"])
    if done:
        print("--- previous ---")
        for item in done:
            print("# %s" % item["title"])
            print(item["text"])
    return 0


def cmd_record(args):
    state_path = Path(args.state)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    text = Path(args.output).read_text(encoding="utf-8").strip()
    if not text:
        raise SystemExit("phase output is empty")
    state.setdefault("outputs", []).append({"title": args.title, "text": text})
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print("recorded %s (%d)" % (args.title, len(state["outputs"])))
    return 0


def self_test():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        workflow = root / "review-changes.json"
        workflow.write_text(json.dumps({
            "name": "review-changes",
            "description": "Review then verify.",
            "artifact": "review.md",
            "phases": [
                {"title": "Review", "prompt": "List findings."},
                {"title": "Verify", "prompt": "Check each finding."},
            ],
        }), encoding="utf-8")
        if cmd_check(argparse.Namespace(workflow=str(workflow))) != 0:
            raise SystemExit("check failed")
        state = root / "state.json"
        note = root / "out.txt"
        note.write_text("one finding\n", encoding="utf-8")
        if cmd_next(argparse.Namespace(workflow=str(workflow), state=str(state))) != 0:
            raise SystemExit("next failed")
        cmd_record(argparse.Namespace(state=str(state), title="Review", output=str(note)))
        cmd_record(argparse.Namespace(state=str(state), title="Verify", output=str(note)))
        # next after both records prints complete; capture by calling and checking state
        cmd_next(argparse.Namespace(workflow=str(workflow), state=str(state)))
        saved = json.loads(state.read_text(encoding="utf-8"))
        if not saved["done"] or len(saved["outputs"]) != 2:
            raise SystemExit(saved)
    print("self-test ok")


def main(argv):
    if argv == ["--self-test"]:
        self_test()
        return 0
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("workflow")
    nxt = sub.add_parser("next")
    nxt.add_argument("workflow")
    nxt.add_argument("--state", required=True)
    record = sub.add_parser("record")
    record.add_argument("--state", required=True)
    record.add_argument("--title", required=True)
    record.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if args.command == "check":
        return cmd_check(args)
    if args.command == "next":
        return cmd_next(args)
    return cmd_record(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
