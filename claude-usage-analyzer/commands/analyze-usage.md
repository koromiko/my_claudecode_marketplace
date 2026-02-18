---
description: Analyze Claude Code session usage data and generate comprehensive report
allowed-tools: Bash(python3:*), Bash(ls:*), Bash(cat:*), Read
argument-hint: [period] [--project <name>] [--session <uuid>]
---

# Claude Code Usage Analysis

Execute a comprehensive analysis of Claude Code session data.

## Arguments

Arguments: $ARGUMENTS

### Period (optional, defaults to "weekly")
- `weekly` - Last 7 days
- `monthly` - Last 30 days
- `daily` - Last 24 hours
- `N` (number) - Custom number of days to look back

### Project Filter (optional)
- `--project <name>` - Filter sessions by project name (partial match, case-insensitive)

### Output Format (optional)
- `--html` - Generate HTML report instead of markdown (self-contained with embedded CSS)

### Comparison (optional)
- `--compare-previous` - Include comparison with the previous period of same length (e.g., last week vs week before)

### Single Session (optional)
- `--session <uuid>` - Deep-dive analysis of a single session by its full UUID (ignores period/project args)

### Examples
- `/analyze-usage` - Weekly report for all projects (markdown)
- `/analyze-usage monthly` - Monthly report for all projects
- `/analyze-usage --project ema` - Weekly report filtered to "ema" project
- `/analyze-usage monthly --project myapp` - Monthly report for "myapp" project
- `/analyze-usage 14 --project api` - 14-day report for "api" project
- `/analyze-usage weekly --html` - Weekly HTML report for all projects
- `/analyze-usage monthly --project myapp --html` - Monthly HTML report for "myapp"
- `/analyze-usage weekly --compare-previous` - Weekly report with week-over-week comparison
- `/analyze-usage monthly --compare-previous --html` - Monthly HTML report with month-over-month comparison
- `/analyze-usage --session 1baea1cc-ad12-472d-806b-cf9455a101df` - Deep-dive analysis of a specific session
- `/analyze-usage --session 1baea1cc-ad12-472d-806b-cf9455a101df --html` - Deep-dive HTML report for a specific session

## Execution Steps

## Single Session Mode

If `--session <uuid>` is present in $ARGUMENTS, follow these steps instead of the standard pipeline:

### Step S1: Extract Single Session Data

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_report.py --session <uuid>
```

Note the output filename: `reports/data/session_deep_dive_{uuid_short}.json`

### Step S2: Analyze Single Session

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/analyze_single_session.py --input <deep_dive_file> --output session_analysis_{uuid_short}.json
```

### Step S3: Generate Deep-Dive Report

Read both `reports/data/session_deep_dive_{uuid_short}.json` and `session_analysis_{uuid_short}.json`, then generate a deep-dive report.

**Data Available for Deep-Dive:**
- `tool_call_timeline`: Every tool call in order with name and key input
- `conversation_flow`: Initial prompts, direction changes, errors, final messages
- `file_operations`: Files grouped by read/edit/write
- `bash_commands`: All bash commands with error detection
- `git_operations`: Git command classification
- `completion_details`: Confidence signals and criteria analysis
- `workflow_phases`: Detected phases (exploration, implementation, testing, etc.)
- `all_user_prompts`: All user messages for context

**Deep-Dive Report Template:**

