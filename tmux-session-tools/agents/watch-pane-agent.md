---
description: Starts watching a pane for context injection. Use when user runs /watch-pane command.
allowed-tools: Bash(bash:*, tmux:*), Write
model: haiku
---

# Watch Pane Agent

Start watching a tmux pane and periodically inject its output as context.

## Input

The prompt will contain:
- **Plugin root path**: The path to the plugin directory (required)
- **Pane reference**: Name or ID of pane to watch (required)
- **Interval**: Seconds between captures (optional, default 30)
- **Session ID**: The Claude session ID for the watch file name (required)

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

Use the resolve-pane.sh script to validate the pane exists:

```bash
bash "PLUGIN_ROOT_PATH/scripts/resolve-pane.sh" "PANE_REF"
```

**Handle errors:**
- If pane not found, inform user and suggest `/list-panes`.
- Stop execution.

### Step 3: Write watch config

Create the watch config file at `~/.claude/tmux-watch-{SESSION_ID}.json`:

```json
{
  "pane_name": "PANE_NAME",
  "interval": INTERVAL,
  "last_capture": 0
}
```

Use the Write tool to create this file at the path:
`$HOME/.claude/tmux-watch-SESSION_ID.json`

Replace SESSION_ID with the actual session ID provided.

### Step 4: Confirm to user

Tell the user:
- Now watching pane `PANE_NAME`
- Output will be injected as context every `INTERVAL` seconds
- Use `/unwatch-pane` to stop watching
- Use `/capture-pane PANE_NAME` for one-time capture

**Note:** The context injection happens via a UserPromptSubmit hook, so the user will see pane output automatically included before their prompts are processed.
