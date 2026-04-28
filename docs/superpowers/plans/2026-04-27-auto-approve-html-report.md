# Auto-Approve HTML Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `/auto-approve-report` slash command that generates a self-contained HTML dashboard from `~/.claude/logs/auto-approve.log`, and rename the existing terminal report for symmetry.

**Architecture:** A single bash script (`auto-approve-report.sh`) does `awk` aggregation (mirroring the existing terminal script), emits a JSON blob, and embeds it into an HTML heredoc with inlined Chart.js. A thin slash command wraps the script with `--open`. The existing terminal script is renamed in-place to `auto-approve-usage.sh`.

**Tech Stack:** bash, awk, jq (already a plugin prerequisite), Chart.js v4 UMD (vendored).

**Spec:** [`docs/superpowers/specs/2026-04-27-auto-approve-html-report-design.md`](../specs/2026-04-27-auto-approve-html-report-design.md)

**Note on testing:** This plugin has no automated test framework for shell scripts (the existing `tests/` harness is for the Ollama evaluator only — out of scope here). Verification is by explicit manual smoke commands with expected outputs, captured in each task. Run the verification before marking the task complete.

---

## File Structure

| Path | Status | Responsibility |
|---|---|---|
| `default-tools/scripts/usage-report.sh` | Renamed (delete) | — |
| `default-tools/scripts/auto-approve-usage.sh` | Renamed (new path) | Existing terminal report; behavior unchanged |
| `default-tools/scripts/auto-approve-report.sh` | New | HTML report: arg parsing, awk aggregation, JSON emission, HTML rendering |
| `default-tools/scripts/vendor/chart.umd.min.js` | New (vendored) | Chart.js v4 UMD minified, inlined into output HTML |
| `default-tools/scripts/vendor/.gitattributes` | New | Mark vendored file as `linguist-vendored` so it doesn't dominate diffs/PRs |
| `default-tools/commands/auto-approve-report.md` | New | Slash command (`/auto-approve-report`) wrapping the script with `--open` |
| `default-tools/CLAUDE.md` | Modified | Update "Usage Report Script" refs to the new name; add "HTML Usage Report" section |
| `default-tools/hooks/permission-denied.sh` | Modified (1 comment line) | Update reference to renamed script |

---

## Task 1: Rename `usage-report.sh` → `auto-approve-usage.sh`

**Files:**
- Rename: `default-tools/scripts/usage-report.sh` → `default-tools/scripts/auto-approve-usage.sh`
- Modify: `default-tools/scripts/auto-approve-usage.sh:5` (in-file usage line in header comment)
- Modify: `default-tools/CLAUDE.md` (4 references in lines ~119–132 + heading)
- Modify: `default-tools/hooks/permission-denied.sh:3` (1 comment reference)

- [ ] **Step 1: Move the script with git mv (preserves history)**

```bash
cd /Users/sthuang/Project/my_claudecode_marketplace
git mv default-tools/scripts/usage-report.sh default-tools/scripts/auto-approve-usage.sh
```

- [ ] **Step 2: Update the in-file usage example in the header comment**

In `default-tools/scripts/auto-approve-usage.sh` line 5, change:
```
#   ./usage-report.sh [--today] [--days N] [--since YYYY-MM-DD]
```
to:
```
#   ./auto-approve-usage.sh [--today] [--days N] [--since YYYY-MM-DD]
```

- [ ] **Step 3: Update the comment in `hooks/permission-denied.sh`**

In `default-tools/hooks/permission-denied.sh` line 3, change `usage-report.sh` to `auto-approve-usage.sh`.

- [ ] **Step 4: Update `default-tools/CLAUDE.md`**

In the "Usage Report Script" section (around line 117–132):
- Change the section heading from `### Usage Report Script` to `### Auto-Approve Usage Report (terminal)`.
- Change the descriptive sentence from `` `scripts/usage-report.sh` aggregates...`` to `` `scripts/auto-approve-usage.sh` aggregates...``
- In the four `bash scripts/usage-report.sh ...` examples, change `usage-report.sh` to `auto-approve-usage.sh`.

- [ ] **Step 5: Verify nothing else still references the old name**

