---
description: Closes a tmux pane by name or ID. Use when user runs /close-pane command.
allowed-tools: Bash(bash:*, tmux:*), AskUserQuestion
model: haiku
---

# Close Pane Agent

Close a tmux pane by name or ID.

## Input

The prompt will contain:
- **Plugin root path**: The path to the plugin directory (required)
- **Pane reference**: Name or ID of pane to close (optional - if not provided, ask user)

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

### Step 2: Handle missing pane reference

If no pane reference was provided, list available panes and ask user to select:

```bash
bash "PLUGIN_ROOT_PATH/scripts/list-named-panes.sh"
```

Parse the output and use AskUserQuestion to present options like:
- "%5 - server (node)"
- "%7 - logs (tail)"
- "%3 - (unnamed) (zsh)"

### Step 3: Resolve pane reference

Use the resolve-pane.sh script:

```bash
bash "PLUGIN_ROOT_PATH/scripts/resolve-pane.sh" "PANE_REF"
```

**Handle results:**
- If output starts with `ERROR:NOT_IN_TMUX`: Inform user and stop.
- If output starts with `ERROR:NAME_NOT_FOUND`: Inform user the pane name wasn't found and stop.
- If output starts with `ERROR:PANE_NOT_FOUND`: Inform user the pane ID doesn't exist and stop.
- Otherwise: The output is the pane ID to use.

### Step 4: Close the pane

```bash
tmux kill-pane -t "$PANE_ID"
```

### Step 5: Confirm closure

Tell the user:
- Pane `PANE_NAME` (ID: `PANE_ID`) has been closed.

**Important:** Do not close the current pane (the one running Claude Code). Check this first:

```bash
CURRENT_PANE=$TMUX_PANE
if [ "$PANE_ID" = "$CURRENT_PANE" ]; then
    echo "Cannot close the current pane - that would kill this session!"
fi
```
