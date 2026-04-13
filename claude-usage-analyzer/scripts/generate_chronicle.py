#!/usr/bin/env python3
"""
Generate a visual timeline chronicle HTML page from a single Claude Code session JSONL.

Parses the JSONL stream to extract timestamped events (API turns, tool calls,
user idle periods), computes durations, and renders them into an HTML timeline
using the chronicle_template module.

Usage:
    python generate_chronicle.py --input <session.jsonl> --output <output.html>
    python generate_chronicle.py --input <session.jsonl> --output <output.html> --project "my-app"
"""

import argparse
import html
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from chronicle_template import CHRONICLE_TEMPLATE, get_tool_color_var


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------

def parse_timestamp(ts) -> Optional[datetime]:
    """Parse ISO or epoch-ms timestamp to datetime."""
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts / 1000)
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


def fmt_time(dt: datetime) -> str:
    """Format datetime as HH:MM:SS for the timeline left rail."""
    return dt.strftime("%H:%M:%S")


def fmt_duration(seconds: float) -> str:
    """Human-readable duration string."""
    if seconds < 0.1:
        return "<0.1s"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds) // 60
    secs = seconds - minutes * 60
    if minutes < 60:
        return f"{minutes}m {secs:.0f}s"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m"


def fmt_tokens(n: int) -> str:
    """Format token count with comma separators."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


# ---------------------------------------------------------------------------
# JSONL parsing → event list
# ---------------------------------------------------------------------------

class Event:
    """A single timeline event."""
    __slots__ = (
        "kind", "timestamp", "duration_s", "tool_name", "tool_detail",
        "input_tokens", "output_tokens", "parallel_group",
        "tool_input", "tool_result",
    )

    def __init__(self, kind: str, timestamp: datetime, duration_s: float = 0.0,
                 tool_name: str = "", tool_detail: str = "",
                 input_tokens: int = 0, output_tokens: int = 0,
                 parallel_group: Optional[int] = None,
                 tool_input: Optional[Dict] = None, tool_result: str = ""):
        self.kind = kind                    # "thinking", "tool", "user_idle"
        self.timestamp = timestamp
        self.duration_s = duration_s
        self.tool_name = tool_name
        self.tool_detail = tool_detail      # e.g. file path, command snippet
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.parallel_group = parallel_group
        self.tool_input = tool_input        # full tool_use input dict
        self.tool_result = tool_result      # truncated tool result text


def _extract_tool_detail(tool_name: str, tool_input: Dict) -> str:
    """Extract a short detail string from tool_use input."""
    if tool_name in ("Read", "Edit", "Write", "MultiEdit", "NotebookEdit"):
        fp = tool_input.get("file_path", "")
        if fp:
            # Show just the filename and parent
            parts = fp.rsplit("/", 2)
            return "/".join(parts[-2:]) if len(parts) >= 2 else fp
    elif tool_name == "Bash":
        cmd = tool_input.get("command", "")
        return cmd[:80] + ("..." if len(cmd) > 80 else "")
    elif tool_name == "Grep":
        pattern = tool_input.get("pattern", "")
        return f'/{pattern}/' if pattern else ""
    elif tool_name == "Glob":
        return tool_input.get("pattern", "")
    elif tool_name == "Skill":
        return tool_input.get("skill", "")
    elif tool_name == "Agent":
        return tool_input.get("description", "")[:60]
    elif tool_name in ("TaskCreate", "TaskUpdate", "TaskGet", "TaskList"):
        subj = tool_input.get("subject", "")
        return subj[:60] if subj else ""
    elif tool_name == "ToolSearch":
        return tool_input.get("query", "")[:60]
    elif tool_name in ("WebSearch", "WebFetch"):
        return tool_input.get("query", tool_input.get("url", ""))[:60]
    elif tool_name.startswith("mcp__"):
        # MCP tools — try to show key param
        for key in ("query", "url", "channel", "message", "text"):
            if key in tool_input:
                return f"{key}={str(tool_input[key])[:50]}"
    return ""


def parse_jsonl(path: str) -> Tuple[List[Event], Dict[str, Any]]:
    """Parse a session JSONL file and return (events, session_meta).

    The timing model:
      - API thinking time = gap from last user message to next assistant message
      - Tool execution time = gap from assistant tool_use to next user tool_result
      - User idle time = gap from assistant output to next real user message
    """
    events: List[Event] = []
    session_meta: Dict[str, Any] = {
        "session_id": "",
        "project": "",
        "total_input_tokens": 0,
        "total_output_tokens": 0,
    }

    messages: List[Dict] = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not messages:
        return events, session_meta

    # Extract session metadata from first messages
    for msg in messages[:20]:
        if msg.get("sessionId") and not session_meta["session_id"]:
            session_meta["session_id"] = msg["sessionId"]
        if msg.get("gitBranch"):
            session_meta["git_branch"] = msg["gitBranch"]

    # Build a map of tool_use_id → assistant timestamp for matching results
    tool_use_ts: Dict[str, datetime] = {}
    tool_use_info: Dict[str, Tuple[str, str]] = {}  # id → (name, detail)
    tool_use_inputs: Dict[str, Dict] = {}  # id → full input dict

    # Track parallel groups: assistant messages with multiple tool_use blocks
    parallel_group_counter = 0

    # Process messages to build events
    prev_ts: Optional[datetime] = None
    prev_type: Optional[str] = None  # "user_real", "user_tool_result", "assistant_text", "assistant_tool"

    for msg in messages:
        msg_type = msg.get("type")
        ts = parse_timestamp(msg.get("timestamp"))
        if ts is None:
            continue

        if msg_type == "assistant":
            message = msg.get("message", {})
            content = message.get("content", [])
            usage = message.get("usage", {})

            # Accumulate tokens
            in_tok = usage.get("input_tokens", 0)
            out_tok = usage.get("output_tokens", 0)
            cache_in = usage.get("cache_read_input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
            session_meta["total_input_tokens"] += in_tok + cache_in
            session_meta["total_output_tokens"] += out_tok

            if not isinstance(content, list):
                continue

            # Classify content blocks
            tool_uses = []
            has_thinking = False
            has_text = False
            for block in content:
                if not isinstance(block, dict):
                    continue
                bt = block.get("type")
                if bt == "thinking":
                    has_thinking = True
                elif bt == "tool_use":
                    tool_uses.append(block)
                elif bt == "text" and block.get("text", "").strip():
                    has_text = True

            # API thinking event: time from previous user message to this assistant message
            if prev_ts and prev_type in ("user_real", "user_tool_result"):
                thinking_dur = (ts - prev_ts).total_seconds()
                if thinking_dur > 0.05:  # skip sub-50ms noise
                    events.append(Event(
                        kind="thinking",
                        timestamp=prev_ts,
                        duration_s=thinking_dur,
                        input_tokens=in_tok + cache_in,
                        output_tokens=out_tok,
                    ))

            # Register tool_use blocks
            if tool_uses:
                pg = None
                if len(tool_uses) > 1:
                    parallel_group_counter += 1
                    pg = parallel_group_counter

                for tu in tool_uses:
                    tid = tu.get("id", "")
                    tname = tu.get("name", "unknown")
                    tinput = tu.get("input", {})
                    tdetail = _extract_tool_detail(tname, tinput)
                    tool_use_ts[tid] = ts
                    tool_use_info[tid] = (tname, tdetail)
                    tool_use_inputs[tid] = tinput
                    # We'll create the tool event when we see the result

                prev_type = "assistant_tool"
            elif has_text:
                prev_type = "assistant_text"
            elif has_thinking:
                prev_type = "assistant_thinking"
            else:
                prev_type = "assistant_other"

            prev_ts = ts

        elif msg_type == "user":
            content = msg.get("message", {}).get("content", "")
            is_meta = msg.get("isMeta", False)

            # Check if this is a tool_result message
            tool_results = []
            is_real_user = False
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        tool_results.append(block)
                    elif isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "").strip()
                        if text and "<command-" not in text and not is_meta:
                            is_real_user = True
            elif isinstance(content, str):
                text = content.strip()
                if text and "<command-" not in text and not is_meta:
                    is_real_user = True

            if tool_results:
                # Resolve tool call durations
                pg_members = []
                for tr in tool_results:
                    tid = tr.get("tool_use_id", "")
                    start = tool_use_ts.get(tid)
                    if start:
                        dur = (ts - start).total_seconds()
                        tname, tdetail = tool_use_info.get(tid, ("unknown", ""))
                        # Extract result content (truncated)
                        result_content = ""
                        tr_content = tr.get("content", "")
                        if isinstance(tr_content, list):
                            texts = []
                            for blk in tr_content:
                                if isinstance(blk, dict) and blk.get("type") == "text":
                                    texts.append(blk.get("text", ""))
                            result_content = "\n".join(texts)
                        elif isinstance(tr_content, str):
                            result_content = tr_content
                        if len(result_content) > 800:
                            result_content = result_content[:800] + "\n\u2026 (truncated)"
                        # Determine parallel group
                        pg = None
                        # If multiple results arrive in one message, they were parallel
                        if len(tool_results) > 1:
                            if not pg_members:
                                parallel_group_counter += 1
                            pg = parallel_group_counter
                        ev = Event(
                            kind="tool",
                            timestamp=start,
                            duration_s=max(dur, 0),
                            tool_name=tname,
                            tool_detail=tdetail,
                            parallel_group=pg,
                            tool_input=tool_use_inputs.get(tid),
                            tool_result=result_content,
                        )
                        events.append(ev)
                        pg_members.append(ev)

                prev_type = "user_tool_result"
                prev_ts = ts

            elif is_real_user:
                # Real user message — compute idle time from previous assistant output
                if prev_ts and prev_type in ("assistant_text", "assistant_other", "assistant_thinking"):
                    idle_dur = (ts - prev_ts).total_seconds()
                    if idle_dur > 2.0:  # only show idle > 2s
                        events.append(Event(
                            kind="user_idle",
                            timestamp=prev_ts,
                            duration_s=idle_dur,
                        ))

                prev_type = "user_real"
                prev_ts = ts

    # Sort events by timestamp
    events.sort(key=lambda e: e.timestamp)

    # Set session start/end from first/last timestamps
    if events:
        session_meta["start_time"] = events[0].timestamp
        session_meta["end_time"] = events[-1].timestamp

    return events, session_meta


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

SLOW_THRESHOLD_S = 10.0  # highlight ops slower than this


def _bar_width_pct(duration_s: float, max_duration_s: float) -> float:
    """Calculate bar fill width as a percentage."""
    if max_duration_s <= 0:
        return 0
    return min(100, max(2, (duration_s / max_duration_s) * 100))


def _event_css_class(event: Event) -> str:
    """Return CSS class for the timeline dot."""
    if event.kind == "thinking":
        return "event-thinking"
    if event.kind == "user_idle":
        return "event-user-idle"
    return f"event-{get_tool_color_var(event.tool_name)}"


def _bar_css_class(event: Event) -> str:
    """Return CSS class for the bar fill."""
    if event.kind == "thinking":
        return "thinking"
    if event.kind == "user_idle":
        return "user-idle"
    return get_tool_color_var(event.tool_name)


def _event_label(event: Event) -> str:
    """Human-readable label for the event."""
    if event.kind == "thinking":
        return "API turn"
    if event.kind == "user_idle":
        return "User idle"
    label = event.tool_name
    if event.tool_detail:
        detail = html.escape(event.tool_detail)
        label += f' <span style="color:var(--text-muted);font-size:0.75rem">{detail}</span>'
    return label


def build_timeline_html(events: List[Event]) -> str:
    """Build the timeline HTML from the event list."""
    if not events:
        return '<div style="padding:2rem;color:var(--text-muted)">No events found in session.</div>'

    max_dur = max((e.duration_s for e in events), default=1)
    lines: List[str] = []

    # Group consecutive events that share a parallel_group
    i = 0
    while i < len(events):
        ev = events[i]

        # Check for start of a parallel group
        if ev.parallel_group is not None:
            pg_id = ev.parallel_group
            group: List[Event] = []
            while i < len(events) and events[i].parallel_group == pg_id:
                group.append(events[i])
                i += 1
            lines.append(_render_parallel_group(group, max_dur))
        else:
            lines.append(_render_single_event(ev, max_dur))
            i += 1

    return "\n".join(lines)


def _render_detail_panel(ev: Event) -> str:
    """Render the expandable detail panel for a tool event."""
    if ev.kind != "tool":
        return ""

    sections = []

    if ev.tool_input:
        input_str = json.dumps(ev.tool_input, indent=2, ensure_ascii=False)
        if len(input_str) > 1500:
            input_str = input_str[:1500] + "\n\u2026"
        sections.append(
            f'<div class="detail-section">'
            f'<div class="detail-label">Input</div>'
            f'<pre>{html.escape(input_str)}</pre>'
            f'</div>'
        )

    if ev.tool_result:
        sections.append(
            f'<div class="detail-section">'
            f'<div class="detail-label">Result</div>'
            f'<pre>{html.escape(ev.tool_result)}</pre>'
            f'</div>'
        )

    if not sections:
        return ""

    return f'<div class="event-details">{"".join(sections)}</div>'


def _render_single_event(ev: Event, max_dur: float) -> str:
    """Render one timeline event row."""
    css_class = _event_css_class(ev)
    time_str = fmt_time(ev.timestamp)
    bar_class = _bar_css_class(ev)
    width = _bar_width_pct(ev.duration_s, max_dur)
    dur_str = fmt_duration(ev.duration_s)
    dur_class = "slow" if ev.duration_s >= SLOW_THRESHOLD_S else ""
    label = _event_label(ev)

    detail_html = _render_detail_panel(ev)
    has_details = ' data-has-details' if detail_html else ''
    chevron = '<span class="bar-chevron">&#9654;</span>' if detail_html else ''

    token_html = ""
    if ev.kind == "thinking" and (ev.input_tokens or ev.output_tokens):
        token_html = (
            f'<span class="token-info">'
            f'<span class="token-in">{fmt_tokens(ev.input_tokens)}in</span> / '
            f'<span class="token-out">{fmt_tokens(ev.output_tokens)}out</span>'
            f'</span>'
        )

    return (
        f'<div class="timeline-event {css_class}" data-time="{time_str}">'
        f'  <div class="event-body">'
        f'    <div class="bar-row"{has_details}>'
        f'      {chevron}'
        f'      <span class="bar-name">{label}{token_html}</span>'
        f'      <div class="bar-track"><div class="bar-fill {bar_class}" style="width:{width:.1f}%"></div></div>'
        f'      <span class="bar-duration {dur_class}">{dur_str}</span>'
        f'    </div>'
        f'    {detail_html}'
        f'  </div>'
        f'</div>'
    )


def _render_parallel_group(group: List[Event], max_dur: float) -> str:
    """Render a group of parallel tool calls."""
    if not group:
        return ""
    first = group[0]
    time_str = fmt_time(first.timestamp)
    css_class = _event_css_class(first)

    inner_lines = []
    for ev in group:
        bar_class = _bar_css_class(ev)
        width = _bar_width_pct(ev.duration_s, max_dur)
        dur_str = fmt_duration(ev.duration_s)
        dur_class = "slow" if ev.duration_s >= SLOW_THRESHOLD_S else ""
        label = _event_label(ev)
        detail_html = _render_detail_panel(ev)
        has_details = ' data-has-details' if detail_html else ''
        chevron = '<span class="bar-chevron">&#9654;</span>' if detail_html else ''
        inner_lines.append(
            f'<div class="bar-row"{has_details}>'
            f'  {chevron}'
            f'  <span class="bar-name">{label}</span>'
            f'  <div class="bar-track"><div class="bar-fill {bar_class}" style="width:{width:.1f}%"></div></div>'
            f'  <span class="bar-duration {dur_class}">{dur_str}</span>'
            f'</div>'
            f'{detail_html}'
        )

    inner_html = "\n".join(inner_lines)
    return (
        f'<div class="timeline-event {css_class}" data-time="{time_str}">'
        f'  <div class="event-body">'
        f'    <div class="parallel-group">'
        f'      <div class="parallel-group-label">parallel ({len(group)})</div>'
        f'      {inner_html}'
        f'    </div>'
        f'  </div>'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# Summary cards
# ---------------------------------------------------------------------------

def build_time_breakdown_card(events: List[Event]) -> str:
    """Build the time breakdown summary card."""
    buckets: Dict[str, float] = defaultdict(float)
    for ev in events:
        if ev.kind == "thinking":
            buckets["API thinking"] += ev.duration_s
        elif ev.kind == "user_idle":
            buckets["User idle"] += ev.duration_s
        else:
            buckets["Tool execution"] += ev.duration_s

    total = sum(buckets.values()) or 1
    colors = {
        "API thinking": "var(--thinking)",
        "Tool execution": "var(--tool-bash)",
        "User idle": "var(--user-idle)",
    }

    bar_segments = ""
    legend_items = ""
    for label in ("API thinking", "Tool execution", "User idle"):
        secs = buckets.get(label, 0)
        pct = (secs / total) * 100
        color = colors[label]
        bar_segments += f'<div class="breakdown-bar-segment" style="width:{pct:.1f}%;background:{color}"></div>'
        legend_items += (
            f'<div class="breakdown-legend-item">'
            f'  <div class="breakdown-legend-swatch" style="background:{color}"></div>'
            f'  <span class="breakdown-legend-label">{label}</span>'
            f'  <span class="breakdown-legend-value">{fmt_duration(secs)} ({pct:.0f}%)</span>'
            f'</div>'
        )

    return (
        f'<div class="summary-card">'
        f'  <h3>Time Breakdown</h3>'
        f'  <div class="breakdown-bar">{bar_segments}</div>'
        f'  <div class="breakdown-legend">{legend_items}</div>'
        f'</div>'
    )


def build_token_breakdown_card(events: List[Event]) -> str:
    """Build the token usage summary card."""
    total_in = sum(e.input_tokens for e in events)
    total_out = sum(e.output_tokens for e in events)
    total = total_in + total_out or 1

    in_pct = (total_in / total) * 100
    out_pct = (total_out / total) * 100

    return (
        f'<div class="summary-card">'
        f'  <h3>Token Usage</h3>'
        f'  <div class="breakdown-bar">'
        f'    <div class="breakdown-bar-segment" style="width:{in_pct:.1f}%;background:var(--accent-primary)"></div>'
        f'    <div class="breakdown-bar-segment" style="width:{out_pct:.1f}%;background:var(--success)"></div>'
        f'  </div>'
        f'  <div class="breakdown-legend">'
        f'    <div class="breakdown-legend-item">'
        f'      <div class="breakdown-legend-swatch" style="background:var(--accent-primary)"></div>'
        f'      <span class="breakdown-legend-label">Input tokens</span>'
        f'      <span class="breakdown-legend-value">{fmt_tokens(total_in)}</span>'
        f'    </div>'
        f'    <div class="breakdown-legend-item">'
        f'      <div class="breakdown-legend-swatch" style="background:var(--success)"></div>'
        f'      <span class="breakdown-legend-label">Output tokens</span>'
        f'      <span class="breakdown-legend-value">{fmt_tokens(total_out)}</span>'
        f'    </div>'
        f'  </div>'
        f'</div>'
    )


def build_slowest_ops_card(events: List[Event], top_n: int = 5) -> str:
    """Build the slowest operations summary card."""
    # Filter to tool and thinking events, sort by duration descending
    ranked = sorted(
        [e for e in events if e.kind in ("tool", "thinking")],
        key=lambda e: e.duration_s,
        reverse=True,
    )[:top_n]

    if not ranked:
        return ""

    items = ""
    for rank, ev in enumerate(ranked, 1):
        name = ev.tool_name if ev.kind == "tool" else "API turn"
        detail = html.escape(ev.tool_detail) if ev.tool_detail else ""
        label = f"{name}"
        if detail:
            label += f' <span style="color:var(--text-muted)">{detail}</span>'
        items += (
            f'<li class="slow-ops-item">'
            f'  <span class="slow-ops-rank">#{rank}</span>'
            f'  <span class="slow-ops-name">{label}</span>'
            f'  <span class="slow-ops-duration">{fmt_duration(ev.duration_s)}</span>'
            f'</li>'
        )

    return (
        f'<div class="summary-card">'
        f'  <h3>Slowest Operations</h3>'
        f'  <ol class="slow-ops-list">{items}</ol>'
        f'</div>'
    )


def build_features_card(events: List[Event]) -> str:
    """Build the features/tool usage summary card."""
    tool_counts: Dict[str, int] = defaultdict(int)
    for ev in events:
        if ev.kind == "tool":
            tool_counts[ev.tool_name] += 1

    if not tool_counts:
        return ""

    # Sort by count descending
    sorted_tools = sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)

    items = ""
    for name, count in sorted_tools[:10]:
        color_var = get_tool_color_var(name)
        items += (
            f'<div class="feature-item">'
            f'  <div class="feature-icon" style="background:var(--{color_var})">'
            f'    {html.escape(name[0])}'
            f'  </div>'
            f'  <span class="feature-label">{html.escape(name)}</span>'
            f'  <span class="feature-count">{count}</span>'
            f'</div>'
        )

    return (
        f'<div class="summary-card">'
        f'  <h3>Tool Usage</h3>'
        f'  <div class="feature-list">{items}</div>'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------

def render_chronicle(events: List[Event], session_meta: Dict, project_name: str) -> str:
    """Render the full chronicle HTML page."""
    sid = session_meta.get("session_id", "unknown")
    sid_short = sid[:8] if len(sid) > 8 else sid

    start = session_meta.get("start_time")
    end = session_meta.get("end_time")
    if start and end:
        total_dur = fmt_duration((end - start).total_seconds())
    else:
        total_dur = "—"

    tool_events = [e for e in events if e.kind == "tool"]
    thinking_events = [e for e in events if e.kind == "thinking"]

    return CHRONICLE_TEMPLATE.format(
        session_id_short=html.escape(sid_short),
        project_name=html.escape(project_name),
        total_duration=total_dur,
        total_turns=len(thinking_events),
        total_tool_calls=len(tool_events),
        total_input_tokens=fmt_tokens(session_meta.get("total_input_tokens", 0)),
        total_output_tokens=fmt_tokens(session_meta.get("total_output_tokens", 0)),
        timeline_html=build_timeline_html(events),
        time_breakdown_card=build_time_breakdown_card(events),
        token_breakdown_card=build_token_breakdown_card(events),
        slowest_ops_card=build_slowest_ops_card(events),
        features_card=build_features_card(events),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate a visual timeline chronicle from a Claude Code session JSONL."
    )
    parser.add_argument("--input", required=True, help="Path to session .jsonl file")
    parser.add_argument("--output", required=True, help="Output HTML file path")
    parser.add_argument("--project", default="", help="Project name for the header")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    events, session_meta = parse_jsonl(str(input_path))

    if not events:
        print("Warning: no events extracted from session file.", file=sys.stderr)

    project_name = args.project or session_meta.get("project", "")
    html_content = render_chronicle(events, session_meta, project_name)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content, encoding="utf-8")

    # Print summary to stdout
    tool_events = [e for e in events if e.kind == "tool"]
    thinking_events = [e for e in events if e.kind == "thinking"]
    print(f"Chronicle generated: {output_path}")
    print(f"  Session: {session_meta.get('session_id', 'unknown')[:8]}")
    print(f"  Events: {len(events)} ({len(thinking_events)} API turns, {len(tool_events)} tool calls)")
    if events:
        slowest = max(events, key=lambda e: e.duration_s)
        label = slowest.tool_name if slowest.kind == "tool" else slowest.kind
        print(f"  Slowest: {label} ({fmt_duration(slowest.duration_s)})")


if __name__ == "__main__":
    main()
