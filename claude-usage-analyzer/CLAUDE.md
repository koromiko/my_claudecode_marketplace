# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a Claude Code plugin that analyzes Claude Code usage data from two sources:
1. **Session data** from `~/.claude/projects/` (JSONL session logs)
2. **Global stats** from `~/.claude.json` (skill usage, startup counts, per-project cumulative stats)

It generates comprehensive usage reports with quantitative and qualitative insights via the `/analyze-usage` slash command.

## Plugin Structure

- `.claude-plugin/plugin.json` - Plugin manifest
- `commands/analyze-usage.md` - Slash command definition with execution steps
- `scripts/` - Python analysis scripts (no external dependencies, Python 3.8+ standard library only)
- `reference/analysis_prompt.md` - Guidelines for Claude to follow when analyzing data
- `reports/data/` - Generated report data JSON files
- `reports/sessions/` - Generated individual session HTML detail pages

## Script Pipeline

The analysis runs as a multi-step pipeline:

1. **generate_report.py** - Entry point; extracts sessions from `~/.claude/projects/` JSONL files
   - Parses CLI args (`--period`, `--days`, `--project`, `--start/--end`, `--output-dir`, `--compare-previous`)
   - Uses `SessionExtractor` from extract_sessions.py
   - Uses `GlobalStatsExtractor` from extract_global_stats.py for `~/.claude.json` data
   - Filters out empty sessions (duration <= 0 AND tool_calls = 0) and agent sub-sessions (`agent-*.jsonl`)
   - Filters out idle sessions (>6hr with <5 tool calls) to prevent duration skew
   - With `--compare-previous`: extracts previous period and calculates deltas
   - With `--session <uuid>`: searches for the specific session file, extracts enriched deep-dive data
   - Outputs: `reports/data/report_data_{dates}.json` (or `report_data_{dates}_{project}.json` with project filter)
   - Single-session output: `reports/data/session_deep_dive_{uuid_short}.json`

2. **analyze_sessions.py** - Quantitative analysis
   - Auto-detects input format (extract_sessions output vs report_data format) via `detect_input_format()`
   - Normalizes sessions to common format for analysis
   - Computes statistics, distributions, per-project/task-type breakdowns
   - Classifies sessions into types: "work" vs "lookup" (based on duration, tool calls, edits)
   - Calculates duration histogram with predefined buckets (<1min, 1-5min, 5-15min, 15-30min, 30-60min, 60min+)
   - Computes activity metrics (sessions with edits, commits, tests) as alternative to completion heuristics
   - Detects issues via heuristics (command errors, high tool ratio >10:1, rapid interactions <5 min with >20 turns)
   - Outputs: `aggregate_report.json`, `session_analysis.json`

3. **prepare_qualitative_analysis.py** - Extracts sessions by category
   - Sessions with issues, successful sessions, long-running sessions (>60 min threshold)
   - Tool usage patterns comparing successful vs problematic sessions
   - Claude Code feature usage patterns (skills, agents, slash commands by outcome)
   - Outputs: `qualitative_data.json`

4. **Claude analysis** - Claude reads both JSON outputs and generates the final markdown report

Optional HTML output:

5. **generate_html_report.py** (for `--html` flag)
   - Loads `aggregate_report.json` and `qualitative_data.json`
   - Uses HTML template from `html_template.py`
   - Fills quantitative data (stats, charts, tables) into template
   - Outputs partial HTML with `<!-- CLAUDE_QUALITATIVE section_name -->` markers
   - Claude then fills qualitative sections and saves the final HTML

6. **html_template.py** - HTML template module
   - Self-contained HTML with embedded CSS (dark theme, responsive)
   - CSS-based bar charts for tool usage rankings
   - SVG pie chart for task type distribution
   - Progress bars for completion/issue rates
   - Placeholder markers for Claude to fill qualitative content

7. **session_template.py** - HTML template for individual session detail pages
   - Renders a single session's JSONL as a threaded conversation view
   - Shared dark-theme styles consistent with html_template.py
   - Color-coded tool call blocks (Read=blue, Edit=green, Write=purple, Bash=yellow, etc.)
   - Output: `reports/sessions/session_{id}.html`

