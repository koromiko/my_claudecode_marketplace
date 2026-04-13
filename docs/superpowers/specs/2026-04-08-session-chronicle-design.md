# Session Chronicle — Design Spec

## Overview

A new command in the `claude-usage-analyzer` plugin that generates a vertical timeline HTML view of the current Claude Code conversation. The goal is to help users understand conversation performance: what tools, skills, MCP tools, agents, and commands were used, how long each operation took, and where the bottlenecks are.

After generating and opening the HTML, the command hands off to `/workflow:retrospective` for session summary, improvement analysis, and memory/CLAUDE.md/rules update opportunities.

## New Files

| File | Purpose |
|------|---------|
| `scripts/generate_chronicle.py` | Parses session JSONL, computes timing/tokens, outputs self-contained HTML |
| `scripts/chronicle_template.py` | HTML/CSS template module for the vertical timeline layout |
| `commands/chronicle.md` | Slash command that orchestrates the flow |

## Data Extraction & Timing Model

### Message Parsing

The script reads the current session's JSONL file and processes these message types:

- **`assistant`**: timestamp, tool_use blocks (name + input summary), text content, token usage (input/output/cache_creation/cache_read)
- **`user`**: timestamp, tool_result blocks, text content (truncated)
- **`system`**: timestamp, subtype (for hook summaries, etc.)
- **Skip**: `file-history-snapshot`, `progress` types

### Timing Computation

All timing is approximate, derived from message timestamps (no precise instrumentation available):

- **API thinking time**: delta between the last user/tool_result message timestamp and the next assistant message timestamp. This covers the full API round-trip (prompt processing + model generation). Note: a single assistant message may contain thinking, text, and tool_use blocks — this entire response counts as one "thinking" duration from the user's perspective.
- **Tool execution time**: delta between the assistant message containing a tool_use and the subsequent user message containing the matching tool_result. When multiple tool_use blocks appear in one assistant message (parallel calls), they share the same start timestamp; each gets its own end timestamp from its corresponding tool_result.
- **User idle time**: delta between the last assistant message in a turn (after all tool results are processed) and the next user-initiated message (non-tool_result). Only counted when >1s to avoid noise.

Each timeline event gets: `start_ts`, `end_ts`, `duration_ms`, `category` (thinking | tool_execution | user_idle).

### Token Tracking

Per assistant turn, extracted from `message.usage`:
- `input_tokens`
- `output_tokens`
- `cache_creation_input_tokens`
- `cache_read_input_tokens`

### Feature Detection

- **Skill invocations**: tool_use where `name == "Skill"` → extract skill name from input
- **Agent spawns**: tool_use where `name == "Agent"` or `name == "Task"` with `subagent_type`
- **MCP tools**: tool_use where name starts with `mcp__`
- **System tools**: Read, Edit, Write, Bash, Grep, Glob, etc.
- **Commands**: user messages starting with `/`
- **System prompts/reminders**: `system` type messages or `<system-reminder>` tags in user content — counted and sized by tokens, not rendered in full

## HTML Chronicle Template

### Layout — Vertical Timeline with Horizontal Duration Bars

```
┌─────────────────────────────────────────────┐
│  Session Chronicle: {project} / {session_id} │
│  Duration: 12m 34s  │  Tokens: 45,231 in / │
│  3,201 out  │  Tools: 47 calls              │
├─────────────────────────────────────────────┤
│  Legend: [thinking] [tool] [user idle]       │
│  Scale: ████████████ = 10s                  │
├─────────────────────────────────────────────┤
│                                             │
│  00:00  USER — "Please update the..."       │
│         ├──████──┤ thinking (2.1s)          │
│         │ 12,431 in / 342 out tokens        │
│                                             │
│  00:02  ASSISTANT — text: "Let me read..."  │
│         ├─██─┤ Read (0.8s)                  │
│         ├─█──┤ Glob (0.6s)    ← parallel    │
│                                             │
│  00:03  ASSISTANT — text: "I'll edit..."    │
│         ├──████████──┤ Bash (5.2s) ⚠ slow   │
│         │ 8,201 in / 1,203 out tokens       │
│                                             │
│  00:09  USER idle (15.3s)                   │
│         ├────────────────────┤              │
│                                             │
│  00:24  USER — "/commit"                    │
│         ├──███──┤ Skill: commit (3.1s)      │
│         ...                                 │
├─────────────────────────────────────────────┤
│  Summary                                    │
│  Time breakdown: Thinking 34% | Tools 41%  │
│                  User idle 25%              │
│  Token breakdown: 45,231 in (cache 82%)    │
│                   3,201 out                 │
│  Slowest operations: ...                    │
│  Features used: skills, MCP, agents, etc.  │
└─────────────────────────────────────────────┘
```

