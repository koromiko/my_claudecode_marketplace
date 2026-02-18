# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a Claude Code plugin for managing terminal sessions across tmux panes and iTerm tabs. It provides:
- Session forking (continue a Claude session in a new pane/tab)
- Command execution in new tracked panes/tabs
- Output capture and command sending to managed panes
- Registry-based pane tracking across Claude sessions

## Plugin Structure

```
.claude-plugin/plugin.json      # Plugin manifest (name, version, description)
commands/
  fork.md                       # Fork current Claude session to new pane/tab
  run-in-pane.md                # Run command in new tracked pane/tab
skills/
  pane-context/SKILL.md         # Skill for interacting with managed panes
scripts/
  fork-iterm.sh                 # Legacy fork script (tmux and iTerm)
  session-manager.sh            # Unified management script with subcommands
```

## Key Components

### session-manager.sh

Unified script with subcommands for pane management:

| Subcommand | Usage | Description |
|------------|-------|-------------|
| `run` | `run <cmd> [--working-dir <path>]` | Run command in new pane/tab, return managed ID |
| `capture` | `capture <id> [--lines N] [--no-sync]` | Capture output from pane (default 100 lines) |
| `send` | `send <id> <cmd> [--no-sync]` | Send command to existing pane |
| `list` | `list [--auto-cleanup] [--no-sync]` | List all managed panes with real-time status |
| `status` | `status <id>` | Check if pane is active/stale |
| `sync` | `sync [--auto-remove]` | Validate registry against actual tmux panes |
| `cleanup` | `cleanup` | Remove stale registry entries |

### Registry System

Panes are tracked in `~/.claude/session-manager/registry.json`:
- Unique managed IDs: `sm-{6-char-random}` format
- Maps to underlying tmux pane IDs or iTerm session IDs
- Persists across Claude sessions

### Terminal Detection

1. Checks `$TMUX` env var for tmux
2. Uses AppleScript to detect running iTerm
3. Creates panes/tabs in detected terminal

## Commands

### /session-manager:fork
Fork the current Claude session into a new tmux pane or iTerm tab. Uses `fork-iterm.sh` to detect the current session, open a forked session, and **return a managed ID** for tracking via session-manager.sh commands.

### /session-manager:run-in-pane
Run a bash command in a new tmux pane or iTerm tab with automatic tracking. Returns a managed ID for subsequent operations.

## Testing

Test the session-manager script:
```bash
cd plugins/session-manager

# Test run command (in tmux)
./scripts/session-manager.sh run "echo hello" --working-dir /tmp
# Should output: sm-XXXXXX

# Test list
./scripts/session-manager.sh list

# Test capture
./scripts/session-manager.sh capture sm-XXXXXX

# Test send
./scripts/session-manager.sh send sm-XXXXXX "echo world"

# Test status
./scripts/session-manager.sh status sm-XXXXXX

# Test cleanup
./scripts/session-manager.sh cleanup
```

Test the fork script (now returns managed ID):
```bash
./scripts/fork-iterm.sh "$(pwd)"
# Should output managed ID: sm-XXXXXX

# Test sync
./scripts/session-manager.sh sync
# Shows stale entries

./scripts/session-manager.sh sync --auto-remove
# Removes stale entries
```

## Error Handling

The scripts exit with error codes on failure:
- macOS check failure
- No supported terminal detected
- Pane not found in registry
- tmux/iTerm operation failure
- Sessions directory not found (for fork)
