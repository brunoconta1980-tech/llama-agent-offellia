---
name: learn
description: Read ~/.llama-agent/sessions JSONL logs, find repeated requests, and propose skill changes. Use for /learn or learning from sessions. scripts/collect_sessions.py writes the report. Edit or add a skill only after the user accepts that action.
license: MIT
compatibility: python3
allowed-tools: bash read write edit glob
---

# Learn from sessions

Sessions are append-only JSONL files under `~/.llama-agent/sessions/`, grouped by working directory. This skill reads them and writes a report. It does not change skills by itself.

```bash
python3 <skill_dir>/scripts/collect_sessions.py
```

`<skill_dir>` is the directory that contains this file. The command prints `report=` and `actions=`. Read `report.md`. Tell the user how many session files and user turns were kept, which tools were called, and the repeated requests. Keep it short.

`actions.json` lists proposals. `apply` is false. A proposal becomes a skill only when the user names that action id.

- Adding a skill follows the create-skill skill and the skill-design-principles skill. Put it in `~/.llama-agent/skills/<name>/` or the project `.llama-agent/skills/<name>/`.
- Editing a shipped skill under the binary's `skills/` directory is overwritten on the next build. Write the replacement in the user or project skills directory so it wins on the next start.
- Do not delete a skill because one report shows zero uses. Say that the window is too small.

If there are no session files, say so and stop. Do not invent repeated phrases.