Run:
```bash
cd /Users/sthuang/Project/my_claudecode_marketplace
grep -rn "usage-report" --include="*.md" --include="*.sh" --include="*.json" default-tools/ docs/ 2>/dev/null
```
Expected: no output, **except** the spec file (`docs/superpowers/specs/2026-04-27-auto-approve-html-report-design.md`) which intentionally references the old name in the "Rename" section. Any other hit is a missed reference — go fix it before continuing.

- [ ] **Step 6: Verify the renamed script still works**

```bash
bash default-tools/scripts/auto-approve-usage.sh --today
```
Expected: same output the old script produced (`=== Auto-Approve Usage Report ...` with decisions, tools, fast-path/LLM split, turnaround). If today's log is empty you'll see `No entries found since YYYY-MM-DD.` — that's also fine.

- [ ] **Step 7: Commit**

```bash
git add default-tools/scripts/auto-approve-usage.sh default-tools/CLAUDE.md default-tools/hooks/permission-denied.sh
git commit -m "refactor(default-tools): rename usage-report.sh to auto-approve-usage.sh"
```

---

## Task 2: Vendor Chart.js v4

**Files:**
- Create: `default-tools/scripts/vendor/chart.umd.min.js`
- Create: `default-tools/scripts/vendor/.gitattributes`

- [ ] **Step 1: Create the vendor directory and download Chart.js v4 UMD minified**

```bash
cd /Users/sthuang/Project/my_claudecode_marketplace
mkdir -p default-tools/scripts/vendor
curl -fsSL https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js \
  -o default-tools/scripts/vendor/chart.umd.min.js
```

- [ ] **Step 2: Verify the file**

```bash
ls -lh default-tools/scripts/vendor/chart.umd.min.js
head -c 200 default-tools/scripts/vendor/chart.umd.min.js
```
Expected: file exists, size in the 150–250KB range, first bytes look like `/*! Chart.js v4...` or a minified IIFE (e.g. `!function(...)`). If it's HTML or an error page, redo step 1 with a different mirror.

- [ ] **Step 3: Mark the file as vendored to keep diffs sane**

Create `default-tools/scripts/vendor/.gitattributes` with:
```
chart.umd.min.js linguist-vendored
chart.umd.min.js -diff
```
The `-diff` attribute prevents `git diff` from dumping the entire minified file when it changes.

- [ ] **Step 4: Commit**

```bash
git add default-tools/scripts/vendor/chart.umd.min.js default-tools/scripts/vendor/.gitattributes
git commit -m "feat(default-tools): vendor Chart.js v4 for offline HTML reports"
```

---

## Task 3: Build `auto-approve-report.sh` — argument parsing + log discovery

This task delivers a runnable script skeleton: it parses flags, finds log files, and (for now) prints the resolved configuration to stderr. Later tasks add aggregation and HTML rendering.

**Files:**
- Create: `default-tools/scripts/auto-approve-report.sh`

- [ ] **Step 1: Write the skeleton script**

Create `default-tools/scripts/auto-approve-report.sh` with content:

```bash
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
  grep '^#' "$0" | grep -v '^#!/' | sed 's/^# \{0,1\}//'
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
      [[ -z "${2:-}" ]] && { echo "Error: --days requires a number" >&2; exit 1; }
      FILTER_SINCE=$(date -v "-${2}d" '+%Y-%m-%d' 2>/dev/null \
        || date -d "${2} days ago" '+%Y-%m-%d')
      FILTER_LABEL="last ${2} days"
      EXPLICIT_WINDOW=1
      shift 2 ;;
    --since)
      [[ -z "${2:-}" ]] && { echo "Error: --since requires a date (YYYY-MM-DD)" >&2; exit 1; }
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
      [[ -z "${2:-}" ]] && { echo "Error: --out requires a path" >&2; exit 1; }
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
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x default-tools/scripts/auto-approve-report.sh
```

- [ ] **Step 3: Verify flag parsing**

```bash
bash default-tools/scripts/auto-approve-report.sh --help | head -15
```
Expected: usage block printed (the `#`-prefixed header lines without the shebang).

```bash
bash default-tools/scripts/auto-approve-report.sh --days 3 2>&1 >/dev/null
```
Expected: stderr contains `since=` (a date 3 days ago), `label=last 3 days`, `out=/tmp/auto-approve-report-...html`, `open=0`.

```bash
bash default-tools/scripts/auto-approve-report.sh --all --out /tmp/foo.html 2>&1 >/dev/null
```
Expected: stderr contains `since=` (empty), `label=all time`, `out=/tmp/foo.html`.

