#!/bin/bash
# Tests for fork-active-pane.sh using shimmed locator/fork (FAP_LOCATOR/FAP_FORK).
# Run: bash session-manager/tests/test-fork-active-pane.sh
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER="$SCRIPT_DIR/../scripts/fork-active-pane.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

pass=0; fail=0
ok() { if [ "$1" = "$2" ]; then echo "PASS: $3"; pass=$((pass+1)); else echo "FAIL: $3 (want='$2' got='$1')"; fail=$((fail+1)); fi; }

# A fake locator: prints whatever JSON / exit code the test puts in control files,
# and records the args it was called with.
FAKE_LOC="$TMP/locator.py"
cat > "$FAKE_LOC" <<'PY'
import os, sys
argf = os.environ.get("LOC_ARGS_OUT")
if argf:
    open(argf, "w").write(" ".join(sys.argv[1:]))
sys.stdout.write(os.environ.get("LOC_OUT", "[]"))
sys.exit(int(os.environ.get("LOC_RC", "0")))
PY

# A fake fork: echoes a managed id (or fails) and records its args.
FAKE_FORK="$TMP/fork.sh"
cat > "$FAKE_FORK" <<'SH'
#!/bin/bash
argf="${FORK_ARGS_OUT:-}"
[ -n "$argf" ] && echo "$@" > "$argf"
if [ "${FORK_RC:-0}" -ne 0 ]; then echo "boom" >&2; exit "${FORK_RC}"; fi
echo "${FORK_ID-sm-test01}"
SH
chmod +x "$FAKE_FORK"

run() { FAP_LOCATOR="$FAKE_LOC" FAP_FORK="$FAKE_FORK" bash "$WRAPPER" "$@"; }

# Case 1: single object -> forks, prints managed id, exit 0.
out=$(TMUX="/private/tmp/tmux-501/default,1,1" LOC_OUT='{"session_id":"abc-123","tty":"ttys9"}' LOC_RC=0 \
      FORK_ID="sm-aaa111" run "%5"); rc=$?
ok "$rc" "0" "single object: exit 0"
ok "$out" "sm-aaa111" "single object: prints managed id"

# Case 1b: the wrapper builds the right pane address and fork args.
LARGS="$TMP/largs"; FARGS="$TMP/fargs"
TMUX="/private/tmp/tmux-501/default,1,1" LOC_OUT='{"session_id":"abc-123","tty":"ttys9"}' LOC_RC=0 \
  LOC_ARGS_OUT="$LARGS" FORK_ARGS_OUT="$FARGS" run "%5" >/dev/null 2>&1
ok "$(cat "$LARGS")" "resolve --pane tmux:default:%5" "builds socket-qualified pane address"
ok "$(cat "$FARGS")" "--session-id abc-123 --target-pane %5 --quiet" "passes session id + target pane to fork"

# Case 2: empty array / rc 1 -> 'no session', exit 0, no managed id.
out=$(TMUX="/private/tmp/tmux-501/default,1,1" LOC_OUT='[]' LOC_RC=1 run "%5"); rc=$?
ok "$rc" "0" "no session: exit 0"
ok "$out" "" "no session: no managed id on stdout"

# Case 3: array of two -> ambiguous, exit 1.
out=$(TMUX="/private/tmp/tmux-501/default,1,1" \
      LOC_OUT='[{"session_id":"a"},{"session_id":"b"}]' LOC_RC=0 run "%5"); rc=$?
ok "$rc" "1" "ambiguous array: exit 1"

# Case 4: no $TMUX -> exit 2.
env -u TMUX bash "$WRAPPER" "%5" >/dev/null 2>&1
ok "$?" "2" "no \$TMUX: exit 2"

# Case 5: missing pane arg -> exit 2.
TMUX="/private/tmp/tmux-501/default,1,1" bash "$WRAPPER" >/dev/null 2>&1
ok "$?" "2" "missing pane arg: exit 2"

# Case 6: fork fails -> exit 1.
out=$(TMUX="/private/tmp/tmux-501/default,1,1" LOC_OUT='{"session_id":"abc","tty":"t"}' LOC_RC=0 \
      FORK_RC=1 run "%5"); rc=$?
ok "$rc" "1" "fork failure: exit 1"

# Case 7: fork exits 0 but emits no managed id -> treated as failure, exit 1.
out=$(TMUX="/private/tmp/tmux-501/default,1,1" LOC_OUT='{"session_id":"abc","tty":"t"}' LOC_RC=0 \
      FORK_RC=0 FORK_ID="" run "%5"); rc=$?
ok "$rc" "1" "fork rc0 but empty managed id: exit 1"

echo "----"
echo "PASS=$pass FAIL=$fail"
[ "$fail" -eq 0 ]
