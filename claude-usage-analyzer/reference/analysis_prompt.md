# Claude Code Usage Analysis

## Analysis Goal

Perform both **quantitative** and **qualitative** analysis of Claude Code session data to identify:
1. Statistical patterns and trends across sessions
2. What patterns lead to successful outcomes
3. What patterns lead to issues or failures
4. Recommendations for improving prompting strategies
5. Lessons learned for future sessions

---

## Step 1: Generate Raw Report Data

First, run `generate_report.py` to extract and process Claude Code session data into a structured JSON format:

```bash
python3 generate_report.py --period weekly
```

### Available Options

| Option | Description |
|--------|-------------|
| `--period weekly` | Last 7 days (default) |
| `--period monthly` | Last 30 days |
| `--period daily` | Last 24 hours |
| `--days N` | Custom number of days to look back |
| `--start YYYY-MM-DD --end YYYY-MM-DD` | Custom date range |
| `--project NAME` | Filter by project name (partial match) |
| `--output-dir PATH` | Custom output directory (default: `./reports`) |

### Examples

```bash
# Last 7 days (default)
python3 generate_report.py --period weekly

# Last 30 days
python3 generate_report.py --period monthly

# Custom date range
python3 generate_report.py --start 2025-12-01 --end 2025-12-15

# Filter by project
python3 generate_report.py --period weekly --project my-app
```

### Output

The script generates: `reports/data/report_data_{start_date}_to_{end_date}.json`

This file contains:
- `report_metadata`: Period, dates, generation timestamp
- `aggregate_statistics`: Total sessions, duration, completion/issue rates
- `averages_per_session`: Per-session averages
- `by_project`: Breakdown by project
- `by_task_type`: Breakdown by task type
- `tools_usage`: Tool usage frequency
- `detected_patterns`: Common successes and issues
- `sessions`: Array of condensed session data

**Note the generated filename** - you'll use it in subsequent steps.

---

## Step 2: Generate Quantitative Data

Run the quantitative analysis script using the report from Step 1:

```bash
python3 analyze_sessions.py \
  --input reports/data/report_data_YYYY-MM-DD_to_YYYY-MM-DD.json \
  --output aggregate_report.json \
  --detailed session_analysis.json
```

**Replace** `YYYY-MM-DD_to_YYYY-MM-DD` with the actual dates from the filename generated in Step 1.

The `aggregate_report.json` contains:

| Section | Description |
|---------|-------------|
| `summary` | Total sessions, valid sessions, duration, message counts |
| `by_project` | Per-project breakdown with completion/issue rates |
| `by_task_type` | Distribution of task types (bug_fix, feature, etc.) |
| `by_outcome` | Distribution of outcomes (completed, unclear, had_issues) |
| `by_date` | Time-series data for trend analysis |
| `tools_usage` | Tool usage frequency across all sessions |
| `topics_frequency` | Common topics/keywords extracted |
| `jira_tickets` | JIRA ticket tracking with session counts |
| `duration_distribution` | Statistical distribution (min, max, median, percentiles) |
| `tool_calls_distribution` | Tool call statistics |
| `files_touched_distribution` | Files modified statistics |
| `efficiency_averages` | Efficiency metrics (tools/file, files/hour, etc.) |
| `common_issues` | Frequency of issue types |
| `common_successes` | Frequency of success types |

---

## Step 3: Generate Qualitative Data

Run the qualitative data preparation script using the report from Step 1:

```bash
python3 prepare_qualitative_analysis.py \
  --input reports/data/report_data_YYYY-MM-DD_to_YYYY-MM-DD.json \
  --output-data qualitative_data.json \
  --output-prompt /dev/null
```

**Replace** `YYYY-MM-DD_to_YYYY-MM-DD` with the actual dates from the filename generated in Step 1.

The `qualitative_data.json` contains:

| Section | Description |
|---------|-------------|
| `metadata` | Report period, total/valid session counts |
| `aggregate_stats` | Completion rate, issue rate, total duration |
| `sessions_with_issues` | Sessions that encountered problems (detailed) |
| `successful_sessions` | Sessions that completed successfully (detailed) |
| `high_effort_sessions` | Sessions taking >100 minutes |
| `task_summaries_by_type` | Task descriptions grouped by type |
| `tool_patterns` | Tool usage comparison: successful vs problematic |
| `detected_patterns` | Common successes and issues |

---

## Step 4: Perform Quantitative Analysis

Read `aggregate_report.json` and analyze with these guiding questions:

### Project Performance
- Which projects have the highest/lowest completion rates?
- Which projects have the most sessions and tool usage?
- Are there projects with high issue rates that need attention?

### Task Type Distribution
- What is the breakdown of task types?
- Are certain task types overrepresented?
- Should task type classification be improved?

### Duration Analysis
- What is the typical session duration (median vs mean)?
- What percentile thresholds indicate problematic sessions?
- Is there correlation between duration and success?

