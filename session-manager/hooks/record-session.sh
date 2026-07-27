#!/bin/bash
# SessionStart hook (SP3): record {session_id, claude_pid, cwd, ts} so the locator can
# resolve an idle session that has no live tagged child process. Never blocks the TUI.
set -u
input=$(cat)
command -v jq >/dev/null 2>&1 || exit 0

session_id=$(printf '%s' "$input" | jq -r '.session_id // ""')
cwd=$(printf '%s' "$input" | jq -r '.cwd // ""')
[ -n "$session_id" ] || exit 0

# TUI pid: prefer CLAUDE_PID; else walk the ppid chain to the claude process.
claude_pid="${CLAUDE_PID:-}"
if [ -z "$claude_pid" ]; then
    pid="${PPID:-1}"
    i=0
    while [ "$i" -lt 20 ]; do
        case "$pid" in ''|*[!0-9]*) break ;; esac
        [ "$pid" -gt 1 ] || break
        comm=$(ps -o comm= -p "$pid" 2>/dev/null)
        case "$comm" in *claude*) claude_pid="$pid"; break ;; esac
        pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
        i=$((i + 1))
    done
fi
case "$claude_pid" in ''|*[!0-9]*) exit 0 ;; esac

dir="${CLAUDE_SM_HOME:-$HOME/.claude/session-manager}/sessions"
mkdir -p "$dir" 2>/dev/null || exit 0
ts=$(date +%s)
cwd_json=$(printf '%s' "$cwd" | jq -R .)
tmp=$(mktemp "$dir/.tmp.XXXXXX" 2>/dev/null) || exit 0
printf '{"session_id":"%s","claude_pid":%s,"cwd":%s,"ts":%s}\n' \
    "$session_id" "$claude_pid" "$cwd_json" "$ts" > "$tmp"
mv -f "$tmp" "$dir/$session_id.json" 2>/dev/null || rm -f "$tmp"
exit 0
