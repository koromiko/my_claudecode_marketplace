---
description: Lists all tmux panes with their Claude names. Use when user runs /list-panes command.
allowed-tools: Bash(bash:*, tmux:*)
model: haiku
---

# List Panes Agent

List all tmux panes in the current session with their Claude names.

## Input

The prompt will contain:
- **Plugin root path**: The path to the plugin directory (required)

## Workflow

### Step 1: Run list-named-panes script

```bash
bash "PLUGIN_ROOT_PATH/scripts/list-named-panes.sh"
```

Replace `PLUGIN_ROOT_PATH` with the actual path provided.

### Step 2: Parse output

The script returns:
- Line 1: `STATUS:OK|NOT_IN_TMUX`
- Lines 2+: `PANE:<pane_id>|<claude_name>|<command>|<window.pane>`

### Step 3: Handle status

**If STATUS is NOT_IN_TMUX:**
- Inform user: "This command requires running inside a tmux session."
- Stop execution.

**If STATUS is OK:**
- Continue to format output.

### Step 4: Format and display

Present the panes in a readable format. For each PANE line:
- Parse: `PANE:<pane_id>|<claude_name>|<command>|<window.pane>`
- Display with clear columns

Example output format:
```
Panes in current session:

| ID  | Name     | Command | Location |
|-----|----------|---------|----------|
| %5  | server   | node    | 1.0      |
| %7  | logs     | tail    | 1.1      |
| %3  | (unnamed)| zsh     | 0.0      |
```

If a pane has no Claude name (empty), show "(unnamed)".

Remind the user they can reference named panes in commands like `/capture-pane server` or `/close-pane logs`.
