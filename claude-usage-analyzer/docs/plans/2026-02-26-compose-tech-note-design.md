# Design: `/compose-tech-note` Command

**Date:** 2026-02-26
**Status:** Approved

## Overview

A new slash command that composes a brief technical article titled "How I Use Claude Code" based on the user's session data. Unlike `/analyze-usage` which produces a metrics dashboard, this command produces a narrative article suitable for sharing with team/colleagues.

## Requirements

- **Audience:** Team/colleagues who may be curious about adopting Claude Code or improving their own usage
- **Tone:** Practical, relatable, data-backed storytelling
- **Scope:** Always across all projects (no `--project` filter) — captures the full user picture
- **Period:** User-configurable, defaulting to monthly
- **Length:** ~1,000–1,500 words (~5–7 minute read)
- **Content:** Balanced quantitative data + qualitative narrative, including real prompt examples from sessions
- **Output:** Markdown by default, HTML with `--html` flag

## Command Interface

```
/compose-tech-note [period] [--html]
```

### Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `period` | `weekly`, `monthly`, `daily`, or number of days | `monthly` |
| `--html` | Generate HTML article instead of markdown | off |

### Output Files

- Markdown: `reports/tech_note_{start_date}_to_{end_date}.md`
- HTML: `reports/tech_note_{start_date}_to_{end_date}.html`

## Article Structure

**Title:** "How I Use Claude Code" (or "How I Use Claude Code: {Month} {Year}")

### 1. Introduction (~100 words)
- Project context and role inferred from session data
- Time period covered, total hours and sessions at a glance
- One-sentence thesis

### 2. My Workflow at a Glance (~150 words)
- Session frequency and typical duration (duration distribution, session counts)
- Work vs. lookup session split
- Daily patterns if detectable
- Key stat callouts

### 3. What I Use Claude Code For (~200 words)
- Task type distribution with narrative (`by_task_type`)
- Top projects and what kind of work each involves (`by_project`)
- Concrete example: quote an actual initial prompt for the most common task type

### 4. My Prompting Style (~250 words)
- Prompt structure — length, specificity, context-giving habits (`conversation_samples`)
- 2–3 real prompt examples: one that worked well, one that didn't, with explanation
- Patterns: breaking tasks into steps vs. big prompts, iterative vs. one-shot

### 5. Tools and Features I Rely On (~200 words)
- Top tools by usage with narrative (`tools_usage`)
- Claude Code features: skills, agents, slash commands (`claude_code_features`)
- Tool combinations that characterize the workflow

### 6. What Works and What Doesn't (~200 words)
- Success patterns with evidence (`successful_sessions`, `detected_patterns`)
- Common friction points (`sessions_with_issues`, `common_issues`)
- One short anecdote from a real session illustrating each

### 7. Key Takeaways (~150 words)
- 3–5 bullet points: most useful insights for a colleague
- Recommendations for someone starting with Claude Code
- What the user plans to change or try next

## Architecture

### New Files

| File | Purpose |
|------|---------|
| `commands/compose-tech-note.md` | Slash command — orchestrates pipeline + article synthesis via subagents |
| `reference/article_prompt.md` | Article structure, tone guidance, section-by-section instructions |
| `scripts/article_html_template.py` | HTML template module for article layout |
| `scripts/generate_article_html.py` | Script to fill template with quantitative data + placeholders |

### No Changes to Existing Files

All 9 existing Python scripts remain untouched. The command reuses the existing pipeline as-is.

## Execution Strategy: Subagent Pipeline

The command uses Task agents to avoid consuming the main conversation's context with large JSON data.

### Step 1: Run Pipeline (main context)

Run the 3 Python scripts sequentially. Main context only sees filenames and success/error output.

```
generate_report.py --period monthly
    → reports/data/report_data_{dates}.json

analyze_sessions.py --input <report_file> --report aggregate_report.json --output session_analysis.json
    → aggregate_report.json, session_analysis.json

prepare_qualitative_analysis.py --input <report_file> --output-data qualitative_data.json
    → qualitative_data.json
```

### Step 2: Data Analysis Agent (Task)

Spawn a `general-purpose` Task agent that:
1. Reads all 3 JSON files + `reference/article_prompt.md`
2. Extracts and condenses data into a structured **article brief** containing:
   - Key stats pre-formatted for each article section
   - Selected and quoted prompt examples
   - Per-section data points and talking points
   - Success/failure anecdotes picked from real sessions
3. Returns the article brief (much smaller than raw JSONs)

### Step 3: Article Writing Agent (Task)

Spawn a second `general-purpose` Task agent that:
1. Reads the article brief from Step 2
2. Follows `reference/article_prompt.md` structure and tone guidance
3. Writes the final ~1,000–1,500 word markdown article
4. Returns the article text

Main context saves to `reports/tech_note_{dates}.md`.

### Step 4: HTML Generation (if --html, Task)

Spawn a third Task agent that:
1. Runs `generate_article_html.py` to produce partial HTML with placeholder markers
2. Reads the partial HTML + article brief
3. Fills qualitative `<!-- CLAUDE_ARTICLE section_name -->` sections
4. Returns the completed HTML

Main context saves to `reports/tech_note_{dates}.html`.

### Step 5: Cleanup Intermediate Files

After the final article (markdown or HTML) is saved, remove intermediate pipeline outputs that are no longer needed:

```bash
rm -f aggregate_report.json session_analysis.json qualitative_data.json
```

The `reports/data/report_data_{dates}.json` file is **kept** — it's stored in the `reports/data/` directory and may be useful for subsequent `/analyze-usage` runs or re-generation.

Only the working-directory intermediate files (`aggregate_report.json`, `session_analysis.json`, `qualitative_data.json`) are cleaned up.

## Data Flow

```
~/.claude/projects/*.jsonl + ~/.claude.json
        |
        v
generate_report.py --period monthly     (Step 1, main context)
        |
        v
reports/data/report_data_{dates}.json
        |
    +---+---+
    |       |
    v       v
analyze_sessions.py    prepare_qualitative_analysis.py    (Step 1, main context)
    |                       |
    v                       v
aggregate_report.json    qualitative_data.json
    |                       |
    +----------+------------+
               |
               v
    Task Agent: reads JSONs              (Step 2, subagent)
    + reference/article_prompt.md
               |
               v
         article_brief
               |
         +-----+-----+
         |           |
         v           v
    Task Agent:    Task Agent:           (Step 3/4, subagents)
    write article  generate HTML
         |           |
         v           v
    tech_note_     tech_note_
    {dates}.md     {dates}.html
               |
               v
         Cleanup intermediate files      (Step 5, main context)
         rm aggregate_report.json
         rm session_analysis.json
         rm qualitative_data.json
```

## HTML Template Design

`scripts/article_html_template.py` — article-optimized layout distinct from the dashboard `html_template.py`:

- **Single-column prose layout** — max-width ~720px, comfortable line-height
- **Dark theme** — consistent with existing styling
- **Pull-quote callouts** — key stats in styled boxes
- **Inline data tables** — small, simple tables for distributions and rankings
- **Prompt example blocks** — styled code-block-like sections for quoted prompts
- **No charts/SVGs** — lightweight; narrative carries the weight
- **Placeholder markers** — `<!-- CLAUDE_ARTICLE section_name -->` pattern for Claude to fill
