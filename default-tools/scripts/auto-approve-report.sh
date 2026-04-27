#!/bin/bash
# Generate a self-contained HTML usage report from ~/.claude/logs/auto-approve.log.
#
# Usage:
#   ./auto-approve-report.sh [--today] [--days N] [--since YYYY-MM-DD] [--all]
#                            [--open] [--out PATH] [--help]
#
# Flags:
#   --today         Only today's entries
#   --days N        Last N days
#   --since DATE    On or after DATE (YYYY-MM-DD)
#   --all           Override default 7-day window; include everything
#   --open          After writing, run `open <file>` (macOS)
#   --out PATH      Output path (default: /tmp/auto-approve-report-<ISO>.html)
#   --help          Show this help message

set -euo pipefail

LOG_DIR="${HOME}/.claude/logs"
LOG_FILE="${LOG_DIR}/auto-approve.log"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART_JS="${SCRIPT_DIR}/vendor/chart.umd.min.js"

usage() {
  # Print only the leading comment block (lines 2 through first blank line)
  awk 'NR==1{next} /^#/{sub(/^# ?/,""); print; next} /^$/{next} {exit}' "$0"
  exit 0
}

# --- Parse arguments ---
FILTER_SINCE=""
FILTER_LABEL="last 7 days"
OPEN_AFTER=0
OUT_PATH=""
EXPLICIT_WINDOW=0  # set when user passes --today/--days/--since/--all

# Default: last 7 days. Computed here so --all can clear it.
default_since() {
  date -v "-7d" '+%Y-%m-%d' 2>/dev/null || date -d "7 days ago" '+%Y-%m-%d'
}
FILTER_SINCE="$(default_since)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --today)
      FILTER_SINCE=$(date '+%Y-%m-%d')
      FILTER_LABEL="today"
      EXPLICIT_WINDOW=1
      shift ;;
    --days)
      [[ -z "${2:-}" || "${2:-}" == --* ]] && { echo "Error: --days requires a positive integer" >&2; exit 1; }
      [[ "$2" =~ ^[0-9]+$ ]] || { echo "Error: --days requires a positive integer (got: $2)" >&2; exit 1; }
      FILTER_SINCE=$(date -v "-${2}d" '+%Y-%m-%d' 2>/dev/null \
        || date -d "${2} days ago" '+%Y-%m-%d')
      FILTER_LABEL="last ${2} days"
      EXPLICIT_WINDOW=1
      shift 2 ;;
    --since)
      [[ -z "${2:-}" || "${2:-}" == --* ]] && { echo "Error: --since requires a date (YYYY-MM-DD)" >&2; exit 1; }
      FILTER_SINCE="$2"
      FILTER_LABEL="since $2"
      EXPLICIT_WINDOW=1
      shift 2 ;;
    --all)
      FILTER_SINCE=""
      FILTER_LABEL="all time"
      EXPLICIT_WINDOW=1
      shift ;;
    --open)
      OPEN_AFTER=1
      shift ;;
    --out)
      [[ -z "${2:-}" || "${2:-}" == --* ]] && { echo "Error: --out requires a path" >&2; exit 1; }
      OUT_PATH="$2"
      shift 2 ;;
    --help|-h)
      usage ;;
    *)
      echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# --- Resolve output path ---
if [[ -z "$OUT_PATH" ]]; then
  ts=$(date '+%Y%m%dT%H%M%S')
  OUT_PATH="/tmp/auto-approve-report-${ts}.html"
fi

# --- Collect log files (current + rotated backups) ---
log_files=()
[[ -f "$LOG_FILE" ]] && log_files+=("$LOG_FILE")
for i in 1 2 3; do
  [[ -f "${LOG_FILE}.${i}" ]] && log_files+=("${LOG_FILE}.${i}")
done

if [[ ${#log_files[@]} -eq 0 ]]; then
  echo "No log files found at ${LOG_FILE}" >&2
  exit 0
fi

# DEBUG: print resolved config (removed in Task 4)
{
  echo "since=${FILTER_SINCE}"
  echo "label=${FILTER_LABEL}"
  echo "out=${OUT_PATH}"
  echo "open=${OPEN_AFTER}"
  echo "log_files=${log_files[*]}"
} >&2
