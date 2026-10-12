#!/usr/bin/env python3
"""Check a SKILL.md for the structural rules this agent can enforce."""

import argparse
import re
import sys
import tempfile
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
BANNED = re.compile(r"\b(TODO|FIXME|placeholder|lorem ipsum)\b", re.IGNORECASE)


def check_text(text, directory_name):
    errors = []
    if not text.startswith("---"):
        return ["SKILL.md must start with ---"]
    end = text.find("\n---", 3)
    if end < 0:
        return ["frontmatter is missing the closing --- line"]
    description = ""
    name = ""
    for line in text[3:end].splitlines():
        if line[:1] in (" ", "\t") or not line.strip() or ":" not in line:
            continue
        key, value = line.strip().split(":", 1)
        value = value.strip().strip("'").strip('"')
        if key.strip() == "name":
            name = value
        elif key.strip() == "description":
            description = value
    if not NAME_RE.fullmatch(name or ""):
        errors.append("name is missing or uses characters the parser rejects")
    if directory_name and name != directory_name:
        errors.append("name must equal the skill directory name")
    if not description or description in {">", "|"}:
        errors.append("description must be a single non-empty line")
    elif len(description) > 1024:
        errors.append("description is longer than 1024 characters")
    body = text[end + 4 :]
    if not body.strip():
        errors.append("body is empty")
    if BANNED.search(body):
        errors.append("body contains TODO, FIXME, placeholder, or lorem ipsum")
    headings = re.findall(r"^## (.+)$", body, re.MULTILINE)
    if len(headings) != len(set(headings)):
        errors.append("duplicate ## headings: keep each rule in one place")
    return errors


def self_test():
    good = "---\nname: demo\ndescription: Check skill text.\n---\n\n# Demo\n\n## One\n\nDo the work.\n"
    if check_text(good, "demo"):
        raise SystemExit(check_text(good, "demo"))
    bad = "---\nname: demo\ndescription: >\n---\n\nTODO\n"
    if not check_text(bad, "demo"):
        raise SystemExit("bad skill was accepted")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "SKILL.md"
        path.write_text(good, encoding="utf-8")
    print("self-test ok")


def main(argv):
    if argv == ["--self-test"]:
        self_test()
        return 0
    parser = argparse.ArgumentParser()
    parser.add_argument("skill_md")
    args = parser.parse_args(argv)
    path = Path(args.skill_md)
    errors = check_text(path.read_text(encoding="utf-8"), path.parent.name)
    if errors:
        for item in errors:
            print(item, file=sys.stderr)
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
