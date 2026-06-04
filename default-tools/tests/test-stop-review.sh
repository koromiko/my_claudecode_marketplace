#!/bin/bash
# Test harness for default-tools/hooks/stop-review.sh.
#
# Each case sets up a temporary "project root" with a synthetic
# .claude/settings.local.json, optional git working-tree state, then pipes a
# canned hook-input JSON to stop-review.sh and asserts on stdout/exit/marker.
#
# Exit code:
#   0 — all assertions pass
#   1 — one or more failures

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK="$SCRIPT_DIR/../hooks/stop-review.sh"

PASSED=0
FAILED=0
FAIL_DETAILS=()

assert_pass() {
  local name="$1"
  PASSED=$(( PASSED + 1 ))
  printf "  PASS  %s\n" "$name"
}
assert_fail() {
  local name="$1" detail="$2"
  FAILED=$(( FAILED + 1 ))
  FAIL_DETAILS+=("$name :: $detail")
  printf "  FAIL  %s\n        %s\n" "$name" "$detail"
}

# --- Per-case fixture builder --------------------------------------------
# make_project [config-json]   — creates a temp dir, optionally writes
#                                .claude/settings.local.json with the given JSON.
#                                Echoes the project path.
make_project() {
  local cfg="${1:-}"
  local dir
  dir=$(mktemp -d)
  ( cd "$dir" && git init -q && git config user.email t@t && git config user.name t )
  if [[ -n "$cfg" ]]; then
    mkdir -p "$dir/.claude"
    printf '%s' "$cfg" > "$dir/.claude/settings.local.json"
  fi
  echo "$dir"
}
make_dirty_project() {
  local cfg="${1:-}"
  local dir
  dir=$(make_project "$cfg")
  echo "untracked content" > "$dir/dirty.txt"
  echo "$dir"
}

run_hook() {
  # $1 = project dir, $2 = stdin JSON, rest = env overrides
  local dir="$1" input="$2"
  shift 2
  ( cd "$dir" && env "$@" bash "$HOOK" <<<"$input" 2>/dev/null )
}

# Clean up /tmp markers between cases
clean_markers() {
  rm -f /tmp/claude-review-* 2>/dev/null
}

echo "=== stop-review.sh test run ==="
echo ""

# --- Case 1: empty last_assistant_message → exit 0, no stdout -------------
clean_markers
DIR=$(make_dirty_project '{"reviewHook":{"enabled":true,"reviewer":{"type":"subagent","subagent":{"name":"code-reviewer"}}}}')
INPUT='{"session_id":"c1","cwd":"'"$DIR"'","last_assistant_message":"","stop_hook_active":false}'
OUT=$(run_hook "$DIR" "$INPUT")
if [[ -z "$OUT" ]]; then
  assert_pass "empty last_assistant_message → no output"
else
  assert_fail "empty last_assistant_message → no output" "got: $OUT"
fi
rm -rf "$DIR"

# --- Case 2: stop_hook_active=true → exit 0, no stdout --------------------
clean_markers
DIR=$(make_dirty_project '{"reviewHook":{"enabled":true,"reviewer":{"type":"subagent","subagent":{"name":"code-reviewer"}}}}')
INPUT='{"session_id":"c2","cwd":"'"$DIR"'","last_assistant_message":"x","stop_hook_active":true}'
OUT=$(run_hook "$DIR" "$INPUT")
if [[ -z "$OUT" ]]; then
  assert_pass "stop_hook_active=true → no output"
else
  assert_fail "stop_hook_active=true → no output" "got: $OUT"
fi
rm -rf "$DIR"

# --- Case 3: hook disabled → exit 0, no stdout ----------------------------
clean_markers
DIR=$(make_dirty_project '{"reviewHook":{"enabled":false,"reviewer":{"type":"subagent","subagent":{"name":"code-reviewer"}}}}')
INPUT='{"session_id":"c3","cwd":"'"$DIR"'","last_assistant_message":"x","stop_hook_active":false}'
OUT=$(run_hook "$DIR" "$INPUT")
if [[ -z "$OUT" ]]; then
  assert_pass "disabled → no output"
else
  assert_fail "disabled → no output" "got: $OUT"
fi
rm -rf "$DIR"

# --- Case 4: subagent mode, dirty tree → block-and-instruct ---------------
clean_markers
DIR=$(make_dirty_project '{"reviewHook":{"enabled":true,"reviewer":{"type":"subagent","subagent":{"name":"code-reviewer"}}}}')
INPUT='{"session_id":"c4","cwd":"'"$DIR"'","last_assistant_message":"I edited auth.py","stop_hook_active":false}'
OUT=$(run_hook "$DIR" "$INPUT")
if echo "$OUT" | jq -e '.decision == "block"' >/dev/null 2>&1 \
   && echo "$OUT" | jq -e '.reason | startswith("Dispatch the @code-reviewer")' >/dev/null 2>&1; then
  if [[ -f /tmp/claude-review-c4 ]]; then
    assert_pass "subagent first-pass → decision:block + marker file"
  else
    assert_fail "subagent first-pass → decision:block + marker file" "block emitted but marker missing"
  fi
