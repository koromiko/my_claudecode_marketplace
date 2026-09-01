#!/bin/bash
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/../scripts/session-open.sh"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
fails=0
check() { if eval "$2"; then echo "ok - $1"; else echo "FAIL - $1"; fails=$((fails+1)); fi; }

# fake osascript captures the AppleScript it receives
cat > "$TMP/osascript" <<'FAKE'
#!/bin/bash
cat > "$OSA_CAPTURE"
echo "1"
FAKE
chmod +x "$TMP/osascript"
export PATH="$TMP:$PATH" OSA_CAPTURE="$TMP/osa.txt"

bash "$SCRIPT" open "/tmp/my proj" "id1" >/dev/null
check "open builds resume command" "grep -q \"cd '/tmp/my proj' && claude -r 'id1'\" \"$TMP/osa.txt\""
check "open uses a new iTerm window" "grep -q 'create window with default profile' \"$TMP/osa.txt\""

bash "$SCRIPT" open "/tmp/p" "id2" --fork >/dev/null
check "open --fork adds --fork-session" "grep -q \"claude -r 'id2' --fork-session\" \"$TMP/osa.txt\""

# attach takes a tmux -L socket basename and the tmux SESSION NAME.
bash "$SCRIPT" attach "default" "mysess" >/dev/null
check "attach builds tmux -L -CC attach with session name" \
    "grep -q \"tmux -L 'default' -CC attach -t 'mysess'\" \"$TMP/osa.txt\""

# focus tests: set up fake tmux
cat > "$TMP/tmux" <<'FAKE'
#!/bin/bash
echo "$@" >> "$TMUX_CAPTURE"
FAKE
chmod +x "$TMP/tmux"
export TMUX_CAPTURE="$TMP/tmux.txt"

# focus-iterm matches on tty (locator's iTerm GUID is not an AppleScript id).
# locator emits a BARE tty ("ttysNNN"); AppleScript `tty of s` is the full
# device path, so focus-iterm must normalize to "/dev/ttysNNN" for the compare.
bash "$SCRIPT" focus-iterm "ttys009" >/dev/null
check "focus-iterm matches by tty" "grep -qi 'tty of s' \"$TMP/osa.txt\""
check "focus-iterm normalizes bare tty to /dev path" "grep -q '/dev/ttys009' \"$TMP/osa.txt\""

# focus-tmux uses -L <socket> (basename), not -S, against the pane id.
bash "$SCRIPT" focus-tmux "default" "%3" >/dev/null
check "focus-tmux uses -L socket basename" "grep -q -- '-L default' \"$TMUX_CAPTURE\""
check "focus-tmux selects the pane id" "grep -q '%3' \"$TMUX_CAPTURE\""
check "focus-tmux does not use -S" "! grep -q -- '-S ' \"$TMUX_CAPTURE\""

bash "$SCRIPT" bogus-cmd >/dev/null 2>&1; rc=$?
check "unknown subcommand errors" "[ $rc -ne 0 ]"

[ "$fails" -eq 0 ] && { echo ALL PASS; exit 0; } || { echo "$fails FAILED"; exit 1; }
