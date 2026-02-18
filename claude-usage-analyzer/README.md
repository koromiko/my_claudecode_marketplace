# Claude Usage Analyzer Plugin

A Claude Code plugin that analyzes your Claude Code session data and generates comprehensive usage reports with quantitative and qualitative insights.

## Features

- **Session Extraction**: Automatically extracts session data from `~/.claude/projects/`
- **Quantitative Analysis**: Statistics on duration, tool usage, completion rates
- **Qualitative Analysis**: Pattern detection, issue identification, success factors
- **Comprehensive Reports**: Markdown reports with actionable recommendations

## Installation

### Option 1: Install from local directory

```bash
claude --plugin-dir /path/to/claude-usage-analyzer
```

### Option 2: Install to project (for team sharing)

Copy the plugin to your project's `.claude/plugins/` directory:

```bash
cp -r claude-usage-analyzer /your/project/.claude/plugins/
```

### Option 3: Publish to a marketplace

Add to your marketplace's `marketplace.json`:

```json
{
  "plugins": [
    {
      "name": "claude-usage-analyzer",
      "description": "Analyze Claude Code session usage data",
      "source": "./plugins/claude-usage-analyzer",
      "version": "1.0.0"
    }
  ]
}
```

## Requirements

- Python 3.8+
- No external dependencies (uses only Python standard library)

## Usage

Once installed, use the `/analyze-usage` command in Claude Code:

```
/analyze-usage weekly      # Analyze last 7 days
/analyze-usage monthly     # Analyze last 30 days
/analyze-usage daily       # Analyze last 24 hours
/analyze-usage 14          # Analyze last 14 days (custom)
```

## What It Does

1. **Step 1**: Extracts session data from your Claude Code history
2. **Step 2**: Generates quantitative statistics (tool usage, duration, completion rates)
3. **Step 3**: Prepares qualitative analysis data (issues, successes, patterns)
4. **Step 4**: Claude analyzes the data following structured guidelines
5. **Step 5**: Generates a comprehensive markdown report

## Output Files

The plugin generates several files in your current working directory:

- `reports/data/report_data_{dates}.json` - Raw extracted data
- `aggregate_report.json` - Quantitative statistics
- `qualitative_data.json` - Qualitative analysis data
- `reports/analysis_report_{dates}.md` - Final comprehensive report

## Report Contents

The final report includes:

1. **Executive Summary** - Key metrics at a glance
2. **Quantitative Findings** - Statistics and distributions
3. **Root Cause Analysis** - Why issues occurred
4. **Success Patterns** - What works well
5. **Prompting Best Practices** - How to write better prompts
6. **Tool Usage Recommendations** - Optimal tool combinations
7. **Actionable Recommendations** - Specific improvements
8. **Session Quality Metrics** - Predictive indicators

## How Quantitative Data is Derived

The numeric/quantitative data in reports is computed from Claude Code's session files stored in `~/.claude/projects/`. Here's how each metric is calculated:

### Data Source

Claude Code stores each conversation as a JSONL file with one JSON object per line. Each line represents either:
- A **user message** (type: "user")
- An **assistant message** (type: "assistant") containing tool calls and text responses
- **Metadata** (git branch, version, timestamps)

### Metrics Calculation

| Metric | How It's Derived |
|--------|------------------|
| **Session Duration** | Calculated from `(end_timestamp - start_timestamp)` of messages in the session file |
| **User Messages** | Count of messages with `type: "user"` |
| **Assistant Messages** | Count of messages with `type: "assistant"` |
| **Tool Calls** | Count of `tool_use` blocks within assistant messages |
| **Tools Used** | Unique set of tool names from `tool_use` blocks (e.g., Read, Edit, Write, Bash) |
| **Files Touched** | Extracted from `file_path` parameter in Read/Edit/Write tool inputs |
| **Commands Run** | Extracted from `command` parameter in Bash tool inputs |

### Statistical Aggregations

Once per-session metrics are collected, the analyzer computes:

| Aggregation | Formula |
|-------------|---------|
| **Averages** | `sum(values) / count(sessions)` |
| **Median** | Middle value when sorted |
| **Percentiles (P25, P75, P90)** | Linear interpolation at percentile index |
| **Standard Deviation** | `sqrt(sum((x - mean)²) / (n-1))` |
| **Completion Rate** | `sessions_with_edits_or_git_ops / total_sessions * 100` |

### Derived Efficiency Metrics

| Metric | Formula |
|--------|---------|
| **Tools per File** | `total_tool_calls / files_touched` |
| **Tools per Message** | `total_tool_calls / user_messages` |
| **Files per Hour** | `files_touched / (duration_minutes / 60)` |
| **Messages per Minute** | `user_messages / duration_minutes` |

### Task Classification

Tasks are classified by keyword matching in user prompts:
- **bug_fix**: Contains "bug", "fix", "error", "issue", "broken"
- **feature**: Contains "add", "create", "implement", "new feature"
- **refactor**: Contains "refactor", "clean", "improve", "optimize"
- **debug**: Contains "debug", "investigate", "why", "understand"
- **testing**: Contains "test", "spec", "e2e", "unit test"
- **config**: Contains "config", "setup", "install", "terraform"
- **exploration**: Contains "explain", "what is", "how does", "document"

### Completion Detection

A session is considered "completed" if:
1. **Actual outcome field exists** (from manual annotation), OR
2. **Heuristic**: Session has Edit/Write tool usage AND (files touched > 0 OR git operations performed)

## Scripts Included

| Script | Purpose |
|--------|---------|
| `generate_report.py` | Main entry point, extracts and processes sessions |
| `extract_sessions.py` | Parses Claude Code session files |
| `analyze_sessions.py` | Generates quantitative analysis |
| `prepare_qualitative_analysis.py` | Prepares qualitative data |

## Plugin Structure

```
claude-usage-analyzer/
├── .claude-plugin/
│   └── plugin.json          # Plugin manifest
├── commands/
│   └── analyze-usage.md     # Slash command definition
├── scripts/
│   ├── generate_report.py
│   ├── extract_sessions.py
│   ├── analyze_sessions.py
│   └── prepare_qualitative_analysis.py
├── reference/
│   └── analysis_prompt.md   # Analysis guidelines
├── requirements.txt
└── README.md
```

## License

MIT