8. **analyze_single_session.py** - Single session deep-dive analysis
   - Takes `session_deep_dive_{uuid}.json` from generate_report.py --session
   - Produces tool usage patterns, workflow phase detection, conversation analysis, file impact
   - Outputs: `session_analysis_{uuid_short}.json`

## Key Implementation Details

### Session Data Format (`~/.claude/projects/`)
- Claude Code stores sessions as JSONL files in `~/.claude/projects/{encoded-project-path}/`
- Each line is a JSON object: user messages (`type: "user"`), assistant messages (`type: "assistant"` with `tool_use` blocks), metadata, summaries (`type: "summary"`)
- Project directory names use `-` as path separator (e.g., `Users-foo-myproject`)
- Agent sub-sessions (files starting with `agent-`) are excluded from analysis

### Global Stats Format (`~/.claude.json`)
The `~/.claude.json` file contains cumulative usage data:

**Global Usage Stats:**
- `numStartups`: Total number of Claude Code startups
- `promptQueueUseCount`: Total prompt queue usage count
- `firstStartTime`: ISO timestamp of first Claude Code usage
- `installMethod`: Installation method (native, npm, etc.)

**Skill Usage (`skillUsage` object):**
- Keys are skill names (e.g., `"commit"`, `"ralph-wiggum:ralph-loop"`)
- Values contain `usageCount` (total invocations) and `lastUsedAt` (timestamp in ms)

**Per-Project Stats (`projects` object):**
- Keys are project paths (e.g., `"/Users/foo/myproject"`)
- Values contain "last session" stats (not cumulative):
  - `lastCost`: Cost in USD of last session
  - `lastTotalInputTokens`, `lastTotalOutputTokens`: Token counts
  - `lastTotalCacheCreationInputTokens`, `lastTotalCacheReadInputTokens`: Cache stats
  - `lastLinesAdded`, `lastLinesRemoved`: Code change metrics
  - `lastDuration`, `lastAPIDuration`, `lastToolDuration`: Duration in ms
  - `lastModelUsage`: Per-model breakdown with tokens and costs
  - `lastSessionId`: UUID of last session

**Tips History (`tipsHistory` object):**
- Tracks which tips/hints have been shown to the user
- Keys are tip names, values are show counts

### Claude Code Feature Tracking
The extractor tracks three categories of Claude Code features:
- **skills_invoked**: Skill tool calls with skill name and args
- **agents_spawned**: Task tool calls with subagent_type
- **slash_commands**: User messages starting with `/` (e.g., `/commit`, `/help`)

### Task Classification
Tasks are classified by keyword matching in prompts (in priority order), with session-characteristic fallback:
- `bug_fix`: bug, fix, error, issue, broken, doesn't work, failing, crash, resolve, patch
- `testing`: test, spec, e2e, unit test, integration test, coverage, jest, pytest
- `config`: config, setup, install, terraform, infra, deploy, ci, cd, docker, kubernetes
- `review`: review, pr, pull request, code review, feedback, approve, merge
- `exploration`: explain, what is, how does, document, learn, describe, help me understand
- `debug`: debug, investigate, why, understand, trace, log, look into, diagnose
- `refactor`: refactor, clean, improve, optimize, restructure, simplify, rename
- `feature`: add, create, implement, new feature, build, introduce, develop, make
- `update`: update, change, modify, edit, adjust, tweak, revise, enhance, upgrade, migrate
- `lookup`: find, search, locate, where, show me, list, get, check, verify, validate; also: sessions <5 min with no edits and <10 tool calls default to lookup instead of general
- `general`: fallback (target: <30% of sessions)

### Session Type Classification
Sessions are classified as "work" or "lookup" based on activity:
- `lookup`: <5 min duration, <10 tool calls, no file edits (quick information retrieval)
- `work`: >=5 min duration OR >=10 tool calls OR has file edits (substantive work sessions)

### Completion Detection
The completion detection system uses a multi-layered approach:

