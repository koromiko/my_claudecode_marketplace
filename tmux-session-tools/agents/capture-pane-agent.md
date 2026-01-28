---
description: Captures output from a tmux pane by name or ID. Use when user runs /capture-pane command.
allowed-tools: Bash(bash:*, tmux:*)
model: haiku
---

# Capture Pane Agent

Capture and return output from a tmux pane.

## Input

The prompt will contain:
- **Plugin root path**: The path to the plugin directory (required)
- **Pane reference**: Name or ID of pane to capture (required)
- **Lines**: Number of lines to capture (optional, default 100)

## Workflow

### Step 1: Check tmux environment

```bash
if [ -z "$TMUX" ]; then
    echo "NOT_IN_TMUX"
else
    echo "IN_TMUX"
fi
```

If NOT_IN_TMUX:
- Inform user: "This command requires running inside a tmux session."
- Stop execution.

### Step 2: Resolve pane reference

Use the resolve-pane.sh script:

```bash
bash "PLUGIN_ROOT_PATH/scripts/resolve-pane.sh" "PANE_REF"
```

**Handle results:**
- If output starts with `ERROR:NOT_IN_TMUX`: Inform user and stop.
- If output starts with `ERROR:NAME_NOT_FOUND`: Inform user the pane name wasn't found. Suggest running `/list-panes` to see available panes.
- If output starts with `ERROR:PANE_NOT_FOUND`: Inform user the pane ID doesn't exist.
- Otherwise: The output is the pane ID to use.

### Step 3: Capture pane content

```bash
tmux capture-pane -t "$PANE_ID" -p -S -${LINES:-100}
```

The `-S -N` flag captures the last N lines of scrollback history.
The `-p` flag prints to stdout instead of a paste buffer.

### Step 4: Return captured content

Present the captured output to the user. Format it clearly:

```
--- Captured from pane "PANE_NAME" (ID: PANE_ID) - last N lines ---

[captured content here]

--- End capture ---
```

This content is now part of the conversation context and can be used for analysis, debugging, or reference.
