#!/bin/bash
# Aggregate auto-approve hook usage from ~/.claude/logs/auto-approve.log
#
# Usage:
#   ./usage-report.sh [--today] [--days N] [--since YYYY-MM-DD]
#
# Flags:
#   --today         Show only today's entries
#   --days N        Show entries from the last N days (default: all)
#   --since DATE    Show entries on or after DATE (YYYY-MM-DD)
#   --help          Show this help message

set -euo pipefail

LOG_DIR="${HOME}/.claude/logs"
LOG_FILE="${LOG_DIR}/auto-approve.log"

usage() {
  grep '^#' "$0" | grep -v '^#!/' | sed 's/^# \{0,1\}//'
  exit 0
}

# --- Parse arguments ---
FILTER_SINCE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --today)
      FILTER_SINCE=$(date '+%Y-%m-%d')
      shift ;;
    --days)
      [[ -z "${2:-}" ]] && { echo "Error: --days requires a number" >&2; exit 1; }
      FILTER_SINCE=$(date -v "-${2}d" '+%Y-%m-%d' 2>/dev/null \
        || date -d "${2} days ago" '+%Y-%m-%d')
      shift 2 ;;
    --since)
      [[ -z "${2:-}" ]] && { echo "Error: --since requires a date (YYYY-MM-DD)" >&2; exit 1; }
      FILTER_SINCE="$2"
      shift 2 ;;
    --help|-h)
      usage ;;
    *)
      echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# --- Collect log files (current + rotated backups) ---
log_files=()
[[ -f "$LOG_FILE" ]] && log_files+=("$LOG_FILE")
for i in 1 2 3; do
  [[ -f "${LOG_FILE}.${i}" ]] && log_files+=("${LOG_FILE}.${i}")
done

