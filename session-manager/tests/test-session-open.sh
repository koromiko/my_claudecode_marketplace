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

bash "$SCRIPT" attach "id3" >/dev/null
check "attach builds tmux -CC attach" "grep -q \"tmux -CC attach -t 'id3'\" \"$TMP/osa.txt\""

[ "$fails" -eq 0 ] && { echo ALL PASS; exit 0; } || { echo "$fails FAILED"; exit 1; }
