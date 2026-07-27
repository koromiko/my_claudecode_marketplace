#!/bin/bash
# SessionEnd hook (SP3): delete this session's registry file. Never blocks the TUI.
set -u
input=$(cat)
command -v jq >/dev/null 2>&1 || exit 0
session_id=$(printf '%s' "$input" | jq -r '.session_id // ""')
[ -n "$session_id" ] || exit 0
dir="${CLAUDE_SM_HOME:-$HOME/.claude/session-manager}/sessions"
rm -f "$dir/$session_id.json" 2>/dev/null
exit 0