else
  assert_fail "subagent first-pass → decision:block + marker file" "stdout: $OUT"
fi
rm -rf "$DIR"
clean_markers

# --- Case 5: subagent mode re-entry (marker present) → no output ----------
DIR=$(make_dirty_project '{"reviewHook":{"enabled":true,"reviewer":{"type":"subagent","subagent":{"name":"code-reviewer"}}}}')
touch /tmp/claude-review-c5
INPUT='{"session_id":"c5","cwd":"'"$DIR"'","last_assistant_message":"x","stop_hook_active":false}'
OUT=$(run_hook "$DIR" "$INPUT")
if [[ -z "$OUT" ]] && [[ ! -f /tmp/claude-review-c5 ]]; then
  assert_pass "subagent re-entry → no output, marker removed"
else
  assert_fail "subagent re-entry → no output, marker removed" "out=[$OUT] marker_exists=$([[ -f /tmp/claude-review-c5 ]] && echo yes || echo no)"
fi
rm -rf "$DIR"

# --- Case 6: ollama mode with ALLOW mock → no output ----------------------
clean_markers
DIR=$(make_dirty_project '{"reviewHook":{"enabled":true,"reviewer":{"type":"ollama","ollama":{"model":"x"}},"skipIfNoChanges":false}}')
INPUT='{"session_id":"c6","cwd":"'"$DIR"'","last_assistant_message":"I edited a file","stop_hook_active":false}'
OUT=$(run_hook "$DIR" "$INPUT" "STOP_REVIEW_TEST_OUTPUT=ALLOW: looks fine")
if [[ -z "$OUT" ]]; then
  assert_pass "ollama ALLOW mock → no output"
else
  assert_fail "ollama ALLOW mock → no output" "got: $OUT"
fi
rm -rf "$DIR"

# --- Case 7: ollama mode with BLOCK mock → block, counter=1 ---------------
clean_markers
DIR=$(make_dirty_project '{"reviewHook":{"enabled":true,"reviewer":{"type":"ollama","ollama":{"model":"x"}},"skipIfNoChanges":false,"maxIterations":3}}')
INPUT='{"session_id":"c7","cwd":"'"$DIR"'","last_assistant_message":"I edited a file","stop_hook_active":false}'
OUT=$(run_hook "$DIR" "$INPUT" "STOP_REVIEW_TEST_OUTPUT=BLOCK: missing tests")
if echo "$OUT" | jq -e '.decision == "block"' >/dev/null 2>&1 \
   && echo "$OUT" | jq -e '.reason | contains("missing tests")' >/dev/null 2>&1 \
   && [[ "$(cat /tmp/claude-review-iter-c7 2>/dev/null)" == "1" ]]; then
  assert_pass "ollama BLOCK mock → block emitted, counter=1"
else
  assert_fail "ollama BLOCK mock → block emitted, counter=1" "out=[$OUT] iter=[$(cat /tmp/claude-review-iter-c7 2>/dev/null)]"
fi
rm -rf "$DIR"

# --- Case 8: ollama BLOCK at counter=max → final block, counter=max+1 ----
clean_markers
DIR=$(make_dirty_project '{"reviewHook":{"enabled":true,"reviewer":{"type":"ollama","ollama":{"model":"x"}},"skipIfNoChanges":false,"maxIterations":3}}')
echo 3 > /tmp/claude-review-iter-c8
INPUT='{"session_id":"c8","cwd":"'"$DIR"'","last_assistant_message":"x","stop_hook_active":false}'
OUT=$(run_hook "$DIR" "$INPUT" "STOP_REVIEW_TEST_OUTPUT=BLOCK: still issues")
if echo "$OUT" | jq -e '.decision == "block"' >/dev/null 2>&1 \
   && echo "$OUT" | jq -e '.reason | contains("Manual review needed")' >/dev/null 2>&1 \
   && [[ "$(cat /tmp/claude-review-iter-c8 2>/dev/null)" == "4" ]]; then
  assert_pass "ollama BLOCK at iter=max → final block, counter=max+1"
else
  assert_fail "ollama BLOCK at iter=max → final block, counter=max+1" "out=[$OUT] iter=[$(cat /tmp/claude-review-iter-c8 2>/dev/null)]"
fi
rm -rf "$DIR"

# --- Case 9: counter past cap → silent ------------------------------------
clean_markers
DIR=$(make_dirty_project '{"reviewHook":{"enabled":true,"reviewer":{"type":"ollama","ollama":{"model":"x"}},"skipIfNoChanges":false,"maxIterations":3}}')
echo 4 > /tmp/claude-review-iter-c9
INPUT='{"session_id":"c9","cwd":"'"$DIR"'","last_assistant_message":"x","stop_hook_active":false}'
OUT=$(run_hook "$DIR" "$INPUT" "STOP_REVIEW_TEST_OUTPUT=BLOCK: should be ignored")
if [[ -z "$OUT" ]]; then
  assert_pass "counter past cap → no output"
