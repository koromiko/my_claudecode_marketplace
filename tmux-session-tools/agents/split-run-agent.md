---
description: Creates a named tmux pane and runs a command. Use when user runs /split-run command.
allowed-tools: Bash(bash:*, tmux:*)
model: haiku
---

# Split Run Agent

Create a named tmux pane and run a command in it.

## Input

The prompt will contain:
- **Plugin root path**: The path to the plugin directory (required)
- **Pane name**: Name to assign to the new pane (required)
- **Command**: The command to execute in the new pane (required)

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
- Inform user: "This command requires running inside a tmux session. Start tmux first with `tmux` or `tmux new -s session-name`."
- Stop execution.

### Step 2: Create horizontal split and capture pane ID

```bash
NEW_PANE_ID=$(tmux split-window -h -P -F '#{pane_id}')
echo "Created pane: $NEW_PANE_ID"
```

The `-P -F '#{pane_id}'` flags print the new pane's ID.

### Step 3: Set pane name

Use the set-pane-name.sh script with the plugin root path provided:

```bash
bash "PLUGIN_ROOT_PATH/scripts/set-pane-name.sh" "$NEW_PANE_ID" "PANE_NAME"
```

Replace `PLUGIN_ROOT_PATH` with the actual path provided in the prompt.

### Step 4: Execute command in new pane

```bash
tmux send-keys -t "$NEW_PANE_ID" "COMMAND" Enter
```

Replace `COMMAND` with the full command provided in the prompt.

### Step 5: Report success

Tell the user:
- New pane created with ID `$NEW_PANE_ID`
- Named: `PANE_NAME`
- Running: `COMMAND`
- Reference this pane in other commands using the name (e.g., `/capture-pane PANE_NAME`)
