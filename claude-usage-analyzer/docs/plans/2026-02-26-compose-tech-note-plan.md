# Compose Tech Note — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `/compose-tech-note` slash command that generates a "How I Use Claude Code" article from session data.

**Architecture:** New command reuses the existing Python pipeline (generate_report → analyze_sessions → prepare_qualitative_analysis) for data gathering, then orchestrates 3 Task subagents to condense data, write the article, and optionally generate HTML. No existing files are modified.

**Tech Stack:** Markdown command file, Python 3.8+ stdlib only (for HTML template/generator), existing pipeline scripts.

---

### Task 1: Create the Article Reference Prompt

The reference file that guides Claude's article synthesis — tone, structure, section-by-section data mapping.

**Files:**
- Create: `reference/article_prompt.md`

**Step 1: Write the reference file**

```markdown
# How I Use Claude Code — Article Composition Guide

## Purpose

Guide Claude in synthesizing pipeline data into a ~1,000–1,500 word technical article titled "How I Use Claude Code." The audience is team/colleagues who may want to adopt Claude Code or improve their usage.

## Tone & Style

- **Practical and relatable** — write as a colleague sharing their experience, not a formal report
- **Data-backed** — every claim should reference specific numbers from the data
- **Conversational but professional** — first person ("I"), active voice, short paragraphs
- **Concrete** — include real prompt examples, not abstract descriptions
- **Honest** — acknowledge what doesn't work well, not just successes

## Article Structure

### Title
"How I Use Claude Code" or "How I Use Claude Code: {Month} {Year}" (use the period from report metadata)

### 1. Introduction (~100 words)

**Data sources:** `aggregate_report.json` → `summary` (total_sessions, total_duration_minutes), `by_project` (project names)

Write:
- Number of projects worked on, total sessions, total hours
- One-sentence thesis summarizing the overall usage pattern
- Set expectations: "Here's what I've learned about working with Claude Code over the past N days."

### 2. My Workflow at a Glance (~150 words)

**Data sources:** `aggregate_report.json` → `summary`, `duration_distribution`, `by_date`; `qualitative_data.json` → `aggregate_stats`

Write:
- Average sessions per day (total_sessions / number of days in period)
- Median session duration vs. mean (highlight if skewed)
- Work vs. lookup session split (from session_type counts in summary)
- Daily rhythm if detectable from `by_date` data (e.g., "Most active on weekdays")
- Use a key stat as a pull-quote (e.g., "Median session: 3 minutes — most of my interactions are quick lookups")

### 3. What I Use Claude Code For (~200 words)

**Data sources:** `aggregate_report.json` → `by_task_type`, `by_project`; `qualitative_data.json` → `task_summaries_by_type`

Write:
- Top 3–4 task types with percentages and what they mean in practice
- Top 3–5 projects by session count, briefly describing what each project is about (infer from project name and task summaries)
- Quote one real initial prompt from `task_summaries_by_type` for the most common task type
- Mention if there's a "long tail" of projects with just 1–2 sessions

### 4. My Prompting Style (~250 words)

**Data sources:** `qualitative_data.json` → `successful_sessions` (conversation_samples), `sessions_with_issues` (conversation_samples); `aggregate_report.json` → `summary` (avg messages per session)

Write:
- General prompting pattern: average messages per session, whether interactions are short or long
- **Good prompt example**: Pick one from a successful session's `conversation_samples.initial_prompts`. Quote it verbatim. Explain why it worked (specific, gave context, clear goal).
- **Less effective prompt example**: Pick one from a session with issues or unclear outcome. Quote it. Explain what could be improved (too vague, missing context, too broad).
- Describe the overall pattern: Do prompts tend to be detailed or terse? Do they reference files? Do they break tasks into steps?

### 5. Tools and Features I Rely On (~200 words)

**Data sources:** `aggregate_report.json` → `tools_usage`; `qualitative_data.json` → `tool_patterns`, sessions with `claude_code_features`

Write:
- Top 5 tools by usage count, with brief narrative on why each makes sense
- Claude Code feature adoption: skills used, agents spawned, slash commands invoked
- Note any tool combinations that characterize the workflow (e.g., "Read → Edit is my most common pattern")
- If applicable: "I rarely use X but probably should" based on low adoption of available features

### 6. What Works and What Doesn't (~200 words)

**Data sources:** `qualitative_data.json` → `successful_sessions`, `sessions_with_issues`, `detected_patterns`, `tool_patterns`

Write:
- **What works**: 1–2 success patterns with brief evidence. Pull from `detected_patterns.common_successes` and one concrete session example.
- **What doesn't**: 1–2 friction points. Pull from `detected_patterns.common_issues` and one concrete session example.
- Keep it balanced — this isn't a complaint list, it's honest reflection
- Frame friction points constructively: "I've found that X tends to happen when Y, so now I try Z"

### 7. Key Takeaways (~150 words)

**Data sources:** Synthesize from all above sections

Write:
- 3–5 bullet points: the most useful insights a colleague could take away
- At least one concrete recommendation (e.g., "Start with a specific prompt that references the file you want to change")
- One thing the user plans to change or experiment with next
- End with an encouraging note for colleagues considering Claude Code

## Important Guidelines

- **Word count**: Aim for 1,000–1,500 words total. Each section has a target — stay close.
- **Real examples**: Always use actual prompts from the data, not made-up ones.
- **No sensitive data**: If a prompt contains credentials, API keys, or internal URLs, paraphrase instead of quoting.
- **Reference sessions**: When citing a specific session, include the short session ID for traceability.
- **No tables in prose**: Weave numbers into sentences. Tables are for the HTML version only.
- **Paragraphs, not bullets**: Prefer flowing prose. Bullets only in the Key Takeaways section.
```

