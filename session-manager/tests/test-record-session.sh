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

# 7. SessionEnd writes a resume record merging start ts and end reason
RSID="99999999-8888-7777-6666-555555555555"
echo "{\"session_id\":\"$RSID\",\"cwd\":\"/tmp/proj\"}" | CLAUDE_PID=7777 bash "$REC"
START_TS=$(jq -r '.ts' "$TMP/sessions/$RSID.json")
echo "{\"session_id\":\"$RSID\",\"cwd\":\"/tmp/proj\",\"reason\":\"logout\"}" | bash "$RM"
RF="$TMP/resume/$RSID.json"
check "resume record written" "[ -f '$RF' ]"
check "resume has session_id" "grep -q '\"session_id\":\"$RSID\"' '$RF'"
check "resume has cwd" "grep -q '\"cwd\":\"/tmp/proj\"' '$RF'"
check "resume ts_start from start record" "[ \"\$(jq -r .ts_start '$RF')\" = \"$START_TS\" ]"
check "resume has ts_end" "[ \"\$(jq -r .ts_end '$RF')\" -ge \"$START_TS\" ]"
check "resume has reason" "grep -q '\"reason\":\"logout\"' '$RF'"
check "start record deleted" "[ ! -f '$TMP/sessions/$RSID.json' ]"

# 8. Fallback: no start record -> cwd/reason from input, ts_start==ts_end
RSID2="12121212-3434-5656-7878-909090909090"
echo "{\"session_id\":\"$RSID2\",\"cwd\":\"/tmp/fb\",\"reason\":\"other\"}" | bash "$RM"
RF2="$TMP/resume/$RSID2.json"
check "fallback resume written" "[ -f '$RF2' ]"
check "fallback cwd from input" "grep -q '\"cwd\":\"/tmp/fb\"' '$RF2'"
check "fallback ts_start==ts_end" "[ \"\$(jq -r .ts_start '$RF2')\" = \"\$(jq -r .ts_end '$RF2')\" ]"

# 9. No cwd anywhere -> no resume record, exit 0
RSID3="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
echo "{\"session_id\":\"$RSID3\"}" | bash "$RM"; rc=$?
check "no-cwd remove exits 0" "[ $rc -eq 0 ]"
check "no-cwd writes no resume" "[ ! -f '$TMP/resume/$RSID3.json' ]"

[ "$fails" -eq 0 ] && { echo "ALL PASS"; exit 0; } || { echo "$fails FAILED"; exit 1; }
