# Session Chronicle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/chronicle` command to claude-usage-analyzer that generates a vertical timeline HTML of the current session showing tool durations, token usage, and bottlenecks, then hands off to retrospective.

**Architecture:** Three new files following existing plugin patterns: `chronicle_template.py` (HTML/CSS template module), `generate_chronicle.py` (JSONL parser + timeline builder + HTML renderer), `commands/chronicle.md` (slash command orchestration). Python 3.8+ stdlib only.

**Tech Stack:** Python 3.8+ (stdlib only), HTML/CSS (self-contained, dark theme)

---

### Task 1: Chronicle Template Module (`chronicle_template.py`)

**Files:**
- Create: `claude-usage-analyzer/scripts/chronicle_template.py`

This is the HTML/CSS template that the generator script will fill with data. It follows the same pattern as `html_template.py` and `session_template.py` — a module exporting a template string with Python format placeholders.

- [ ] **Step 1: Create the template module with CSS variables and base layout**

Create `claude-usage-analyzer/scripts/chronicle_template.py`:

```python
#!/usr/bin/env python3
"""
HTML template for Session Chronicle — vertical timeline with horizontal duration bars.
Reuses the dark-theme CSS variables from session_template.py for visual consistency.
"""

CHRONICLE_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chronicle: {{session_id_short}} - {{project_name}}</title>
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

            /* Timeline-specific colors */
            --thinking: #58a6ff;
            --thinking-bg: rgba(88, 166, 255, 0.15);
            --user-idle: #484f58;
            --user-idle-bg: rgba(72, 79, 88, 0.15);
            --slow-warning: #d29922;

            /* Tool colors (from session_template.py) */
            --tool-read: #58a6ff;
            --tool-edit: #3fb950;
            --tool-write: #a371f7;
            --tool-bash: #d29922;
            --tool-grep: #f778ba;
            --tool-glob: #79c0ff;
            --tool-task: #56d364;
            --tool-skill: #f0883e;
            --tool-agent: #56d364;
            --tool-mcp: #e3b341;
            --tool-web: #e3b341;
            --tool-other: #8b949e;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI',
                         'Noto Sans', Helvetica, Arial, sans-serif;
            font-size: 14px;
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
        }}

        .value {{ font-variant-numeric: tabular-nums; }}

        code, pre {{
            font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
        }}

        /* ── Header ── */
        .header {{
            position: sticky;
            top: 0;
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-default);
            padding: 1rem 2rem;
            z-index: 100;
        }}

        .header h1 {{
            font-size: 1.25rem;
            font-weight: 600;
            letter-spacing: -0.025em;
            margin-bottom: 0.5rem;
        }}

        .header-stats {{
            display: flex;
            flex-wrap: wrap;
            gap: 1.5rem;
            font-size: 0.8125rem;
            color: var(--text-secondary);
        }}

        .header-stats .stat {{
            display: flex;
            align-items: center;
            gap: 0.375rem;
        }}

        .header-stats .stat .label {{ color: var(--text-muted); }}
        .header-stats .stat .value {{ color: var(--text-primary); font-weight: 500; }}

        /* ── Legend ── */
        .legend {{
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            padding: 0.75rem 2rem;
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-muted);
            font-size: 0.75rem;
            color: var(--text-secondary);
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            gap: 0.375rem;
        }}

        .legend-swatch {{
            width: 12px;
            height: 12px;
            border-radius: 3px;
        }}

        /* ── Timeline ── */
        .timeline {{
            padding: 1rem 2rem 2rem;
            max-width: 1000px;
            margin: 0 auto;
        }}

        .timeline-event {{
            position: relative;
            padding: 0.5rem 0 0.5rem 5rem;
            border-left: 2px solid var(--border-muted);
            margin-left: 2.5rem;
        }}

        .timeline-event::before {{
            content: attr(data-time);
            position: absolute;
            left: -4.5rem;
            top: 0.5rem;
            font-size: 0.75rem;
            color: var(--text-muted);
            font-variant-numeric: tabular-nums;
            width: 4rem;
            text-align: right;
        }}

        .timeline-event::after {{
            content: '';
            position: absolute;
            left: -0.375rem;
            top: 0.875rem;
            width: 0.625rem;
            height: 0.625rem;
            border-radius: 50%;
            background: var(--bg-elevated);
            border: 2px solid var(--border-default);
        }}

        .event-label {{
            font-size: 0.8125rem;
            color: var(--text-secondary);
            margin-bottom: 0.25rem;
        }}

        .event-label .role {{
            font-weight: 600;
            color: var(--text-primary);
        }}

        .event-label .preview {{
            color: var(--text-muted);
            font-style: italic;
        }}

        /* Duration bars */
        .bar-row {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin: 0.25rem 0;
            font-size: 0.75rem;
        }}

        .bar-name {{
            min-width: 80px;
            color: var(--text-secondary);
            text-align: right;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .bar-track {{
            flex: 1;
            height: 18px;
            background: var(--bg-card);
            border-radius: 3px;
            overflow: hidden;
            max-width: 500px;
        }}

        .bar-fill {{
            height: 100%;
            border-radius: 3px;
            display: flex;
            align-items: center;
            padding: 0 6px;
            font-size: 0.6875rem;
            color: var(--bg-primary);
            font-weight: 600;
            white-space: nowrap;
            min-width: 2px;
        }}

        .bar-duration {{
            color: var(--text-muted);
            font-variant-numeric: tabular-nums;
            min-width: 50px;
        }}

        .bar-duration.slow {{
            color: var(--slow-warning);
        }}

        /* Parallel call group */
        .parallel-group {{
            border-left: 2px solid var(--accent-primary);
            padding-left: 0.5rem;
            margin: 0.25rem 0;
        }}

        .parallel-label {{
            font-size: 0.6875rem;
            color: var(--accent-primary);
            margin-bottom: 0.125rem;
        }}

        /* Token info */
        .token-info {{
            font-size: 0.6875rem;
            color: var(--text-muted);
            margin-top: 0.125rem;
        }}

        .token-info .cache {{
            color: var(--success);
        }}

        /* User idle styling */
        .timeline-event.idle {{
            opacity: 0.6;
        }}

        .timeline-event.idle::after {{
            background: var(--user-idle);
            border-color: var(--user-idle);
        }}

        /* Collapsible details */
        .event-details {{
            margin-top: 0.25rem;
        }}

        .event-details summary {{
            font-size: 0.6875rem;
            color: var(--text-muted);
            cursor: pointer;
            user-select: none;
        }}

        .event-details summary:hover {{
            color: var(--text-secondary);
        }}

        .event-details pre {{
            font-size: 0.6875rem;
            background: var(--bg-card);
            padding: 0.5rem;
            border-radius: 4px;
            margin-top: 0.25rem;
            overflow-x: auto;
            color: var(--text-secondary);
            max-height: 200px;
            overflow-y: auto;
        }}

        /* ── Summary Section ── */
        .summary {{
            padding: 2rem;
            max-width: 1000px;
            margin: 0 auto;
            border-top: 1px solid var(--border-default);
        }}

        .summary h2 {{
            font-size: 1.125rem;
            font-weight: 600;
            margin-bottom: 1rem;
        }}

        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1rem;
        }}

        .summary-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-default);
            border-radius: 8px;
            padding: 1rem;
        }}

        .summary-card h3 {{
            font-size: 0.875rem;
            font-weight: 600;
            margin-bottom: 0.75rem;
            color: var(--text-secondary);
        }}

        /* Breakdown bars in summary */
        .breakdown-bar {{
            display: flex;
            height: 24px;
            border-radius: 4px;
            overflow: hidden;
            margin-bottom: 0.5rem;
        }}

        .breakdown-segment {{
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.6875rem;
            font-weight: 600;
            color: var(--bg-primary);
            min-width: 1px;
        }}

        .breakdown-legend {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            font-size: 0.75rem;
        }}

        .breakdown-legend-item {{
            display: flex;
            align-items: center;
            gap: 0.25rem;
        }}

        .breakdown-legend-swatch {{
            width: 10px;
            height: 10px;
            border-radius: 2px;
        }}

        /* Slowest operations list */
        .slow-ops {{
            list-style: none;
        }}

        .slow-ops li {{
            display: flex;
            justify-content: space-between;
            padding: 0.375rem 0;
            border-bottom: 1px solid var(--border-muted);
            font-size: 0.8125rem;
        }}

        .slow-ops li:last-child {{
            border-bottom: none;
        }}

        .slow-ops .op-name {{
            color: var(--text-primary);
        }}

        .slow-ops .op-duration {{
            color: var(--slow-warning);
            font-variant-numeric: tabular-nums;
            font-weight: 500;
        }}

        /* Feature inventory */
        .feature-list {{
            list-style: none;
        }}

        .feature-list li {{
            padding: 0.25rem 0;
            font-size: 0.8125rem;
            color: var(--text-secondary);
        }}

        .feature-list .feature-cat {{
            color: var(--text-muted);
            min-width: 80px;
            display: inline-block;
        }}

        .feature-list .feature-items {{
            color: var(--text-primary);
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Session Chronicle: {project_name} / {session_id_short}</h1>
        <div class="header-stats">
            <div class="stat"><span class="label">Duration</span><span class="value">{total_duration}</span></div>
            <div class="stat"><span class="label">Tokens in</span><span class="value">{total_input_tokens}</span></div>
            <div class="stat"><span class="label">Tokens out</span><span class="value">{total_output_tokens}</span></div>
            <div class="stat"><span class="label">Tool calls</span><span class="value">{total_tool_calls}</span></div>
            <div class="stat"><span class="label">Turns</span><span class="value">{total_turns}</span></div>
        </div>
    </div>
    <div class="legend">
        <div class="legend-item"><div class="legend-swatch" style="background: var(--thinking)"></div>API thinking</div>
        <div class="legend-item"><div class="legend-swatch" style="background: var(--tool-read)"></div>Read</div>
        <div class="legend-item"><div class="legend-swatch" style="background: var(--tool-edit)"></div>Edit</div>
        <div class="legend-item"><div class="legend-swatch" style="background: var(--tool-write)"></div>Write</div>
        <div class="legend-item"><div class="legend-swatch" style="background: var(--tool-bash)"></div>Bash</div>
        <div class="legend-item"><div class="legend-swatch" style="background: var(--tool-grep)"></div>Grep</div>
        <div class="legend-item"><div class="legend-swatch" style="background: var(--tool-glob)"></div>Glob</div>
        <div class="legend-item"><div class="legend-swatch" style="background: var(--tool-skill)"></div>Skill</div>
        <div class="legend-item"><div class="legend-swatch" style="background: var(--tool-agent)"></div>Agent</div>
        <div class="legend-item"><div class="legend-swatch" style="background: var(--tool-mcp)"></div>MCP</div>
        <div class="legend-item"><div class="legend-swatch" style="background: var(--user-idle)"></div>User idle</div>
    </div>
    <div class="timeline">
        {timeline_html}
    </div>
    <div class="summary">
        <h2>Summary</h2>
        <div class="summary-grid">
            {time_breakdown_card}
            {token_breakdown_card}
            {slowest_ops_card}
            {features_card}
        </div>
    </div>
</body>
</html>'''


def get_tool_color_var(tool_name: str) -> str:
    """Map a tool name to its CSS variable name."""
    tool_map = {
        'Read': 'tool-read',
        'Edit': 'tool-edit',
        'Write': 'tool-write',
        'Bash': 'tool-bash',
        'Grep': 'tool-grep',
        'Glob': 'tool-glob',
        'Skill': 'tool-skill',
        'Agent': 'tool-agent',
        'Task': 'tool-agent',
        'TaskCreate': 'tool-agent',
        'TaskUpdate': 'tool-agent',
        'WebSearch': 'tool-web',
        'WebFetch': 'tool-web',
        'NotebookEdit': 'tool-write',
    }
    # MCP tools
    if tool_name.startswith('mcp__'):
        return 'tool-mcp'
    return tool_map.get(tool_name, 'tool-other')
```