**Step 2: Verify file created**

Run: `ls -la reference/article_prompt.md`
Expected: file exists, ~4KB

**Step 3: Commit**

```bash
git add reference/article_prompt.md
git commit -m "feat(compose-tech-note): add article reference prompt"
```

---

### Task 2: Create the Article HTML Template

A Python module providing the HTML template string for the article layout. Follows the same pattern as `scripts/html_template.py` but with a single-column prose layout.

**Files:**
- Create: `scripts/article_html_template.py`
- Reference: `scripts/html_template.py` (for CSS variable names and color palette — reuse `--bg-primary`, `--text-primary`, etc.)

**Step 1: Write the template module**

Create `scripts/article_html_template.py` with:

```python
#!/usr/bin/env python3
"""
HTML template for "How I Use Claude Code" article.
Single-column prose layout with dark theme, pull-quote callouts, and prompt example blocks.
"""

ARTICLE_HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>How I Use Claude Code: {period}</title>
    <style>
        :root {{
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-card: #21262d;
            --bg-elevated: #30363d;
            --text-primary: #e6edf3;
            --text-secondary: #8b949e;
            --text-muted: #6e7681;
            --accent-primary: #58a6ff;
            --accent-secondary: #79c0ff;
            --success: #3fb950;
            --warning: #d29922;
            --error: #f85149;
            --border-default: #30363d;
            --border-muted: #21262d;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI',
                         'Noto Sans', Helvetica, Arial, sans-serif;
            font-size: 16px;
            line-height: 1.75;
            -webkit-font-smoothing: antialiased;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
        }}

        .article-container {{
            max-width: 720px;
            margin: 0 auto;
            padding: 3rem 1.5rem;
        }}

        h1 {{
            font-size: 2rem;
            font-weight: 700;
            letter-spacing: -0.03em;
            margin-bottom: 0.5rem;
            line-height: 1.2;
        }}

        .subtitle {{
            font-size: 1rem;
            color: var(--text-secondary);
            margin-bottom: 2.5rem;
            padding-bottom: 1.5rem;
            border-bottom: 1px solid var(--border-default);
        }}

        h2 {{
            font-size: 1.375rem;
            font-weight: 600;
            letter-spacing: -0.02em;
            margin-top: 2.5rem;
            margin-bottom: 1rem;
            color: var(--accent-secondary);
        }}

        p {{
            margin-bottom: 1rem;
            color: var(--text-primary);
        }}

        /* Pull-quote callout for key stats */
        .pullquote {{
            border-left: 3px solid var(--accent-primary);
            padding: 1rem 1.25rem;
            margin: 1.5rem 0;
            background: var(--bg-secondary);
            border-radius: 0 6px 6px 0;
            font-size: 1.0625rem;
            color: var(--text-primary);
        }}

        .pullquote .stat {{
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--accent-primary);
            display: block;
            margin-bottom: 0.25rem;
            font-variant-numeric: tabular-nums;
        }}

        /* Prompt example blocks */
        .prompt-example {{
            background: var(--bg-card);
            border: 1px solid var(--border-default);
            border-radius: 6px;
            padding: 1rem 1.25rem;
            margin: 1rem 0;
            font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
            font-size: 0.875rem;
            line-height: 1.6;
            color: var(--text-primary);
            white-space: pre-wrap;
            word-break: break-word;
        }}

        .prompt-label {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
            display: block;
        }}

        .prompt-label.good {{
            color: var(--success);
        }}

        .prompt-label.poor {{
            color: var(--warning);
        }}

        /* Inline data tables */
        .data-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
            font-size: 0.875rem;
        }}

        .data-table th {{
            text-align: left;
            padding: 0.5rem 0.75rem;
            border-bottom: 2px solid var(--border-default);
            color: var(--text-secondary);
            font-weight: 600;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}

        .data-table td {{
            padding: 0.5rem 0.75rem;
            border-bottom: 1px solid var(--border-muted);
            font-variant-numeric: tabular-nums;
        }}

        .data-table tr:last-child td {{
            border-bottom: none;
        }}

        /* Takeaway bullets */
        .takeaways {{
            list-style: none;
            padding: 0;
        }}

        .takeaways li {{
            padding: 0.5rem 0 0.5rem 1.5rem;
            position: relative;
            margin-bottom: 0.25rem;
        }}

        .takeaways li::before {{
            content: "→";
            position: absolute;
            left: 0;
            color: var(--accent-primary);
            font-weight: 600;
        }}

        /* Footer */
        .article-footer {{
            margin-top: 3rem;
            padding-top: 1.5rem;
            border-top: 1px solid var(--border-default);
            color: var(--text-muted);
            font-size: 0.8125rem;
        }}

        /* Responsive */
        @media (max-width: 600px) {{
            .article-container {{
                padding: 2rem 1rem;
            }}
            h1 {{
                font-size: 1.5rem;
            }}
        }}
    </style>
</head>
<body>
    <div class="article-container">
        <h1>How I Use Claude Code</h1>
        <div class="subtitle">{period} · {total_sessions} sessions · {total_hours} hours</div>

        <h2>Introduction</h2>
        <!-- CLAUDE_ARTICLE introduction -->
        <p><em>Claude will fill this section with introduction content.</em></p>
        <!-- /CLAUDE_ARTICLE -->

        <h2>My Workflow at a Glance</h2>
        {workflow_stats_html}
        <!-- CLAUDE_ARTICLE workflow -->
        <p><em>Claude will fill this section with workflow narrative.</em></p>
        <!-- /CLAUDE_ARTICLE -->

        <h2>What I Use Claude Code For</h2>
        {task_type_table_html}
        <!-- CLAUDE_ARTICLE usage -->
        <p><em>Claude will fill this section with usage narrative.</em></p>
        <!-- /CLAUDE_ARTICLE -->

        <h2>My Prompting Style</h2>
        <!-- CLAUDE_ARTICLE prompting -->
        <p><em>Claude will fill this section with prompting analysis and examples.</em></p>
        <!-- /CLAUDE_ARTICLE -->

        <h2>Tools and Features I Rely On</h2>
        {tools_table_html}
        <!-- CLAUDE_ARTICLE tools -->
        <p><em>Claude will fill this section with tools narrative.</em></p>
        <!-- /CLAUDE_ARTICLE -->

        <h2>What Works and What Doesn't</h2>
        <!-- CLAUDE_ARTICLE works_and_doesnt -->
        <p><em>Claude will fill this section with success/friction analysis.</em></p>
        <!-- /CLAUDE_ARTICLE -->

        <h2>Key Takeaways</h2>
        <!-- CLAUDE_ARTICLE takeaways -->
        <p><em>Claude will fill this section with takeaway bullets.</em></p>
        <!-- /CLAUDE_ARTICLE -->

        <div class="article-footer">
            Generated on {generated_date} · Data from {start_date} to {end_date}
        </div>
    </div>
</body>
</html>'''
```

