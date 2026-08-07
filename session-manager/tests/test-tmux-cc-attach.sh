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
# An autonomous (teammate/agent) session must be excluded from the list.
mkdir -p "$CLAUDE_PROJECTS_DIR/-tmp-auto2"
printf '{"type":"agent-setting"}\n' > "$CLAUDE_PROJECTS_DIR/-tmp-auto2/autosid2.jsonl"
printf '{"session_id":"autosid2","cwd":"/tmp/auto2","ts_start":1,"ts_end":%s,"reason":"other"}\n' "$NOW2" \
    > "$(resume_dir)/autosid2.json"
out=$(TMUX_CC_LOCATOR=/nonexistent bash "$SCRIPT" --resume-only -n 2>/dev/null)
check "dry-run shows resumable" "printf '%s' \"\$out\" | grep -q \"claude -r 'livesid'\""
check "dry-run drops stale age" "! printf '%s' \"\$out\" | grep -q oldsid"
check "dry-run drops no-transcript" "! printf '%s' \"\$out\" | grep -q ghostsid"
check "dry-run drops autonomous" "! printf '%s' \"\$out\" | grep -q autosid2"
check "dry-run has no selection prompt" "! printf '%s' \"\$out\" | grep -q 'Select projects'"
check "dry-run does not prune stale record" "[ -f \"\$(resume_dir)/oldsid.json\" ]"
check "dry-run does not prune no-transcript record" "[ -f \"\$(resume_dir)/ghostsid.json\" ]"

# Report: the resumable session must appear under its project group. Anchor
# on the report's own numbered group-header line ("  [N] <group>", nothing
# else) so this doesn't pass merely because the dry-run commands list also
# mentions the project (it prints "# resume ... @ <group>" regardless of the
# report loop).
live_group=$(project_of_dir /tmp/live)
check "report shows project group for /tmp/live" \
    "printf '%s\n' \"\$out\" | grep -E '^  \[[0-9]+\] ' | sed -E 's/^  \[[0-9]+\] //' | grep -qxF \"\$live_group\""
check "report shows resume marker line for livesid" \
    "printf '%s' \"\$out\" | grep -q '^ *livesid ' && printf '%s' \"\$out\" | grep -q '\\[resume'"

bash "$SCRIPT" --since foo --resume-only -n >/dev/null 2>&1; rc=$?
check "--since non-numeric dies" "[ $rc -ne 0 ]"

# parse_group_selection: empty=all, subset, comma form, none(rc2), bad(rc1)
check "sel empty = all" "[ \"\$(parse_group_selection '' 3 | tr '\n' ' ')\" = '1 2 3 ' ]"
check "sel subset"      "[ \"\$(parse_group_selection '1 3' 3 | tr '\n' ' ')\" = '1 3 ' ]"
check "sel comma"       "[ \"\$(parse_group_selection '2,3' 3 | tr '\n' ' ')\" = '2 3 ' ]"
parse_group_selection 'n' 3 >/dev/null; check "sel none rc2" "[ $? -eq 2 ]"
parse_group_selection '5' 3 >/dev/null; check "sel oob rc1"  "[ $? -eq 1 ]"
parse_group_selection 'x' 3 >/dev/null; check "sel nonnum rc1" "[ $? -eq 1 ]"

# parse_group_selection: leading-zero tokens must normalize to decimal, not
# be read as octal (bash treats a leading-0 numeric literal as octal in
# arithmetic context, e.g. array subscripts).
check "sel zero-padded 008 = 8"  "[ \"\$(parse_group_selection '008' 10 | tr '\n' ' ')\" = '8 ' ]"
check "sel zero-padded 010 = 10" "[ \"\$(parse_group_selection '010' 10 | tr '\n' ' ')\" = '10 ' ]"
check "sel mixed zero-padded"    "[ \"\$(parse_group_selection '01 03' 5 | tr '\n' ' ')\" = '1 3 ' ]"

[ "$fails" -eq 0 ] && { echo "ALL PASS"; exit 0; } || { echo "$fails FAILED"; exit 1; }
