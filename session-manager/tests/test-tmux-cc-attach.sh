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

cmd=$(resume_attach_command "/tmp/my proj" "id'x")
check "attach cmd cwd"  "printf '%s' \"\$cmd\" | grep -q \"new-session -c '/tmp/my proj'\""
check "attach cmd id"   "printf '%s' \"\$cmd\" | grep -q \"claude -r 'id'\\\\\\\\''x'\""

mkdir -p "$(resume_dir)"
printf '{"session_id":"s1","cwd":"/tmp/a","ts_start":1,"ts_end":100,"reason":"logout"}\n' > "$(resume_dir)/s1.json"
line=$(read_resume_records)
check "read record joined" "[ \"\$line\" = 's1|/tmp/a|100|logout' ]"

# Integration: --resume-only -n prints a resume command for a fresh, resumable record.
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
out=$(TMUX_CC_LOCATOR=/nonexistent bash "$SCRIPT" --resume-only -n 2>/dev/null)
check "dry-run shows resumable" "printf '%s' \"\$out\" | grep -q \"claude -r 'livesid'\""
check "dry-run drops stale age" "! printf '%s' \"\$out\" | grep -q oldsid"
check "dry-run drops no-transcript" "! printf '%s' \"\$out\" | grep -q ghostsid"
check "dry-run does not prune stale record" "[ -f \"\$(resume_dir)/oldsid.json\" ]"
check "dry-run does not prune no-transcript record" "[ -f \"\$(resume_dir)/ghostsid.json\" ]"

bash "$SCRIPT" --since foo --resume-only -n >/dev/null 2>&1; rc=$?
check "--since non-numeric dies" "[ $rc -ne 0 ]"

[ "$fails" -eq 0 ] && { echo "ALL PASS"; exit 0; } || { echo "$fails FAILED"; exit 1; }
