#!/bin/bash
# Unit tests for tmux-cc-attach resume helpers (sourced lib-only).
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/../scripts/tmux-cc-attach"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export CLAUDE_SM_HOME="$TMP"
export CLAUDE_PROJECTS_DIR="$TMP/projects"
fails=0
check() { if eval "$2"; then echo "ok - $1"; else echo "FAIL - $1"; fails=$((fails+1)); fi; }

TMUX_CC_LIB_ONLY=1 . "$SCRIPT"
trap 'rm -rf "$TMP"' EXIT

NOW=1785000000
check "within age true"  "resume_within_age $((NOW-86400)) $NOW 14"
check "within age false" "! resume_within_age $((NOW-15*86400)) $NOW 14"
check "within age junk"  "! resume_within_age '' $NOW 14"

mkdir -p "$CLAUDE_PROJECTS_DIR/-tmp-proj"
touch "$CLAUDE_PROJECTS_DIR/-tmp-proj/abc123.jsonl"
check "resumable true"  "resume_is_resumable abc123 \"\$(transcript_root)\""
check "resumable false" "! resume_is_resumable nope \"\$(transcript_root)\""

# resume_is_autonomous: a transcript carrying an agent-setting record is
# autonomous; a plain human transcript is not; a missing transcript is not.
mkdir -p "$CLAUDE_PROJECTS_DIR/-tmp-auto"
printf '{"type":"agent-setting"}\n{"type":"user"}\n' > "$CLAUDE_PROJECTS_DIR/-tmp-auto/autosid.jsonl"
printf '{"type":"user"}\n{"type":"assistant"}\n'     > "$CLAUDE_PROJECTS_DIR/-tmp-auto/humansid.jsonl"
check "autonomous true"    "resume_is_autonomous autosid \"\$(transcript_root)\""
check "autonomous false"   "! resume_is_autonomous humansid \"\$(transcript_root)\""
check "autonomous missing" "! resume_is_autonomous nope \"\$(transcript_root)\""

mkdir -p "$(resume_dir)"
printf '{"session_id":"s1","cwd":"/tmp/a","ts_start":1,"ts_end":100,"reason":"logout"}\n' > "$(resume_dir)/s1.json"
line=$(read_resume_records)
check "read record joined" "[ \"\$line\" = 's1|/tmp/a|100|logout' ]"

# Default (non-json) invocation execs the web server, passing recognized
# web-launch flags through untouched.
cat > "$TMP/python3" <<'FAKE'
#!/bin/bash
echo "$@" > "$PY_CAPTURE"
FAKE
chmod +x "$TMP/python3"; export PY_CAPTURE="$TMP/py.txt"
PATH="$TMP:$PATH" bash "$SCRIPT" --port 8790 --no-open >/dev/null 2>&1
check "no-json execs web server" "grep -q 'tmux-cc-web.py' \"\$PY_CAPTURE\""
check "web-launch passes flags through" "grep -q -- '--port 8790 --no-open' \"\$PY_CAPTURE\""
check "removed --resume-only errors" "! bash \"\$SCRIPT\" --resume-only >/dev/null 2>&1"

