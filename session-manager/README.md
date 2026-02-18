# session-manager

Manage Claude Code sessions across tmux panes and iTerm tabs - fork sessions, run commands, and capture output.

## Overview

This plugin provides comprehensive terminal session management for Claude Code:

- **Fork Sessions**: Branch your current Claude session into a new pane/tab for parallel work
- **Run Commands**: Execute commands in new tracked panes/tabs with unique IDs
- **Capture Output**: Retrieve output from managed panes
- **Send Commands**: Send commands to existing managed panes
- **Track Status**: Monitor which panes are active or stale

The plugin automatically detects your terminal environment and uses the appropriate method:
- **tmux**: Creates new panes in your current tmux window
- **iTerm2**: Opens new tabs in your current iTerm window

## Prerequisites

- **macOS** - This plugin only works on macOS
- **Python 3** - Required for JSON manipulation
- **One of the following**:
  - **tmux** - If running inside a tmux session, no additional setup needed
  - **iTerm2** - Must be installed and running (if not using tmux)
    - Install via Homebrew: `brew install --cask iterm2`
    - Or download from: https://iterm2.com/

## Commands

### /session-manager:fork

Fork your current Claude Code session into a new tmux pane or iTerm tab.

```
/session-manager:fork
```

This will:
1. Auto-detect if you're running in tmux or iTerm
2. Auto-detect your current session from Claude's session files
3. Open a new tmux pane or iTerm tab
4. Start a forked Claude session with all the context from the original

### /session-manager:run-in-pane

Run a bash command in a new tracked pane/tab.

```
/session-manager:run-in-pane npm run dev --working-dir /path/to/project
```

This will:
1. Create a new tmux pane or iTerm tab
2. Execute the command
3. Return a managed ID (e.g., `sm-abc123`) for tracking

## Interacting with Managed Panes

After creating a pane with `run-in-pane`, you can interact with it using the session-manager script:

### Capture Output
```bash
./scripts/session-manager.sh capture sm-abc123 --lines 50
```

### Send Commands
```bash
./scripts/session-manager.sh send sm-abc123 "npm test"
```

### List All Panes
```bash
./scripts/session-manager.sh list
```

### Check Status
```bash
./scripts/session-manager.sh status sm-abc123
```

### Cleanup Stale Entries
```bash
./scripts/session-manager.sh cleanup
```

## Registry

Managed panes are tracked in `~/.claude/session-manager/registry.json`. This allows:
- Persistence across Claude sessions
- Tracking of pane metadata (working directory, initial command, creation time)
- Status monitoring (active vs stale)

## Error Handling

The plugin provides helpful error messages if:
- Not running on macOS
- Not in tmux AND iTerm2 is not installed/running
- Pane ID not found in registry
- Terminal pane no longer exists (stale)

## Examples

### Start a dev server and capture its output

```
/session-manager:run-in-pane npm run dev
```

Later, capture what's happening:
```bash
./scripts/session-manager.sh capture sm-xyz789
```

### Run tests in a separate pane

```
/session-manager:run-in-pane npm test -- --watch
```

### Fork session for parallel exploration

```
/session-manager:fork
```