**Step 2: Verify syntax**

Run: `python3 scripts/article_html_template.py`
Expected: no errors (module loads cleanly)

**Step 3: Commit**

```bash
git add scripts/article_html_template.py
git commit -m "feat(compose-tech-note): add article HTML template"
```

---

### Task 3: Create the HTML Generation Script

Follows the same pattern as `scripts/generate_html_report.py`: loads JSON data, fills quantitative placeholders in the template, outputs partial HTML with `<!-- CLAUDE_ARTICLE -->` markers for Claude to complete.

**Files:**
- Create: `scripts/generate_article_html.py`
- Reference: `scripts/generate_html_report.py` (for argument pattern and `escape_html` utility)

**Step 1: Write the generation script**

Create `scripts/generate_article_html.py` with:

```python
#!/usr/bin/env python3
"""
Generate HTML article from Claude Code usage analysis data.

Takes aggregate_report.json and qualitative_data.json and generates
a partial HTML article with quantitative data pre-filled.
Claude then completes the narrative sections.
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    if not isinstance(text, str):
        text = str(text)
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#39;'))


def generate_workflow_stats(summary: Dict) -> str:
    """Generate pull-quote stats for the workflow section."""
    total = summary.get('total_sessions', 0)
    duration = summary.get('total_duration_minutes', 0)
    median = summary.get('median_duration_minutes', 0)
    # Calculate work vs lookup from session_types if available
    work = summary.get('work_sessions', 0)
    lookup = summary.get('lookup_sessions', 0)

    parts = []
    if median > 0:
        parts.append(
            f'<div class="pullquote">'
            f'<span class="stat">{median:.0f} min</span>'
            f'Median session duration ({total} sessions over {duration / 60:.1f} hours)'
            f'</div>'
        )
    if work > 0 or lookup > 0:
        total_typed = work + lookup
        if total_typed > 0:
            work_pct = round(work / total_typed * 100)
            parts.append(
                f'<div class="pullquote">'
                f'<span class="stat">{work_pct}% work · {100 - work_pct}% lookup</span>'
                f'Session type split'
                f'</div>'
            )
    return '\n'.join(parts) if parts else ''


def generate_task_type_table(by_task_type: Dict) -> str:
    """Generate a small table for task type distribution."""
    if not by_task_type:
        return ''

    sorted_types = sorted(by_task_type.items(), key=lambda x: -x[1].get('sessions', x[1]) if isinstance(x[1], dict) else -x[1])[:8]

    rows = []
    for task_type, data in sorted_types:
        if isinstance(data, dict):
            count = data.get('sessions', 0)
        else:
            count = data
        rows.append(f'<tr><td>{escape_html(task_type)}</td><td>{count}</td></tr>')

    return (
        '<table class="data-table">'
        '<thead><tr><th>Task Type</th><th>Sessions</th></tr></thead>'
        '<tbody>' + ''.join(rows) + '</tbody></table>'
    )


def generate_tools_table(tools_usage: Dict[str, int]) -> str:
    """Generate a small table for top tools."""
    if not tools_usage:
        return ''

    sorted_tools = sorted(tools_usage.items(), key=lambda x: -x[1])[:10]

    rows = []
    for tool, count in sorted_tools:
        rows.append(f'<tr><td>{escape_html(tool)}</td><td>{count}</td></tr>')

    return (
        '<table class="data-table">'
        '<thead><tr><th>Tool</th><th>Calls</th></tr></thead>'
        '<tbody>' + ''.join(rows) + '</tbody></table>'
    )


def fill_article_template(aggregate: Dict, qualitative: Dict, report_metadata: Dict) -> str:
    """Fill the article HTML template with quantitative data."""
    from article_html_template import ARTICLE_HTML_TEMPLATE

    summary = aggregate.get('summary', {})
    by_task_type = aggregate.get('by_task_type', {})
    tools_usage = aggregate.get('tools_usage', {})

    total_sessions = summary.get('total_sessions', 0)
    total_minutes = summary.get('total_duration_minutes', 0)
    total_hours = f"{total_minutes / 60:.1f}" if total_minutes else "0"

    start_date = report_metadata.get('start_date', 'unknown')
    end_date = report_metadata.get('end_date', 'unknown')
    period = report_metadata.get('period', f"{start_date} to {end_date}")

    html = ARTICLE_HTML_TEMPLATE.format(
        period=escape_html(period),
        total_sessions=total_sessions,
        total_hours=total_hours,
        workflow_stats_html=generate_workflow_stats(summary),
        task_type_table_html=generate_task_type_table(by_task_type),
        tools_table_html=generate_tools_table(tools_usage),
        generated_date=datetime.now().strftime('%Y-%m-%d'),
        start_date=escape_html(start_date),
        end_date=escape_html(end_date),
    )

    return html


def extract_report_metadata(report_data_path: str) -> Dict:
    """Extract metadata from the report data file."""
    with open(report_data_path, 'r') as f:
        data = json.load(f)
    metadata = data.get('report_metadata', {})
    return {
        'start_date': metadata.get('start_date', 'unknown'),
        'end_date': metadata.get('end_date', 'unknown'),
        'period': metadata.get('period', 'unknown'),
    }


def main():
    parser = argparse.ArgumentParser(
        description='Generate HTML article from Claude Code usage analysis'
    )
    parser.add_argument(
        '--aggregate', '-a',
        type=str,
        default='aggregate_report.json',
        help='Path to aggregate_report.json'
    )
    parser.add_argument(
        '--qualitative', '-q',
        type=str,
        default='qualitative_data.json',
        help='Path to qualitative_data.json'
    )
    parser.add_argument(
        '--report-data', '-r',
        type=str,
        required=True,
        help='Path to report_data JSON file (for metadata)'
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        default='tech_note.html',
        help='Output HTML file path'
    )

    args = parser.parse_args()

    print(f"Loading aggregate report from: {args.aggregate}")
    with open(args.aggregate, 'r') as f:
        aggregate = json.load(f)

    print(f"Loading qualitative data from: {args.qualitative}")
    with open(args.qualitative, 'r') as f:
        qualitative = json.load(f)

    print(f"Loading report metadata from: {args.report_data}")
    report_metadata = extract_report_metadata(args.report_data)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("Generating article HTML...")
    html = fill_article_template(aggregate, qualitative, report_metadata)

    with open(output_path, 'w') as f:
        f.write(html)

    print(f"Article HTML saved to: {output_path}")
    print("\nPartial HTML generated with CLAUDE_ARTICLE placeholders.")
    print("Claude should now fill in the narrative sections.")


if __name__ == '__main__':
    main()
```

