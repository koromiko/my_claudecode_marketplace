---
description: Open a local web UI listing resumable Claude Code sessions, grouped by project
allowed-tools:
  - Bash(*)
---

# Resumable Sessions Web UI

Launch a local web page that lists Claude Code sessions (grouped by project)
with title, last-activity, turn count, and end reason. Both currently running
(live) and ended sessions are shown. This is also what a bare `tmux-cc-attach`
(no args) opens — the interactive terminal picker has been removed.

Per-row actions:
- Live rows (green ● LIVE badge): **Go to pane** (focus the pane running the
  session), **Attach ‑CC** (tmux sessions only — `tmux -CC attach` in a new
  iTerm window), **Fork** (`claude -r <id> --fork-session` in a new iTerm
  window).
- Ended rows: **Launch** (`claude -r <id>` in a new iTerm window).
- Every row also has a **Copy** button for the equivalent command.

Filter controls: an All / Live / Ended toggle (with counts) and an "Active
within" window that defaults to 7 days. The server never deletes or modifies
session records; actions run locally via AppleScript/tmux against the
session's own pane or a fresh iTerm window.

## Instructions

Start the server (it prints a URL and opens the browser):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/tmux-cc-web.py
```

Options: `--port N` (default: a free port), `--host H` (default `127.0.0.1`),
`--no-open` (do not open a browser). Stop with Ctrl-C.

## Reporting to User

1. Print the served URL.
2. Note the server binds to loopback and validates every action against the
   current session list; Go to pane / Attach ‑CC / Fork / Launch act
   immediately — Copy is the only button that just puts a command on the
   clipboard.
3. Remind them to stop it with Ctrl-C when done.
