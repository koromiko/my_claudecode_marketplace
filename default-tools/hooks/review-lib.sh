#!/bin/bash
# Helpers for the Stop-hook code-review feature.
# Source this file from stop-review.sh; do not execute directly.
#
# Conventions:
#   - cfg_* variables are set by review_load_config from .claude/settings.local.json
#   - Marker and counter files live in /tmp, keyed by session_id
#   - Decisions are logged TSV to ~/.claude/logs/code-review.log

# --- Logging --------------------------------------------------------------

REVIEW_LOG_DIR="${HOME}/.claude/logs"
REVIEW_LOG_FILE="${REVIEW_LOG_DIR}/code-review.log"
REVIEW_LOG_MAX_SIZE=1048576   # 1 MB
REVIEW_LOG_MAX_BACKUPS=3

review_log_init() {
  [[ -d "$REVIEW_LOG_DIR" ]] || mkdir -p "$REVIEW_LOG_DIR"
}

_review_log_rotate() {
  [[ -f "$REVIEW_LOG_FILE" ]] || return 0
  local size
  size=$(stat -f%z "$REVIEW_LOG_FILE" 2>/dev/null) || \
    size=$(wc -c < "$REVIEW_LOG_FILE") || return 0
  (( size < REVIEW_LOG_MAX_SIZE )) && return 0

  local i
  for (( i = REVIEW_LOG_MAX_BACKUPS; i > 1; i-- )); do
    local prev=$(( i - 1 ))
    [[ -f "${REVIEW_LOG_FILE}.${prev}" ]] && \
      mv -f "${REVIEW_LOG_FILE}.${prev}" "${REVIEW_LOG_FILE}.${i}"
  done
  mv -f "$REVIEW_LOG_FILE" "${REVIEW_LOG_FILE}.1"
}

# Usage: review_log DECISION REVIEWER SESSION ITER REASON [DURATION_MS]
review_log() {
  local decision="$1"
  local reviewer="$2"
  local session="$3"
  local iter="$4"
  local reason="$5"
  local duration_ms="${6:-}"

  review_log_init
  _review_log_rotate

  reason="${reason//$'\t'/ }"
  reason="${reason//$'\n'/ }"
  reason="${reason:0:300}"

  local ts
  ts=$(date '+%Y-%m-%dT%H:%M:%S')

  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$ts" "$decision" "$reviewer" "$session" "$iter" "$reason" "$duration_ms" \
    >> "$REVIEW_LOG_FILE" 2>/dev/null || true
}

# --- Config loader --------------------------------------------------------

