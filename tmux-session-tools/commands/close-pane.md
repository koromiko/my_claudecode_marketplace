---
description: Close a tmux pane by name or ID
argument-hint: <pane-name>
---

Use the Task tool to spawn the `close-pane-agent` subagent from this plugin.

Pass these values to the agent in the prompt:
- Plugin root path: `${CLAUDE_PLUGIN_ROOT}`
- Pane name or ID: `$1` (if provided)

The agent will:
1. Check tmux environment
2. If no pane specified, list panes and ask user to select
3. Resolve pane name to ID
4. Close the pane
5. Confirm closure
