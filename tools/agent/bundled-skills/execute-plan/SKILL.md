---
name: execute-plan
description: Parse a design document PR Plan, order it, and implement each pull request on a local git branch. Use for execute plan, run the plan, implement the design, or /execute-plan. scripts/plan.py parses, prepares the branch, and records state. Push only when the user asks.
license: MIT
compatibility: python3 and git
allowed-tools: bash read write edit glob
---

# Execute a PR plan

You implement the plan in this working tree. Do the work in dependency order. Do not push, and do not open a remote pull request, unless the user asks.

1. Parse the design document. It must contain the `## PR Plan` section written by the design skill.

```bash
python3 <skill_dir>/scripts/plan.py parse <design.md> --out <state.json>
```

`<skill_dir>` is the directory that contains this file. For `--dry-run`, stop after this command and show the order.

2. Repeat until `next` prints `complete`:

```bash
python3 <skill_dir>/scripts/plan.py next <state.json>
python3 <skill_dir>/scripts/plan.py prepare <state.json> --checkout
```

`prepare` refuses a dirty tree. It creates `execute-plan/<plan-id>-pr-N-<slug>` and checks it out. Implement only that PR's files. Run the smallest check that applies (`python3 -m py_compile`, the project's test, or the build of the target you changed). Commit on that branch.

```bash
python3 <skill_dir>/scripts/plan.py mark <state.json> <pr-id> completed --commit <sha>
```

3. Before marking a PR completed, collect the branch diff with the review skill's `collect_diff.py` when that skill is installed, or with `git diff <base>...<branch>`. Fix defects you can reproduce. Record a failed PR as `failed` and keep going with PRs that do not depend on it.

4. When `next` prints `complete`, check out the branch saved as `original_branch` in the state file. Report each PR id, branch, and commit. A later push, if the user asks, uses `git push --force-with-lease` and only for those `execute-plan/` branches.
