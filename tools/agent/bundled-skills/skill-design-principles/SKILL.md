---
name: skill-design-principles
description: Rules for writing or editing a skill. One home per fact, no empty guardrails, no one-off patches. Use whenever authoring or editing a SKILL.md. Run scripts/check_skill_text.py on the file before saving it.
license: MIT
compatibility: python3
allowed-tools: bash read write edit glob
---

# Skill design

Apply these rules when writing a skill and when editing one. Check the diff against them before finishing. Do not refactor unrelated parts of a skill the user did not ask to change. If you see a cleanup, do the requested edit first and then mention the cleanup.

## One home per fact

Keep each rule, value, and list in one place. Other text points at that place. If the fact already exists, do not copy it into a second section.

## No empty lines

If a sentence does not change what the agent does, delete it. Replacing "do X" with "do Y" does not also need "do not do X" when Y is already clear.

## Fix the class of problem

When one example fails, change the place that owns the fact so the whole class is handled. Do not add a special case that only names the example you just saw. Stay precise. Do not widen the rule past the cases that are actually the same.

## Check

Run this on the SKILL.md you changed. `<skill_dir>` is the directory that contains this file.

```bash
python3 <skill_dir>/scripts/check_skill_text.py <path-to-SKILL.md>
```

The description in the frontmatter is one line. The `name` matches the directory. The body is the procedure, not a stub.
