---
name: tmux
description: Use this skill when users mention "tmux", "tmux pane", "tmux window", "tmux session", "background terminal", "parallel terminal", or when users need to run commands in separate terminals, capture output from other panes, or manage multiple Claude Code sessions in tmux.
version: 1.0.0
context: fork
---

# Tmux Operations for Claude Code

Reference for tmux commands to manage multiple terminals, run background processes, and capture output from other panes.

## Detecting Tmux Environment

Check if running inside tmux before using tmux commands:

```bash
# $TMUX is set when inside tmux (contains socket path)
if [ -n "$TMUX" ]; then
    echo "Inside tmux"
fi

# $TMUX_PANE contains current pane ID (e.g., %0)
echo $TMUX_PANE
```

## Creating New Windows and Panes

### New Window

```bash
# Create new window in current session
tmux new-window

# Create with name
tmux new-window -n "build"

# Create with working directory
tmux new-window -c "/path/to/project"

# Create and run command
tmux new-window -n "server" "npm run dev"

# Create in specific session
tmux new-window -t session_name -n "window_name"
```

### Split Pane

```bash
# Horizontal split (left/right)
tmux split-window -h

# Vertical split (top/bottom)
tmux split-window -v

# Split with working directory
tmux split-window -h -c "/path/to/project"

# Split and run command
tmux split-window -h "tail -f logs/app.log"
```

## Executing Commands in Other Panes

Use `send-keys` to run commands in a specific pane:

```bash
# Send command to target pane (Enter executes it)
tmux send-keys -t target "npm run build" Enter

# Send without executing (omit Enter)
tmux send-keys -t target "npm run build"

# Send special keys
tmux send-keys -t target C-c    # Ctrl+C
tmux send-keys -t target C-d    # Ctrl+D
tmux send-keys -t target Escape
```

## Capturing Output from Panes

Use `capture-pane` to get console content:

```bash
# Capture visible content from target pane
tmux capture-pane -t target -p

# Capture with history (last 500 lines)
tmux capture-pane -t target -p -S -500

# Capture entire scrollback
tmux capture-pane -t target -p -S -

# Capture to file
tmux capture-pane -t target -p > output.txt
```

## Target Specification

The `-t` flag specifies which session, window, or pane to target:

| Format | Description |
|--------|-------------|
| `-t session` | Target session by name |
| `-t session:window` | Target window in session |
| `-t session:window.pane` | Target specific pane |
| `-t :window` | Window in current session |
| `-t :.pane` | Pane in current window |
| `-t %N` | Pane by ID (e.g., `%0`, `%1`) |

### Finding Pane IDs

```bash
# List all panes with their IDs
tmux list-panes -a -F '#{session_name}:#{window_index}.#{pane_index} #{pane_id}'

# List panes in current window
tmux list-panes -F '#{pane_index}: #{pane_id} #{pane_current_command}'
```

## Common Patterns

### Run Background Process in New Window

```bash
# Check if in tmux, then create window for long-running process
if [ -n "$TMUX" ]; then
    tmux new-window -n "build" "npm run build"
fi
```

### Get Output from Another Pane

```bash
# Capture last 100 lines from pane 1
output=$(tmux capture-pane -t :.1 -p -S -100)
echo "$output"
```

### Send Command and Wait for Completion

```bash
# Send command to pane
tmux send-keys -t :.1 "npm test" Enter

# Wait a bit then capture output
sleep 5
tmux capture-pane -t :.1 -p -S -50
```

### Get User Selection from Another Pane

**For iTerm2 with mouse selection (recommended):**

Mouse selections in iTerm2 go to the macOS clipboard. Access via `pbpaste`:

```bash
# Get user's mouse selection from clipboard
selection=$(pbpaste)
echo "$selection"
```

**For tmux copy-mode selections:**

When using tmux copy-mode (prefix + `[`), selections go to tmux buffer:

```bash
# Get from tmux buffer
if selection=$(tmux show-buffer 2>/dev/null); then
    echo "$selection"
else
    echo "No selection in tmux buffer"
fi

# List all buffers
tmux list-buffers

# Load text into buffer programmatically
echo "some text" | tmux load-buffer -
```

## Plugin Commands

This plugin provides commands for managing tmux panes:

| Command | Description |
|---------|-------------|
| `/split-run <name> <cmd>` | Split pane and run command with a name |
| `/capture-pane <name> [lines]` | Capture output from a named pane |
| `/watch-pane <name> [secs]` | Auto-inject pane output as context |
| `/unwatch-pane` | Stop watching a pane |
| `/close-pane <name>` | Close a pane by name |
| `/list-panes` | List all panes with their names |
| `/fork-session [name]` | Fork Claude session into new window |

### Named Panes

Panes created with `/split-run` are automatically named. Reference them by name:

```
/split-run server npm run dev
/capture-pane server
/close-pane server
```

## Additional Resources

For advanced patterns like waiting for command completion and error handling, see `references/advanced-scripting.md`.
