#!/bin/bash
# Tests for the SP3 SessionStart/SessionEnd hook scripts.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REC="$HERE/../hooks/record-session.sh"
RM="$HERE/../hooks/remove-session.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export CLAUDE_SM_HOME="$TMP"
fails=0
check() { if eval "$2"; then echo "ok - $1"; else echo "FAIL - $1"; fails=$((fails+1)); fi; }

SID="11111111-2222-3333-4444-555555555555"
F="$TMP/sessions/$SID.json"

# 1. record with CLAUDE_PID set writes the four fields
echo "{\"session_id\":\"$SID\",\"cwd\":\"/tmp/x\"}" | CLAUDE_PID=4242 bash "$REC"
check "record writes file" "[ -f '$F' ]"
check "has session_id" "grep -q '\"session_id\":\"$SID\"' '$F'"
check "has claude_pid" "grep -q '\"claude_pid\":4242' '$F'"
check "has cwd" "grep -q '\"cwd\":\"/tmp/x\"' '$F'"
check "has ts" "grep -q '\"ts\":[0-9]' '$F'"

# 2. re-record is idempotent (still one valid file, new pid)
echo "{\"session_id\":\"$SID\",\"cwd\":\"/tmp/x\"}" | CLAUDE_PID=4243 bash "$REC"
check "re-record updates pid" "grep -q '\"claude_pid\":4243' '$F'"

# 3. missing session_id -> no file, exit 0
echo '{"cwd":"/tmp/x"}' | CLAUDE_PID=4242 bash "$REC"; rc=$?
check "missing sid exits 0" "[ $rc -eq 0 ]"

# 4. remove deletes the file
echo "{\"session_id\":\"$SID\"}" | bash "$RM"
check "remove deletes file" "[ ! -f '$F' ]"

# 5. remove of nonexistent file still exits 0
echo "{\"session_id\":\"$SID\"}" | bash "$RM"; rc=$?
check "remove nonexistent exits 0" "[ $rc -eq 0 ]"

# 6. no CLAUDE_PID -> ppid-walk best-effort; must still exit 0 (may or may not write)
echo "{\"session_id\":\"$SID\",\"cwd\":\"/tmp/x\"}" | env -u CLAUDE_PID bash "$REC"; rc=$?
check "no CLAUDE_PID exits 0" "[ $rc -eq 0 ]"

[ "$fails" -eq 0 ] && { echo "ALL PASS"; exit 0; } || { echo "$fails FAILED"; exit 1; }