**Step 2: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('scripts/generate_article_html.py').read()); print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add scripts/generate_article_html.py
git commit -m "feat(compose-tech-note): add article HTML generation script"
```

---

### Task 4: Create the Slash Command

The command file that orchestrates the pipeline and subagent dispatch. This is the main entry point.

**Files:**
- Create: `commands/compose-tech-note.md`
- Reference: `commands/analyze-usage.md` (for frontmatter pattern and `${CLAUDE_PLUGIN_ROOT}`)

**Step 1: Write the command file**

Create `commands/compose-tech-note.md` — the full command follows. Key design decisions:
- Frontmatter allows `Bash(python3:*)`, `Read`, and `Task` tools
- Uses `--period monthly` as default (not weekly like analyze-usage)
- No `--project` filter — always all projects
- Steps 2–4 run via Task subagents to keep main context clean
- Step 5 cleans up intermediate files

```markdown
---
description: Compose a "How I Use Claude Code" technical article from session data
allowed-tools: Bash(python3:*), Bash(ls:*), Bash(rm:*), Read, Task
argument-hint: [period] [--html]
---

# Compose Tech Note: "How I Use Claude Code"

Compose a brief technical article about Claude Code usage patterns, suitable for sharing with team/colleagues.

## Arguments

Arguments: $ARGUMENTS