NOW2=$(date +%s)
rm -f "$(resume_dir)"/*.json
mkdir -p "$CLAUDE_PROJECTS_DIR/-tmp-live"
touch "$CLAUDE_PROJECTS_DIR/-tmp-live/livesid.jsonl"
printf '{"session_id":"livesid","cwd":"/tmp/live","ts_start":1,"ts_end":%s,"reason":"logout"}\n' "$NOW2" \
    > "$(resume_dir)/livesid.json"
# A stale (old) record and a no-transcript record must be dropped.
printf '{"session_id":"oldsid","cwd":"/tmp/old","ts_start":1,"ts_end":1,"reason":"other"}\n' \
    > "$(resume_dir)/oldsid.json"
printf '{"session_id":"ghostsid","cwd":"/tmp/ghost","ts_start":1,"ts_end":%s,"reason":"other"}\n' "$NOW2" \
    > "$(resume_dir)/ghostsid.json"
# An autonomous (teammate/agent) session must be excluded from the list.
mkdir -p "$CLAUDE_PROJECTS_DIR/-tmp-auto2"
printf '{"type":"agent-setting"}\n' > "$CLAUDE_PROJECTS_DIR/-tmp-auto2/autosid2.jsonl"
printf '{"session_id":"autosid2","cwd":"/tmp/auto2","ts_start":1,"ts_end":%s,"reason":"other"}\n' "$NOW2" \
    > "$(resume_dir)/autosid2.json"

bash "$SCRIPT" --since foo --json >/dev/null 2>&1; rc=$?
check "--since non-numeric dies" "[ $rc -ne 0 ]"

# --json emits a JSON array of resumable sessions, honoring the same filters.
jout=$(TMUX_CC_LOCATOR=/nonexistent bash "$SCRIPT" --json 2>/dev/null)
check "--json is valid array" \
    "printf '%s' \"\$jout\" | jq -e 'type==\"array\"' >/dev/null"
check "--json includes livesid" \
    "printf '%s' \"\$jout\" | jq -e '.[]|select(.session_id==\"livesid\")' >/dev/null"
check "--json livesid cwd" \
    "[ \"\$(printf '%s' \"\$jout\" | jq -r '.[]|select(.session_id==\"livesid\").cwd')\" = '/tmp/live' ]"
check "--json livesid ts_end numeric" \
    "printf '%s' \"\$jout\" | jq -e '.[]|select(.session_id==\"livesid\").ts_end|type==\"number\"' >/dev/null"
check "--json drops stale/ghost/auto" \
    "[ \"\$(printf '%s' \"\$jout\" | jq -r '[.[]|select(.session_id|IN(\"oldsid\",\"ghostsid\",\"autosid2\"))]|length')\" = '0' ]"
check "--json no report text" \
    "! printf '%s' \"\$jout\" | grep -q 'Attaching/resuming'"
check "--json ended carries status ended" \
    "[ \"\$(printf '%s' \"\$jout\" | jq -r '.[]|select(.session_id==\"livesid\").status')\" = 'ended' ]"

# --json with a live locator: interactive sessions with a transcript are emitted
# as status:"live"; child (subagent) sessions and transcript-less live processes
# are omitted; and a live id also present in the resume store appears once (live
# wins, no double-list).
mkdir -p "$CLAUDE_PROJECTS_DIR/-tmp-liveproc"
touch "$CLAUDE_PROJECTS_DIR/-tmp-liveproc/liveproc.jsonl"
STUB="$TMP/locstub.py"
cat > "$STUB" <<'PY'
import json
print(json.dumps([
    {"session_id": "liveproc", "cwd": "/tmp/liveproc", "role": "interactive", "leader_pid": 4242, "pane": "iterm:GUID-1", "host": "iterm"},
    {"session_id": "childproc", "cwd": "/tmp/child", "role": "child"},
    {"session_id": "notxsid", "cwd": "/tmp/notx", "role": "interactive"},
    {"session_id": "livesid", "cwd": "/tmp/live", "role": "interactive"},
]))
PY
ljout=$(TMUX_CC_LOCATOR="$STUB" bash "$SCRIPT" --json 2>/dev/null)
check "--json live is valid array" \
    "printf '%s' \"\$ljout\" | jq -e 'type==\"array\"' >/dev/null"
check "--json includes live interactive session" \
    "[ \"\$(printf '%s' \"\$ljout\" | jq -r '.[]|select(.session_id==\"liveproc\").status')\" = 'live' ]"
check "--json live carries leader pid" \
    "[ \"\$(printf '%s' \"\$ljout\" | jq -r '.[]|select(.session_id==\"liveproc\").pid')\" = '4242' ]"
check "--json omits child role session" \
    "printf '%s' \"\$ljout\" | jq -e '[.[]|select(.session_id==\"childproc\")]|length==0' >/dev/null"
check "--json omits transcript-less live session" \
    "printf '%s' \"\$ljout\" | jq -e '[.[]|select(.session_id==\"notxsid\")]|length==0' >/dev/null"
check "--json live id not double-listed" \
    "[ \"\$(printf '%s' \"\$ljout\" | jq -r '[.[]|select(.session_id==\"livesid\")]|length')\" = '1' ]"
check "--json live id resolves to live status" \
    "[ \"\$(printf '%s' \"\$ljout\" | jq -r '.[]|select(.session_id==\"livesid\").status')\" = 'live' ]"
check "--json live carries pane" \
    "[ \"\$(printf '%s' \"\$ljout\" | jq -r '.[]|select(.session_id==\"liveproc\").pane')\" = 'iterm:GUID-1' ]"
check "--json live carries host" \
    "[ \"\$(printf '%s' \"\$ljout\" | jq -r '.[]|select(.session_id==\"liveproc\").host')\" = 'iterm' ]"

# --json is a read-only view: it must never prune resume records, even when a
# narrow --since window excludes them (regression: --since deleted stale files).
mkdir -p "$CLAUDE_PROJECTS_DIR/-tmp-keep"
touch "$CLAUDE_PROJECTS_DIR/-tmp-keep/keepsid.jsonl"
printf '{"session_id":"keepsid","cwd":"/tmp/keep","ts_start":1,"ts_end":%s,"reason":"other"}\n' "$((NOW2 - 5*86400))" \
    > "$(resume_dir)/keepsid.json"
TMUX_CC_LOCATOR=/nonexistent bash "$SCRIPT" --json --since 1 >/dev/null 2>&1
check "--json --since does not prune out-of-window record" "[ -f \"$(resume_dir)/keepsid.json\" ]"

[ "$fails" -eq 0 ] && { echo "ALL PASS"; exit 0; } || { echo "$fails FAILED"; exit 1; }
