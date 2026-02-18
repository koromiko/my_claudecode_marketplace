---
name: session-manager-pane-context
description: Use this skill when the user asks about capturing output from a managed pane or tab, sending commands to running panes, checking pane status, listing managed panes, or interacting with terminal sessions created by session-manager. Triggers on questions like "capture output from pane", "send command to tab", "what panes are running", "check pane status", "get console context", "attach to pane".
---

# Pane Context Skill

This skill helps interact with terminal panes and tabs managed by the session-manager plugin.

## Overview

The session-manager plugin tracks panes/tabs created via `/session-manager:run-in-pane` in a registry at `~/.claude/session-manager/registry.json`. Each managed pane has a unique ID in the format `sm-XXXXXX`.

## Available Operations

### Capture Output from a Pane

Retrieve the current content/output from a managed pane:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/session-manager.sh capture <id> [--lines N]
```

- `<id>`: The managed pane ID (e.g., `sm-abc123`)
- `--lines N`: Number of lines to capture (default: 100)

Example:
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/session-manager.sh capture sm-abc123 --lines 50
```

### Send Command to a Pane

Execute a command in an existing managed pane:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/session-manager.sh send <id> <command>
```

Example:
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/session-manager.sh send sm-abc123 "npm test"
```

### List All Managed Panes

Show all panes tracked by session-manager:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/session-manager.sh list
```

Output includes: ID, type (tmux/iterm), pane ID, status, and initial command.

### Check Pane Status

Verify if a pane is still active or has become stale:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/session-manager.sh status <id>
```

Returns: `active` or `stale`

### Cleanup Stale Entries

Remove registry entries for panes that no longer exist:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/session-manager.sh cleanup
```

## Registry Location

The pane registry is stored at: `~/.claude/session-manager/registry.json`

Each entry contains:
- `id`: Managed pane ID
- `type`: Terminal type (`tmux` or `iterm`)
- `pane_id`: Underlying terminal pane/session ID
- `created_at`: ISO timestamp
- `working_directory`: Directory where command was started
- `initial_command`: The command that was run
- `status`: Current status

## Best Practices

1. **Always list panes first** when the user asks about "their panes" or "running tabs"
2. **Check status** before sending commands to verify the pane still exists
3. **Capture output** to get context about what's happening in a pane
4. **Run cleanup** periodically to remove stale entries from closed panes

## Error Handling

- If a pane ID is not found, suggest running `list` to see available panes
- If a pane is stale, suggest running `cleanup` and creating a new pane
- If capture fails for iTerm, note that iTerm output capture is limited compared to tmux
