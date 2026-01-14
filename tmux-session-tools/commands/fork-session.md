---
description: Fork a Claude Code session into a new tmux window
argument-hint: [optional-window-name]
---

Use the Task tool to spawn the `fork-session-agent` subagent from this plugin.

Pass these values to the agent in the prompt:
- Plugin root path: `${CLAUDE_PLUGIN_ROOT}`
- Window name argument (if provided): `$1`

The agent will:
1. Check tmux environment
2. List recent sessions for this project
3. Let user select which session to fork
4. Create new tmux window with forked session
