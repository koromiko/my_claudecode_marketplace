---
description: List all tmux panes with their Claude names
argument-hint:
---

Use the Task tool to spawn the `list-panes-agent` subagent from this plugin.

Pass these values to the agent in the prompt:
- Plugin root path: `${CLAUDE_PLUGIN_ROOT}`

The agent will:
1. Check tmux environment
2. Run the list-named-panes.sh script
3. Format and display pane info in a readable table
