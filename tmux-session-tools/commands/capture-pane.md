---
description: Capture output from a named tmux pane
argument-hint: <pane-name> [lines]
---

Use the Task tool to spawn the `capture-pane-agent` subagent from this plugin.

Pass these values to the agent in the prompt:
- Plugin root path: `${CLAUDE_PLUGIN_ROOT}`
- Pane name or ID: `$1`
- Number of lines to capture: `$2` (optional, default 100)

The agent will:
1. Check tmux environment
2. Resolve pane name to ID
3. Capture pane content
4. Return captured output to the conversation