### Period (optional, defaults to "monthly")
- `weekly` - Last 7 days
- `monthly` - Last 30 days (default)
- `daily` - Last 24 hours
- `N` (number) - Custom number of days

### Output Format (optional)
- `--html` - Generate HTML article instead of markdown

### Examples
- `/compose-tech-note` - Monthly article (markdown)
- `/compose-tech-note weekly` - Weekly article
- `/compose-tech-note --html` - Monthly HTML article
- `/compose-tech-note 90 --html` - 90-day HTML article

## Execution Steps

### Step 1: Run Data Pipeline (main context)

**Parse the arguments:**
1. Check if `--html` flag is present in $ARGUMENTS
2. The remaining argument (if any) is the period (default: `monthly`)

**Determine CLI arguments:**
- Period argument:
  - If "weekly", "monthly", or "daily": use `--period <value>`
  - If a number: use `--days <value>`
  - If empty/not provided: use `--period monthly`

**Run the 3 pipeline scripts sequentially:**

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_report.py [period-args]
```

Note the output filename from stdout (e.g., `reports/data/report_data_2026-01-19_to_2026-02-19.json`).

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/analyze_sessions.py --input <report_file> --report aggregate_report.json --output session_analysis.json
```

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/prepare_qualitative_analysis.py --input <report_file> --output-data qualitative_data.json
```

**Do not read the JSON files** — they will be read by subagents in the next steps.

### Step 2: Extract Article Brief (Task subagent)

Spawn a `general-purpose` Task agent with this prompt:

> You are a data analyst extracting key insights for a "How I Use Claude Code" article.
>
> Read these files:
> 1. `aggregate_report.json` — quantitative analysis
> 2. `qualitative_data.json` — session details and patterns
> 3. `${CLAUDE_PLUGIN_ROOT}/reference/article_prompt.md` — article structure guide
>
> Produce a structured **article brief** as a markdown document. For each article section listed in the reference prompt, extract:
> - The specific numbers and stats needed (pre-formatted as readable text)
> - 2–3 real prompt examples quoted verbatim from successful and problematic sessions' `conversation_samples`
> - One success anecdote and one friction anecdote (session ID, what happened, outcome)
> - Key talking points
>
> The brief should be self-contained — a writer should be able to produce the article from this brief alone without reading the raw JSONs.
>
> Output the brief as a single markdown document. Do NOT write the article itself — just the structured data brief.

Save the agent's returned brief to a temporary file: `article_brief.md`

### Step 3: Write Article (Task subagent)

Spawn a `general-purpose` Task agent with this prompt:

> You are a technical writer composing a "How I Use Claude Code" article for a colleague audience.
>
> Read these files:
> 1. `article_brief.md` — the extracted data and talking points
> 2. `${CLAUDE_PLUGIN_ROOT}/reference/article_prompt.md` — article structure and tone guide
>
> Write the complete article following the structure in the reference prompt. Target 1,000–1,500 words.
>
> **Key rules:**
> - Write in first person ("I")
> - Weave data into narrative prose — no raw tables in the markdown version
> - Quote real prompts using markdown blockquotes
> - Keep each section close to its target word count
> - Be honest about what doesn't work well
> - End with actionable takeaways
>
> Output ONLY the article markdown text, starting with the `# How I Use Claude Code` title.

