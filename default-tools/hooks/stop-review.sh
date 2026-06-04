#!/bin/bash
# Stop-hook code review for default-tools.
#
# Runs a configurable second-pass review of the previous Claude turn before
# the session is allowed to stop. Three reviewer modes:
#   - ollama   : local LLM via http://localhost:11434/api/generate
#   - cli      : generic external CLI (codex, gemini, ...) returning
#                ALLOW: <reason> / BLOCK: <reason> on its first line
#   - subagent : block-and-instruct — emits decision:block telling Claude to
#                dispatch a named in-session subagent
#
# Reads hook JSON from stdin. Emits a JSON {"decision":"block","reason":...}
# to stdout when blocking, or exits 0 silently to let the session stop.
#
# Fail-open: any infrastructure error (missing CLI, jq, timeout, malformed
# output) logs PASS_REVIEW and exits 0. The gate only blocks on actual
# reviewer BLOCK verdicts.
#
# Disabled by default. Configure via /review-config in a Claude session.

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=hooks/review-lib.sh
source "$SCRIPT_DIR/review-lib.sh"

_now_ms() {
  perl -MTime::HiRes=time -e 'printf "%d\n", time()*1000' 2>/dev/null \
    || echo $(( $(date +%s) * 1000 ))
}
START_MS=$(_now_ms)
elapsed_ms() { echo $(( $(_now_ms) - START_MS )); }

# Lowercase a string (Bash 3.2 portable)
_lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }
# Uppercase a string (Bash 3.2 portable)
_upper() { printf '%s' "$1" | tr '[:lower:]' '[:upper:]'; }

# --- 1. Read input ---------------------------------------------------------

INPUT=$(cat)

if ! command -v jq >/dev/null 2>&1; then
  exit 0
fi

session_id=$(printf '%s' "$INPUT" | jq -r '.session_id // ""')
cwd=$(printf '%s' "$INPUT" | jq -r '.cwd // ""')
last_msg=$(printf '%s' "$INPUT" | jq -r '.last_assistant_message // ""')
stop_hook_active=$(printf '%s' "$INPUT" | jq -r '.stop_hook_active // false')

[[ -z "$cwd" ]] && cwd="$PWD"
[[ -z "$session_id" ]] && session_id="default"

# --- 2. Cheap exits --------------------------------------------------------

# Re-entry guard: Claude Code sets stop_hook_active=true when this Stop is
# fired in response to a previous block decision. Allow it through.
if [[ "$stop_hook_active" == "true" ]]; then
  # Subagent mode: also clear the marker so a fresh stop later works.
  rm -f "$(review_marker_path "$session_id")"
  exit 0
fi

# Sensitive cwd: never review (we'd be sending secrets to a third party).
if is_sensitive_cwd "$cwd"; then
  exit 0
fi

# --- 3. Load config --------------------------------------------------------

# Defaults if config absent — every cfg_* var must have a value before we
# branch on cfg_enabled, so we initialize first then overlay file contents.
cfg_enabled="false"
cfg_type="ollama"
cfg_ollama_model="gemma4:latest"
cfg_ollama_host="http://localhost:11434"
cfg_ollama_timeout="60"
cfg_cli_cmd=""
cfg_cli_args=()
cfg_cli_timeout="900"
cfg_cli_field=""
cfg_subagent_name="code-reviewer"
cfg_max_iter="3"
cfg_skip_clean="true"
cfg_redact="true"
cfg_prompt_override=""

review_load_config "$cwd" || true

if [[ "$cfg_enabled" != "true" ]]; then
  exit 0
fi

# --- 4. Skip-conditions that don't depend on reviewer type ----------------

# Already past max-iter+1 → silent (we already emitted the manual-review block)
if review_should_skip "$session_id" "$cfg_max_iter"; then
  review_log SKIP_REVIEW "$cfg_type" "$session_id" \
    "$(review_iter_get "$session_id")" "iter past cap" "$(elapsed_ms)"
  exit 0
fi

# Empty assistant message → nothing to review
if [[ -z "$last_msg" ]]; then
  exit 0
fi

# Clean working tree → no edits to review (cheap shell-side enforcement of
# the prompt's "ignore status/setup turns" rule)
if [[ "$cfg_skip_clean" == "true" ]]; then
  if [[ -z "$(git -C "$cwd" status --porcelain 2>/dev/null)" ]]; then
    review_log ALLOW_CLEAN "$cfg_type" "$session_id" \
      "$(review_iter_get "$session_id")" "working tree clean" "$(elapsed_ms)"
    exit 0
  fi
fi

