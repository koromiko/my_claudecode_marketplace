#!/bin/bash
# resolve-pane.sh - Resolve pane name to tmux pane ID
# Usage: resolve-pane.sh <pane-name-or-id>
# Output: pane ID (e.g., %5) or ERROR:message

set -euo pipefail

PANE_REF="${1:-}"

if [ -z "$PANE_REF" ]; then
    echo "ERROR:NO_INPUT"
    exit 1
fi

# Check if running in tmux
if [ -z "${TMUX:-}" ]; then
    echo "ERROR:NOT_IN_TMUX"
    exit 1
fi

# If already a pane ID (starts with %), validate and return
if [[ "$PANE_REF" == %* ]]; then
    if tmux display -p -t "$PANE_REF" '#{pane_id}' 2>/dev/null; then
        exit 0
    else
        echo "ERROR:PANE_NOT_FOUND:$PANE_REF"
        exit 1
    fi
fi

# Otherwise, search by @claude_pane_name in current session
FOUND=$(tmux list-panes -s -F '#{pane_id}|#{@claude_pane_name}' 2>/dev/null | grep "|${PANE_REF}$" | head -1 | cut -d'|' -f1)

if [ -n "$FOUND" ]; then
    echo "$FOUND"
    exit 0
else
    echo "ERROR:NAME_NOT_FOUND:$PANE_REF"
    exit 1
fi
