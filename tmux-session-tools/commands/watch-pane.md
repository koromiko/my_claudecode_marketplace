---
description: Start watching a pane and inject its output as context periodically
argument-hint: <pane-name> [interval-seconds]
---

Use the Task tool to spawn the `watch-pane-agent` subagent from this plugin.

Pass these values to the agent in the prompt:
- Plugin root path: `${CLAUDE_PLUGIN_ROOT}`
- Pane name or ID: `$1`
- Interval in seconds: `$2` (optional, default 30)
- Session ID: `${CLAUDE_SESSION_ID}`

The agent will:
1. Check tmux environment
2. Resolve pane name to validate it exists
3. Write watch config to ~/.claude/tmux-watch-{session_id}.json
4. Confirm watch started