- [ ] **Step 2: Commit**

```bash
cd /Users/sthuang/Project/my_claudecode_marketplace
git add claude-usage-analyzer/scripts/chronicle_template.py
git commit -m "feat(chronicle): add HTML template module for session chronicle timeline"
```

---

### Task 2: Chronicle Generator Script (`generate_chronicle.py`)

**Files:**
- Create: `claude-usage-analyzer/scripts/generate_chronicle.py`

This script parses a session JSONL file, builds a timeline with timing and token data, then renders the HTML using the template from Task 1.

- [ ] **Step 1: Create the script with JSONL parser and timeline builder**

Create `claude-usage-analyzer/scripts/generate_chronicle.py`:

```python
#!/usr/bin/env python3
"""
Session Chronicle Generator

Parses a Claude Code session JSONL file and generates a vertical timeline
HTML showing tool durations, token usage per turn, and bottlenecks.

Usage:
    python generate_chronicle.py --input <session.jsonl> --output <output.html>
"""

import json
import argparse
import html as html_module
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple

from chronicle_template import CHRONICLE_TEMPLATE, get_tool_color_var


# ── JSONL Parsing ──

def parse_jsonl(path: Path) -> List[Dict]:
    """Read JSONL file and return messages sorted by timestamp.

    Filters to user/assistant/system types, skips file-history-snapshot and progress.
    """
    messages = []
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg_type = msg.get('type')
            if msg_type in ('user', 'assistant', 'system'):
                ts = msg.get('timestamp')
                if ts:
                    messages.append(msg)
    # Sort by timestamp (ISO format sorts lexicographically)
    messages.sort(key=lambda m: m.get('timestamp', ''))
    return messages


def parse_iso_ts(ts: str) -> Optional[datetime]:
    """Parse ISO timestamp string to datetime."""
    if not ts:
        return None
    try:
        # Handle both 'Z' suffix and '+00:00'
        ts = ts.replace('Z', '+00:00')
        if hasattr(datetime, 'fromisoformat'):
            return datetime.fromisoformat(ts)
        else:
            # Python 3.8 fallback for 'Z' timestamps
            from datetime import timezone
            ts_clean = ts.replace('+00:00', '')
            return datetime.strptime(ts_clean, '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        return None


def ms_between(ts1: str, ts2: str) -> float:
    """Compute milliseconds between two ISO timestamps."""
    dt1 = parse_iso_ts(ts1)
    dt2 = parse_iso_ts(ts2)
    if dt1 and dt2:
        return (dt2 - dt1).total_seconds() * 1000
    return 0.0


# ── Content Extraction ──

def get_text_content(message: Dict) -> str:
    """Extract text content from a message, truncated."""
    content = message.get('message', {}).get('content', [])
    if isinstance(content, str):
        return content[:150]
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get('type') == 'text':
                parts.append(block.get('text', ''))
            elif isinstance(block, str):
                parts.append(block)
        return ' '.join(parts)[:150]
    return ''


def get_tool_uses(message: Dict) -> List[Dict]:
    """Extract tool_use blocks from an assistant message."""
    content = message.get('message', {}).get('content', [])
    if not isinstance(content, list):
        return []
    tools = []
    for block in content:
        if isinstance(block, dict) and block.get('type') == 'tool_use':
            tool_input = block.get('input', {})
            # Build a short summary of the input
            summary = ''
            if isinstance(tool_input, dict):
                if 'command' in tool_input:
                    summary = str(tool_input['command'])[:100]
                elif 'pattern' in tool_input:
                    summary = str(tool_input['pattern'])[:100]
                elif 'file_path' in tool_input:
                    summary = str(tool_input['file_path'])[:100]
                elif 'skill' in tool_input:
                    summary = str(tool_input['skill'])[:100]
                elif 'prompt' in tool_input:
                    summary = str(tool_input['prompt'])[:80]
                else:
                    # Generic: first key=value
                    for k, v in list(tool_input.items())[:1]:
                        summary = f"{k}: {str(v)[:80]}"
            tools.append({
                'id': block.get('id', ''),
                'name': block.get('name', 'Unknown'),
                'input_summary': summary,
            })
    return tools


def get_tool_results(message: Dict) -> Dict[str, str]:
    """Extract tool_result blocks from a user message. Returns {tool_use_id: timestamp}."""
    content = message.get('message', {}).get('content', [])
    if not isinstance(content, list):
        return {}
    results = {}
    ts = message.get('timestamp', '')
    for block in content:
        if isinstance(block, dict) and block.get('type') == 'tool_result':
            tool_use_id = block.get('tool_use_id', '')
            if tool_use_id:
                results[tool_use_id] = ts
    return results


def get_token_usage(message: Dict) -> Dict[str, int]:
    """Extract token usage from an assistant message."""
    usage = message.get('message', {}).get('usage', {})
    if not usage:
        return {}
    return {
        'input_tokens': usage.get('input_tokens', 0),
        'output_tokens': usage.get('output_tokens', 0),
        'cache_creation': usage.get('cache_creation_input_tokens', 0)
                          or usage.get('cache_creation', {}).get('ephemeral_5m_input_tokens', 0),
        'cache_read': usage.get('cache_read_input_tokens', 0),
    }


def classify_tool(name: str, tool_input_summary: str) -> str:
    """Classify a tool into a category."""
    if name == 'Skill':
        return 'skill'
    if name in ('Agent', 'Task', 'TaskCreate', 'TaskUpdate', 'TaskGet', 'TaskList', 'TaskStop'):
        return 'agent'
    if name.startswith('mcp__'):
        return 'mcp_tool'
    return 'system_tool'


def count_system_reminders(message: Dict) -> int:
    """Count <system-reminder> tags in a user message's content."""
    content = message.get('message', {}).get('content', [])
    count = 0
    if isinstance(content, list):
        for block in content:
            text = ''
            if isinstance(block, dict) and block.get('type') == 'text':
                text = block.get('text', '')
            elif isinstance(block, str):
                text = block
            count += text.count('<system-reminder>')
    return count


# ── Timeline Builder ──

def build_timeline(messages: List[Dict]) -> Tuple[List[Dict], Dict]:
    """Build ordered timeline events from parsed messages.

    Returns (events, summary_stats).

    Event types:
    - user_message: user sent a text message
    - thinking: API round-trip time before assistant responded
    - tool_call: a tool was invoked and returned
    - user_idle: gap between assistant finishing and user's next input
    """
    events = []
    session_start_ts = messages[0].get('timestamp', '') if messages else ''

    # Accumulated stats
    total_tokens = defaultdict(int)
    tool_counts = defaultdict(int)
    feature_inventory = {
        'skills': set(),
        'mcp_tools': set(),
        'agents': [],
        'system_tools': set(),
        'commands': [],
        'system_reminders': 0,
    }

    # Track the last timestamp where the assistant finished responding
    # (after all tool results for that turn are processed)
    last_assistant_done_ts = None
    # Track whether we're in a tool-call loop (assistant → tool_result → assistant → ...)
    # vs a fresh user turn
    pending_tool_ids = {}  # tool_use_id → {name, start_ts, input_summary, category}

    i = 0
    turn_number = 0
    while i < len(messages):
        msg = messages[i]
        msg_type = msg.get('type')
        ts = msg.get('timestamp', '')

        if msg_type == 'user':
            tool_results = get_tool_results(msg)

            if tool_results:
                # This is a tool_result message — match with pending tool calls
                for tool_use_id, result_ts in tool_results.items():
                    if tool_use_id in pending_tool_ids:
                        pending = pending_tool_ids.pop(tool_use_id)
                        duration = ms_between(pending['start_ts'], result_ts)
                        events.append({
                            'type': 'tool_call',
                            'tool_name': pending['name'],
                            'start_ts': pending['start_ts'],
                            'end_ts': result_ts,
                            'duration_ms': max(duration, 0),
                            'input_summary': pending['input_summary'],
                            'category': pending['category'],
                            'parallel_group': pending.get('parallel_group'),
                        })
                        tool_counts[pending['name']] += 1
                        cat = pending['category']
                        if cat == 'skill':
                            feature_inventory['skills'].add(pending['input_summary'])
                        elif cat == 'mcp_tool':
                            feature_inventory['mcp_tools'].add(pending['name'])
                        elif cat == 'agent':
                            feature_inventory['agents'].append(pending['name'])
                        else:
                            feature_inventory['system_tools'].add(pending['name'])
                # Update last_assistant_done_ts if all pending tools resolved
                if not pending_tool_ids:
                    last_assistant_done_ts = ts
            else:
                # This is a real user message (not a tool result)
                text = get_text_content(msg)
                reminder_count = count_system_reminders(msg)
                feature_inventory['system_reminders'] += reminder_count

                # Check for slash commands
                if text.strip().startswith('/'):
                    feature_inventory['commands'].append(text.strip().split()[0])

                # User idle time (if there was a previous assistant response)
                if last_assistant_done_ts:
                    idle_ms = ms_between(last_assistant_done_ts, ts)
                    if idle_ms > 1000:  # Only count >1s
                        events.append({
                            'type': 'user_idle',
                            'start_ts': last_assistant_done_ts,
                            'end_ts': ts,
                            'duration_ms': idle_ms,
                        })
                    last_assistant_done_ts = None

                turn_number += 1
                events.append({
                    'type': 'user_message',
                    'ts': ts,
                    'content_preview': text[:150] if text else '(empty)',
                    'turn_number': turn_number,
                    'system_reminders': reminder_count,
                })

        elif msg_type == 'assistant':
            # Thinking time: delta from last event to this assistant message
            prev_ts = None
            if events:
                # Find the most recent timestamp
                for e in reversed(events):
                    if e.get('end_ts'):
                        prev_ts = e['end_ts']
                        break
                    elif e.get('ts'):
                        prev_ts = e['ts']
                        break
            if prev_ts:
                think_ms = ms_between(prev_ts, ts)
                if think_ms > 50:  # Only count if meaningful
                    tokens = get_token_usage(msg)
                    for k, v in tokens.items():
                        total_tokens[k] += v
                    events.append({
                        'type': 'thinking',
                        'start_ts': prev_ts,
                        'end_ts': ts,
                        'duration_ms': think_ms,
                        'tokens': tokens,
                    })

            # Extract tool uses
            tool_uses = get_tool_uses(msg)
            if tool_uses:
                is_parallel = len(tool_uses) > 1
                parallel_group = len(events) if is_parallel else None
                for tu in tool_uses:
                    category = classify_tool(tu['name'], tu['input_summary'])
                    pending_tool_ids[tu['id']] = {
                        'name': tu['name'],
                        'start_ts': ts,
                        'input_summary': tu['input_summary'],
                        'category': category,
                        'parallel_group': parallel_group,
                    }
            else:
                # Pure text response — this is assistant done (no tools pending)
                tokens = get_token_usage(msg)
                # Only count tokens if not already counted in a thinking event
                # (avoid double-counting for messages that had thinking + text)
                text = get_text_content(msg)
                if text and not any(
                    e.get('type') == 'thinking' and e.get('end_ts') == ts
                    for e in events[-3:]
                ):
                    for k, v in tokens.items():
                        total_tokens[k] += v
                last_assistant_done_ts = ts

        elif msg_type == 'system':
            # Just count, don't render
            feature_inventory['system_reminders'] += 1

        i += 1

    # Compute summary
    total_thinking_ms = sum(e['duration_ms'] for e in events if e['type'] == 'thinking')
    total_tool_ms = sum(e['duration_ms'] for e in events if e['type'] == 'tool_call')
    total_idle_ms = sum(e['duration_ms'] for e in events if e['type'] == 'user_idle')
    total_ms = total_thinking_ms + total_tool_ms + total_idle_ms

    # Slowest operations (top 10)
    timed_events = [e for e in events if e['type'] in ('thinking', 'tool_call')]
    timed_events.sort(key=lambda e: -e['duration_ms'])
    slowest = timed_events[:10]

    summary = {
        'session_start_ts': session_start_ts,
        'total_duration_ms': total_ms,
        'total_thinking_ms': total_thinking_ms,
        'total_tool_ms': total_tool_ms,
        'total_idle_ms': total_idle_ms,
        'total_tokens': dict(total_tokens),
        'tool_counts': dict(tool_counts),
        'total_tool_calls': sum(tool_counts.values()),
        'total_turns': turn_number,
        'slowest_operations': slowest,
        'feature_inventory': {
            'skills': sorted(feature_inventory['skills']),
            'mcp_tools': sorted(feature_inventory['mcp_tools']),
            'agents': feature_inventory['agents'],
            'system_tools': sorted(feature_inventory['system_tools']),
            'commands': feature_inventory['commands'],
            'system_reminders': feature_inventory['system_reminders'],
        },
    }

    return events, summary


# ── HTML Rendering ──

def format_duration(ms: float) -> str:
    """Format milliseconds to human-readable duration."""
    if ms < 1000:
        return f"{ms:.0f}ms"
    secs = ms / 1000
    if secs < 60:
        return f"{secs:.1f}s"
    mins = int(secs // 60)
    remaining_secs = secs % 60
    return f"{mins}m {remaining_secs:.0f}s"


def format_relative_time(start_ts: str, event_ts: str) -> str:
    """Format time as MM:SS offset from session start."""
    ms = ms_between(start_ts, event_ts)
    if ms < 0:
        ms = 0
    total_secs = int(ms / 1000)
    mins = total_secs // 60
    secs = total_secs % 60
    return f"{mins:02d}:{secs:02d}"


def format_number(n: int) -> str:
    """Format a number with comma separators."""
    return f"{n:,}"


def escape(text: str) -> str:
    """Escape HTML special characters."""
    return html_module.escape(str(text)) if text else ''


def compute_bar_width(duration_ms: float, max_duration_ms: float) -> float:
    """Compute bar width as percentage, with the max event filling 80%."""
    if max_duration_ms <= 0:
        return 1.0
    return max(1.0, (duration_ms / max_duration_ms) * 80.0)


def render_bar(tool_name: str, duration_ms: float, max_duration_ms: float,
               input_summary: str = '', is_slow: bool = False) -> str:
    """Render a single horizontal duration bar."""
    width = compute_bar_width(duration_ms, max_duration_ms)
    color_var = get_tool_color_var(tool_name) if tool_name not in ('thinking', 'user_idle') else (
        'thinking' if tool_name == 'thinking' else 'user-idle'
    )
    duration_str = format_duration(duration_ms)
    slow_class = ' slow' if is_slow else ''
    slow_marker = ' ⚠' if is_slow else ''

    detail_html = ''
    if input_summary:
        detail_html = f'''
        <details class="event-details">
            <summary>details</summary>
            <pre>{escape(input_summary)}</pre>
        </details>'''

    return f'''<div class="bar-row">
        <span class="bar-name">{escape(tool_name)}</span>
        <div class="bar-track">
            <div class="bar-fill" style="width: {width}%; background: var(--{color_var});">
                {duration_str if width > 15 else ''}
            </div>
        </div>
        <span class="bar-duration{slow_class}">{duration_str}{slow_marker}</span>
    </div>{detail_html}'''


def render_timeline_html(events: List[Dict], summary: Dict) -> str:
    """Render the timeline events as HTML."""
    start_ts = summary['session_start_ts']
    # Find max duration for bar scaling
    max_duration = max(
        (e['duration_ms'] for e in events if e.get('duration_ms')),
        default=1000
    )
    slow_threshold_ms = 3000

    html_parts = []
    # Track parallel groups already rendered
    rendered_parallel_groups = set()

    for event in events:
        etype = event['type']

        if etype == 'user_message':
            time_str = format_relative_time(start_ts, event['ts'])
            preview = escape(event.get('content_preview', ''))
            reminder_note = ''
            if event.get('system_reminders', 0) > 0:
                reminder_note = f' <span style="color: var(--text-muted)">(+{event["system_reminders"]} system prompts)</span>'
            html_parts.append(f'''
    <div class="timeline-event" data-time="{time_str}">
        <div class="event-label"><span class="role">USER</span> — <span class="preview">{preview}</span>{reminder_note}</div>
    </div>''')

        elif etype == 'thinking':
            time_str = format_relative_time(start_ts, event['start_ts'])
            is_slow = event['duration_ms'] > slow_threshold_ms
            bar = render_bar('thinking', event['duration_ms'], max_duration, is_slow=is_slow)
            token_html = ''
            tokens = event.get('tokens', {})
            if tokens:
                in_t = format_number(tokens.get('input_tokens', 0))
                out_t = format_number(tokens.get('output_tokens', 0))
                cache_parts = []
                cache_create = tokens.get('cache_creation', 0)
                cache_read = tokens.get('cache_read', 0)
                if cache_create:
                    cache_parts.append(f'cache write: {format_number(cache_create)}')
                if cache_read:
                    cache_parts.append(f'cache read: {format_number(cache_read)}')
                cache_str = f' <span class="cache">({", ".join(cache_parts)})</span>' if cache_parts else ''
                token_html = f'<div class="token-info">{in_t} in / {out_t} out{cache_str}</div>'
            html_parts.append(f'''
    <div class="timeline-event" data-time="{time_str}">
        {bar}
        {token_html}
    </div>''')

        elif etype == 'tool_call':
            pg = event.get('parallel_group')
            if pg is not None and pg in rendered_parallel_groups:
                continue  # Already rendered as part of the parallel group

            time_str = format_relative_time(start_ts, event['start_ts'])

            if pg is not None:
                rendered_parallel_groups.add(pg)
                # Gather all events in this parallel group
                group_events = [e for e in events if e.get('parallel_group') == pg]
                bars = []
                for ge in group_events:
                    is_slow = ge['duration_ms'] > slow_threshold_ms
                    bars.append(render_bar(
                        ge['tool_name'], ge['duration_ms'], max_duration,
                        ge.get('input_summary', ''), is_slow=is_slow
                    ))
                html_parts.append(f'''
    <div class="timeline-event" data-time="{time_str}">
        <div class="parallel-group">
            <div class="parallel-label">parallel ({len(group_events)} calls)</div>
            {''.join(bars)}
        </div>
    </div>''')
            else:
                is_slow = event['duration_ms'] > slow_threshold_ms
                bar = render_bar(
                    event['tool_name'], event['duration_ms'], max_duration,
                    event.get('input_summary', ''), is_slow=is_slow
                )
                html_parts.append(f'''
    <div class="timeline-event" data-time="{time_str}">
        {bar}
    </div>''')

        elif etype == 'user_idle':
            time_str = format_relative_time(start_ts, event['start_ts'])
            bar = render_bar('user_idle', event['duration_ms'], max_duration)
            html_parts.append(f'''
    <div class="timeline-event idle" data-time="{time_str}">
        <div class="event-label"><span class="role" style="color: var(--user-idle)">USER IDLE</span> — {format_duration(event['duration_ms'])}</div>
        {bar}
    </div>''')

    return '\n'.join(html_parts)


def render_time_breakdown_card(summary: Dict) -> str:
    """Render the time breakdown summary card."""
    total = summary['total_duration_ms']
    if total <= 0:
        return '<div class="summary-card"><h3>Time Breakdown</h3><p>No timing data.</p></div>'

    think_pct = (summary['total_thinking_ms'] / total) * 100
    tool_pct = (summary['total_tool_ms'] / total) * 100
    idle_pct = (summary['total_idle_ms'] / total) * 100

    return f'''<div class="summary-card">
        <h3>Time Breakdown</h3>
        <div class="breakdown-bar">
            <div class="breakdown-segment" style="width: {think_pct}%; background: var(--thinking);">{think_pct:.0f}%</div>
            <div class="breakdown-segment" style="width: {tool_pct}%; background: var(--tool-bash);">{tool_pct:.0f}%</div>
            <div class="breakdown-segment" style="width: {idle_pct}%; background: var(--user-idle);">{idle_pct:.0f}%</div>
        </div>
        <div class="breakdown-legend">
            <div class="breakdown-legend-item"><div class="breakdown-legend-swatch" style="background: var(--thinking)"></div>Thinking {format_duration(summary['total_thinking_ms'])}</div>
            <div class="breakdown-legend-item"><div class="breakdown-legend-swatch" style="background: var(--tool-bash)"></div>Tools {format_duration(summary['total_tool_ms'])}</div>
            <div class="breakdown-legend-item"><div class="breakdown-legend-swatch" style="background: var(--user-idle)"></div>User idle {format_duration(summary['total_idle_ms'])}</div>
        </div>
    </div>'''


def render_token_breakdown_card(summary: Dict) -> str:
    """Render the token breakdown summary card."""
    tokens = summary['total_tokens']
    total_in = tokens.get('input_tokens', 0)
    total_out = tokens.get('output_tokens', 0)
    cache_create = tokens.get('cache_creation', 0)
    cache_read = tokens.get('cache_read', 0)
    total_cache = cache_create + cache_read
    cache_pct = (total_cache / total_in * 100) if total_in > 0 else 0

    return f'''<div class="summary-card">
        <h3>Token Usage</h3>
        <div class="feature-list">
            <li><span class="feature-cat">Input:</span> <span class="feature-items">{format_number(total_in)}</span></li>
            <li><span class="feature-cat">Output:</span> <span class="feature-items">{format_number(total_out)}</span></li>
            <li><span class="feature-cat">Cache write:</span> <span class="feature-items">{format_number(cache_create)}</span></li>
            <li><span class="feature-cat">Cache read:</span> <span class="feature-items">{format_number(cache_read)}</span></li>
            <li><span class="feature-cat">Cache rate:</span> <span class="feature-items">{cache_pct:.0f}%</span></li>
        </div>
    </div>'''


def render_slowest_ops_card(summary: Dict) -> str:
    """Render the slowest operations summary card."""
    slowest = summary['slowest_operations']
    if not slowest:
        return '<div class="summary-card"><h3>Slowest Operations</h3><p>No timed operations.</p></div>'

    items = []
    for op in slowest[:8]:
        name = op.get('tool_name', 'thinking') if op['type'] == 'tool_call' else 'API thinking'
        items.append(
            f'<li><span class="op-name">{escape(name)}</span>'
            f'<span class="op-duration">{format_duration(op["duration_ms"])}</span></li>'
        )

    return f'''<div class="summary-card">
        <h3>Slowest Operations</h3>
        <ul class="slow-ops">
            {''.join(items)}
        </ul>
    </div>'''


def render_features_card(summary: Dict) -> str:
    """Render the features used summary card."""
    inv = summary['feature_inventory']
    items = []

    if inv['skills']:
        items.append(f'<li><span class="feature-cat">Skills:</span> <span class="feature-items">{escape(", ".join(inv["skills"]))}</span></li>')
    if inv['mcp_tools']:
        # Clean up mcp__ prefix for display
        clean = [t.replace('mcp__', '').replace('__', ' / ') for t in inv['mcp_tools']]
        items.append(f'<li><span class="feature-cat">MCP:</span> <span class="feature-items">{escape(", ".join(clean))}</span></li>')
    if inv['agents']:
        items.append(f'<li><span class="feature-cat">Agents:</span> <span class="feature-items">{len(inv["agents"])} spawned</span></li>')
    if inv['system_tools']:
        items.append(f'<li><span class="feature-cat">Tools:</span> <span class="feature-items">{escape(", ".join(inv["system_tools"]))}</span></li>')
    if inv['commands']:
        items.append(f'<li><span class="feature-cat">Commands:</span> <span class="feature-items">{escape(", ".join(inv["commands"]))}</span></li>')
    if inv['system_reminders']:
        items.append(f'<li><span class="feature-cat">Sys prompts:</span> <span class="feature-items">{inv["system_reminders"]} loaded</span></li>')

    if not items:
        return '<div class="summary-card"><h3>Features Used</h3><p>None detected.</p></div>'

    return f'''<div class="summary-card">
        <h3>Features Used</h3>
        <ul class="feature-list">
            {''.join(items)}
        </ul>
    </div>'''


def generate_chronicle_html(events: List[Dict], summary: Dict,
                            project_name: str, session_id: str) -> str:
    """Render the full chronicle HTML page."""
    session_id_short = session_id[:8] if len(session_id) > 8 else session_id

    timeline_html = render_timeline_html(events, summary)
    time_card = render_time_breakdown_card(summary)
    token_card = render_token_breakdown_card(summary)
    slowest_card = render_slowest_ops_card(summary)
    features_card = render_features_card(summary)

    return CHRONICLE_TEMPLATE.format(
        project_name=escape(project_name),
        session_id_short=escape(session_id_short),
        total_duration=format_duration(summary['total_duration_ms']),
        total_input_tokens=format_number(summary['total_tokens'].get('input_tokens', 0)),
        total_output_tokens=format_number(summary['total_tokens'].get('output_tokens', 0)),
        total_tool_calls=summary['total_tool_calls'],
        total_turns=summary['total_turns'],
        timeline_html=timeline_html,
        time_breakdown_card=time_card,
        token_breakdown_card=token_card,
        slowest_ops_card=slowest_card,
        features_card=features_card,
    )


# ── Main ──

def main():
    parser = argparse.ArgumentParser(
        description='Generate a session chronicle HTML from a Claude Code JSONL file',
    )
    parser.add_argument('--input', '-i', required=True, help='Path to session JSONL file')
    parser.add_argument('--output', '-o', required=True, help='Path for output HTML file')
    parser.add_argument('--project', '-p', default='Unknown', help='Project name for display')
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        return 1

    print(f"Parsing session: {input_path}")
    messages = parse_jsonl(input_path)
    if not messages:
        print("Error: No messages found in session file")
        return 1

    print(f"Found {len(messages)} messages, building timeline...")
    events, summary = build_timeline(messages)
    print(f"Timeline: {len(events)} events, {summary['total_tool_calls']} tool calls")

    # Derive session ID from filename
    session_id = input_path.stem

    html = generate_chronicle_html(events, summary, args.project, session_id)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(html)

    print(f"Chronicle saved to: {output_path}")
    return 0


if __name__ == '__main__':
    exit(main() or 0)
```

