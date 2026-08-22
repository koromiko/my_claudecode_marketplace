---
description: Open a local web UI listing resumable Claude Code sessions, grouped by project
allowed-tools:
  - Bash(*)
---

# Resumable Sessions Web UI

Launch a local web page that lists Claude Code sessions (grouped by project)
with title, last-activity, turn count, and end reason. Both currently running
(live) and ended sessions are shown:

- Ended rows have a single Resume button copying `cd <cwd> && claude -r <id>`.
- Live rows are marked with a green ● LIVE badge and offer two buttons — Fork
  (`… claude -r <id> --fork-session`) and Resume (`… claude -r <id>`).

Filter controls: an All / Live / Ended toggle (with counts) and an "Active
within" window that defaults to 7 days. The view is read-only — it never
deletes or modifies any session record.

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
