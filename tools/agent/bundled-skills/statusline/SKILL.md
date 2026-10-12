---
name: statusline
description: Show the built-in llama-agent footer and render a custom status row with scripts/statusline.py. Use when the user wants a status line, footer items, or a prompt row. The footer shows cwd, session, tokens, speed, context, and model. Custom items live in ~/.llama-agent/statusline.json.
license: MIT
compatibility: python3. Optional git for the branch item.
allowed-tools: bash read write edit glob
---

# Status line

The TUI footer is part of the binary. It shows the working directory, the session file name, input and output token counts, tokens per second, context percent, and the model name. A JSON file does not change that footer.

A custom row is a separate command. Write it only after the user says what they want on it. If they have not said, show the current config and ask. Do not guess.

Config path: `~/.llama-agent/statusline.json`.

```bash
python3 <skill_dir>/scripts/statusline.py show
python3 <skill_dir>/scripts/statusline.py write --type builtin --items cwd,model,context
python3 <skill_dir>/scripts/statusline.py render
```

`<skill_dir>` is the directory that contains this file.

`items` may be `cwd`, `model`, `context`, `branch`, and `session`. Keep at least one. `render` reads a JSON object on stdin when one is piped (`cwd`, `model`, `context_used_pct`, `session`, `branch`) and otherwise uses the working directory. Missing fields are omitted.

`write --type disabled` clears the custom row. `write --type command --command "<shell command>"` runs that command. It receives the same JSON on stdin and its stdout is the row. Try the command with a sample object before saving it.

```bash
printf '%s\n' '{"cwd":"/work","model":"local","context_used_pct":12}' | python3 <skill_dir>/scripts/statusline.py render
```

Do not edit the user's shell startup file unless they ask to install the row there. When they do, add one line that runs `render`, and tell them to open a new shell.
