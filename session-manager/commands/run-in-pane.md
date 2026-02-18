---
description: Run a bash command in a new tmux pane or iTerm tab with tracking
allowed-tools:
  - Bash(*)
argument-hint: <command> [--working-dir <path>]
---

# Run in Pane

Run a bash command in a new tmux pane or iTerm tab, with automatic tracking via the session-manager registry.

## Instructions

Execute the session-manager script with the `run` subcommand, passing the user's command and optional working directory.

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/session-manager.sh run "<command>" --working-dir "$(pwd)"
```

The script will:
1. Detect if running inside tmux (creates new pane) or iTerm (creates new tab)
2. Execute the command in the new pane/tab
3. Register the pane with a unique managed ID (format: `sm-XXXXXX`)
4. Return the managed ID for future reference

## Output

On success, the script outputs the managed ID (e.g., `sm-abc123`). Report this ID to the user so they can:
- Capture output: `session-manager.sh capture sm-abc123`
- Send commands: `session-manager.sh send sm-abc123 "another command"`
- Check status: `session-manager.sh status sm-abc123`

## Examples

Run a dev server:
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/session-manager.sh run "npm run dev" --working-dir "/path/to/project"
```

Run tests in background:
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/session-manager.sh run "npm test -- --watch"
```

Start a database:
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/session-manager.sh run "docker-compose up postgres"
```