# Optional secret redaction before sending to a third-party reviewer
if [[ "$cfg_redact" == "true" ]]; then
  last_msg=$(review_redact "$last_msg")
fi

# --- 5. Subagent mode ------------------------------------------------------

if [[ "$cfg_type" == "subagent" ]]; then
  marker=$(review_marker_path "$session_id")
  if [[ -f "$marker" ]]; then
    # Already requested the subagent for this turn — let stop proceed
    rm -f "$marker"
    exit 0
  fi
  touch "$marker"

  reason=$(printf '%s' "Dispatch the @${cfg_subagent_name} subagent to review the previous turn before stopping. Focus on the code edits made in that turn: design tradeoffs, second-order failures, empty-state behavior, retries, stale state, rollback risk. Reply with ALLOW or BLOCK and rationale, then address any BLOCK findings.")
  review_emit_block "$reason"
  review_log BLOCK_SUBAGENT "subagent" "$session_id" "0" \
    "dispatch @${cfg_subagent_name}" "$(elapsed_ms)"
  exit 0
fi

# --- 6. ollama / cli — assemble prompt and call reviewer ------------------

repo_state=$(review_ground_in_repo "$cwd")
prompt=$(review_assemble_prompt "$last_msg" "$repo_state") || {
  review_log PASS_REVIEW "$cfg_type" "$session_id" \
    "$(review_iter_get "$session_id")" "prompt-template-missing" "$(elapsed_ms)"
  exit 0
}

case "$cfg_type" in
  ollama)
    output=$(review_run_ollama "$prompt") || {
      review_log PASS_REVIEW "ollama" "$session_id" \
        "$(review_iter_get "$session_id")" "ollama-unreachable" "$(elapsed_ms)"
      exit 0
    }
    ;;
  cli)
    if [[ -z "$cfg_cli_cmd" ]] || ! command -v "$cfg_cli_cmd" >/dev/null 2>&1; then
      review_log PASS_REVIEW "cli" "$session_id" \
        "$(review_iter_get "$session_id")" "cli-missing:${cfg_cli_cmd:-unset}" "$(elapsed_ms)"
      exit 0
    fi
    output=$(review_run_cli "$prompt") || {
      review_log PASS_REVIEW "cli" "$session_id" \
        "$(review_iter_get "$session_id")" "cli-failed" "$(elapsed_ms)"
      exit 0
    }
    ;;
  *)
    # Unknown reviewer type — fail open
    review_log PASS_REVIEW "unknown" "$session_id" \
      "$(review_iter_get "$session_id")" "unknown-reviewer-type:${cfg_type}" "$(elapsed_ms)"
    exit 0
    ;;
esac

# --- 7. Parse verdict ------------------------------------------------------

verdict_line=$(review_parse_verdict "$output")
verdict="${verdict_line%%$'\t'*}"
reason="${verdict_line#*$'\t'}"

case "$verdict" in
  ALLOW)
    review_iter_clear "$session_id"
    review_log "ALLOW_$(_upper "$cfg_type")" "$cfg_type" "$session_id" "0" \
      "${reason:-ok}" "$(elapsed_ms)"
    exit 0
    ;;
  BLOCK)
    iter=$(review_iter_get "$session_id")
    next=$(( iter + 1 ))
    review_iter_set "$session_id" "$next"
    if (( next > cfg_max_iter )); then
      # Final block: surface the cap, then bump counter past the cap so the
      # next stop is silent.
      final_reason="Manual review needed: max iterations (${cfg_max_iter}) reached. Last reviewer reason: ${reason:-no detail}. Disable or raise reviewHook.maxIterations to continue automated review."
      review_emit_block "$final_reason"
      review_iter_set "$session_id" "$(( cfg_max_iter + 1 ))"
      review_log "BLOCK_FINAL" "$cfg_type" "$session_id" "$next" \
        "max-iter ${cfg_max_iter}" "$(elapsed_ms)"
      exit 0
    fi
    block_reason="Code review found issues (${cfg_type}, iter ${next}/${cfg_max_iter}): ${reason:-no detail}"
    review_emit_block "$block_reason"
    review_log "BLOCK_$(_upper "$cfg_type")" "$cfg_type" "$session_id" "$next" \
      "${reason:-no detail}" "$(elapsed_ms)"
    exit 0
    ;;
  MALFORMED|*)
    # Reviewer returned something we can't parse — fail open
    review_log PASS_REVIEW "$cfg_type" "$session_id" \
      "$(review_iter_get "$session_id")" "malformed-output:${reason:0:80}" "$(elapsed_ms)"
    exit 0
    ;;
esac