Save the agent's returned article to: `reports/tech_note_{start_date}_to_{end_date}.md`
(Use the dates from the report_data filename.)

### Step 4: Generate HTML (if --html flag, Task subagent)

If `--html` was NOT specified, skip to Step 5.

**4a. Generate partial HTML:**

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_article_html.py \
  --aggregate aggregate_report.json \
  --qualitative qualitative_data.json \
  --report-data <report_file> \
  --output reports/tech_note_{dates}.html
```

**4b. Fill HTML sections (Task subagent):**

Spawn a `general-purpose` Task agent with this prompt:

> You are filling in the narrative sections of an HTML article about Claude Code usage.
>
> Read these files:
> 1. `reports/tech_note_{dates}.html` — partial HTML with `<!-- CLAUDE_ARTICLE section_name -->` placeholders
> 2. `article_brief.md` — the data brief with all talking points
> 3. `${CLAUDE_PLUGIN_ROOT}/reference/article_prompt.md` — structure and tone guide
>
> For each `<!-- CLAUDE_ARTICLE section_name -->` ... `<!-- /CLAUDE_ARTICLE -->` block, replace the placeholder content with HTML prose based on the article brief.
>
> **HTML formatting rules:**
> - Paragraphs: `<p>Text</p>`
> - Prompt examples: `<div class="prompt-example"><span class="prompt-label good">Effective prompt</span>prompt text here</div>`
> - Poor prompts: use `class="prompt-label poor"` instead
> - Pull-quotes: `<div class="pullquote"><span class="stat">42</span>Description</div>`
> - Takeaway list: `<ul class="takeaways"><li>Point</li></ul>`
> - Bold: `<strong>text</strong>`
>
> Write the completed HTML file back to the same path.

### Step 5: Cleanup Intermediate Files

Remove intermediate pipeline outputs:

```bash
rm -f aggregate_report.json session_analysis.json qualitative_data.json article_brief.md
```

The `reports/data/report_data_{dates}.json` is kept for potential reuse.

## Deliverables

The final output is:
- **Markdown** (default): `reports/tech_note_{start_date}_to_{end_date}.md`
- **HTML** (with `--html`): `reports/tech_note_{start_date}_to_{end_date}.html`

Tell the user where the file was saved and offer to open it.
```