### Efficiency Metrics
- What is the average tools-per-file ratio?
- What is the files-per-hour productivity rate?
- How do efficiency metrics vary by project?

### Trend Analysis (by_date)
- Are there trends in session frequency over time?
- Are completion rates improving or declining?
- Are there patterns by day of week?

### Tool Effectiveness
- Which tools are most frequently used?
- What is the correlation between tool usage and success?
- Are there underutilized tools that could help?

---

## Step 5: Perform Qualitative Analysis

Read `qualitative_data.json` and analyze with these guiding questions:

### Sessions with Issues (Root Cause Analysis)
- What types of tasks tend to have issues?
- Are there common tool combinations that lead to problems?
- What do the issue descriptions tell us about failure modes?
- Did sessions with issues still complete successfully? Why?

### Successful Sessions (Pattern Replication)
- What characteristics do successful sessions share?
- How do task summaries in successful sessions differ from problematic ones?
- What tool combinations are associated with success?
- What is the typical duration and file count for successful sessions?

### High Effort Sessions (Efficiency Analysis)
- Were these sessions appropriately complex, or could they have been faster?
- What factors contributed to the extended duration?
- Did high effort correlate with better outcomes?
- Is there a relationship between user_messages and outcome?

### Tool Usage Patterns
- Which tools appear more often in problematic sessions?
- Are there tool combinations that predict success?
- What is the ratio of tool usage between successful and problematic sessions?

### Task Summaries by Type
- Which task descriptions led to better outcomes?
- What makes a good vs poor task prompt?
- Are certain task types more prone to issues?
- Do specific keywords correlate with success or failure?

---

## Deliverables

Based on your analysis of both data files, provide:

### 1. Executive Summary
- Key statistics at a glance
- Overall health assessment
- Top 3 findings

### 2. Quantitative Findings
- Project performance comparison table
- Duration and efficiency statistics
- Trend analysis with insights
- Tool usage rankings

### 3. Root Cause Analysis
Identify the top 3-5 root causes of session issues, with:
- Specific examples from the data
- Frequency/impact assessment
- Contributing factors

### 4. Success Patterns
Document 3-5 patterns that correlate with successful outcomes:
- Pattern description
- Supporting evidence (session references)
- Replication recommendations

### 5. Prompting Best Practices
Based on task summaries, what makes an effective prompt for Claude Code? Provide:
- Good prompt examples (from successful sessions)
- Poor prompt examples (from unclear/failed sessions)
- Key elements that improve outcomes
- Prompt templates for common task types

### 6. Tool Usage Recommendations
Which tool combinations should be encouraged or avoided? Include:
- Tools associated with success
- Tools associated with issues
- Recommended workflow patterns
- Efficiency optimization tips

### 7. Action Items
Consolidate all recommendations into a single prioritized section:

**Quick Wins (This Week)**
High-impact, low-effort improvements to implement immediately:
- 2-3 specific, actionable items
- Focus on prompting or workflow changes

**Process Improvements (This Month)**
Larger changes requiring more planning:
- 2-3 workflow or habit changes
- May involve tooling setup or team coordination

**Further Investigation**
Topics needing deeper analysis:
- Areas where more data is needed
- Potential improvements requiring validation

### 8. Session Quality Metrics
Suggest metrics that could predict session success:
- Leading indicators of success
- Warning signs of potential issues
- Thresholds for intervention
- Dashboard recommendations

---

## Output Format

Structure your analysis report as follows:

```markdown
# Claude Code Usage Analysis Report

## Executive Summary
[Key statistics and top 3 findings]

## 1. Quantitative Findings
### 1.1 Project Performance
[Table and analysis]
### 1.2 Duration & Efficiency
[Statistics and insights]
### 1.3 Trend Analysis
[Time-series insights]
### 1.4 Tool Usage Statistics
[Rankings and patterns]

## 2. Root Cause Analysis
[Top 3-5 causes with examples]

## 3. Success Patterns
[Documented patterns with evidence]

## 4. Prompting Best Practices
[Guidelines, examples, templates]

## 5. Tool Usage Recommendations
[Specific recommendations]

## 6. Actionable Recommendations
[Numbered list of actions]

## 7. Session Quality Metrics
[Proposed metrics and thresholds]

## Appendix A: Data Summary
[Key statistics tables]

## Appendix B: Methodology
[How analysis was performed]
```

---

## Important Notes

- **Do not read raw session data directly** - use the scripts to extract and aggregate data
- **Reference specific sessions** by session_id when citing examples
- **Combine quantitative and qualitative insights** for stronger conclusions
- **Focus on actionable insights** rather than just describing the data
- **Consider the context** - some "issues" may be false positives (command errors that were recovered)
- **Use statistical significance** when comparing groups (avoid conclusions from small samples)
