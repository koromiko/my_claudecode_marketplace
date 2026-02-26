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