if [[ ${#log_files[@]} -eq 0 ]]; then
  echo "No log files found at ${LOG_FILE}"
  exit 0
fi

# --- Filter entries and pass to awk for aggregation ---
# awk emits lines like: TOTAL:<n>, DECISION:<d>:<n>, TOOL:<t>:<n>
raw=$(awk -v since="$FILTER_SINCE" '
BEGIN { FS = "\t"; total = 0 }
NF < 3 { next }
since != "" && substr($1, 1, 10) < since { next }
{
  total++
  decisions[$2]++
  tools[$3]++
}
END {
  print "TOTAL:" total
  for (d in decisions) print "DECISION:" d ":" decisions[d]
  for (t in tools)     print "TOOL:" t ":" tools[t]
}
' "${log_files[@]}")

total=$(printf '%s\n' "$raw" | awk -F: '$1=="TOTAL"{print $2}')

if [[ -z "$total" || "$total" -eq 0 ]]; then
  echo "No entries found${FILTER_SINCE:+ since $FILTER_SINCE}."
  exit 0
fi

# --- Render report ---
echo ""
echo "=== Auto-Approve Usage Report${FILTER_SINCE:+ (since $FILTER_SINCE)} ==="
echo ""
printf "Total decisions: %s\n" "$total"

# Helper: render a bar for a count/total
bar() {
  local count=$1 total=$2 width=30
  local filled=$(( count * width / total ))
  printf '%0.s#' $(seq 1 $filled 2>/dev/null) 2>/dev/null || true
  printf '%0.s ' $(seq 1 $(( width - filled )) 2>/dev/null) 2>/dev/null || true
}

# --- Decision breakdown ---
echo ""
echo "--- Decisions ---"
decision_data=$(printf '%s\n' "$raw" | awk -F: '$1=="DECISION"{print $3 "\t" $2}' | sort -rn)
max_dlen=$(printf '%s\n' "$raw" | awk -F: '$1=="DECISION"{print length($2)}' | sort -n | tail -1)
while IFS=$'\t' read -r count name; do
  pct=$(( count * 100 / total ))
  filled=$(( count * 30 / total ))
  bar=$(printf '%0.s#' $(seq 1 $filled) 2>/dev/null; printf '%0.s ' $(seq 1 $(( 30 - filled ))) 2>/dev/null)
  printf "  %-${max_dlen}s  %5d  (%3d%%)  |%-30s|\n" "$name" "$count" "$pct" "$bar"
done <<< "$decision_data"

# --- Tool breakdown ---
echo ""
echo "--- Tool Calls ---"
tool_data=$(printf '%s\n' "$raw" | awk -F: '$1=="TOOL"{print $3 "\t" $2}' | sort -rn)
max_tlen=$(printf '%s\n' "$raw" | awk -F: '$1=="TOOL"{print length($2)}' | sort -n | tail -1)
while IFS=$'\t' read -r count name; do
  pct=$(( count * 100 / total ))
  printf "  %-${max_tlen}s  %5d  (%3d%%)\n" "$name" "$count" "$pct"
done <<< "$tool_data"

# --- Fast-path vs LLM vs Classifier ---
echo ""
echo "--- Decision source ---"
fast=$(printf '%s\n' "$raw" | awk -F: '$1=="DECISION" && $2 !~ /LLM/ && $2 !~ /DENIED_AUTO/{s+=$3} END{print s+0}')
llm=$(printf '%s\n' "$raw"  | awk -F: '$1=="DECISION" && $2 ~ /LLM/{s+=$3} END{print s+0}')
cls=$(printf '%s\n' "$raw"  | awk -F: '$1=="DECISION" && $2 ~ /DENIED_AUTO/{s+=$3} END{print s+0}')
fast_pct=$(( fast * 100 / total ))
llm_pct=$(( llm  * 100 / total ))
cls_pct=$((  cls  * 100 / total ))
printf "  %-32s  %5d  (%3d%%)\n" "Fast-path (ALLOW/PASS)"       "$fast" "$fast_pct"
printf "  %-32s  %5d  (%3d%%)\n" "LLM (ALLOW_LLM/PASS_LLM)"     "$llm"  "$llm_pct"
printf "  %-32s  %5d  (%3d%%)\n" "Classifier (DENIED_AUTO*)"    "$cls"  "$cls_pct"

# --- Turnaround time (ms) per decision type ---
# Column 6 is duration_ms (added later; rows without it are skipped).
echo ""
echo "--- Turnaround time (ms) ---"
lat_data=$(awk -v since="$FILTER_SINCE" '
  BEGIN { FS = "\t" }
  NF < 6 { next }
  since != "" && substr($1, 1, 10) < since { next }
  $6 !~ /^[0-9]+$/ { next }
  {
    d = $2
    counts[d]++
    sums[d] += $6
    # Buffer per-decision durations for percentile calculation
    key = d ":" counts[d]
    vals[key] = $6
  }
  END {
    for (d in counts) {
      n = counts[d]
      # Copy to numeric array and sort
      delete arr
      for (i = 1; i <= n; i++) arr[i] = vals[d ":" i]
      # Insertion sort (n is small per decision in typical windows)
      for (i = 2; i <= n; i++) {
        v = arr[i]; j = i - 1
        while (j >= 1 && arr[j] > v) { arr[j+1] = arr[j]; j-- }
        arr[j+1] = v
      }
      avg = sums[d] / n
      p50_idx = int((n + 1) * 0.5); if (p50_idx < 1) p50_idx = 1; if (p50_idx > n) p50_idx = n
      p95_idx = int((n + 1) * 0.95); if (p95_idx < 1) p95_idx = 1; if (p95_idx > n) p95_idx = n
      printf "%s\t%d\t%d\t%d\t%d\t%d\n", d, n, avg, arr[p50_idx], arr[p95_idx], arr[n]
    }
  }
' "${log_files[@]}" | sort)

if [[ -z "$lat_data" ]]; then
  echo "  (no timing data yet — runs before logging added have no duration_ms)"
else
  printf "  %-11s  %7s  %7s  %7s  %7s  %7s\n" "Decision" "count" "avg" "p50" "p95" "max"
  while IFS=$'\t' read -r name count avg p50 p95 mx; do
    [[ -z "$name" ]] && continue
    printf "  %-11s  %7d  %7d  %7d  %7d  %7d\n" "$name" "$count" "$avg" "$p50" "$p95" "$mx"
  done <<< "$lat_data"
fi

# --- Classifier denials detail ---
if (( cls > 0 )); then
  echo ""
  echo "--- Classifier denials (top reasons) ---"
  awk -v since="$FILTER_SINCE" '
    BEGIN { FS = "\t" }
    NF < 5 { next }
    since != "" && substr($1, 1, 10) < since { next }
    $2 ~ /^DENIED_AUTO/ {
      reason = $5
      if (length(reason) > 100) reason = substr(reason, 1, 100) "..."
      reasons[reason]++
    }
    END {
      for (r in reasons) printf "%d\t%s\n", reasons[r], r
    }
  ' "${log_files[@]}" | sort -rn | head -10 | while IFS=$'\t' read -r count reason; do
    printf "  %5d  %s\n" "$count" "$reason"
  done
fi

echo ""