**1. Task-Type Specific Criteria:**
Each task type has different completion signals:
| Task Type | Completion Signals |
|-----------|-------------------|
| `bug_fix` | Edit/Write + (test run OR git commit) |
| `feature` | Edit/Write + files_touched > 0 |
| `refactor` | Edit/Write + files_touched > 1 |
| `debug` | Read operations + duration > 5 min + user_msgs > 1 |
| `testing` | Test command execution |
| `config` | Bash OR Edit/Write |
| `exploration` | Read/Grep/Glob + user_msgs > 1 |
| `general` | Edit/Write OR (files_touched > 0 + git commit/push) |

**2. Failure Signal Detection:**
Signals that indicate a session may have failed or been abandoned:
- `error_in_commands`: Error patterns in bash output (severity 1-3 based on count)
- `high_retry_ratio`: Tool-to-message ratio > 15
- `quick_abandonment`: Duration < 2 min with > 5 tool calls
- `read_without_edit`: Many reads but no edits with > 10 tool calls
- `failed_git_commit`: Git commit with error indicators
- `user_frustration`: Keywords like "never mind", "doesn't work", "give up"
- `no_tangible_output`: Long session with no edits or commits

**3. Confidence Scoring (0-100):**
Each session receives a confidence score based on:
- Positive signals: has_edits (+15), successful_commit (+20), git_push (+10), tests_ran (+15), files_touched (+10), multiple_files (+5), sufficient_work_time (+5), user_engagement (+5)
- Negative signals: errors_detected (-5 to -20), failed_commit (-15), high_retry_ratio (-15), user_frustration (-20), quick_abandonment (-20), no_tangible_output (-10)
- Threshold: Sessions with confidence >= 60 are considered "likely completed"

**4. Expanded Outcome States:**
Sessions are classified into one of these outcomes:
| Outcome | Definition |
|---------|------------|
| `completed` | Task accomplished, no issues, confidence >= 60 |
| `completed_with_issues` | Task done but had problems along the way |
| `partially_completed` | Some criteria met but not all |
| `exploration_complete` | Research/exploration task answered (no code needed) |
| `lookup_complete` | Short read-only session that answered a question (duration <5 min, no edits, no frustration) |
| `abandoned` | Quick abandonment or user frustration signals |
| `blocked` | External dependency prevented completion (errors after significant effort) |
| `unclear` | Cannot determine outcome |

### Issue Detection Heuristics
- `command_error`: Commands containing "error" or "fail"
- `high_tool_usage`: Tool calls per user message ratio > 10
- `rapid_interactions`: >20 turns in <5 minutes

### Git Operations Classification
Git commands are classified into categories:
- `has_commit`: git commit was executed
- `has_push`: git push was executed
- `has_add`: git add was executed
- `read_only`: Only read operations (status, log, diff, branch, show)
- `has_failed_commit`: Commit appears to have failed (error in output)

### Metrics Formulas
- Completion rate: `(completed + completed_with_issues + exploration_complete + lookup_complete) / total_sessions * 100`
- Expanded completion rate: Includes all successful outcomes
- Average confidence score: Mean of all session confidence scores
- Tools per file: `total_tool_calls / files_touched`
- Files per hour: `files_touched / (duration_minutes / 60)`
- Percentiles: Linear interpolation at percentile index

## Running Scripts Directly

