#!/bin/bash
# check-watch.sh - Hook script for pane watching context injection
# Called on UserPromptSubmit to inject pane output as context
# Input: JSON with session_id from stdin
# Output: JSON with optional systemMessage field

set -euo pipefail

# Read hook input from stdin
input=$(cat)

# Extract session_id from input
session_id=$(echo "$input" | grep -o '"session_id"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"\([^"]*\)"$/\1/' || echo "")

if [ -z "$session_id" ]; then
    # No session ID, can't check watch file
    echo '{}'
    exit 0
fi

WATCH_FILE="$HOME/.claude/tmux-watch-${session_id}.json"

# No watch configured
if [ ! -f "$WATCH_FILE" ]; then
    echo '{}'
    exit 0
fi

# Not in tmux, can't capture
if [ -z "${TMUX:-}" ]; then
    echo '{}'
    exit 0
fi

# Read watch config
watch_config=$(cat "$WATCH_FILE")

# Parse config fields
pane_name=$(echo "$watch_config" | grep -o '"pane_name"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"\([^"]*\)"$/\1/' || echo "")
interval=$(echo "$watch_config" | grep -o '"interval"[[:space:]]*:[[:space:]]*[0-9]*' | grep -o '[0-9]*$' || echo "30")
last_capture=$(echo "$watch_config" | grep -o '"last_capture"[[:space:]]*:[[:space:]]*[0-9]*' | grep -o '[0-9]*$' || echo "0")

if [ -z "$pane_name" ]; then
    echo '{}'
    exit 0
fi

current_time=$(date +%s)
elapsed=$((current_time - last_capture))

# Not time yet
if [ "$elapsed" -lt "$interval" ]; then
    echo '{}'
    exit 0
fi

# Get script directory to use resolve-pane.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Resolve pane
pane_id=$(bash "$SCRIPT_DIR/resolve-pane.sh" "$pane_name" 2>/dev/null || echo "ERROR")

if [[ "$pane_id" == ERROR* ]]; then
    # Pane no longer exists, clean up watch
    rm -f "$WATCH_FILE"
    # Escape for JSON
    message="Watch pane \\\"$pane_name\\\" no longer exists. Watch stopped."
    echo "{\"systemMessage\": \"$message\"}"
    exit 0
fi

# Capture pane content (last 50 lines)
content=$(tmux capture-pane -t "$pane_id" -p -S -50 2>/dev/null || echo "(capture failed)")

# Escape content for JSON (newlines, quotes, backslashes)
escaped_content=$(printf '%s' "$content" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g' | sed ':a;N;$!ba;s/\n/\\n/g')

# Update last capture time in watch file
cat > "$WATCH_FILE" << EOF
{
  "pane_name": "$pane_name",
  "interval": $interval,
  "last_capture": $current_time
}
EOF

# Return context injection
echo "{\"systemMessage\": \"--- Watched Pane [$pane_name] Output ---\\n$escaped_content\\n--- End Pane Output ---\"}"
