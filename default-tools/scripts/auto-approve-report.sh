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

# --- Aggregate ---
# Emit raw rows the same way auto-approve-usage.sh does, plus turnaround details
# and denial reasons. Awk emits TSV; we shape into JSON below with jq.
raw=$(awk -v since="$FILTER_SINCE" '
BEGIN { FS = "\t" }
NF < 3 { next }
since != "" && substr($1, 1, 10) < since { next }
{
  total++
  decisions[$2]++
  tools[$3]++
  if (NF >= 6 && $6 ~ /^[0-9]+$/) {
    d = $2
    lat_count[d]++
    lat_sum[d] += $6
    key = d ":" lat_count[d]
    lat_vals[key] = $6
    all_durations[++all_n] = $6
  }
  if (NF >= 5 && $2 ~ /^DENIED_AUTO/) {
    reason = $5
    if (length(reason) > 100) reason = substr(reason, 1, 100) "..."
    denial_reasons[reason]++
  }
}
END {
  print "TOTAL\t" (total+0)
  for (d in decisions) print "DECISION\t" d "\t" decisions[d]
  for (t in tools)     print "TOOL\t"     t "\t" tools[t]
  for (r in denial_reasons) print "DENIAL\t" denial_reasons[r] "\t" r
  for (d in lat_count) {
    n = lat_count[d]
    delete arr
    for (i = 1; i <= n; i++) arr[i] = lat_vals[d ":" i]
    for (i = 2; i <= n; i++) {
      v = arr[i]; j = i - 1
      while (j >= 1 && arr[j] > v) { arr[j+1] = arr[j]; j-- }
      arr[j+1] = v
    }
    avg = lat_sum[d] / n
    p50_idx = int((n + 1) * 0.5); if (p50_idx < 1) p50_idx = 1; if (p50_idx > n) p50_idx = n
    p95_idx = int((n + 1) * 0.95); if (p95_idx < 1) p95_idx = 1; if (p95_idx > n) p95_idx = n
    printf "TURN\t%s\t%d\t%d\t%d\t%d\t%d\n", d, n, avg, arr[p50_idx], arr[p95_idx], arr[n]
  }
  if (all_n > 0) {
    n = all_n
    for (i = 2; i <= n; i++) {
      v = all_durations[i]; j = i - 1
      while (j >= 1 && all_durations[j] > v) { all_durations[j+1] = all_durations[j]; j-- }
      all_durations[j+1] = v
    }
    p95_idx = int((n + 1) * 0.95); if (p95_idx < 1) p95_idx = 1; if (p95_idx > n) p95_idx = n
    printf "OVERALL_P95\t%d\n", all_durations[p95_idx]
  } else {
    print "OVERALL_P95\t0"
  }
}
' "${log_files[@]}")

total=$(printf '%s\n' "$raw" | awk -F'\t' '$1=="TOTAL"{print $2}')

# --- Build JSON with jq ---
log_files_json=$(printf '%s\n' "${log_files[@]}" | jq -R . | jq -s .)
generated_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

fast=$(printf '%s\n' "$raw" | awk -F'\t' '$1=="DECISION" && $2 !~ /LLM/ && $2 !~ /DENIED_AUTO/{s+=$3} END{print s+0}')
llm=$(printf '%s\n' "$raw" | awk -F'\t' '$1=="DECISION" && $2 ~ /LLM/{s+=$3} END{print s+0}')
classifier=$(printf '%s\n' "$raw" | awk -F'\t' '$1=="DECISION" && $2 ~ /DENIED_AUTO/{s+=$3} END{print s+0}')
overall_p95=$(printf '%s\n' "$raw" | awk -F'\t' '$1=="OVERALL_P95"{print $2}')

decisions_json=$(printf '%s\n' "$raw" \
  | awk -F'\t' '$1=="DECISION"{printf "{\"name\":\"%s\",\"count\":%d}\n", $2, $3}' \
  | jq -s 'sort_by(-.count)')
tools_json=$(printf '%s\n' "$raw" \
  | awk -F'\t' '$1=="TOOL"{printf "{\"name\":\"%s\",\"count\":%d}\n", $2, $3}' \
  | jq -s 'sort_by(-.count)')
turn_json=$(printf '%s\n' "$raw" \
  | awk -F'\t' '$1=="TURN"{printf "{\"decision\":\"%s\",\"count\":%d,\"avg\":%d,\"p50\":%d,\"p95\":%d,\"max\":%d}\n", $2,$3,$4,$5,$6,$7}' \
  | jq -s 'sort_by(-.count)')

# Build denials with jq for safe string escaping (awk has no JSON escape).
denials_json=$(printf '%s\n' "$raw" \
  | awk -F'\t' '$1=="DENIAL"{print $2 "\t" $3}' \
  | jq -R 'split("\t") | {count: (.[0]|tonumber), reason: .[1]}' \
  | jq -s 'sort_by(-.count) | .[0:10]')

data_json=$(jq -n \
  --arg generated_at "$generated_at" \
  --arg filter_since "$FILTER_SINCE" \
  --arg filter_label "$FILTER_LABEL" \
  --argjson log_files "$log_files_json" \
  --argjson total "${total:-0}" \
  --argjson decisions "$decisions_json" \
  --argjson tools "$tools_json" \
  --argjson turnaround "$turn_json" \
  --argjson denials "$denials_json" \
  --argjson fast "$fast" \
  --argjson llm "$llm" \
  --argjson classifier "$classifier" \
  --argjson overall_p95 "${overall_p95:-0}" \
  '{
    generated_at: $generated_at,
    filter_since: $filter_since,
    filter_label: $filter_label,
    log_files: $log_files,
    total: $total,
    decisions: $decisions,
    tools: $tools,
    source_split: { fast: $fast, llm: $llm, classifier: $classifier },
    overall_p95_ms: $overall_p95,
    turnaround: $turnaround,
    denials: $denials
  }')

# DEBUG: emit JSON to stdout (replaced with HTML in Task 5)
echo "$data_json"