- [ ] **Step 4: Commit**

```bash
git add default-tools/scripts/auto-approve-report.sh
git commit -m "feat(default-tools): add auto-approve-report.sh skeleton with flag parsing"
```

---

## Task 4: Aggregate the log into a JSON blob

Add the aggregation logic. The script will print a single JSON object to stdout (no HTML yet) so we can verify the data shape independently.

**Files:**
- Modify: `default-tools/scripts/auto-approve-report.sh` (replace the DEBUG block)

- [ ] **Step 1: Replace the debug block with aggregation + JSON emission**

In `default-tools/scripts/auto-approve-report.sh`, delete the `# DEBUG: print resolved config (removed in Task 4)` block and everything inside its braces, and append:

```bash
# --- Aggregate ---
# Emit raw rows the same way usage-report.sh does, plus turnaround details
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
  # Turnaround per decision: sort durations and emit count/avg/p50/p95/max
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
  # Overall p95 across all decisions
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
# Pass the awk output to jq via stdin; jq groups it into the final shape.
log_files_json=$(printf '%s\n' "${log_files[@]}" | jq -R . | jq -s .)
generated_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

# Compute fast/llm/classifier split from decision counts
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
```

- [ ] **Step 2: Verify the JSON shape against a real log**

```bash
bash default-tools/scripts/auto-approve-report.sh --days 7 | jq '. | {total, filter_label, decisions: (.decisions[0:3]), source_split, overall_p95_ms}'
```
Expected: a valid JSON object printed. `total` is a non-negative integer, `decisions` is a non-empty array of `{name, count}` objects (assuming the log has 7-day data), `source_split` has `fast/llm/classifier`, `overall_p95_ms` is a non-negative integer.

- [ ] **Step 3: Cross-check totals against the terminal report**

```bash
bash default-tools/scripts/auto-approve-usage.sh --days 7 | grep "Total decisions"
bash default-tools/scripts/auto-approve-report.sh --days 7 | jq .total
```
Expected: the two totals match exactly.

- [ ] **Step 4: Verify the empty-log edge case**

```bash
bash default-tools/scripts/auto-approve-report.sh --since 2099-01-01 | jq '{total, decisions, tools, denials}'
```
Expected: `total: 0`, `decisions: []`, `tools: []`, `denials: []`. Script exits 0.

- [ ] **Step 5: Commit**

```bash
git add default-tools/scripts/auto-approve-report.sh
git commit -m "feat(default-tools): aggregate auto-approve log into JSON for HTML report"
```

---

## Task 5: Render HTML with embedded JSON and inlined Chart.js

Replace the `echo "$data_json"` debug line with the HTML template and write to `OUT_PATH`.

**Files:**
- Modify: `default-tools/scripts/auto-approve-report.sh` (replace the trailing `echo "$data_json"`)

- [ ] **Step 1: Replace the debug echo with HTML rendering**

In `default-tools/scripts/auto-approve-report.sh`, delete the trailing block:
```bash
# DEBUG: emit JSON to stdout (replaced with HTML in Task 5)
echo "$data_json"
```
and append:

```bash
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

// Fill metadata
document.getElementById('m-range').textContent = DATA.filter_label;
document.getElementById('m-time').textContent = DATA.generated_at;
document.getElementById('m-sources').textContent = DATA.log_files.join(', ');

// KPIs
document.getElementById('k-total').textContent = DATA.total.toLocaleString();
const pct = (n, d) => d > 0 ? Math.round(n * 100 / d) + '%' : '0%';
document.getElementById('k-fast').textContent = pct(DATA.source_split.fast, DATA.total);
document.getElementById('k-llm').textContent = pct(DATA.source_split.llm, DATA.total);
document.getElementById('k-p95').textContent = (DATA.overall_p95_ms || 0) + ' ms';

if (DATA.total === 0) {
  document.getElementById('empty-banner').style.display = 'block';
  document.getElementById('charts-row').style.display = 'none';
  document.getElementById('donut-row').style.display = 'none';
  // Stop here — no charts to draw.
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

  // Tools: top 20 + "+N more"
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

  // Donut: fast vs llm vs classifier
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

  // Turnaround table
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

  // Denials (only if any)
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
```

- [ ] **Step 2: Generate a real report**

