---
description: Fork the current Claude Code session into a new tmux pane or iTerm tab
allowed-tools:
  - Bash(*)
---

# Fork Session

Fork the current session into a new tmux pane (if in tmux) or iTerm tab, allowing parallel work on the same context.

## Instructions

Run the fork script, passing the current working directory. The script will:
1. Detect if running inside tmux (uses tmux pane) or iTerm (uses new tab)
2. Find the Claude sessions directory for this project
3. Detect the most recently modified session (the current one)
4. Open a new tmux pane or iTerm tab and fork into that session
5. **Verify the forked Claude session actually started** in the target pane/tab before reporting success
6. Register the forked session and return a managed ID

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/fork-iterm.sh "$(pwd)"
```

The script verifies the new pane/tab before it succeeds: for tmux it polls the target
pane (up to ~10s) until `claude` takes over the foreground process and scans the pane
buffer for failure markers; for iTerm it scans the new tab's visible contents (best
effort). It only prints a managed ID (e.g., `sm-abc123`) on the last line of stdout
**after** the session is confirmed up. On verification failure the script exits non-zero,
prints the captured pane/tab output, and does NOT register the session.

## Reporting to User

**Base your report on the script's exit code, not just on the pane/tab opening.**

- **Exit code 0 with a managed ID on stdout** — the fork was verified. Report success and:
  1. **Important**: Tell the user the managed ID that was returned
  2. If stderr contained a `Warning:` line (iTerm could not positively confirm the
     Claude TUI), pass that caveat along — the tab opened but verification was
     best-effort, so ask them to glance at the new tab.
  3. Explain they can use this ID with session-manager commands:
     - `session-manager.sh capture <id>` - Capture output from the forked session
     - `session-manager.sh send <id> <command>` - Send a command to the forked session
     - `session-manager.sh status <id>` - Check if the session is still active
     - `session-manager.sh list` - List all managed sessions
- **Non-zero exit code** — the fork did NOT start (e.g., `claude` not on PATH, invalid
  session, resume error). Do **not** report success or invent a managed ID. Surface the
  captured pane/tab output the script printed and explain what failed so the user can fix
  it (the orphan pane/tab was left open for inspection and was not registered).
