---
name: design
description: Write a design document, review it, and revise until scripts/check_design.py and scripts/check_review.py report zero open issues. Use for design, a design doc, system design, an architecture doc, a technical spec, or /design. The document includes Key Decisions, Open Questions, and a PR Plan.
license: MIT
compatibility: python3
allowed-tools: bash read write edit glob
---

# Design

Write the document yourself, then review it yourself in a second pass. Keep both in files so the checks can see them.

1. Write `<path>.md`. If the user gave no path, use `design/<short-name>.md` in the working directory. Include the problem, the design, alternatives you rejected, and these three sections exactly:

```markdown
## Key Decisions

- Decision: reason.

## Open Questions

None.

## PR Plan

### PR 1: Title
- Files: path/a, path/b
- Dependencies: None
- Description: What this change does.

### PR 2: Title
- Files: path/c
- Dependencies: PR 1
- Description: What this change does.
```

Dependencies are `None` or `PR` numbers that exist. The graph must have no cycles. Each PR is one reviewable change.

2. Run `<skill_dir>/scripts/check_design.py <path>.md` and fix every error. `<skill_dir>` is the directory that contains this file.

3. Write `<path>.review.md`. For each issue:

```markdown
### Issue 1
- Severity: major
- Section: PR Plan
- Description: What is wrong.
- Suggestion: What to change.
- Status: open
```

If you find nothing, the file is a single line: `No open issues.`

4. Run `<skill_dir>/scripts/check_review.py <path>.review.md`. While it prints `open=` greater than 0, edit the design, set each handled issue to `Status: addressed` with a `Response` line, and review again. A real disagreement stays `Status: needs-user-input`. Ask the user that question and treat the answer as final.

5. Stop when `check_review.py` exits 0. Show the path, the key decisions, any open questions, and the PR order. Do not upload the document.