```bash
# Extract sessions from last 7 days
python3 scripts/generate_report.py --period weekly

# Filter by project
python3 scripts/generate_report.py --period weekly --project myapp

# Custom date range
python3 scripts/generate_report.py --start 2025-12-01 --end 2025-12-15

# Run quantitative analysis on generated data
python3 scripts/analyze_sessions.py --input reports/data/report_data_*.json --report aggregate_report.json --output session_analysis.json

# Prepare qualitative data
python3 scripts/prepare_qualitative_analysis.py --input reports/data/report_data_*.json --output-data qualitative_data.json

# Direct session extraction (standalone, for debugging)
python3 scripts/extract_sessions.py --days 7 --output sessions.json
python3 scripts/extract_sessions.py --days 7 --messages  # Include raw messages
python3 scripts/extract_sessions.py --days 7 --full      # Full data, no summarization

# Extract global stats from ~/.claude.json (standalone)
python3 scripts/extract_global_stats.py --output global_stats.json
python3 scripts/extract_global_stats.py --skills-only    # Only skill usage data
python3 scripts/extract_global_stats.py --project myapp  # Filter projects by name

# Analyze a single session by UUID
python3 scripts/generate_report.py --session 1baea1cc-ad12-472d-806b-cf9455a101df
python3 scripts/analyze_single_session.py --input reports/data/session_deep_dive_1baea1cc.json --output session_analysis_1baea1cc.json

# Generate HTML report (after running analyze_sessions.py and prepare_qualitative_analysis.py)
python3 scripts/generate_html_report.py \
  --aggregate aggregate_report.json \
  --qualitative qualitative_data.json \
  --report-data reports/data/report_data_*.json \
  --output reports/analysis_report.html \
  --partial
```

## Data Flow

```
~/.claude/projects/*.jsonl          ~/.claude.json
        |                                  |
        v                                  v
    SessionExtractor              GlobalStatsExtractor
        |                                  |
        +------------+     +---------------+
                     |     |
                     v     v
              generate_report.py
                     |
                     v
         reports/data/report_data_{dates}.json
         (includes both session data + global_stats)
                     |
        +------------+------------+
        |                         |
        v                         v
analyze_sessions.py    prepare_qualitative_analysis.py
        |                         |
        v                         v
aggregate_report.json     qualitative_data.json
session_analysis.json
        |                         |
        +------------+------------+
                     |
        +------------+------------+
        |                         |
        v                         v
    [Markdown output]        [HTML output (--html flag)]
Claude reads JSONs           generate_html_report.py
        |                            |
        v                            v
reports/analysis_report_{dates}.md   partial HTML + markers
                                            |
                                            v
                                     Claude fills qualitative
                                            |
                                            v
                                     reports/analysis_report_{dates}.html
                                            |
                                            v
                                     reports/sessions/session_{id}.html
                                     (individual session detail pages)
```

**Note on output locations:**
- Report data: `reports/data/` (within plugin or CWD)
- Final reports: `reports/` (markdown and HTML)
- Session detail pages: `reports/sessions/`
- Intermediate files (`aggregate_report.json`, `session_analysis.json`, `qualitative_data.json`): generated in the current working directory

### HTML Report Features
- Self-contained: all CSS embedded, no external dependencies
- Dark theme with responsive design (works on mobile)
- CSS-based horizontal bar charts for tool usage
- SVG pie chart for task type distribution
- Progress bars showing completion and issue rates
- Time series sparkline for sessions over time
- Qualitative sections filled by Claude after initial generation

## Testing & Validation

There are no automated tests. To validate changes:

1. **Test data extraction**: Run with a short period and verify JSON output structure
   ```bash
   python3 scripts/generate_report.py --days 1
   cat reports/data/report_data_*.json | python3 -m json.tool > /dev/null && echo "Valid JSON"
   ```

2. **Test analysis pipeline**: Run full pipeline and check for Python errors
   ```bash
   python3 scripts/generate_report.py --period daily && \
   python3 scripts/analyze_sessions.py --input reports/data/report_data_*.json --report aggregate_report.json --output session_analysis.json && \
   python3 scripts/prepare_qualitative_analysis.py --input reports/data/report_data_*.json --output-data qualitative_data.json
   ```

3. **Verify empty session filtering**: Sessions with `duration <= 0 AND tool_calls = 0` should be excluded

## Debugging

- **No sessions found**: Check `~/.claude/projects/` exists and contains `.jsonl` files
- **Empty results with project filter**: Project filter is case-insensitive partial match on decoded path (e.g., `--project myapp` matches `/Users/foo/myapp-backend`)
- **Inspect raw session data**: Use `--full` flag with extract_sessions.py to see complete session data without summarization
- **View message content**: Use `--messages` flag to include raw message text in output
