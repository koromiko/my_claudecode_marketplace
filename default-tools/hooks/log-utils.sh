#!/bin/bash
# Logging utilities for auto-approve hooks.
# Source this file; do not execute directly.

# --- Configuration ---
AUTO_APPROVE_LOG_DIR="${HOME}/.claude/logs"
AUTO_APPROVE_LOG_FILE="${AUTO_APPROVE_LOG_DIR}/auto-approve.log"
AUTO_APPROVE_LOG_MAX_SIZE=1048576   # 1 MB
AUTO_APPROVE_LOG_MAX_BACKUPS=3

# --- log_init: ensure the log directory exists ---
log_init() {
  [[ -d "$AUTO_APPROVE_LOG_DIR" ]] || mkdir -p "$AUTO_APPROVE_LOG_DIR"
}

# --- _log_rotate: rotate log file if it exceeds max size ---
_log_rotate() {
  [[ -f "$AUTO_APPROVE_LOG_FILE" ]] || return 0

  local size
  size=$(stat -f%z "$AUTO_APPROVE_LOG_FILE" 2>/dev/null) || \
    size=$(wc -c < "$AUTO_APPROVE_LOG_FILE") || return 0

  (( size < AUTO_APPROVE_LOG_MAX_SIZE )) && return 0

  # Shift backups: .3 deleted, .2->.3, .1->.2, current->.1
  local i
  for (( i = AUTO_APPROVE_LOG_MAX_BACKUPS; i > 1; i-- )); do
    local prev=$(( i - 1 ))
    [[ -f "${AUTO_APPROVE_LOG_FILE}.${prev}" ]] && \
      mv -f "${AUTO_APPROVE_LOG_FILE}.${prev}" "${AUTO_APPROVE_LOG_FILE}.${i}"
  done
  mv -f "$AUTO_APPROVE_LOG_FILE" "${AUTO_APPROVE_LOG_FILE}.1"
}

# --- log_decision: write one log entry ---
# Usage: log_decision DECISION TOOL_NAME INPUT_SUMMARY REASON
log_decision() {
  local decision="$1"
  local tool_name="$2"
  local input_summary="$3"
  local reason="$4"

  _log_rotate

  # Sanitize input_summary: replace tabs and newlines with spaces, truncate
  input_summary="${input_summary//$'\t'/ }"
  input_summary="${input_summary//$'\n'/ }"
  input_summary="${input_summary:0:200}"

  local ts
  ts=$(date '+%Y-%m-%dT%H:%M:%S')

  printf '%s\t%s\t%s\t%s\t%s\n' \
    "$ts" "$decision" "$tool_name" "$input_summary" "$reason" \
    >> "$AUTO_APPROVE_LOG_FILE" 2>/dev/null || true
}
