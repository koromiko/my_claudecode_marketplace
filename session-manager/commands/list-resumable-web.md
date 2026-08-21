---
description: Open a local web UI listing resumable Claude Code sessions, grouped by project
allowed-tools:
  - Bash(*)
---

# Resumable Sessions Web UI

Launch a local web page that lists resumable Claude Code sessions (grouped by
project) with title, last-activity, turn count, and end reason. Each row has a
Copy button that puts `cd <cwd> && claude -r <id>` on the clipboard.

## Instructions

Start the server (it prints a URL and opens the browser):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/tmux-cc-web.py
```

Options: `--port N` (default: a free port), `--host H` (default `127.0.0.1`),
`--no-open` (do not open a browser). Stop with Ctrl-C.

## Reporting to User

1. Print the served URL.
2. Note the server is read-only and binds to loopback; clicking Copy does not
   resume anything — paste the copied command into a terminal to resume.
3. Remind them to stop it with Ctrl-C when done.
