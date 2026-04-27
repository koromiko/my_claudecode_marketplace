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
      [[ "$2" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || { echo "Error: --since requires YYYY-MM-DD format (got: $2)" >&2; exit 1; }
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
  | awk -F'\t' '$1=="DECISION"{print $2 "\t" $3}' \
  | jq -R 'split("\t") | {name: .[0], count: (.[1]|tonumber)}' \
  | jq -s 'sort_by(-.count)')
tools_json=$(printf '%s\n' "$raw" \
  | awk -F'\t' '$1=="TOOL"{print $2 "\t" $3}' \
  | jq -R 'split("\t") | {name: .[0], count: (.[1]|tonumber)}' \
  | jq -s 'sort_by(-.count)')
turn_json=$(printf '%s\n' "$raw" \
  | awk -F'\t' '$1=="TURN"{print $2 "\t" $3 "\t" $4 "\t" $5 "\t" $6 "\t" $7}' \
  | jq -R 'split("\t") | {decision: .[0], count: (.[1]|tonumber), avg: (.[2]|tonumber), p50: (.[3]|tonumber), p95: (.[4]|tonumber), max: (.[5]|tonumber)}' \
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

# --- Render HTML ---
if [[ ! -f "$CHART_JS" ]]; then
  echo "Error: Chart.js not found at ${CHART_JS}. Run Task 2 of the implementation plan." >&2
  exit 1
fi
chart_js_inline=$(cat "$CHART_JS")

cat > "$OUT_PATH" <<HTML_EOF
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Auto-Approve Usage Report — ${FILTER_LABEL}</title>
<style>
  :root {
    --bg: #0f1115; --panel: #181b22; --border: #262a33;
    --text: #e6e8ec; --muted: #8a8f99; --accent: #5fa8ff;
    --green: #4ade80; --yellow: #facc15; --red: #f87171;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--text);
         font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
  .wrap { max-width: 1200px; margin: 0 auto; padding: 32px 24px; }
  header { margin-bottom: 24px; }
  header h1 { margin: 0 0 4px; font-size: 22px; font-weight: 600; }
  header .meta { color: var(--muted); font-size: 12px; }
  .kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
  .kpi { background: var(--panel); border: 1px solid var(--border);
         border-radius: 8px; padding: 16px; }
  .kpi .label { color: var(--muted); font-size: 11px; text-transform: uppercase;
                letter-spacing: .5px; margin-bottom: 6px; }
  .kpi .value { font-size: 24px; font-weight: 600; }
  .row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px; }
  .panel { background: var(--panel); border: 1px solid var(--border);
           border-radius: 8px; padding: 16px; }
  .panel h2 { margin: 0 0 12px; font-size: 14px; font-weight: 600;
              color: var(--muted); text-transform: uppercase; letter-spacing: .5px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border); }
  th { color: var(--muted); font-weight: 500; font-size: 11px; text-transform: uppercase; }
  td.num { text-align: right; font-variant-numeric: tabular-nums; }
  .empty { color: var(--muted); font-style: italic; padding: 24px 0; text-align: center; }
  footer { color: var(--muted); font-size: 11px; margin-top: 32px;
           padding-top: 16px; border-top: 1px solid var(--border); }
  footer code { background: var(--panel); padding: 2px 6px; border-radius: 4px; }
  @media (max-width: 900px) {
    .kpis { grid-template-columns: repeat(2, 1fr); }
    .row { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Auto-Approve Usage</h1>
    <div class="meta">
      <span id="m-range"></span> · generated <span id="m-time"></span><br>
      sources: <span id="m-sources"></span>
    </div>
  </header>

  <section class="kpis">
    <div class="kpi"><div class="label">Total decisions</div><div class="value" id="k-total">0</div></div>
    <div class="kpi"><div class="label">Fast-path</div><div class="value" id="k-fast">0%</div></div>
    <div class="kpi"><div class="label">LLM</div><div class="value" id="k-llm">0%</div></div>
    <div class="kpi"><div class="label">p95 turnaround</div><div class="value" id="k-p95">— ms</div></div>
  </section>

  <div id="empty-banner" class="empty" style="display:none">No entries in this window.</div>

  <section class="row" id="charts-row">
    <div class="panel"><h2>Decisions</h2><canvas id="c-decisions" height="200"></canvas></div>
    <div class="panel"><h2>Tool calls</h2><canvas id="c-tools" height="200"></canvas></div>
  </section>

  <section class="row" id="donut-row">
    <div class="panel"><h2>Decision source</h2><canvas id="c-source" height="200"></canvas></div>
    <div class="panel"><h2>Turnaround time (ms)</h2>
      <table id="t-turn"><thead><tr><th>Decision</th><th class="num">count</th><th class="num">avg</th><th class="num">p50</th><th class="num">p95</th><th class="num">max</th></tr></thead><tbody></tbody></table>
    </div>
  </section>

  <section class="panel" id="denials-panel" style="display:none">
    <h2>Top classifier denial reasons</h2>
    <table id="t-denials"><thead><tr><th class="num" style="width:80px">count</th><th>reason</th></tr></thead><tbody></tbody></table>
  </section>

  <footer>
    Generated by <code>auto-approve-report.sh</code>. Source log:
    <code>~/.claude/logs/auto-approve.log</code>.
  </footer>
</div>

<script>${chart_js_inline}</script>
<script>
const DATA = ${data_json};

document.getElementById('m-range').textContent = DATA.filter_label;
document.getElementById('m-time').textContent = DATA.generated_at;
document.getElementById('m-sources').textContent = DATA.log_files.join(', ');

document.getElementById('k-total').textContent = DATA.total.toLocaleString();
const pct = (n, d) => d > 0 ? Math.round(n * 100 / d) + '%' : '0%';
document.getElementById('k-fast').textContent = pct(DATA.source_split.fast, DATA.total);
document.getElementById('k-llm').textContent = pct(DATA.source_split.llm, DATA.total);
document.getElementById('k-p95').textContent = (DATA.overall_p95_ms || 0) + ' ms';

if (DATA.total === 0) {
  document.getElementById('empty-banner').style.display = 'block';
  document.getElementById('charts-row').style.display = 'none';
  document.getElementById('donut-row').style.display = 'none';
} else {
  const COLORS = {
    ALLOW: '#4ade80', PASS: '#facc15',
    ALLOW_LLM: '#5fa8ff', PASS_LLM: '#a78bfa',
    DENIED_AUTO: '#f87171', DENIED_AUTO_LLM: '#fb923c'
  };
  const colorFor = name => COLORS[name] || '#888';
  const baseOpts = {
    indexAxis: 'y', responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { color: '#8a8f99' }, grid: { color: '#262a33' } },
      y: { ticks: { color: '#e6e8ec' }, grid: { display: false } }
    }
  };

  new Chart(document.getElementById('c-decisions'), {
    type: 'bar',
    data: {
      labels: DATA.decisions.map(d => d.name),
      datasets: [{
        data: DATA.decisions.map(d => d.count),
        backgroundColor: DATA.decisions.map(d => colorFor(d.name))
      }]
    },
    options: baseOpts
  });

  const tools = DATA.tools.slice(0, 20);
  const moreCount = DATA.tools.length - tools.length;
  new Chart(document.getElementById('c-tools'), {
    type: 'bar',
    data: {
      labels: tools.map(t => t.name).concat(moreCount > 0 ? ['+' + moreCount + ' more'] : []),
      datasets: [{
        data: tools.map(t => t.count).concat(moreCount > 0 ? [DATA.tools.slice(20).reduce((a,b) => a + b.count, 0)] : []),
        backgroundColor: '#5fa8ff'
      }]
    },
    options: baseOpts
  });

  new Chart(document.getElementById('c-source'), {
    type: 'doughnut',
    data: {
      labels: ['Fast-path', 'LLM', 'Classifier'],
      datasets: [{
        data: [DATA.source_split.fast, DATA.source_split.llm, DATA.source_split.classifier],
        backgroundColor: ['#4ade80', '#5fa8ff', '#f87171']
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'right', labels: { color: '#e6e8ec' } } }
    }
  });

  const turnBody = document.querySelector('#t-turn tbody');
  if (DATA.turnaround.length === 0) {
    turnBody.innerHTML = '<tr><td colspan="6" class="empty">No timing data.</td></tr>';
  } else {
    turnBody.innerHTML = DATA.turnaround.map(r =>
      '<tr><td>' + r.decision + '</td>' +
      '<td class="num">' + r.count + '</td>' +
      '<td class="num">' + r.avg + '</td>' +
      '<td class="num">' + r.p50 + '</td>' +
      '<td class="num">' + r.p95 + '</td>' +
      '<td class="num">' + r.max + '</td></tr>').join('');
  }

  if (DATA.denials.length > 0) {
    document.getElementById('denials-panel').style.display = 'block';
    document.querySelector('#t-denials tbody').innerHTML = DATA.denials.map(d =>
      '<tr><td class="num">' + d.count + '</td><td>' + d.reason.replace(/[<>&]/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;'}[c])) + '</td></tr>'
    ).join('');
  }
}
</script>
</body>
</html>
HTML_EOF

echo "$OUT_PATH"

if [[ "$OPEN_AFTER" -eq 1 ]]; then
  open "$OUT_PATH" 2>/dev/null || true
fi
