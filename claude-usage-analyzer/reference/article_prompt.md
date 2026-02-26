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
