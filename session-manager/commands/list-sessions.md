---
description: List all managed terminal sessions (tmux panes and iTerm tabs) with their status
allowed-tools:
  - Bash(*)
---

# List Managed Sessions

List all terminal sessions tracked by session-manager, showing their status (active or stale) and details.

## Instructions

Run the session-manager script with the `list` subcommand and `--auto-cleanup` to automatically remove stale entries:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/session-manager.sh list --auto-cleanup
```

## Reporting to User

After running the script:
1. Present the table of managed sessions, formatted for readability
2. Explain the columns:
   - **Managed ID**: The `sm-XXXXXX` identifier used with other session-manager commands
   - **Tmux Pane / iTerm Session**: The underlying terminal identifier
   - **Status**: Whether the session is `active` (still running) or was cleaned up as stale
   - **Command**: The command that was run in the session (if available)
   - **Working Dir**: The directory the session was started in (if available)
3. If no sessions are listed, let the user know there are no active managed sessions
4. Remind the user they can interact with active sessions using:
   - `session-manager.sh capture <id>` - Capture output
   - `session-manager.sh send <id> <command>` - Send a command
   - `session-manager.sh status <id>` - Check status
