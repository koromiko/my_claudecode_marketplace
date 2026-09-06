#!/bin/bash
# fork-active-pane.sh — tmux key-binding entrypoint: fork the Claude Code session
# running in a given pane into a new split beside it.
#
# Usage (from ~/.tmux.conf):
#   bind-key F run-shell "/abs/path/to/fork-active-pane.sh '#{pane_id}'"
#
# Why resolve from the PANE, not the environment: a tmux `run-shell` command runs
# detached from the active pane and does NOT inherit its CLAUDE_CODE_SESSION_ID,
# so the session must be looked up from the pane id via locator.py (SP1).
#
# Tests may override the resolver/forker via FAP_LOCATOR / FAP_FORK env vars.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCATOR="${FAP_LOCATOR:-$SCRIPT_DIR/locator.py}"
FORK="${FAP_FORK:-$SCRIPT_DIR/fork-iterm.sh}"

# A key-binding has no stdout the user sees; route status to the tmux status line.
# Also output to stderr so tests can capture the message.
notify() { echo "$1" >&2; tmux display-message "$1" 2>/dev/null || true; }

PANE_ID="${1:-}"
if [ -z "$PANE_ID" ]; then
    echo "Error: no pane id. Usage: fork-active-pane.sh '#{pane_id}'" >&2
    exit 2
fi

if [ -z "${TMUX:-}" ]; then
    echo "Error: fork-active-pane.sh must run inside tmux (\$TMUX unset)." >&2
    exit 2
fi

# Socket basename from $TMUX (e.g. /private/tmp/tmux-501/default,2611,7 -> default).
SOCKET="$(basename "${TMUX%%,*}")"
ADDR="tmux:${SOCKET}:${PANE_ID}"

# Resolve the interactive session in that pane (SP1).
RESOLVE_OUT="$(python3 "$LOCATOR" resolve --pane "$ADDR" 2>/dev/null)"
RESOLVE_RC=$?

# Classify the three SP1 return shapes: object -> session_id ; array -> AMBIGUOUS ;
# [] / parse failure / locator error -> NONE.
if [ "$RESOLVE_RC" -eq 0 ]; then
    SESSION_ID="$(printf '%s' "$RESOLVE_OUT" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    print("NONE"); sys.exit()
if isinstance(data, list):
    print("AMBIGUOUS" if data else "NONE")
elif isinstance(data, dict) and data.get("session_id"):
    print(data["session_id"])
else:
    print("NONE")
')"
else
    SESSION_ID="NONE"
fi

if [ "$SESSION_ID" = "NONE" ]; then
    notify "No Claude session in this pane to fork."
    exit 0
fi
if [ "$SESSION_ID" = "AMBIGUOUS" ]; then
    notify "Multiple Claude sessions in this pane — can't disambiguate."
    exit 1
fi

# Fork that session into a split beside the focused pane (reuse fork-iterm.sh).
ERRF="$(mktemp -t fork-active-pane.XXXXXX)"
MANAGED_ID="$("$FORK" --session-id "$SESSION_ID" --target-pane "$PANE_ID" --quiet 2>"$ERRF")"
FORK_RC=$?

if [ "$FORK_RC" -eq 0 ] && [ -n "$MANAGED_ID" ]; then
    notify "Forked → $MANAGED_ID"
    echo "$MANAGED_ID"
    rm -f "$ERRF"
    exit 0
else
    if grep -q "no transcript found" "$ERRF" 2>/dev/null; then
        notify "No saved conversation in this pane yet — nothing to fork."
    else
        notify "Fork failed: $(head -1 "$ERRF" 2>/dev/null)"
    fi
    cat "$ERRF" >&2 2>/dev/null || true
    rm -f "$ERRF"
    exit 1
fi
