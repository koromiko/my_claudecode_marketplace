#!/bin/bash
# Claude Code Stop hook — sends macOS notification when Claude finishes.
# Only notifies if a permission prompt occurred during this session
# (indicated by a marker file written by permission-notification.sh).

set -euo pipefail

input=$(cat)

if ! command -v jq &>/dev/null; then
  exit 0
fi

session_id=$(echo "$input" | jq -r '.session_id // ""')
cwd=$(echo "$input" | jq -r '.cwd // ""')
stop_hook_active=$(echo "$input" | jq -r '.stop_hook_active // false')
reason=$(echo "$input" | jq -r '.stop_reason // ""')

# Don't notify if this is a re-entry from a stop hook (prevent loops)
if [[ "$stop_hook_active" == "true" ]]; then
  exit 0
fi

# Only notify if a permission prompt occurred during this session
marker="/tmp/claude-hook-session-${session_id}"
if [[ -z "$session_id" ]] || [[ ! -f "$marker" ]]; then
  exit 0
fi

# Clean up the marker file
rm -f "$marker"

# Extract project name from cwd
if [[ -n "$cwd" ]]; then
  project_name=$(basename "$cwd")
else
  project_name="Unknown Project"
fi

# Set notification message
if [[ -n "$reason" ]]; then
  message="Stop reason: $reason"
else
  message="Claude has finished working."
fi

# Send macOS notification
if command -v terminal-notifier &>/dev/null; then
  terminal-notifier -title "Claude Code" -subtitle "Project: $project_name" \
    -message "$message" -activate com.googlecode.iterm2
fi

# Read out project name and status
say "$project_name: $message" &
