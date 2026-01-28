---
description: Create a custom tmux workflow command for your project
argument-hint: [workflow-name]
---

Use the Task tool to spawn the `create-workflow-agent` subagent from this plugin.

Pass these values to the agent in the prompt:
- Plugin root path: `${CLAUDE_PLUGIN_ROOT}`
- Current working directory: `${CWD}`
- Optional workflow name: `$1` (if provided)

The agent will:
1. Analyze the current project structure using detection scripts
2. Identify project type, frameworks, and available scripts
3. Suggest an appropriate tmux layout based on project type
4. Guide user through customizing pane names, commands, and watch intervals
5. Generate an executable workflow command that can be reused