```bash
bash default-tools/scripts/auto-approve-report.sh --days 7
```
Expected: prints a path like `/tmp/auto-approve-report-20260427T143211.html` to stdout. Exit 0. No stderr noise.

- [ ] **Step 3: Sanity-check the HTML file**

```bash
report=$(bash default-tools/scripts/auto-approve-report.sh --days 7)
ls -lh "$report"
grep -c '<canvas' "$report"      # expect: 3
grep -c 'Chart.js v4' "$report"  # expect: ≥1 (from the inlined library banner)
```
Expected: file size in the 200–300KB range (Chart.js dominates), three `<canvas>` elements, the Chart.js banner is present.

- [ ] **Step 4: Visually verify in browser**

```bash
open "$report"
```
Expected, in the browser:
- Header shows "Auto-Approve Usage", `last 7 days`, generated timestamp, source log paths.
- Four KPI cards: total, fast-path %, LLM %, p95 ms — values match the terminal report (`auto-approve-usage.sh --days 7`).
- Decisions bar chart and Tool calls bar chart render with bars sorted descending.
- Donut chart shows the fast/LLM/classifier split.
- Turnaround table has one row per decision type that has timing data.
- Denial reasons section appears **only** if there are `DENIED_AUTO*` entries; otherwise hidden.

- [ ] **Step 5: Verify empty-window edge case**

```bash
bash default-tools/scripts/auto-approve-report.sh --since 2099-01-01 --out /tmp/empty.html
open /tmp/empty.html
```
Expected: header still renders, KPI cards show `0` / `0%` / `0%` / `0 ms`, an "No entries in this window." message replaces the chart sections, no JS errors in the browser console.

- [ ] **Step 6: Verify `--open` flag**

```bash
bash default-tools/scripts/auto-approve-report.sh --days 7 --open
```
Expected: report path is printed AND the browser opens the file automatically.

- [ ] **Step 7: Commit**

```bash
git add default-tools/scripts/auto-approve-report.sh
git commit -m "feat(default-tools): render HTML dashboard with embedded Chart.js"
```

---

## Task 6: Add the `/auto-approve-report` slash command

**Files:**
- Create: `default-tools/commands/auto-approve-report.md`

- [ ] **Step 1: Create the commands directory and the command file**

```bash
mkdir -p default-tools/commands
```

Create `default-tools/commands/auto-approve-report.md` with content:

````markdown
---
description: Generate an HTML dashboard of auto-approve hook usage and open it in the browser
allowed-tools:
  - Bash(bash:*)
  - Bash(open:*)
---

# Auto-Approve Report

Generate a self-contained HTML report of auto-approve hook decisions from `~/.claude/logs/auto-approve.log` and open it in the default browser.

The report covers the **last 7 days by default**. Pass time-filter flags as command arguments to widen or narrow the window.

## Arguments

`$ARGUMENTS` is forwarded to the script verbatim. Supported flags:

- `--today` — only today's entries
- `--days N` — last N days
- `--since YYYY-MM-DD` — on or after a specific date
- `--all` — entire log (overrides default 7-day window)

## Instructions

Run the report script with `--open` plus any user-supplied flags. The script prints the output path to stdout and opens the file in the default browser.

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/auto-approve-report.sh" --open $ARGUMENTS
```

After the command completes, summarize:
- The output file path
- The time window covered
- One-line headline (total decisions, fast-path %)

If the script reports `No log files found`, tell the user the auto-approve hook hasn't logged anything yet and point them at `~/.claude/logs/auto-approve.log`.
````

- [ ] **Step 2: Refresh the plugin cache so Claude Code picks up the new command**

```bash
cd /Users/sthuang/Project/my_claudecode_marketplace
./scripts/bump-plugin.sh default-tools none
```
Expected: cache cleared message. (Use `./scripts/bump-plugin.sh default-tools` to also bump the patch version per CLAUDE.md.)

- [ ] **Step 3: Verify the slash command is wired up**

In a Claude Code session, run `/auto-approve-report --days 3`.
Expected: the script runs, the path is printed, the browser opens the file. The command also works with no arguments (defaults to 7 days).

- [ ] **Step 4: Commit**

```bash
git add default-tools/commands/auto-approve-report.md
git commit -m "feat(default-tools): add /auto-approve-report slash command"
```

---

## Task 7: Update `default-tools/CLAUDE.md`

**Files:**
- Modify: `default-tools/CLAUDE.md` (add a new "HTML Usage Report" subsection right after the existing "Usage Report Script" / "Auto-Approve Usage Report (terminal)" section)

- [ ] **Step 1: Add the HTML report section**

After the existing terminal-report subsection (the one renamed in Task 1), append a new subsection. The full text to insert:

````markdown
### Auto-Approve Usage Report (HTML)

`scripts/auto-approve-report.sh` generates a self-contained HTML dashboard with KPI cards, decision/tool bar charts, a fast-path vs LLM donut, and a turnaround table. The report works offline (Chart.js is vendored at `scripts/vendor/chart.umd.min.js`).

```bash
# Default: last 7 days, written to /tmp/auto-approve-report-<ISO>.html
bash scripts/auto-approve-report.sh

