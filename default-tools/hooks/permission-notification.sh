#!/bin/bash
# Claude Code Notification hook — fires ONLY when a real permission prompt is shown.
# Configured with matcher: "permission_prompt" on the Notification hook event.
#
# Input JSON fields: message, cwd, session_id, notification_type

set -euo pipefail

input=$(cat)

if ! command -v jq &>/dev/null; then
  exit 0
fi

message=$(echo "$input" | jq -r '.message // "Permission needed"')
cwd=$(echo "$input" | jq -r '.cwd // ""')
session_id=$(echo "$input" | jq -r '.session_id // ""')

# Derive project name from git root or cwd
project_name=""
if [[ -n "$cwd" ]]; then
  project_root=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null || true)
  if [[ -n "$project_root" ]]; then
    project_name=$(basename "$project_root")
  else
    project_name=$(basename "$cwd")
  fi
fi
project_name="${project_name:-Unknown}"

# Write session marker so the Stop hook knows a permission prompt occurred
if [[ -n "$session_id" ]]; then
  touch "/tmp/claude-hook-session-${session_id}"
fi

# Suppress notifications during meetings (Zoom, mic active)
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if ! "$HOOK_DIR/is-in-meeting.sh"; then
  # Send macOS notification
  if command -v terminal-notifier &>/dev/null; then
    terminal-notifier -title "Claude Code" -subtitle "$project_name" \
      -message "$message" -activate com.googlecode.iterm2
  fi

  # Speak the notification
  say "$project_name: $message" &
fi
