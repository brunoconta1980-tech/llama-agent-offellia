---
name: create-skill
description: Create a llama-agent skill directory with SKILL.md and optional scripts. Use when the user wants a new skill or says /create-skill. Project skills go in .llama-agent/skills/<name>/ and user skills go in ~/.llama-agent/skills/<name>/. Run scripts/validate_skill.py before finishing.
license: MIT
compatibility: python3
allowed-tools: bash read write edit glob
---

# Create a skill

Ask one question at a time for anything the user has not already said.

1. Name. Lowercase letters, digits, and single hyphens. It must start and end with a letter or digit and be 1 to 64 characters. The directory name and the `name` field are the same string.
2. Scope. Inside a git repo, default to `<repo>/.llama-agent/skills/<name>/`. Otherwise use `~/.llama-agent/skills/<name>/`. A project skill overrides a shipped skill of the same name.
3. The task the skill performs and the phrases that should select it.

Write `SKILL.md` in this shape. The `description` value is one physical line, at most 1024 characters, and includes what the skill does and the phrases that should select it.

```markdown
---
name: <name>
description: <what it does and when to use it>
allowed-tools: bash read write edit glob
---

# <title>

Steps the agent follows. Point at scripts/<file> for mechanical work.
```

Put helper programs in `<skill>/scripts/` as regular non-hidden files. A script must do the work, not print a fake result. Read `skill-design-principles` before editing the body when that skill is available.

Then run:

```bash
python3 <skill_dir>/scripts/validate_skill.py <new-skill-directory>
```

`<skill_dir>` is the directory that contains this file. Fix every line the validator prints. Tell the user the path and that the skill is picked up on the next agent start, or immediately if it is already on a discovery path.