- [ ] **Step 2: Smoke-test the script against a real session file**

```bash
cd /Users/sthuang/Project/my_claudecode_marketplace/claude-usage-analyzer
JSONL=$(ls -t ~/.claude/projects/-Users-sthuang-Project-my-claudecode-marketplace/*.jsonl | head -1)
python3 scripts/generate_chronicle.py --input "$JSONL" --output /tmp/chronicle_test.html --project "my-claudecode-marketplace"
```

Expected: script prints message counts and "Chronicle saved to: /tmp/chronicle_test.html"

- [ ] **Step 3: Open the test output and visually verify**

```bash
open /tmp/chronicle_test.html
```

Visually confirm: header shows stats, timeline has vertical events with horizontal bars, summary section shows time/token breakdowns. Fix any rendering issues.

- [ ] **Step 4: Commit**

```bash
cd /Users/sthuang/Project/my_claudecode_marketplace
git add claude-usage-analyzer/scripts/generate_chronicle.py
git commit -m "feat(chronicle): add generator script for session chronicle HTML"
```

---

### Task 3: Chronicle Slash Command (`commands/chronicle.md`)

**Files:**
- Create: `claude-usage-analyzer/commands/chronicle.md`

- [ ] **Step 1: Create the slash command**

Create `claude-usage-analyzer/commands/chronicle.md`:

