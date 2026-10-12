---
name: review
description: Review the working tree, the last commit, or a branch and write findings that cite the diff. Use for review, code review, review my changes, or /review. scripts/collect_diff.py gathers the diff and scripts/check_findings.py checks the write-up.
license: MIT
compatibility: python3 and git
allowed-tools: bash read write edit glob
---

# Review

Read the diff the script collected. Do not review from memory.

```bash
python3 <skill_dir>/scripts/collect_diff.py --repo . --out /tmp/review-packet.md
```

`<skill_dir>` is the directory that contains this file.

- A dirty tree reviews `git diff HEAD` plus untracked files.
- A clean tree reviews the last commit.
- `review the branch` uses `--base <branch>` (`git diff <base>...HEAD`).

Read the packet. Open the cited files with `read` when the hunk is not enough. Write `review.md`:

```markdown
### Issue 1
- Severity: bug
- File: src/app.py:40
- Description: What breaks.
- Suggestion: What to change.
```

Severity is `bug`, `suggestion`, or `nit`. `File` is a path that appears in the packet, plus a line when you have one. If the change is sound, write exactly `No issues found.`

```bash
python3 <skill_dir>/scripts/check_findings.py review.md /tmp/review-packet.md
```

Fix any check error. Lead the reply with the bugs. Include the file and line. Do not post the review to a forge unless the user asks.