### Design Details

- **Dark theme** consistent with existing `session_template.py` and `html_template.py` — reuses the same CSS custom properties (colors, fonts, spacing)
- **Horizontal bars** scaled proportionally — auto-scale so the longest event fills ~80% of available width
- **Color coding**:
  - Blue for API thinking time
  - Yellow/tool-specific colors for tool execution (reuse existing `--tool-read`, `--tool-bash`, etc. CSS vars)
  - Gray for user idle time
- **Parallel tool calls** shown as stacked bars at the same vertical position
- **Slow operations** (>3s) get a warning indicator
- **Summary section** at bottom with CSS-based charts (no JS dependencies)
- **Collapsible details**: tool input/output via CSS-only `<details>` elements
- **Self-contained HTML**: no external dependencies, inline CSS/JS only

## Python Script (`generate_chronicle.py`)

### Interface

```bash
python3 scripts/generate_chronicle.py --input <session.jsonl> --output <output.html>
```

### Processing Pipeline

1. **Parse JSONL** — read all lines, filter to `user`/`assistant`/`system` types, build ordered message list
2. **Build timeline events** — iterate messages, produce:
   - `{type: "user_message", ts, content_preview}` for user text
   - `{type: "thinking", start_ts, end_ts, duration_ms, tokens}` for assistant thinking
   - `{type: "tool_call", tool_name, start_ts, end_ts, duration_ms, input_summary, category}` for each tool_use + matching tool_result (category: system_tool | mcp_tool | skill | agent | command)
   - `{type: "user_idle", start_ts, end_ts, duration_ms}` for idle gaps
3. **Detect parallel calls** — tool_use blocks in the same assistant message with overlapping timestamps get grouped
4. **Compute summary stats**:
   - Time breakdown: total thinking / tool execution / user idle
   - Token totals: input, output, cache creation, cache read
   - Tokens per turn
   - Top N slowest operations
   - Feature inventory: skills, MCP tools, agents, system tools, commands
5. **Render HTML** — import `chronicle_template.py`, inject timeline and summary data via string formatting

### Constraints

- Python 3.8+ stdlib only (no pip install)
- Tool input summaries truncated to ~100 chars
- System prompt content counted (token size) but not rendered in full
- Complete HTML output — no Claude fill-in needed

## Command (`commands/chronicle.md`)

### Invocation

```
/chronicle
```

No arguments — always analyzes the current session.

### Execution Steps

1. **Determine session JSONL path**:
   - Get CWD, encode to Claude projects path format (replace `/` with `-`, strip leading `-`)
   - Find the most recently modified JSONL in `~/.claude/projects/{encoded_path}/`
   - Read first few lines to confirm it's the active session (verify `sessionId` matches)
2. **Run Python script**:
   ```bash
   python3 scripts/generate_chronicle.py --input <path> --output /tmp/chronicle_{session_id_short}.html
   ```
3. **Open in browser**:
   ```bash
   open /tmp/chronicle_{session_id_short}.html
   ```
4. **Hand off to retrospective**:
   - Invoke `/workflow:retrospective`

### Allowed Tools

`Bash(python3:*)`, `Bash(open:*)`, `Bash(ls:*)`, `Bash(head:*)`, `Read`, `Skill`

## Non-Goals

- Analyzing past sessions by UUID (use existing `/analyze-usage --session <uuid>` for that)
- Rendering full system prompt content in the HTML
- JavaScript-heavy interactive charts (CSS-only approach)
- External dependencies or pip packages