```markdown
# Session Deep-Dive: {session_id_short}

## Overview
| Field | Value |
|-------|-------|
| **Session ID** | {session_id} |
| **Project** | {project} |
| **Date** | {date} |
| **Duration** | {duration_minutes} minutes |
| **Branch** | {git_branch} |
| **Task Type** | {task_type} |
| **Outcome** | {outcome} (confidence: {completion_confidence}/100) |

## Task Summary
{Describe what the user was trying to accomplish based on initial_prompts and task_summary}

## Session Timeline
{Chronological narrative of key events using tool_call_timeline and conversation_flow:}
1. User started with: "{initial prompt}"
2. Exploration phase: {what was searched/read}
3. Implementation phase: {what was edited/written}
4. Testing/validation: {bash commands run}
5. Outcome: {how the session ended}

## Workflow Phases
{Use workflow_phases to describe the session structure}
| Phase | Tools | Description |
|-------|-------|-------------|

## Tool Usage Analysis
{Use tool_analysis data}
| Tool | Calls | Purpose |
|------|-------|---------|

**Patterns Detected:**
{List workflow_patterns from tool_analysis}

## File Impact
{Use file_impact data}
- Files modified: {list}
- Files read-only: {list}
- Total operations: {counts}

## What Went Well
{Success patterns with specific evidence from the session data}

## Issues Encountered
{Problems identified with root cause analysis referencing specific tool calls or conversation moments}

## Conversation Analysis
- Total user messages: {count}
- Direction changes: {count and descriptions}
- Average prompt length: {chars}

## Recommendations
{Specific, actionable suggestions based on this session's patterns:}
1. {Recommendation based on tool usage patterns}
2. {Recommendation based on conversation flow}
3. {Recommendation based on outcome analysis}
```

Save to: `reports/session_deep_dive_{session_id_short}.md`

Then skip the standard pipeline steps (Steps 1-5) and proceed to Deliverables.

### Step 1: Generate Raw Report Data

Run the report generator with the specified period and optional project filter.

**Parse the arguments:**
1. Extract project filter if `--project <name>` is present in $ARGUMENTS
2. Check if `--compare-previous` flag is present in $ARGUMENTS
3. The remaining argument (if any) is the period

**Determine CLI arguments:**
- Period argument:
  - If "weekly", "monthly", or "daily": use `--period <value>`
  - If a number: use `--days <value>`
  - If empty/not provided: use `--period weekly`
- Project filter (if specified): add `--project <name>`
- Comparison (if `--compare-previous` flag present): add `--compare-previous`

Execute:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_report.py [period-args] [--project <name>] [--compare-previous]
```

**Examples:**
- `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_report.py --period weekly`
- `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_report.py --period monthly --project ema`
- `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_report.py --days 14 --project myapp`
- `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_report.py --period weekly --compare-previous`

The script will output files to a `reports/data/` directory in the current working directory.

After running, note the output filename:
- Without project filter: `report_data_{start_date}_to_{end_date}.json`
- With project filter: `report_data_{start_date}_to_{end_date}_{project}.json`

### Step 2: Generate Quantitative Data

Run `analyze_sessions.py` using the report file from Step 1:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/analyze_sessions.py --input <report_file> --output session_analysis.json --report aggregate_report.json
```

- Input: the JSON file generated in Step 1
- Output: `aggregate_report.json` and `session_analysis.json`

### Step 3: Generate Qualitative Data

Run `prepare_qualitative_analysis.py` using the report file from Step 1:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/prepare_qualitative_analysis.py --input <report_file> --output-data qualitative_data.json
```

- Input: the JSON file generated in Step 1
- Output: `qualitative_data.json`

### Step 4: Perform Analysis

Read both `aggregate_report.json` and `qualitative_data.json`, then perform comprehensive analysis.

**Data Available for Analysis:**
Each session in the report data now includes:
- `ai_summary`: Claude's auto-generated summary of the session (if available)
- `conversation_samples`: Initial user prompts and assistant response samples
- `task_summary`: First meaningful user prompt describing the task
- `successes` and `issues`: Detected patterns
- `claude_code_features`: Skills invoked, agents spawned, and slash commands used

When `--compare-previous` flag is used, the report data also includes:
- `comparison`: Object containing `previous_period` stats and `deltas` showing changes in key metrics (sessions, duration, completion rate, issue rate, etc.)

**Analysis Focus Areas:**
- Project performance metrics
- Task type distribution
- Duration and efficiency analysis
- Tool usage patterns
- Root cause analysis for issues (use `ai_summary` and `conversation_samples` for context)
- Success pattern identification
- Prompting pattern analysis (review `conversation_samples.initial_prompts`)
- Claude Code feature adoption (skills, agents, slash commands)

**Key Questions to Answer:**
1. Which projects have the highest/lowest completion rates?
2. What task types are most common and which are most problematic?
3. What is the typical session duration distribution?
4. Which tool combinations correlate with success vs. issues?
5. What prompting patterns lead to better outcomes? (Analyze conversation samples)
6. What context in AI summaries correlates with successful sessions?
7. Which Claude Code features (skills, agents, commands) are most used and effective?
8. Are there underutilized features that could improve productivity?

### Step 4b: Generate HTML Report (if --html flag)

If the `--html` flag is present in $ARGUMENTS, generate an HTML report instead of markdown.

**1. Run the HTML generation script:**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_html_report.py \
  --aggregate aggregate_report.json \
  --qualitative qualitative_data.json \
  --report-data <report_file> \
  --output reports/analysis_report_{dates}.html \
  --partial
```

