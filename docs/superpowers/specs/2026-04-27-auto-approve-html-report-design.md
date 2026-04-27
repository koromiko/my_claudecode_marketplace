# Auto-Approve HTML Report — Design

**Date:** 2026-04-27
**Plugin:** `default-tools`
**Status:** Approved (brainstorm)

## Goal

Produce a visualized HTML companion to the existing terminal report (currently `default-tools/scripts/usage-report.sh`, renamed to `auto-approve-usage.sh` as part of this work — see "Rename" below) that aggregates decisions logged to `~/.claude/logs/auto-approve.log` by the auto-approve hook.

Phase 1 is **feature parity** with the terminal report, rendered as a self-contained HTML dashboard. The structure must allow Phase 2 additions (time-series, latency distributions, denial drill-downs) without re-architecting.

## Non-goals

- Live/streaming dashboard. The report is a snapshot generated on demand.
- Server component. Output is a single static HTML file.
- New analytics in Phase 1. Only data already aggregated by the terminal report.
- Refactoring the terminal report's aggregation logic or extracting shared aggregation libraries (we rename the script but do not change its behavior).

## Artifacts

1. **`default-tools/scripts/auto-approve-report.sh`** *(new)* — bash script. Reads the log files, aggregates with `awk`, emits a single self-contained HTML file.
2. **`default-tools/commands/auto-approve-report.md`** *(new)* — slash command (`/auto-approve-report`) that invokes the script with `--open` and forwards `$ARGUMENTS` for time-filter flags.
3. **`default-tools/scripts/vendor/chart.umd.min.js`** *(new)* — Chart.js v4 (UMD minified, ~200KB), committed to the repo so the report works offline and renders deterministically without a CDN dependency.
4. **Rename** *(in-place)* — `default-tools/scripts/usage-report.sh` → `default-tools/scripts/auto-approve-usage.sh`. Behavior unchanged. The pair becomes:
   - `auto-approve-usage.sh` — terminal summary (existing)
   - `auto-approve-report.sh` — HTML dashboard (new)

## Rename

`usage-report.sh` is renamed to `auto-approve-usage.sh` for symmetry with the new HTML script and to make its scope (the auto-approve hook) clear from the filename.

**Steps:**
- `git mv default-tools/scripts/usage-report.sh default-tools/scripts/auto-approve-usage.sh`
- Update the in-file usage line (`./usage-report.sh ...` in the header comment) to `./auto-approve-usage.sh ...`.
- Update `default-tools/CLAUDE.md` — the "Usage Report Script" section heading and all four `bash scripts/usage-report.sh ...` examples (lines ~119–132) to reference the new name.
- Update the comment in `default-tools/hooks/permission-denied.sh` (line 3) that mentions `usage-report.sh`.
- No backward-compat shim. The script is internal to the plugin; no external caller depends on the old name.

## CLI surface

```
auto-approve-report.sh [--today] [--days N] [--since YYYY-MM-DD] [--all]
                       [--open] [--out PATH] [--help]
```

| Flag         | Behavior                                                              |
|--------------|-----------------------------------------------------------------------|
| `--today`    | Only today's entries                                                  |
| `--days N`   | Last N days                                                           |
| `--since D`  | On or after date `D` (YYYY-MM-DD)                                     |
| `--all`      | Override default 7-day window; include everything                     |
| `--open`     | After writing, run `open <file>` (macOS)                              |
| `--out PATH` | Output path; default `/tmp/auto-approve-report-<ISO-timestamp>.html`  |

**Default time window:** last 7 days. Mirrors `auto-approve-usage.sh` flag names but differs on default (which is all-time there).

The slash command always passes `--open`; the user can supply additional flags as command arguments.

## Output structure (single HTML file)

Header → KPI strip → 2-column charts row → donut → turnaround table → optional denial reasons → footer.

1. **Header**
   - Title: "Auto-Approve Usage"
   - Subtitle: human-readable time range (e.g. "since 2026-04-20" or "all time")
   - Generated-at timestamp
   - Source log file paths (current + rotated backups actually consumed)

2. **KPI strip (4 cards, grid)**
   - Total decisions
   - Fast-path % (ALLOW + PASS, excluding LLM and DENIED_AUTO*)
   - LLM % (ALLOW_LLM + PASS_LLM)
   - p95 turnaround in milliseconds, computed over every row in the window that has a `DURATION_MS` value (single percentile across all decision types combined)