**Step 2: Verify frontmatter parses correctly**

Run: `head -5 commands/compose-tech-note.md`
Expected: YAML frontmatter with `description`, `allowed-tools`, `argument-hint`

**Step 3: Commit**

```bash
git add commands/compose-tech-note.md
git commit -m "feat(compose-tech-note): add slash command"
```

---

### Task 5: End-to-End Validation

Test the full pipeline manually to verify everything works.

**Files:**
- None created or modified

**Step 1: Verify all new files exist**

Run: `ls -la commands/compose-tech-note.md reference/article_prompt.md scripts/article_html_template.py scripts/generate_article_html.py`
Expected: all 4 files listed

**Step 2: Test Python script syntax**

Run: `python3 -c "import sys; sys.path.insert(0, 'scripts'); import article_html_template; import generate_article_html; print('All imports OK')"`
Expected: `All imports OK`

**Step 3: Test the data pipeline (dry run)**

Run the existing pipeline with a short period to verify it still works:

```bash
python3 scripts/generate_report.py --days 1
```

Expected: JSON file created in `reports/data/`

**Step 4: Test HTML generation script**

Using the output from Step 3, run:

```bash
python3 scripts/analyze_sessions.py --input reports/data/report_data_*.json --report aggregate_report.json --output session_analysis.json && \
python3 scripts/prepare_qualitative_analysis.py --input reports/data/report_data_*.json --output-data qualitative_data.json && \
python3 scripts/generate_article_html.py --aggregate aggregate_report.json --qualitative qualitative_data.json --report-data reports/data/report_data_*.json --output /tmp/test_article.html
```

Expected: HTML file created at `/tmp/test_article.html` with `CLAUDE_ARTICLE` placeholder markers

**Step 5: Verify HTML has correct structure**

Run: `grep "CLAUDE_ARTICLE" /tmp/test_article.html`
Expected: 7 pairs of opening/closing markers (introduction, workflow, usage, prompting, tools, works_and_doesnt, takeaways)

**Step 6: Cleanup test artifacts**

```bash
rm -f aggregate_report.json session_analysis.json qualitative_data.json /tmp/test_article.html
```

---

### Task 6: Update Plugin CLAUDE.md

Add documentation for the new command to the plugin's CLAUDE.md.

**Files:**
- Modify: `CLAUDE.md` (the plugin-level one at the repo root for claude-usage-analyzer)

**Step 1: Add command documentation**

In the `CLAUDE.md` file, find the section that documents `commands/analyze-usage.md` and add a parallel section for the new command. Add after the existing pipeline documentation:

Under `## Plugin Structure`, add `commands/compose-tech-note.md` to the list.

Under `## Script Pipeline` or a new subsection, add:

```markdown
### compose-tech-note Command

`/compose-tech-note [period] [--html]` — generates a "How I Use Claude Code" article.

- Default period: monthly (all projects, no project filter)
- Reuses the same 3-step data pipeline as analyze-usage
- Orchestrates via Task subagents to keep main context lean:
  1. Pipeline scripts produce JSON data
  2. Data Analysis agent extracts an article brief
  3. Article Writing agent composes the narrative
  4. (Optional) HTML agent fills the styled template
  5. Cleanup removes intermediate files
- Article reference prompt: `reference/article_prompt.md`
- HTML template: `scripts/article_html_template.py`
- HTML generator: `scripts/generate_article_html.py`
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add compose-tech-note command to CLAUDE.md"
```
