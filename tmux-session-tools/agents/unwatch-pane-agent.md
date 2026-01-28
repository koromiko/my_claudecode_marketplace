---
description: Stops watching a pane. Use when user runs /unwatch-pane command.
allowed-tools: Bash(bash:rm, bash:ls, bash:cat)
model: haiku
---

# Unwatch Pane Agent

Stop watching a tmux pane (disable context injection).

## Input

The prompt will contain:
- **Session ID**: The Claude session ID for the watch file name (required)

## Workflow

### Step 1: Check if watch is active

```bash
WATCH_FILE="$HOME/.claude/tmux-watch-SESSION_ID.json"
if [ -f "$WATCH_FILE" ]; then
    cat "$WATCH_FILE"
    echo "WATCH_ACTIVE"
else
    echo "NO_WATCH"
fi
```

Replace SESSION_ID with the actual session ID provided.

### Step 2: Handle result

**If NO_WATCH:**
- Inform user: "No active pane watch for this session."
- Stop execution.

**If WATCH_ACTIVE:**
- Read the config to get the pane name being watched
- Continue to removal

### Step 3: Remove watch config

```bash
rm -f "$HOME/.claude/tmux-watch-SESSION_ID.json"
```

### Step 4: Confirm to user

Tell the user:
- Stopped watching pane `PANE_NAME`
- Context injection is now disabled
- Use `/watch-pane NAME` to start watching again
