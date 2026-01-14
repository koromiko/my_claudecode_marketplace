---
description: Handles forking Claude Code sessions into new tmux windows. Use when user runs /fork-session command.
allowed-tools: Bash(bash:*, tmux:*), AskUserQuestion
model: haiku
---

# Fork Session Agent

Fork a Claude Code session into a new tmux window.

## Input

The prompt will contain:
- **Plugin root path**: The path to the plugin directory (required)
- **Window name**: Optional custom window name. Use "claude-fork" as default if not specified.

## Workflow

### Step 1: Run list-sessions script

Execute the list-sessions script using the plugin root path provided in the prompt:
```bash
bash "PLUGIN_ROOT_PATH/scripts/list-sessions.sh"
```

Replace `PLUGIN_ROOT_PATH` with the actual path provided.

### Step 2: Parse output

The script returns structured output:
- Line 1: `STATUS:OK|NOT_IN_TMUX|NO_SESSIONS`
- Line 2: `SESSION_COUNT:N`
- Lines 3+: `SESSION:uuid|timestamp|first_message_preview`

### Step 3: Handle status

**If STATUS is NOT_IN_TMUX:**
- Inform user: "This command requires running inside a tmux session. Start tmux first with `tmux` or `tmux new -s session-name`, then run Claude Code inside it."
- Stop execution.

**If STATUS is NO_SESSIONS:**
- Inform user: "No recent sessions found for this project."
- Stop execution.

**If STATUS is OK:**
- Continue to session selection.

### Step 4: Present sessions to user

Use AskUserQuestion to present the sessions. For each session line:
- Parse: `SESSION:uuid|timestamp|message_preview`
- Display: Short ID (first 8 chars), timestamp, message preview

Example options:
- "e3e2cc8d - 2026-01-14 10:30 - Help me create a plugin..."
- "113147cc - 2026-01-14 09:15 - Fix the authentication bug..."

### Step 5: Execute fork

Once user selects a session:
```bash
tmux new-window -n "WINDOW_NAME" "claude -r FULL_SESSION_ID --fork-session"
```

Replace:
- WINDOW_NAME: provided argument or "claude-fork"
- FULL_SESSION_ID: complete UUID from selected session

### Step 6: Confirm

Report to user:
- New tmux window created with name
- Session ID that was forked
- Focus has switched to new window
