#!/bin/bash
# Unit tests for the fork-verification helpers in fork-iterm.sh.
#
# Covers the pre-flight resume check that is the core of the fix: a forked
# `claude -r <id>` only resolves a session stored under the current project, so
# we must confirm the detected session id has a transcript under WORKING_DIR
# before spawning the fork (otherwise it fails with "Resuming session failed").
#
# Run: bash session-manager/tests/test-fork-verify.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Sandbox HOME so sourcing the script (which mkdir's the registry dir, and where
# project_sessions_dir resolves under $HOME) never touches the real ~/.claude.
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
export HOME="$TMP/home"
mkdir -p "$HOME"

# Source helpers only — the guard stops before the fork flow runs.
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

WD="$TMP/proj"
mkdir -p "$WD"
SESS=$(project_sessions_dir "$WD")
mkdir -p "$SESS"

# project_sessions_dir lands under the sandboxed HOME.
case "$SESS" in
    "$HOME"/.claude/projects/*) ok "yes" "yes" "project_sessions_dir is under HOME/.claude/projects" ;;
    *) ok "$SESS" "<under HOME/.claude/projects>" "project_sessions_dir is under HOME/.claude/projects" ;;
esac

# A session whose transcript exists in this project dir is resumable here.
touch "$SESS/aaaa.jsonl"
session_resumable_in "aaaa" "$WD" && r=yes || r=no
ok "$r" "yes" "session_resumable_in: true when transcript exists in the project dir"

# A session id with no transcript here (e.g. a cross-project debug-symlink id) is NOT.
session_resumable_in "ffff" "$WD" && r=yes || r=no
ok "$r" "no" "session_resumable_in: false when no transcript in the project dir"

# A session that exists ONLY under a different project is not resumable here —
# this is exactly the "Resuming session failed" cross-project case.
OTHER="$TMP/other"
mkdir -p "$OTHER"
mkdir -p "$(project_sessions_dir "$OTHER")"
touch "$(project_sessions_dir "$OTHER")/bbbb.jsonl"
session_resumable_in "bbbb" "$WD" && r=yes || r=no
ok "$r" "no" "session_resumable_in: false for a session that lives under another project"
session_resumable_in "bbbb" "$OTHER" && r=yes || r=no
ok "$r" "yes" "session_resumable_in: true in the project that actually owns the session"

# --- find_session_owner_file / session_launch_cwd ---
# These resolve a session by id across ALL projects and read its real launch cwd,
# which is how the fork finds where a session is resumable from regardless of pwd.
REAL_CWD="/Users/example/Project/demo_app"
# A realistic transcript: metadata lines first, then an event carrying cwd.
{
  printf '{"type":"last-prompt","sessionId":"dddd"}\n'
  printf '{"type":"attachment","sessionId":"dddd","cwd":"%s","version":"x"}\n' "$REAL_CWD"
} > "$SESS/dddd.jsonl"

found=$(find_session_owner_file "dddd")
ok "$found" "$SESS/dddd.jsonl" "find_session_owner_file: locates the owning transcript by id"
ok "$(find_session_owner_file "nope")" "" "find_session_owner_file: empty when no project owns the id"
ok "$(session_launch_cwd "$SESS/dddd.jsonl")" "$REAL_CWD" "session_launch_cwd: reads the real launch cwd from the record"
ok "$(session_launch_cwd "$SESS/aaaa.jsonl")" "" "session_launch_cwd: empty when no cwd recorded"

echo "----"
echo "PASS=$pass FAIL=$fail"
[ "$fail" -eq 0 ]
