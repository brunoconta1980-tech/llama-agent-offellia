---
name: long-running-background-tasks
description: Start, watch, and stop work that keeps running after the command returns. Builds, servers, training, and watchers. Use before launching or reporting on a background job. scripts/job.py stores the pid and log and stays silent until DONE, FAILED, or ACTION_REQUIRED.
license: MIT
compatibility: python3
allowed-tools: bash read write edit glob
---

# Background jobs

Do not poll a long job by printing every few seconds. Start it, record the pid and log, and have `watch` stay quiet until the process ends.

`<skill_dir>` is the directory that contains this file. The default directory is `~/.llama-agent/jobs/<name>/`.

```bash
python3 <skill_dir>/scripts/job.py start --name build -- cmake --build build --target llama-agent
python3 <skill_dir>/scripts/job.py watch --name build --timeout 3600
python3 <skill_dir>/scripts/job.py status --name build
python3 <skill_dir>/scripts/job.py stop --name build
```

Put `--` before the command when it has its own flags.

`watch` prints one line: `DONE <name>`, `FAILED <name> exit=<code>`, or `ACTION_REQUIRED timeout...`. On failure it appends the tail of the log. Do not report success from memory. Read that line.

`status` is for a direct question about the job. It prints `running` or `exited`.

Use one job name per process. Stopping sends `SIGTERM` to the process group, then `SIGKILL` if it is still alive after a few seconds. A dev server stays in `start` and is not watched to exit. Say the pid and the log path when you leave it running.
