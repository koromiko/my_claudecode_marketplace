#!/bin/bash
# set-pane-name.sh - Set Claude name on a pane
# Usage: set-pane-name.sh <pane_id> <name>
# Output: OK:<pane_id>:<name> or ERROR:message

set -euo pipefail

PANE_ID="${1:-}"
NAME="${2:-}"

if [ -z "$PANE_ID" ] || [ -z "$NAME" ]; then
    echo "ERROR:USAGE:set-pane-name.sh <pane_id> <name>"
    exit 1
fi

# Check if running in tmux
if [ -z "${TMUX:-}" ]; then
    echo "ERROR:NOT_IN_TMUX"
    exit 1
fi

# Verify pane exists
if ! tmux display -p -t "$PANE_ID" '#{pane_id}' >/dev/null 2>&1; then
    echo "ERROR:PANE_NOT_FOUND:$PANE_ID"
    exit 1
fi

# Set the name
if tmux set-option -p -t "$PANE_ID" @claude_pane_name "$NAME" 2>/dev/null; then
    echo "OK:$PANE_ID:$NAME"
    exit 0
else
    echo "ERROR:SET_FAILED:$PANE_ID:$NAME"
    exit 1
fi
