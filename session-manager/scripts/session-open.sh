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

# Raise the iTerm session whose controlling tty matches $1 (bare "ttysNNN" or
# "/dev/ttysNNN"). Returns 0 on a match (window raised), non-zero on no match —
# never dies, so callers decide whether a miss is fatal.
raise_iterm_tty() {   # <tty>
    local tty="$1" want escaped
    [ -n "$tty" ] || return 1
    # locator/tmux emit device names both bare and /dev/-prefixed; iTerm's
    # AppleScript `tty of s` is the full device path — normalize to that.
    want="/dev/${tty#/dev/}"
    escaped=$(escape_applescript "$want")
    osascript 2>/dev/null >/dev/null <<OSA
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
}

# Focus the iTerm session serving a given tty. locator's iTerm GUID is not an
# AppleScript session id, so match on tty (which locator does emit) instead.
focus_iterm() {   # <tty>  (bare "ttysNNN" from locator, or "/dev/ttysNNN")
    local tty="$1"
    [ -n "$tty" ] || die "usage: focus-iterm <tty>"
    raise_iterm_tty "$tty" || die "iTerm session not found for tty: $tty"
    echo ok
}

# Focus a tmux pane. socket is a -L basename; pane_id is a tmux pane target.
# Under tmux -CC every project has its own client attached to its own session,
# so we navigate WITHIN the pane's own session (select-window/select-pane) and
# never switch-client — a bare `switch-client -t <pane>` retargets whatever
# client tmux last used, hijacking another project's iTerm window. To surface
# the pane we raise the iTerm window of a client already attached to that
# session (the -CC client's tty is a real iTerm session tty; the tmux pane pty
# is not), preferring the most-recently-active client.
focus_tmux() {    # <socket> <pane_id>
    local socket="$1" pane_id="$2" sess ctty
    [ -n "$socket" ] && [ -n "$pane_id" ] || die "usage: focus-tmux <socket> <pane_id>"
    tmux -L "$socket" select-window -t "$pane_id" 2>/dev/null || \
        die "tmux window not found: $pane_id (socket $socket)"
    tmux -L "$socket" select-pane   -t "$pane_id" 2>/dev/null || true
    sess=$(tmux -L "$socket" display-message -p -t "$pane_id" '#{session_id}' 2>/dev/null)
    if [ -n "$sess" ]; then
        ctty=$(tmux -L "$socket" list-clients -t "$sess" \
                   -F '#{client_activity} #{client_tty}' 2>/dev/null \
               | sort -rn | head -1 | cut -d' ' -f2-)
        [ -n "$ctty" ] && raise_iterm_tty "$ctty"
    fi
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
