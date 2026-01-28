#!/bin/bash
# list-named-panes.sh - List all panes with their Claude names
# Output format:
#   STATUS:OK|NOT_IN_TMUX
#   PANE:<pane_id>|<claude_name>|<command>|<target>
#   ...

set -euo pipefail

# Check if running in tmux
if [ -z "${TMUX:-}" ]; then
    echo "STATUS:NOT_IN_TMUX"
    exit 0
fi

echo "STATUS:OK"

# List panes in current session with format: pane_id|claude_name|command|window.pane
# -s lists all panes in current session (all windows)
tmux list-panes -s -F '#{pane_id}|#{@claude_pane_name}|#{pane_current_command}|#{window_index}.#{pane_index}' | while read -r line; do
    echo "PANE:$line"
done