Where `{dates}` matches the date range from the report file name (e.g., `2025-01-01_to_2025-01-07`).

**2. Read the partial HTML and qualitative_data.json**

The generated HTML has placeholder markers for qualitative sections:
- `<!-- CLAUDE_QUALITATIVE key_findings -->` - Executive summary key findings
- `<!-- CLAUDE_QUALITATIVE root_cause -->` - Root cause analysis for issues
- `<!-- CLAUDE_QUALITATIVE success_patterns -->` - Patterns that lead to success
- `<!-- CLAUDE_QUALITATIVE feature_effectiveness -->` - Claude Code feature analysis
- `<!-- CLAUDE_QUALITATIVE recommendations -->` - Actionable recommendations

**3. Generate qualitative content for each marked section:**

Based on `qualitative_data.json`, write HTML content for each section:

- **Key Findings**: 3-5 bullet points summarizing the most important insights
- **Root Cause Analysis**: For each issue type, explain why it happens with examples
- **Success Patterns**: What workflows, prompts, or approaches lead to successful sessions
- **Feature Effectiveness**: Which Claude Code features (skills, agents, commands) are most effective
- **Recommendations**: 5-10 specific, actionable items

**4. Format qualitative content as HTML:**

Convert your analysis to HTML using these patterns:
- Bullet points: `<ul><li>Item 1</li><li>Item 2</li></ul>`
- Bold text: `<strong>important</strong>`
- Paragraphs: `<p>Text here</p>`
- Subheadings: `<h4>Subheading</h4>`

**5. Replace placeholders in the HTML file:**

Find each `<!-- CLAUDE_QUALITATIVE section_name -->` marker and replace the placeholder content between it and the closing `<!-- /CLAUDE_QUALITATIVE -->` with your generated HTML content.

**6. Save the completed HTML file.**

Then skip Step 5 (markdown generation) and proceed to the deliverables note.

### Step 5: Generate Report (Markdown - skip if --html)

Create a comprehensive markdown report and save to:
- Without project filter: `reports/analysis_report_{start_date}_to_{end_date}.md`
- With project filter: `reports/analysis_report_{start_date}_to_{end_date}_{project}.md`

## Report Format