```markdown
---
description: Generate a visual timeline chronicle of the current Claude Code session, then run a retrospective
allowed-tools: Bash(python3:*), Bash(open:*), Bash(ls:*), Bash(head:*), Read, Skill
---

# Session Chronicle

Generate a vertical timeline HTML view of the current conversation showing tool durations, token usage, and bottlenecks. Then run a retrospective for improvement analysis and memory updates.

## Step 1: Locate the Current Session JSONL

Determine the session file path:

1. The current working directory is the project root. Encode it to the Claude projects path format:
   - Take the absolute path (e.g., `/Users/sthuang/Project/myapp`)
   - Replace each `/` with `-` and strip the leading `-` (e.g., `Users-sthuang-Project-myapp`)
   - The session directory is `~/.claude/projects/{encoded_path}/`

2. Find the most recently modified JSONL file (this is likely the current session):

```bash
ls -t ~/.claude/projects/{encoded_path}/*.jsonl | head -1
```

3. Confirm it's the active session by reading the first few messages:

```bash
head -20 <path> | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        d = json.loads(line.strip())
        if d.get('sessionId'):
            print('Session:', d['sessionId'])
            break
    except: pass
"
```

Note the session ID for use in the output filename.

## Step 2: Generate the Chronicle HTML

Run the generator script. The `--project` flag is the human-readable project name (decode the directory name by replacing `-` with `/`).

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_chronicle.py \
  --input <session_jsonl_path> \
  --output /tmp/chronicle_<session_id_first_8_chars>.html \
  --project "<project_name>"
```

If the script fails, read the error output and troubleshoot. Common issues:
- File not found: double-check the encoded path
- No messages: the session file may be too new (still being written); retry

## Step 3: Open in Browser

```bash
open /tmp/chronicle_<session_id_first_8_chars>.html
```

Tell the user the chronicle is open in their browser and give a brief summary of what it shows:
- Total session duration
- Number of tool calls and turns
- The top 3 slowest operations
- Notable features used (skills, MCP tools, agents)

## Step 4: Run Retrospective

Hand off to the retrospective skill for session summary, improvement analysis, and memory/CLAUDE.md/rules update opportunities:

Invoke `/workflow:retrospective`
```

- [ ] **Step 2: Commit**

```bash
cd /Users/sthuang/Project/my_claudecode_marketplace
git add claude-usage-analyzer/commands/chronicle.md
git commit -m "feat(chronicle): add /chronicle slash command"
```

---

### Task 4: Update Plugin Metadata and CLAUDE.md

**Files:**
- Modify: `claude-usage-analyzer/CLAUDE.md`
- Modify: `claude-usage-analyzer/.claude-plugin/plugin.json`

- [ ] **Step 1: Update plugin.json to register the commands directory (if not already)**

Read `claude-usage-analyzer/.claude-plugin/plugin.json`. It already has `"commands": "./commands/"` — verify this and no changes needed. If the version should be bumped, update from `1.1.0` to `1.2.0`.

- [ ] **Step 2: Add chronicle documentation to CLAUDE.md**

Add a new section to `claude-usage-analyzer/CLAUDE.md` after the `compose-tech-note` command section (around line 83). Add:

```markdown
### chronicle Command

`/chronicle` — generates a vertical timeline HTML of the current session.

- Analyzes the current session's JSONL file (auto-detected from CWD)
- Computes approximate timing from message timestamps + token usage per turn
- Outputs self-contained HTML to `/tmp/chronicle_{session_id_short}.html` and opens it
- Hands off to `/workflow:retrospective` for retro and memory updates
- Generator script: `scripts/generate_chronicle.py`
- Template module: `scripts/chronicle_template.py`
```

Also add to the Script Pipeline section (after item 8, `analyze_single_session.py`):

```markdown
9. **generate_chronicle.py** - Session chronicle timeline generator
   - Takes a single session JSONL file, computes timing deltas and token usage
   - Builds vertical timeline events: thinking, tool_call, user_idle, user_message
   - Detects parallel tool calls, slow operations (>3s), feature usage
   - Uses HTML template from `chronicle_template.py`
   - Output: self-contained HTML file

10. **chronicle_template.py** - HTML template for session chronicle
    - Vertical timeline with horizontal duration bars
    - Dark theme consistent with session_template.py
    - Color-coded bars by tool type, parallel call grouping
    - Summary section: time breakdown, token usage, slowest operations, features used
```

- [ ] **Step 3: Commit**

```bash
cd /Users/sthuang/Project/my_claudecode_marketplace
git add claude-usage-analyzer/CLAUDE.md claude-usage-analyzer/.claude-plugin/plugin.json
git commit -m "docs(chronicle): update CLAUDE.md and plugin metadata for chronicle command"
```

---

### Task 5: End-to-End Validation

**Files:** (no new files — testing existing)

- [ ] **Step 1: Run the full flow manually**

Simulate what `/chronicle` does:

```bash
cd /Users/sthuang/Project/my_claudecode_marketplace
ENCODED="Users-sthuang-Project-my-claudecode-marketplace"
JSONL=$(ls -t ~/.claude/projects/-${ENCODED}/*.jsonl | head -1)
SESSION_ID=$(basename "$JSONL" .jsonl)
SHORT_ID=${SESSION_ID:0:8}
python3 claude-usage-analyzer/scripts/generate_chronicle.py \
  --input "$JSONL" \
  --output "/tmp/chronicle_${SHORT_ID}.html" \
  --project "my-claudecode-marketplace"
```

Expected: completes without errors, HTML file created.

- [ ] **Step 2: Open and visually verify the HTML**

```bash
open /tmp/chronicle_${SHORT_ID}.html
```

Check:
- Header shows correct project name, session ID, duration, token counts
- Timeline shows user messages, thinking bars, tool call bars, user idle bars
- Parallel tool calls are grouped with "parallel (N calls)" label
- Slow operations (>3s) have ⚠ warning marker
- Summary section shows time breakdown bar, token usage, slowest ops, features
- Dark theme renders correctly, no broken CSS

- [ ] **Step 3: Test with a different project's session**

```bash
OTHER_JSONL=$(ls -t ~/.claude/projects/-Users-sthuang-Project-cc-plugin-marketplace/*.jsonl | head -1)
python3 claude-usage-analyzer/scripts/generate_chronicle.py \
  --input "$OTHER_JSONL" \
  --output "/tmp/chronicle_other_test.html" \
  --project "cc-plugin-marketplace"
open /tmp/chronicle_other_test.html
```

Expected: works with a different session, shows different data.

- [ ] **Step 4: Fix any issues found during validation**

If any rendering bugs, timing miscalculations, or crashes are found, fix them in the relevant script/template and re-run the test.

- [ ] **Step 5: Final commit (if fixes were needed)**

```bash
cd /Users/sthuang/Project/my_claudecode_marketplace
git add -A claude-usage-analyzer/
git commit -m "fix(chronicle): address issues found during e2e validation"
```
