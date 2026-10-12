---
name: create-workflow
description: Author a multi-phase workflow as JSON and walk it with scripts/workflow.py. Use when the user wants a workflow, a pipeline, or /create-workflow. The running model performs each phase. The script checks the file, prints the next prompt, and records outputs.
license: MIT
compatibility: python3
allowed-tools: bash read write edit glob
---

# Workflows

A workflow is a JSON file this agent executes one phase at a time. There is no separate workflow runtime. You are the model that does each phase.

## File

Ask what the workflow should produce, which phases run in order, and what each phase must read. Default the path to `<repo>/.llama-agent/workflows/<name>.json` inside a git repo, otherwise `~/.llama-agent/workflows/<name>.json`.

```json
{
  "name": "review-changes",
  "description": "Review a diff and then check each finding.",
  "artifact": "review.md",
  "phases": [
    {"title": "Review", "prompt": "Read the diff and list concrete findings."},
    {"title": "Verify", "prompt": "Check each finding against the file contents."}
  ]
}
```

`name` is lowercase letters, digits, and single hyphens, and it matches the file stem. `artifact` is a single file name. Every phase has its own title and a prompt that says which files to read.

## Run

`<skill_dir>` is the directory that contains this file.

```bash
python3 <skill_dir>/scripts/workflow.py check <workflow.json>
python3 <skill_dir>/scripts/workflow.py next <workflow.json> --state <state.json>
```

Follow the printed prompt. Write that phase's result to a file with the `write` tool. Then:

```bash
python3 <skill_dir>/scripts/workflow.py record --state <state.json> --title "<title>" --output <phase.txt>
```

Call `next` again until it prints `complete`. Write the artifact from the recorded phase texts. Do not mark a phase done without a non-empty output file.
