#!/bin/bash
# Logs auto-mode classifier denials to ~/.claude/logs/auto-approve.log so
# usage-report.sh can aggregate them alongside ALLOW/PASS/ALLOW_LLM/PASS_LLM.
# Optional opt-in behaviors:
#   DEFAULT_TOOLS_AUTO_RETRY_REGEX — if the denial reason matches this regex,
#     emit a retry JSON so Claude Code tells the model to try again.
#   DEFAULT_TOOLS_NOTIFY_DENIAL=1 — fire a macOS notification on each denial.
#
# Exit code is ignored by Claude Code per the hook schema.

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/log-utils.sh"

log_init

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // "unknown"')
REASON=$(echo "$INPUT" | jq -r '.reason // "(no reason)"')
SUMMARY=$(echo "$INPUT" | jq -r '
  .tool_input
  | to_entries
  | map("\(.key)=\(.value | tostring | .[0:120])")
  | join(" ")
' 2>/dev/null) || SUMMARY=""

DECISION="DENIED_AUTO"
RETRY_JSON=""

if [[ -n "${DEFAULT_TOOLS_AUTO_RETRY_REGEX:-}" ]] && [[ "$REASON" =~ $DEFAULT_TOOLS_AUTO_RETRY_REGEX ]]; then
  DECISION="DENIED_AUTO_RETRIED"
  RETRY_JSON='{"hookSpecificOutput":{"hookEventName":"PermissionDenied","retry":true}}'
fi

log_decision "$DECISION" "$TOOL" "$SUMMARY" "$REASON"

if [[ "${DEFAULT_TOOLS_NOTIFY_DENIAL:-}" == "1" ]] && command -v terminal-notifier >/dev/null 2>&1; then
  terminal-notifier \
    -title "Claude Code auto-mode denied: $TOOL" \
    -message "${REASON:0:200}" \
    -activate com.googlecode.iterm2 >/dev/null 2>&1 &
fi

[[ -n "$RETRY_JSON" ]] && echo "$RETRY_JSON"
exit 0
