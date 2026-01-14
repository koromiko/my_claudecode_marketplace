# Advanced Tmux Scripting

Patterns for inter-process communication and robust tmux operations.

## Sending Commands to Panes

### Send to Specific Pane

```bash
# Send command to specific pane
tmux_send() {
    local target=$1
    shift
    tmux send-keys -t "$target" "$*" Enter
}

# Usage
tmux_send ":.1" "npm restart"
tmux_send "dev:server" "npm run build"
```

### Broadcast to All Panes in Window

```bash
# Send to all panes in a window
tmux_broadcast() {
    local window=$1
    shift
    local cmd="$*"

    local panes=$(tmux list-panes -t "$window" -F '#{pane_id}')
    for pane in $panes; do
        tmux send-keys -t "$pane" "$cmd" Enter
    done
}

# Usage
tmux_broadcast ":0" "clear"
```

## Capturing Pane Output

### Basic Capture

```bash
# Capture visible content
tmux capture-pane -t target -p > output.txt

# Capture with history (last 1000 lines)
tmux capture-pane -t target -p -S -1000 > full_output.txt
```

### Capture to Buffer

```bash
# Capture to named buffer and save
tmux capture-pane -t target -b temp_buffer
tmux save-buffer -b temp_buffer output.txt
tmux delete-buffer -b temp_buffer
```

## Waiting for Command Completion

### Poll for Shell Prompt

```bash
# Wait for pane to return to shell prompt
wait_for_prompt() {
    local target=$1
    local timeout=${2:-60}
    local count=0

    while [ $count -lt $timeout ]; do
        # Check if pane shows shell prompt (customize pattern as needed)
        local content=$(tmux capture-pane -t "$target" -p | tail -1)
        if [[ "$content" =~ \$[[:space:]]*$ ]] || [[ "$content" =~ \>[[:space:]]*$ ]]; then
            return 0
        fi
        sleep 1
        ((count++))
    done
    return 1  # Timeout
}

# Usage
tmux send-keys -t ":.1" "npm run build" Enter
if wait_for_prompt ":.1" 120; then
    echo "Build completed"
    tmux capture-pane -t ":.1" -p -S -50
else
    echo "Build timed out"
fi
```

## Error Handling

### Check Tmux Availability

```bash
# Verify tmux is installed
command -v tmux >/dev/null 2>&1 || {
    echo "tmux is not installed" >&2
    exit 1
}
```

### Check If Inside Tmux

```bash
ensure_in_tmux() {
    if [ -z "${TMUX:-}" ]; then
        echo "Not inside tmux session" >&2
        return 1
    fi
}
```

### Check Session Exists

```bash
session_exists() {
    tmux has-session -t "$1" 2>/dev/null
}

# Usage
if session_exists "dev"; then
    tmux send-keys -t "dev:0" "echo hello" Enter
fi
```

### Safe Command Sending

```bash
safe_send() {
    local target=$1
    local cmd=$2

    # Extract session name from target
    local session="${target%%:*}"

    if ! tmux has-session -t "$session" 2>/dev/null; then
        echo "Session not found: $session" >&2
        return 1
    fi

    tmux send-keys -t "$target" "$cmd" Enter
}
```

## Complete Example: Run and Capture

```bash
#!/bin/bash
# Run command in another pane and capture output

run_and_capture() {
    local target=$1
    local cmd=$2
    local timeout=${3:-30}

    # Verify we're in tmux
    if [ -z "$TMUX" ]; then
        echo "Not in tmux" >&2
        return 1
    fi

    # Send the command
    tmux send-keys -t "$target" "$cmd" Enter

    # Wait for completion
    sleep 2
    local count=0
    while [ $count -lt $timeout ]; do
        local last_line=$(tmux capture-pane -t "$target" -p | tail -1)
        if [[ "$last_line" =~ \$[[:space:]]*$ ]]; then
            break
        fi
        sleep 1
        ((count++))
    done

    # Capture and return output
    tmux capture-pane -t "$target" -p -S -100
}

# Usage
output=$(run_and_capture ":.1" "npm test" 60)
echo "$output"
```
