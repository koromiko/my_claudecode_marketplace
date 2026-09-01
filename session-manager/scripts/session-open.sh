#!/usr/bin/env bash
# session-open.sh — terminal actions for the sessions web UI (macOS/iTerm/tmux).
set -uo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Reuse escaping helpers from tmux-cc-attach's lib section.
TMUX_CC_LIB_ONLY=1 . "$SELF_DIR/tmux-cc-attach"

die() { echo "$*" >&2; exit 1; }

# Open a command in a fresh iTerm window; dies on failure.
open_iterm_window() {
    local cmd="$1" escaped out
    escaped=$(escape_applescript "$cmd")
    out=$(osascript 2>/dev/null <<OSA
tell application "iTerm"
  activate
  set w to (create window with default profile)
  tell current session of w to write text "$escaped"
  return (id of w) as string
end tell
OSA
)
    [ -n "$out" ] || die "failed to open iTerm window"
}

cmd_open() {
    local cwd="$1" sid="$2" fork="${3:-}" ecwd esid line
    ecwd=$(escape_shell_single "$cwd"); esid=$(escape_shell_single "$sid")
    line="cd '$ecwd' && claude -r '$esid'"
    [ "$fork" = "--fork" ] && line="$line --fork-session"
    open_iterm_window "$line" && echo ok
}

cmd_attach() {
    local sid="$1" esid
    esid=$(escape_shell_single "$sid")
    open_iterm_window "tmux -CC attach -t '$esid'" && echo ok
}

focus_iterm() {   # $1 = iTerm session GUID
    local guid="$1" escaped
    escaped=$(escape_applescript "$guid")
    osascript 2>/dev/null <<OSA >/dev/null || die "iTerm session not found: $guid"
tell application "iTerm"
  activate
  repeat with w in windows
    repeat with t in tabs of w
      repeat with s in sessions of t
        if (id of s) is "$escaped" then
          tell s to select
          tell t to select
          set index of w to 1
          return "ok"
        end if
      end repeat
    end repeat
  end repeat
  error "not found"
end tell
OSA
    echo ok
}

focus_tmux() {    # $1 = "<socket>:<pane_id>"
    local rest="$1" socket pane_id
    socket="${rest%%:*}"; pane_id="${rest#*:}"
    [ -n "$socket" ] && [ -n "$pane_id" ] || die "bad tmux pane: $rest"
    tmux -S "$socket" select-window -t "$pane_id" 2>/dev/null || \
        die "tmux window not found: $pane_id"
    tmux -S "$socket" select-pane   -t "$pane_id" 2>/dev/null || true
    tmux -S "$socket" switch-client -t "$pane_id" 2>/dev/null || true
    echo ok
}

cmd_focus() {
    local pane="${1:-}"
    [ -n "$pane" ] || die "usage: focus <pane>"
    case "$pane" in
        iterm:*) focus_iterm "${pane#iterm:}" ;;
        tmux:*)  focus_tmux  "${pane#tmux:}" ;;
        *)       die "cannot focus host for pane: $pane" ;;
    esac
}

# When sourced by tests, stop here with all helpers defined.
if [ -n "${SESSION_OPEN_LIB_ONLY:-}" ]; then
    return 0 2>/dev/null || exit 0
fi

case "${1:-}" in
    open)   shift; [ $# -ge 2 ] || die "usage: open <cwd> <id> [--fork]"; cmd_open "$@" ;;
    attach) shift; [ $# -ge 1 ] || die "usage: attach <id>"; cmd_attach "$@" ;;
    focus)  shift; cmd_focus "$@" ;;          # defined in Task 3
    "")     die "usage: session-open.sh {open|attach|focus} …" ;;
    *)      die "unknown subcommand: $1" ;;
esac
