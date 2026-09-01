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

# Attach a live tmux session in a fresh iTerm control-mode window.
# The socket is a tmux -L basename and the target is the tmux session NAME
# (not the Claude session id), both as emitted by locator via --json.
cmd_attach() {
    local socket="$1" sess="$2" esock esess
    esock=$(escape_shell_single "$socket"); esess=$(escape_shell_single "$sess")
    open_iterm_window "tmux -L '$esock' -CC attach -t '$esess'" && echo ok
}

# Focus the iTerm session serving a given tty. locator's iTerm GUID is not an
# AppleScript session id, so match on tty (which locator does emit) instead.
focus_iterm() {   # <tty>  (bare "ttysNNN" from locator, or "/dev/ttysNNN")
    local tty="$1" want escaped
    [ -n "$tty" ] || die "usage: focus-iterm <tty>"
    # locator strips /dev/; iTerm's AppleScript `tty of s` is the full device
    # path — normalize to that so the comparison matches.
    want="/dev/${tty#/dev/}"
    escaped=$(escape_applescript "$want")
    osascript 2>/dev/null <<OSA >/dev/null || die "iTerm session not found for tty: $tty"
tell application "iTerm"
  activate
  repeat with w in windows
    repeat with t in tabs of w
      repeat with s in sessions of t
        if (tty of s) is "$escaped" then
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

# Focus a tmux pane. socket is a -L basename; pane_id is a tmux pane target.
focus_tmux() {    # <socket> <pane_id>
    local socket="$1" pane_id="$2"
    [ -n "$socket" ] && [ -n "$pane_id" ] || die "usage: focus-tmux <socket> <pane_id>"
    tmux -L "$socket" select-window -t "$pane_id" 2>/dev/null || \
        die "tmux window not found: $pane_id (socket $socket)"
    tmux -L "$socket" select-pane   -t "$pane_id" 2>/dev/null || true
    tmux -L "$socket" switch-client -t "$pane_id" 2>/dev/null || true
    echo ok
}

# When sourced by tests, stop here with all helpers defined.
if [ -n "${SESSION_OPEN_LIB_ONLY:-}" ]; then
    return 0 2>/dev/null || exit 0
fi

case "${1:-}" in
    open)        shift; [ $# -ge 2 ] || die "usage: open <cwd> <id> [--fork]"; cmd_open "$@" ;;
    attach)      shift; [ $# -ge 2 ] || die "usage: attach <socket> <session>"; cmd_attach "$@" ;;
    focus-tmux)  shift; [ $# -ge 2 ] || die "usage: focus-tmux <socket> <pane_id>"; focus_tmux "$@" ;;
    focus-iterm) shift; [ $# -ge 1 ] || die "usage: focus-iterm <tty>"; focus_iterm "$@" ;;
    "")          die "usage: session-open.sh {open|attach|focus-tmux|focus-iterm} …" ;;
    *)           die "unknown subcommand: $1" ;;
esac