```markdown
# Claude Code Usage Report: {period}
<!-- If project filter was used, add: -->
**Project: {project_name}**

<!-- If --compare-previous was used, add comparison date range: -->
**Comparing: {current_period} vs {previous_period}**

## Executive Summary
- Key metrics at a glance (sessions, hours, completion rate)
- Project scope (all projects or filtered to specific project)
<!-- If comparison data available, include trends: -->
- Period-over-period changes (e.g., sessions +15%, completion rate +5%, issue rate -10%)
- Top 3 highlights
- Top 3 areas for improvement

## Quantitative Analysis

### Session Overview
- Total sessions, duration distribution
- Completion rate, issue rate
<!-- If comparison data available, add delta columns: -->
- Period-over-period changes with trend indicators (↑/↓)

### By Project
| Project | Sessions | Completion Rate | Avg Duration | Issues |
|---------|----------|-----------------|--------------|--------|
<!-- If comparison available, add delta columns showing changes for each metric -->

### By Task Type
- Distribution of task types
- Success rates by type
<!-- If comparison available: -->
- Changes in task type distribution (e.g., more feature work, less debugging)
- Task type success rate trends

### Tool Usage
- Most used tools
- Tool combinations in successful vs. problematic sessions
<!-- If comparison available: -->
- Changes in tool usage patterns (e.g., increased use of Read, decreased Bash)

### Claude Code Features
| Feature Type | Feature | Count | Sessions Using |
|--------------|---------|-------|----------------|
| Skill | /commit | N | N |
| Agent | Explore | N | N |
| Command | /help | N | N |

- Skills adoption rate and effectiveness
- Agent usage patterns by task type
- Most popular slash commands
<!-- If comparison available: -->
- Changes in feature adoption (e.g., +20% skill usage, new agents introduced)
- Feature effectiveness trends

## Qualitative Analysis

### Root Cause Analysis
For each major issue type:
- Description of the issue
- Example sessions affected (reference AI summaries for context)
- Contributing factors
- Recommended mitigation
<!-- If comparison available: -->
- Trends: Are specific issue types increasing or decreasing?
- Impact of previous recommendations (if available)

### Success Patterns
What works well:
- Effective prompting patterns (cite examples from conversation_samples)
- Successful workflows
- Tool usage that correlates with success
- Common characteristics from AI summaries of successful sessions
<!-- If comparison available: -->
- Emerging success patterns (new approaches showing positive results)
- Improvements in workflow efficiency

### Prompting Best Practices
Based on successful sessions (analyze conversation_samples.initial_prompts), recommend:
- How to structure initial prompts
- When to break tasks into smaller pieces
- What context to provide
- Example effective prompts from high-performing sessions

### Claude Code Feature Effectiveness
Analysis of how Claude Code features contribute to outcomes:
- Which skills correlate with successful sessions?
- Which agent types are most effective for different task types?
- Are there features that should be used more or less?
- Recommendations for optimizing feature usage
<!-- If comparison available: -->
- Feature adoption trends (increasing or decreasing usage)
- Correlation between feature adoption changes and outcome improvements

## Action Items

<!-- If comparison available, prioritize based on trends: -->
<!-- - Address metrics that are declining -->
<!-- - Double down on practices showing improvement -->
<!-- - Investigate significant changes (positive or negative) -->

### Quick Wins (This Week)
High-impact, low-effort improvements to implement immediately:
1. [Specific, actionable recommendation]
2. [Specific, actionable recommendation]

### Process Improvements (This Month)
Workflow or habit changes requiring more planning:
1. [Workflow or habit change]
2. [Workflow or habit change]

### Further Investigation
Topics needing deeper analysis before action:
- [Topics needing more analysis]
<!-- If comparison shows unexpected trends: -->
- [Investigate root causes of significant metric changes]
```

## Deliverables

The final report should include:
1. Executive Summary
2. Quantitative Findings
3. Root Cause Analysis (with AI summary context)
4. Success Patterns (with example prompts from conversation_samples)
5. Prompting Best Practices (derived from successful session prompts)
6. Tool Usage Recommendations
7. Claude Code Feature Analysis (skills, agents, commands usage and effectiveness)
8. Actionable Recommendations
9. Session Quality Metrics

**Output format:**
- Default: Markdown file at `reports/analysis_report_{dates}.md`
- With `--html`: HTML file at `reports/analysis_report_{dates}.html`

## Important Notes

- Do not read raw session data directly - use the scripts to extract and aggregate data
- Reference specific sessions by session_id when citing examples
- Use `ai_summary` fields to understand session context when available
- Use `conversation_samples` to cite actual prompts as examples of best/worst practices
- Use `claude_code_features` to analyze skills, agents, and commands usage patterns
- Combine quantitative and qualitative insights for stronger conclusions
- Focus on actionable insights rather than just describing the data
