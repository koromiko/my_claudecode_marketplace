---
description: Split current pane and run a command in the new pane with an auto-assigned name
argument-hint: <name> <command...>
---

Use the Task tool to spawn the `split-run-agent` subagent from this plugin.

Pass these values to the agent in the prompt:
- Plugin root path: `${CLAUDE_PLUGIN_ROOT}`
- Pane name: `$1`
- Command to run: `$2` (all remaining arguments)

The agent will:
1. Check tmux environment
2. Create a horizontal split pane
3. Set the `@claude_pane_name` on the new pane
4. Execute the command in the new pane
5. Report success with pane info
