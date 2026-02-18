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
5. Register the forked session and return a managed ID

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/fork-iterm.sh "$(pwd)"
```

The script outputs a managed ID (e.g., `sm-abc123`) on the last line of stdout.

## Reporting to User

After running the script:
1. Report if the fork was successful and the new pane/tab was opened
2. **Important**: Tell the user the managed ID that was returned
3. Explain they can use this ID with session-manager commands:
   - `session-manager.sh capture <id>` - Capture output from the forked session
   - `session-manager.sh send <id> <command>` - Send a command to the forked session
   - `session-manager.sh status <id>` - Check if the session is still active
   - `session-manager.sh list` - List all managed sessions
