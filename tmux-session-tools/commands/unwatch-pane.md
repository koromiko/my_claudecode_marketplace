---
description: Stop watching a pane
argument-hint:
---

Use the Task tool to spawn the `unwatch-pane-agent` subagent from this plugin.

Pass these values to the agent in the prompt:
- Session ID: `${CLAUDE_SESSION_ID}`

The agent will:
1. Remove the watch config file
2. Confirm watch stopped