3. **Charts row (2-col grid, collapses below ~900px)**
   - **Decisions** — horizontal bar chart, one bar per decision type (ALLOW, PASS, ALLOW_LLM, PASS_LLM, DENIED_AUTO\*), sorted descending by count, labeled with count and percentage.
   - **Tool calls** — horizontal bar chart, one bar per tool name, sorted descending. Truncates to top 20 with a "+ N more" footer line if more exist.

4. **Donut chart** — Fast-path vs LLM vs Classifier split. Same buckets and percentages as the terminal report's "Decision source" section.

5. **Turnaround table** — columns: Decision · count · avg · p50 · p95 · max. Same numbers as the terminal report's "Turnaround time (ms)" section. Skips decision types with no `DURATION_MS` rows.

6. **Top classifier denial reasons** — rendered only if at least one `DENIED_AUTO*` row exists in the window. Two columns: count · reason (truncated to 100 chars), top 10 sorted descending.

7. **Footer** — plugin name/version, command line invocation that produced the report, link to the source script for reproducibility.

## Data flow

```
~/.claude/logs/auto-approve.log (+ .1 .2 .3 rotated)
        │
        ▼
  awk aggregation in auto-approve-report.sh
        │ (same patterns as auto-approve-usage.sh)
        ▼
  JSON blob (built with jq -n or printf)
        │
        ▼
  HTML template (heredoc) with inlined JSON + inlined Chart.js
        │
        ▼
  /tmp/auto-approve-report-<ISO>.html  (self-contained, offline-capable)
```

The HTML template is a single heredoc inside the script. Chart.js is inlined via `cat scripts/vendor/chart.umd.min.js` into a `<script>` tag, so the output file has no external dependencies.

## JSON shape (embedded in HTML)

```json
{
  "generated_at": "2026-04-27T14:32:11Z",
  "filter_since": "2026-04-20",
  "filter_label": "last 7 days",
  "log_files": ["/Users/.../auto-approve.log", "/Users/.../auto-approve.log.1"],
  "total": 1284,
  "decisions":  [{"name": "ALLOW", "count": 812}, ...],
  "tools":      [{"name": "Read",  "count": 540}, ...],
  "source_split": {"fast": 1002, "llm": 240, "classifier": 42},
  "turnaround":  [{"decision": "ALLOW", "count": 812, "avg": 12, "p50": 10, "p95": 38, "max": 210}, ...],
  "denials":     [{"count": 14, "reason": "writes outside project root"}, ...]
}
```

## Trade-offs

- **Duplicated aggregation logic** with `auto-approve-usage.sh`. Acceptable: both scripts are <300 lines, no third caller is anticipated, and a shared library would need its own contract. Revisit only if a third report appears.
- **Bundled Chart.js (~200KB committed binary).** Worth it for offline use, deterministic rendering, no CDN trust dependency. The file is added once and rarely updated.
- **Default 7-day window differs from terminal report.** Documented in `--help`, in CLAUDE.md, and in the report header. Trade-off: most users want recent data; `--all` is one flag away.

## Testing

**Manual smoke test (added to plugin CLAUDE.md):**

```bash
# Generate against real log
bash default-tools/scripts/auto-approve-report.sh --days 7 --open

# Verify KPIs match terminal report
bash default-tools/scripts/auto-approve-usage.sh --days 7
# (compare totals, percentages, turnaround p95)
```

**Edge cases to verify manually:**

- Empty log file (`auto-approve.log` exists, zero entries) → graceful "No entries" HTML, not a broken chart.
- Filter window with no entries → same.
- Log rows missing `DURATION_MS` (pre-timing rows) → skipped from turnaround table; do not break the report.
- No `DENIED_AUTO*` rows in window → "Denial reasons" section is omitted entirely (not rendered as an empty table).
- No log files at all → exits 0 with a stderr message, no HTML written, same as `auto-approve-usage.sh`.

No automated tests in Phase 1. The existing `tests/` harness is for the Ollama evaluator and is out of scope.

## Documentation

- Update `default-tools/CLAUDE.md` with a new section "HTML Usage Report" pointing at the script and slash command. Mirror the existing "Usage Report Script" section style.
- Update `default-tools/README.md` if it describes user-facing commands (verify during implementation).

## Phase 2 hooks (not in scope, but informs design)

The output structure is intentionally section-based so future work can append:

- Time-series chart (decisions/day) — slot below the donut.
- Latency-over-time line chart — slot next to time-series.
- Per-tool latency distribution — extra column in the turnaround table or a new section.
- Drill-down: paginated table of recent denials with filters.

The JSON shape can grow additively (new keys) without breaking Phase 1 sections.
