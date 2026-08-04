#!/bin/bash
# Unit tests for write_fork_snapshot in fork-iterm.sh.
#
# The fork runs inside the forking turn, so the live transcript on disk ends
# mid-turn (its last row is the fork's own unresolved tool_use). The child must
# resume a copy cut at the last complete assistant turn instead.
#
# Run: bash session-manager/tests/test-fork-snapshot.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
export HOME="$TMP/home"
mkdir -p "$HOME"

FORK_LIB_ONLY=1 source "$SCRIPT_DIR/../scripts/fork-iterm.sh"

pass=0
fail=0
ok() { # got want label
    if [ "$1" = "$2" ]; then
        echo "PASS: $3"
        pass=$((pass + 1))
    else
        echo "FAIL: $3 (want='$2' got='$1')"
        fail=$((fail + 1))
    fi
}

DEST="$TMP/dest"
mkdir -p "$DEST"

rows_of() { grep -c . "$1"; }
has_type() { grep -c "\"type\":\"$2\"" "$1"; }

# --- Case 1: transcript captured mid-fork (trailing unresolved tool_use) -----
MID="$TMP/mid.jsonl"
cat > "$MID" <<'EOF'
{"type":"user","uuid":"u1","message":{"role":"user","content":"hello"}}
{"type":"assistant","uuid":"a1","message":{"role":"assistant","content":[{"type":"text","text":"hi"}]}}
{"type":"user","uuid":"u2","message":{"role":"user","content":"/session-manager:fork"}}
{"type":"assistant","uuid":"a2","message":{"role":"assistant","content":[{"type":"tool_use","id":"t1","name":"Bash"}]}}
{"type":"user","uuid":"u3","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"t1"}]}}
{"type":"assistant","uuid":"a3","message":{"role":"assistant","content":[{"type":"tool_use","id":"t2","name":"Bash"}]}}
{"type":"mode","mode":"plan"}
{"type":"permission-mode","permissionMode":"acceptEdits"}
EOF
MID_SUM=$(shasum "$MID" | awk '{print $1}')

SNAP_ID=$(write_fork_snapshot "$MID" "$DEST")
RC=$?
ok "$RC" "0" "mid-fork transcript yields a snapshot"
SNAP="$DEST/$SNAP_ID.jsonl"
ok "$([ -f "$SNAP" ] && echo yes || echo no)" "yes" "snapshot file written into dest dir"
# u1 + a1, then the carried-over mode rows: the incomplete turn (u2/a2/u3/a3) is cut.
ok "$(rows_of "$SNAP")" "4" "snapshot cut at the last complete assistant turn"
ok "$(grep -c '"uuid":"a1"' "$SNAP")" "1" "last complete assistant turn kept"
ok "$(grep -c '"uuid":"u2"' "$SNAP")" "0" "the fork's own user prompt dropped"
ok "$(grep -c 'tool_use' "$SNAP")" "0" "no unresolved tool_use in snapshot"
ok "$(has_type "$SNAP" mode)" "1" "mode carried over from after the cut"
ok "$(has_type "$SNAP" permission-mode)" "1" "permission-mode carried over from after the cut"
ok "$(shasum "$MID" | awk '{print $1}')" "$MID_SUM" "source transcript left untouched"

# --- Case 2: complete transcript (idle session, e.g. hotkey fork) ------------
DONE="$TMP/done.jsonl"
cat > "$DONE" <<'EOF'
{"type":"user","uuid":"u1","message":{"role":"user","content":"hello"}}
{"type":"assistant","uuid":"a1","message":{"role":"assistant","content":[{"type":"tool_use","id":"t1","name":"Bash"}]}}
{"type":"user","uuid":"u2","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"t1"}]}}
{"type":"assistant","uuid":"a2","message":{"role":"assistant","content":[{"type":"text","text":"done"}]}}
{"type":"last-prompt","leafUuid":"u1"}
EOF
SNAP_ID=$(write_fork_snapshot "$DONE" "$DEST")
SNAP="$DEST/$SNAP_ID.jsonl"
ok "$(rows_of "$SNAP")" "4" "complete transcript keeps every message row"
ok "$(grep -c '"uuid":"a2"' "$SNAP")" "1" "final assistant turn kept"

# --- Case 3: turn-opening rows are not cut points ----------------------------
OPENERS="$TMP/openers.jsonl"
cat > "$OPENERS" <<'EOF'
{"type":"user","uuid":"u1","message":{"role":"user","content":"hello"}}
{"type":"assistant","uuid":"a1","message":{"role":"assistant","content":[{"type":"text","text":"hi"}]}}
{"type":"user","uuid":"u2","message":{"role":"user","content":"and now?"}}
{"type":"assistant","uuid":"a2","message":{"role":"assistant","content":[{"type":"thinking","thinking":"pondering"}]}}
EOF
SNAP_ID=$(write_fork_snapshot "$OPENERS" "$DEST")
SNAP="$DEST/$SNAP_ID.jsonl"
ok "$(rows_of "$SNAP")" "2" "thinking-only row does not end a turn"
ok "$(grep -c '"uuid":"a2"' "$SNAP")" "0" "trailing thinking block dropped"

# A sidechain (subagent) reply is not the parent conversation's turn boundary.
SIDE="$TMP/side.jsonl"
cat > "$SIDE" <<'EOF'
{"type":"user","uuid":"u1","message":{"role":"user","content":"hello"}}
{"type":"assistant","uuid":"a1","message":{"role":"assistant","content":[{"type":"text","text":"hi"}]}}
{"type":"assistant","uuid":"s1","isSidechain":true,"message":{"role":"assistant","content":[{"type":"text","text":"subagent done"}]}}
EOF
SNAP_ID=$(write_fork_snapshot "$SIDE" "$DEST")
ok "$(rows_of "$DEST/$SNAP_ID.jsonl")" "2" "sidechain reply is not a cut point"

# --- Case 4: in_flight=1 drops the whole unfinished turn ---------------------
# Shape of a real /fork turn: typed prompt, the command's own expansion (isMeta),
# a line of assistant prose, then the tool calls that run the fork.
SELF="$TMP/self.jsonl"
cat > "$SELF" <<'EOF'
{"type":"user","uuid":"u1","message":{"role":"user","content":"hello"}}
{"type":"assistant","uuid":"a1","message":{"role":"assistant","content":[{"type":"text","text":"hi"}]}}
{"type":"user","uuid":"u2","message":{"role":"user","content":"<command-name>/session-manager:fork</command-name>"}}
{"type":"user","uuid":"u3","isMeta":true,"message":{"role":"user","content":[{"type":"text","text":"# Fork Session"}]}}
{"type":"assistant","uuid":"a2","message":{"role":"assistant","content":[{"type":"text","text":"I'll resolve the session first."}]}}
{"type":"assistant","uuid":"a3","message":{"role":"assistant","content":[{"type":"tool_use","id":"t1","name":"Bash"}]}}
EOF
SNAP_ID=$(write_fork_snapshot "$SELF" "$DEST" 1)
SNAP="$DEST/$SNAP_ID.jsonl"
ok "$(rows_of "$SNAP")" "2" "in_flight cut lands before the fork's own prompt"
ok "$(grep -c '"uuid":"a2"' "$SNAP")" "0" "mid-turn prose inside the unfinished turn dropped"
ok "$(grep -c 'session-manager:fork' "$SNAP")" "0" "the fork request is not carried into the fork"
# Without the flag the same transcript keeps that prose — the caller is a hotkey
# fork of another session, whose last turn may legitimately have ended there.
SNAP_ID=$(write_fork_snapshot "$SELF" "$DEST")
ok "$(grep -c '"uuid":"a2"' "$DEST/$SNAP_ID.jsonl")" "1" "without the flag the last assistant reply is kept"

# --- Case 5: nothing complete to fork from ----------------------------------
BARE="$TMP/bare.jsonl"
cat > "$BARE" <<'EOF'
{"type":"user","uuid":"u1","message":{"role":"user","content":"/session-manager:fork"}}
{"type":"assistant","uuid":"a1","message":{"role":"assistant","content":[{"type":"tool_use","id":"t1","name":"Bash"}]}}
EOF
BEFORE=$(ls "$DEST" | wc -l | tr -d ' ')
OUT=$(write_fork_snapshot "$BARE" "$DEST")
RC=$?
ok "$([ "$RC" -ne 0 ] && echo nonzero || echo zero)" "nonzero" "no complete turn => no snapshot (caller falls back)"
ok "$OUT" "" "no session id printed when there is nothing to cut at"
ok "$(ls "$DEST" | wc -l | tr -d ' ')" "$BEFORE" "no file written when there is nothing to cut at"

# --- Case 6: unreadable transcript ------------------------------------------
OUT=$(write_fork_snapshot "$TMP/missing.jsonl" "$DEST" 2>/dev/null)
RC=$?
ok "$([ "$RC" -ne 0 ] && echo nonzero || echo zero)" "nonzero" "missing transcript => nonzero exit"

# --- Case 7: deferred sweep of spent snapshots -------------------------------
# Snapshots outlive the fork on purpose (the child reads them seconds into
# startup), so cleanup is a later fork's job.
rm -f "$SNAPSHOT_LIST"
touch "$DEST/old.jsonl" "$DEST/fresh.jsonl"
NOW=$(date +%s)
printf '%s %s\n' "$((NOW - SNAPSHOT_TTL - 60))" "$DEST/old.jsonl" >> "$SNAPSHOT_LIST"
snapshot_track "$DEST/fresh.jsonl"
snapshot_sweep
ok "$([ -f "$DEST/old.jsonl" ] && echo yes || echo no)" "no" "snapshot past its TTL is swept"
ok "$([ -f "$DEST/fresh.jsonl" ] && echo yes || echo no)" "yes" "snapshot a child may still be reading is kept"
ok "$(grep -c . "$SNAPSHOT_LIST")" "1" "swept entry dropped from the list"
ok "$(grep -c 'fresh.jsonl' "$SNAPSHOT_LIST")" "1" "kept entry stays in the list"

echo
echo "passed: $pass  failed: $fail"
[ "$fail" -eq 0 ]