else
  assert_fail "counter past cap → no output" "got: $OUT"
fi
rm -rf "$DIR"

# --- Case 10: cli mode with command not on PATH → no output ---------------
clean_markers
DIR=$(make_dirty_project '{"reviewHook":{"enabled":true,"reviewer":{"type":"cli","cli":{"command":"this-binary-does-not-exist-xyz"}},"skipIfNoChanges":false}}')
INPUT='{"session_id":"c10","cwd":"'"$DIR"'","last_assistant_message":"x","stop_hook_active":false}'
OUT=$(run_hook "$DIR" "$INPUT")
if [[ -z "$OUT" ]]; then
  assert_pass "cli not on PATH → no output (fail open)"
else
  assert_fail "cli not on PATH → no output (fail open)" "got: $OUT"
fi
rm -rf "$DIR"

# --- Case 11: clean working tree + skipIfNoChanges=true → no output -------
clean_markers
DIR=$(make_project '{"reviewHook":{"enabled":true,"reviewer":{"type":"ollama","ollama":{"model":"x"}},"skipIfNoChanges":true}}')
INPUT='{"session_id":"c11","cwd":"'"$DIR"'","last_assistant_message":"x","stop_hook_active":false}'
OUT=$(run_hook "$DIR" "$INPUT" "STOP_REVIEW_TEST_OUTPUT=BLOCK: should not run")
if [[ -z "$OUT" ]]; then
  assert_pass "clean tree + skipIfNoChanges → no output"
else
  assert_fail "clean tree + skipIfNoChanges → no output" "got: $OUT"
fi
rm -rf "$DIR"

# --- Case 12: redaction strips AWS key from prompt ------------------------
clean_markers
DIR=$(make_dirty_project '{"reviewHook":{"enabled":true,"reviewer":{"type":"ollama","ollama":{"model":"x"}},"skipIfNoChanges":false,"redactSecrets":true}}')
# Use a special test mode that echoes the assembled prompt back verbatim so we
# can assert the AWS key was redacted before the reviewer was called.
# stop-review.sh treats STOP_REVIEW_TEST_OUTPUT as the reviewer reply, but the
# prompt itself is built before review_run_ollama is called. We check the
# review-lib.sh redactor directly since asserting on prompt content via the
# verdict path requires more plumbing.
( cd "$DIR" && \
  source "$SCRIPT_DIR/../hooks/review-lib.sh" && \
  redacted=$(review_redact "AKIAIOSFODNN7EXAMPLE in code") && \
  if [[ "$redacted" == *"REDACTED-AWS-KEY"* ]] && [[ "$redacted" != *"AKIAIOSFODNN7EXAMPLE"* ]]; then exit 0; else exit 1; fi )
if [[ $? -eq 0 ]]; then
  assert_pass "redaction strips AKIA AWS key"
else
  assert_fail "redaction strips AKIA AWS key" "review_redact did not strip AKIAIOSFODNN7EXAMPLE"
fi
rm -rf "$DIR"

# --- Case 13: sensitive cwd (.ssh) → no output ----------------------------
clean_markers
DIR_BASE=$(mktemp -d)
DIR="$DIR_BASE/.ssh"
mkdir -p "$DIR"
( cd "$DIR" && git init -q )
mkdir -p "$DIR/.claude"
echo '{"reviewHook":{"enabled":true,"reviewer":{"type":"ollama"}}}' > "$DIR/.claude/settings.local.json"
INPUT='{"session_id":"c13","cwd":"'"$DIR"'","last_assistant_message":"x","stop_hook_active":false}'
OUT=$(run_hook "$DIR" "$INPUT" "STOP_REVIEW_TEST_OUTPUT=BLOCK: should not run")
if [[ -z "$OUT" ]]; then
  assert_pass "sensitive cwd (.ssh) → no output"
else
  assert_fail "sensitive cwd (.ssh) → no output" "got: $OUT"
fi
rm -rf "$DIR_BASE"

# --- Case 14: malformed reviewer output → no output (fail open) -----------
clean_markers
DIR=$(make_dirty_project '{"reviewHook":{"enabled":true,"reviewer":{"type":"ollama","ollama":{"model":"x"}},"skipIfNoChanges":false}}')
INPUT='{"session_id":"c14","cwd":"'"$DIR"'","last_assistant_message":"x","stop_hook_active":false}'
OUT=$(run_hook "$DIR" "$INPUT" "STOP_REVIEW_TEST_OUTPUT=Sure, looks fine to me!")
if [[ -z "$OUT" ]]; then
  assert_pass "malformed reviewer output → no output (fail open)"
else
  assert_fail "malformed reviewer output → no output (fail open)" "got: $OUT"
fi
rm -rf "$DIR"

clean_markers
echo ""
echo "Summary: $PASSED passed / $FAILED failed"
if (( FAILED > 0 )); then
  echo ""
  echo "Failures:"
  for d in "${FAIL_DETAILS[@]}"; do
    echo "  - $d"
  done
  exit 1
fi
exit 0