# Reads the reviewHook block from .claude/settings.local.json (project-scoped,
# git root preferred, falling back to cwd) and exports cfg_* vars.
# Returns 0 on success, non-zero if config file missing or jq fails.
review_load_config() {
  local cwd="${1:-$PWD}"
  local root
  root=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null) || root="$cwd"

  local f="${root}/.claude/settings.local.json"
  [[ -f "$f" ]] || return 1
  command -v jq >/dev/null 2>&1 || return 1

  # Emit one field per line (newline-delimited). We read each into its own
  # variable. NOT tab-delimited: Bash treats tab as whitespace IFS and
  # collapses consecutive empties, which corrupts records like ""\t900\t""
  # (cli.command empty + cli.timeout=900 + cli.field empty).
  local fields
  fields=$(jq -r '
    .reviewHook as $r
    | (
        ($r.enabled // false | tostring),
        ($r.reviewer.type // "ollama"),
        ($r.reviewer.ollama.model // "gemma4:latest"),
        ($r.reviewer.ollama.host // "http://localhost:11434"),
        ($r.reviewer.ollama.timeout // 60 | tostring),
        ($r.reviewer.cli.command // ""),
        ($r.reviewer.cli.timeout // 900 | tostring),
        ($r.reviewer.cli.outputField // ""),
        ($r.reviewer.subagent.name // "code-reviewer"),
        ($r.maxIterations // 3 | tostring),
        ($r.skipIfNoChanges // true | tostring),
        ($r.redactSecrets // true | tostring),
        ($r.promptOverride // "")
      )' "$f" 2>/dev/null) || return 1

  {
    IFS= read -r cfg_enabled
    IFS= read -r cfg_type
    IFS= read -r cfg_ollama_model
    IFS= read -r cfg_ollama_host
    IFS= read -r cfg_ollama_timeout
    IFS= read -r cfg_cli_cmd
    IFS= read -r cfg_cli_timeout
    IFS= read -r cfg_cli_field
    IFS= read -r cfg_subagent_name
    IFS= read -r cfg_max_iter
    IFS= read -r cfg_skip_clean
    IFS= read -r cfg_redact
    IFS= read -r cfg_prompt_override
  } <<<"$fields" || return 1

  # cli.args is an array — read separately into a Bash array
  cfg_cli_args=()
  local arg
  while IFS= read -r arg; do
    [[ -n "$arg" ]] && cfg_cli_args+=("$arg")
  done < <(jq -r '.reviewHook.reviewer.cli.args[]? // empty' "$f" 2>/dev/null)

  return 0
}

# --- Marker + iteration counter ------------------------------------------

review_marker_path() {
  local session="$1"
  echo "/tmp/claude-review-${session}"
}

review_iter_path() {
  local session="$1"
  echo "/tmp/claude-review-iter-${session}"
}

review_iter_get() {
  local session="$1"
  local f
  f=$(review_iter_path "$session")
  if [[ -f "$f" ]]; then
    local n
    n=$(<"$f")
    [[ "$n" =~ ^[0-9]+$ ]] && echo "$n" || echo "0"
  else
    echo "0"
  fi
}

review_iter_set() {
  local session="$1" value="$2"
  echo "$value" > "$(review_iter_path "$session")"
}

review_iter_clear() {
  local session="$1"
  rm -f "$(review_iter_path "$session")"
}

# True (return 0) when the session's iteration counter has already exceeded
# maxIterations + 1 — i.e. we've emitted the final "manual review" block.
# Subsequent stops in the same session should exit silently.
review_should_skip() {
  local session="$1" max="$2"
  local n
  n=$(review_iter_get "$session")
  (( n > max ))
}

# --- Sensitive-path predicate (mirrors auto-approve.sh::is_sensitive_path) -

is_sensitive_cwd() {
  local path="$1"
  [[ -z "$path" ]] && return 1
  local lpath
  lpath=$(printf '%s' "$path" | tr '[:upper:]' '[:lower:]')
  if [[ "$lpath" == *"/.ssh"* ]] || \
     [[ "$lpath" == *"/.aws"* ]] || \
     [[ "$lpath" == *"/.gnupg"* ]] || \
     [[ "$lpath" == *"/.kube"* ]] || \
     [[ "$lpath" == *"/.docker"* ]]; then
    return 0
  fi
  return 1
}

# --- Secret redaction -----------------------------------------------------

# Strip likely-secret tokens from a multi-line string before sending to a
# third-party reviewer. Conservative: matches only high-signal patterns to
# avoid mangling legit code.
review_redact() {
  local text="$1"
  # Patterns:
  #   AKIA + 16 uppercase alnum (AWS access key id)
  #   sk-... (OpenAI-style)
  #   ghp_/gho_/ghs_/ghu_/ghr_ + alnum (GitHub tokens)
  #   key-value style: (api_key|secret|token|bearer|password) followed by =/: + value
  printf '%s' "$text" | perl -pe '
    s/AKIA[0-9A-Z]{16}/[REDACTED-AWS-KEY]/g;
    s/sk-[A-Za-z0-9_\-]{20,}/[REDACTED-API-KEY]/g;
    s/(gh[pousr]_[A-Za-z0-9]{20,})/[REDACTED-GH-TOKEN]/g;
    s/((?i)(?:api[_-]?key|secret|token|bearer|password)\s*[:=]\s*)([^\s,;"'\'']{6,})/\1[REDACTED]/g;
  ' 2>/dev/null || printf '%s' "$text"
}

# --- Repo state grounding -------------------------------------------------

# Returns a compact repo-state block: porcelain status + diff stat (HEAD).
# Capped to ~100 lines total to keep the prompt small.
review_ground_in_repo() {
  local cwd="$1"
  {
    echo "Working tree status (git status --porcelain):"
    git -C "$cwd" status --porcelain 2>/dev/null | head -n 50
    echo ""
    echo "Diff stat vs HEAD:"
    git -C "$cwd" diff --stat HEAD 2>/dev/null | head -n 50
  }
}

# --- Prompt assembly ------------------------------------------------------

# Loads the prompt template (cfg_prompt_override if set, else bundled),
# substitutes {{CLAUDE_RESPONSE_BLOCK}} and {{REPO_STATE_BLOCK}}.
review_assemble_prompt() {
  local last_msg="$1"
  local repo_state="$2"

  local template_path
  if [[ -n "$cfg_prompt_override" ]] && [[ -f "$cfg_prompt_override" ]]; then
    template_path="$cfg_prompt_override"
  else
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    template_path="$script_dir/stop-review-prompt.md"
  fi

  [[ -f "$template_path" ]] || return 1

  local response_block=""
  if [[ -n "$last_msg" ]]; then
    response_block="Previous Claude response:"$'\n'"$last_msg"
  fi

  local repo_state_block=""
  if [[ -n "$repo_state" ]]; then
    repo_state_block="Repository state:"$'\n'"$repo_state"
  fi

  # Substitute via Bash parameter expansion. Avoids awk -v / sed which both
  # have trouble with multi-line replacement values.
  local template
  template=$(<"$template_path")
  local prompt="${template//\{\{CLAUDE_RESPONSE_BLOCK\}\}/$response_block}"
  prompt="${prompt//\{\{REPO_STATE_BLOCK\}\}/$repo_state_block}"
  printf '%s' "$prompt"
}

# --- First-line ALLOW/BLOCK parser ---------------------------------------

# Parses reviewer output. Echoes one of:
#   "ALLOW\t<reason>"
#   "BLOCK\t<reason>"
#   "MALFORMED\t<original-first-line>"
review_parse_verdict() {
  local text="$1"
  local first
  # First non-empty, non-whitespace line
  first=$(printf '%s\n' "$text" | awk 'NF { print; exit }')
  first="${first#"${first%%[![:space:]]*}"}"

  if [[ "$first" == ALLOW:* ]]; then
    printf 'ALLOW\t%s\n' "${first#ALLOW:}"
  elif [[ "$first" == BLOCK:* ]]; then
    printf 'BLOCK\t%s\n' "${first#BLOCK:}"
  else
    printf 'MALFORMED\t%s\n' "$first"
  fi
}

# --- Reviewer runners -----------------------------------------------------

# Calls the local Ollama HTTP API with the assembled prompt.
# Echoes the model's text response to stdout; returns 0 on success, non-zero
# on connection/timeout/parse failure.
#
# Test hook: when STOP_REVIEW_TEST_OUTPUT is set, that string is echoed
# verbatim and no HTTP call is made (parallels OLLAMA_TEST_MODE pattern).
review_run_ollama() {
  local prompt="$1"
  if [[ -n "${STOP_REVIEW_TEST_OUTPUT:-}" ]]; then
    printf '%s' "$STOP_REVIEW_TEST_OUTPUT"
    return 0
  fi

  local body
  body=$(jq -n \
    --arg model "$cfg_ollama_model" \
    --arg prompt "$prompt" \
    '{model:$model, prompt:$prompt, stream:false, think:false}')

  local response
  response=$(curl -s --fail --max-time "$cfg_ollama_timeout" \
    -H "Content-Type: application/json" \
    -d "$body" \
    "${cfg_ollama_host}/api/generate" 2>/dev/null) || return 1

  printf '%s' "$response" | jq -r '.response // ""' 2>/dev/null
}

# Calls the configured CLI with the prompt as the final argument.
# Echoes the CLI's stdout (or the extracted JSON field if cfg_cli_field set).
# Returns 0 on success, non-zero on CLI failure.
#
# Test hook: STOP_REVIEW_TEST_OUTPUT short-circuits as in review_run_ollama.
review_run_cli() {
  local prompt="$1"
  if [[ -n "${STOP_REVIEW_TEST_OUTPUT:-}" ]]; then
    printf '%s' "$STOP_REVIEW_TEST_OUTPUT"
    return 0
  fi

  local stdout
  if (( ${#cfg_cli_args[@]} > 0 )); then
    stdout=$("$cfg_cli_cmd" "${cfg_cli_args[@]}" "$prompt" 2>/dev/null) || return 1
  else
    stdout=$("$cfg_cli_cmd" "$prompt" 2>/dev/null) || return 1
  fi

  if [[ -n "$cfg_cli_field" ]]; then
    printf '%s' "$stdout" | jq -r ".${cfg_cli_field} // \"\"" 2>/dev/null
  else
    printf '%s' "$stdout"
  fi
}

# --- Decision emitter -----------------------------------------------------

# Emit a {"decision":"block","reason":...} JSON object to stdout.
review_emit_block() {
  local reason="$1"
  jq -n --arg r "$reason" '{decision:"block", reason:$r}'
}