# Generate and open in the browser
bash scripts/auto-approve-report.sh --open

# Filter by time window (mirrors the terminal report's flags)
bash scripts/auto-approve-report.sh --today
bash scripts/auto-approve-report.sh --days 30
bash scripts/auto-approve-report.sh --since 2026-04-01
bash scripts/auto-approve-report.sh --all          # override default 7-day window

# Custom output path
bash scripts/auto-approve-report.sh --out ~/Desktop/auto-approve.html --open
```

Slash command: `/auto-approve-report [flags]` runs the script with `--open` and forwards any flags as arguments.

The default time window is **last 7 days** (the terminal report defaults to all-time). Use `--all` to match the terminal report's default.
````

- [ ] **Step 2: Verify CLAUDE.md is consistent**

```bash
cd /Users/sthuang/Project/my_claudecode_marketplace
grep -n "auto-approve-usage\|auto-approve-report\|usage-report" default-tools/CLAUDE.md
```
Expected: every result references either `auto-approve-usage.sh` or `auto-approve-report.sh`. No `usage-report.sh` references remain.

- [ ] **Step 3: Commit**

```bash
git add default-tools/CLAUDE.md
git commit -m "docs(default-tools): document HTML auto-approve report"
```

---

## Task 8: Final integration check

- [ ] **Step 1: Confirm the full surface from a clean shell**

```bash
cd /Users/sthuang/Project/my_claudecode_marketplace

# Terminal report still works at its new path
bash default-tools/scripts/auto-approve-usage.sh --days 7 | head -5

# HTML report runs end-to-end
report=$(bash default-tools/scripts/auto-approve-report.sh --days 7)
echo "$report"
ls -lh "$report"

# JSON-internal data is parseable
grep -o 'const DATA = .*;' "$report" | head -c 200
```
Expected:
- Terminal report prints its standard header with the 7-day window.
- HTML report path is printed and the file is 200–300KB.
- The embedded `const DATA = {...};` is a single-line, well-formed JSON object.

- [ ] **Step 2: Confirm KPI parity with the terminal report**

```bash
bash default-tools/scripts/auto-approve-usage.sh --days 7 | grep -E "Total decisions|Fast-path|LLM"
report=$(bash default-tools/scripts/auto-approve-report.sh --days 7)
grep -oE '"total":[0-9]+|"fast":[0-9]+|"llm":[0-9]+|"classifier":[0-9]+' "$report"
```
Expected: the same totals appear in both outputs.

- [ ] **Step 3: Confirm the slash command works end-to-end**

In a Claude Code session: `/auto-approve-report --today`. Verify the browser opens a report scoped to today.

- [ ] **Step 4: Final commit if anything was tweaked**

If any small fixes were needed during integration, commit them with a message like `fix(default-tools): integration polish for auto-approve-report`. If everything passed cleanly, no commit needed.

---

## Self-Review (already performed by author)

- **Spec coverage**: Each spec section has a task — rename (T1), Chart.js vendoring (T2), CLI surface (T3), aggregation/JSON shape (T4), output structure including all six sections + footer (T5), slash command (T6), CLAUDE.md docs (T7), edge cases (T4 step 4 + T5 step 5 + T8).
- **No placeholders**: All code blocks are complete and runnable. No "TBD" or "similar to above".
- **Type consistency**: JSON keys (`total`, `decisions`, `tools`, `source_split.fast/llm/classifier`, `turnaround[].decision`, `denials[].reason`, `overall_p95_ms`) are used identically in the awk emit, the jq shape, and the HTML script.
