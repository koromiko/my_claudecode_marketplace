#!/bin/bash
# SessionEnd hook (SP3 + resume): write a resume record, then delete this
# session's live-registry file. Never blocks the TUI.
set -u
input=$(cat)
command -v jq >/dev/null 2>&1 || exit 0
session_id=$(printf '%s' "$input" | jq -r '.session_id // ""')
[ -n "$session_id" ] || exit 0

base="${CLAUDE_SM_HOME:-$HOME/.claude/session-manager}"
start_file="$base/sessions/$session_id.json"

cwd=""; ts_start=""
if [ -f "$start_file" ]; then
    cwd=$(jq -r '.cwd // ""' "$start_file" 2>/dev/null)
    ts_start=$(jq -r '.ts // ""' "$start_file" 2>/dev/null)
fi
[ -n "$cwd" ] || cwd=$(printf '%s' "$input" | jq -r '.cwd // ""')
reason=$(printf '%s' "$input" | jq -r '.reason // ""')
ts_end=$(date +%s)
case "$ts_start" in ''|*[!0-9]*) ts_start="$ts_end" ;; esac

# Write the resume record only when we know the owning cwd (claude -r needs it).
if [ -n "$cwd" ]; then
    rdir="$base/resume"
    mkdir -p "$rdir" 2>/dev/null
    cwd_json=$(printf '%s' "$cwd" | jq -R .)
    reason_json=$(printf '%s' "$reason" | jq -R .)
    tmp=$(mktemp "$rdir/.tmp.XXXXXX" 2>/dev/null) && {
        printf '{"session_id":"%s","cwd":%s,"ts_start":%s,"ts_end":%s,"reason":%s}\n' \
            "$session_id" "$cwd_json" "$ts_start" "$ts_end" "$reason_json" > "$tmp"
        mv -f "$tmp" "$rdir/$session_id.json" 2>/dev/null || rm -f "$tmp"
    }
fi

rm -f "$start_file" 2>/dev/null
exit 0
