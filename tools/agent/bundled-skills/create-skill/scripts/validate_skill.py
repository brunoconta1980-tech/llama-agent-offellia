#!/usr/bin/env python3
"""Validate a llama-agent skill directory against the on-disk parser rules."""

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path


NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_name(name):
    if not name or len(name) > 64:
        return "name must be 1-64 characters"
    if not NAME_RE.fullmatch(name):
        return "name must be lowercase letters, digits, and single hyphens"
    return None


def parse_frontmatter(text):
    if not text.startswith("---"):
        return None, "SKILL.md must start with ---"
    end = text.find("\n---", 3)
    if end < 0:
        return None, "frontmatter is missing the closing --- line"
    fields = {}
    for line in text[3:end].splitlines():
        stripped = line.strip()
        if not stripped or stripped == "metadata:" or line[:1] in (" ", "\t"):
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        fields[key.strip()] = value
    return fields, None


def validate_dir(skill_dir):
    root = Path(skill_dir)
    errors = []
    skill_md = root / "SKILL.md"
    if not skill_md.is_file():
        return ["SKILL.md is missing"]
    text = skill_md.read_text(encoding="utf-8")
    fields, err = parse_frontmatter(text)
    if err:
        return [err]
    name = fields.get("name", "")
    description = fields.get("description", "")
    name_err = validate_name(name)
    if name_err:
        errors.append(name_err)
    if root.name != name:
        errors.append("directory name %r does not match name %r" % (root.name, name))
    if not description:
        errors.append("description is empty")
    elif description in {">", ">", "|"}:
        errors.append("description must be one physical line, not a YAML block scalar")
    elif len(description) > 1024:
        errors.append("description is longer than 1024 characters")
    body = text.split("\n---", 1)[-1]
    if not body.strip():
        errors.append("SKILL.md has no body")
    scripts = root / "scripts"
    if scripts.exists():
        if not scripts.is_dir():
            errors.append("scripts is not a directory")
        else:
            for entry in sorted(scripts.iterdir()):
                if entry.name.startswith("."):
                    continue
                if not entry.is_file():
                    errors.append("scripts/%s is not a regular file" % entry.name)
                elif entry.stat().st_size == 0:
                    errors.append("scripts/%s is empty" % entry.name)
    return errors


def self_test():
    with tempfile.TemporaryDirectory() as tmp:
        good = Path(tmp) / "demo-skill"
        (good / "scripts").mkdir(parents=True)
        (good / "SKILL.md").write_text(
            "---\nname: demo-skill\ndescription: Demo skill for the validator.\n---\n\n# Demo\n\nRun the script.\n",
            encoding="utf-8",
        )
        (good / "scripts" / "run.py").write_text("print('ok')\n", encoding="utf-8")
        if validate_dir(good):
            raise SystemExit("valid skill was rejected: %s" % validate_dir(good))
        bad = Path(tmp) / "other"
        bad.mkdir()
        (bad / "SKILL.md").write_text("---\nname: demo-skill\ndescription: >\n---\n\nbody\n", encoding="utf-8")
        errors = validate_dir(bad)
        if not errors:
            raise SystemExit("invalid skill was accepted")
    print("self-test ok")


def main(argv):
    if argv == ["--self-test"]:
        self_test()
        return 0
    parser = argparse.ArgumentParser()
    parser.add_argument("skill_dir")
    args = parser.parse_args(argv)
    errors = validate_dir(args.skill_dir)
    if errors:
        for item in errors:
            print(item, file=sys.stderr)
        return 1
    print("valid: %s" % os.path.abspath(args.skill_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
