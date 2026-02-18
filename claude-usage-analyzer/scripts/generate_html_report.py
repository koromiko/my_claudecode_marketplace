#!/usr/bin/env python3
"""
Generate HTML report from Claude Code usage analysis data.

This script takes the aggregate_report.json and qualitative_data.json files
and generates a partial HTML report with quantitative data filled in.
Claude then completes the qualitative sections.
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

from html_template import HTML_TEMPLATE, get_chart_color
from session_template import get_session_template


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


def generate_project_table(by_project: Dict[str, Dict]) -> str:
    """Generate HTML table for project breakdown."""
    if not by_project:
        return '<p class="text-muted">No project data available.</p>'

    # Sort by sessions descending
    sorted_projects = sorted(by_project.items(), key=lambda x: -x[1].get('sessions', 0))

    rows = []
    for project, data in sorted_projects[:20]:  # Limit to top 20
        sessions = data.get('sessions', 0)
        completed = data.get('completed', 0)
        comp_rate = data.get('completion_rate', 0)
        issue_rate = data.get('issue_rate', 0)
        avg_duration = data.get('avg_duration', 0)
        files_touched = data.get('files_touched', 0)

        # Color code rates
        comp_class = 'success' if comp_rate >= 70 else ('warning' if comp_rate >= 50 else 'error')
        issue_class = 'error' if issue_rate > 30 else ('warning' if issue_rate > 15 else 'success')

        row = f'''
        <tr>
            <td><strong>{escape_html(project)}</strong></td>
            <td>{sessions}</td>
            <td>
                <span style="color: var(--{comp_class})">{comp_rate}%</span>
                <div class="progress-bar">
                    <div class="fill {comp_class}" style="width: {comp_rate}%"></div>
                </div>
            </td>
            <td>
                <span style="color: var(--{issue_class})">{issue_rate}%</span>
            </td>
            <td>{avg_duration:.1f}m</td>
            <td>{files_touched}</td>
        </tr>'''
        rows.append(row)

    return f'''
    <div class="table-container">
        <table>
            <thead>
                <tr>
                    <th>Project</th>
                    <th>Sessions</th>
                    <th>Completion Rate</th>
                    <th>Issue Rate</th>
                    <th>Avg Duration</th>
                    <th>Files Touched</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
    </div>'''


def generate_tool_usage_chart(tools_usage: Dict[str, int], max_items: int = 15) -> str:
    """Generate CSS-based horizontal bar chart for tool usage."""
    if not tools_usage:
        return '<p class="text-muted">No tool usage data available.</p>'

    # Get top N tools
    sorted_tools = sorted(tools_usage.items(), key=lambda x: -x[1])[:max_items]
    max_value = sorted_tools[0][1] if sorted_tools else 1

    bars = []
    for i, (tool, count) in enumerate(sorted_tools):
        width_pct = (count / max_value) * 100
        color = get_chart_color(i)

        bar = f'''
        <div class="bar-item">
            <span class="bar-label" title="{escape_html(tool)}">{escape_html(tool)}</span>
            <div class="bar-track">
                <div class="bar-fill" style="width: {width_pct}%; background: {color};">
                    {count if width_pct > 15 else ''}
                </div>
            </div>
            <span class="bar-value">{count}</span>
        </div>'''
        bars.append(bar)

    return f'<div class="bar-chart">{"".join(bars)}</div>'


def generate_task_type_chart(by_task_type: Dict[str, int]) -> str:
    """Generate SVG pie chart for task type distribution."""
    if not by_task_type:
        return '<p class="text-muted">No task type data available.</p>'

    total = sum(by_task_type.values())
    if total == 0:
        return '<p class="text-muted">No task type data available.</p>'

    # Sort by count
    sorted_types = sorted(by_task_type.items(), key=lambda x: -x[1])

    # Generate pie segments
    segments = []
    legend_items = []
    cumulative = 0

    for i, (task_type, count) in enumerate(sorted_types):
        pct = (count / total) * 100
        start_angle = cumulative * 3.6  # Convert percentage to degrees
        cumulative += pct
        end_angle = cumulative * 3.6

        color = get_chart_color(i)

        # SVG arc calculation
        large_arc = 1 if pct > 50 else 0
        start_x = 100 + 80 * _cos(start_angle)
        start_y = 100 + 80 * _sin(start_angle)
        end_x = 100 + 80 * _cos(end_angle)
        end_y = 100 + 80 * _sin(end_angle)

        if pct >= 100:
            # Full circle
            segment = f'<circle cx="100" cy="100" r="80" fill="{color}" />'
        elif pct > 0:
            segment = f'''<path d="M 100 100 L {start_x:.2f} {start_y:.2f} A 80 80 0 {large_arc} 1 {end_x:.2f} {end_y:.2f} Z" fill="{color}" />'''
        else:
            segment = ''

        segments.append(segment)

        legend_items.append(f'''
        <div class="legend-item">
            <div class="legend-color" style="background: {color}"></div>
            <span>{escape_html(task_type)}: {count} ({pct:.1f}%)</span>
        </div>''')

    svg = f'''
    <svg class="pie-chart" viewBox="0 0 200 200">
        {''.join(segments)}
    </svg>'''

    return f'''
    <div class="pie-chart-container">
        {svg}
        <div class="pie-legend">
            {''.join(legend_items)}
        </div>
    </div>'''


def generate_task_type_bars(by_task_type: Dict[str, int]) -> str:
    """Generate horizontal bar chart for task types."""
    if not by_task_type:
        return '<p class="text-muted">No task type data available.</p>'

    sorted_types = sorted(by_task_type.items(), key=lambda x: -x[1])
    max_value = sorted_types[0][1] if sorted_types else 1

    bars = []
    for i, (task_type, count) in enumerate(sorted_types):
        width_pct = (count / max_value) * 100
        color = get_chart_color(i)

        bar = f'''
        <div class="bar-item">
            <span class="bar-label">{escape_html(task_type)}</span>
            <div class="bar-track">
                <div class="bar-fill" style="width: {width_pct}%; background: {color};">
                </div>
            </div>
            <span class="bar-value">{count}</span>
        </div>'''
        bars.append(bar)

    return f'<div class="bar-chart">{"".join(bars)}</div>'


def generate_comparison_section(comparison: Dict) -> str:
    """Generate HTML for comparison data between current and previous periods.

    Args:
        comparison: Comparison data from report_data JSON

    Returns:
        HTML string for the comparison section
    """
    if not comparison or not comparison.get('has_comparison'):
        return ''

    prev_period = comparison.get('previous_period', {})
    prev_start = prev_period.get('start_date', 'N/A')
    prev_end = prev_period.get('end_date', 'N/A')

    def render_delta(delta_data: Dict, label: str, format_fn=None, invert_color: bool = False) -> str:
        """Render a single delta metric with trend indicator.

        Args:
            delta_data: Dict with 'value', 'delta', 'delta_pct' keys
            label: Display label for the metric
            format_fn: Optional function to format the value
            invert_color: If True, negative deltas are good (e.g., for issue rate)
        """
        value = delta_data.get('value', 0)
        delta = delta_data.get('delta', 0)
        delta_pct = delta_data.get('delta_pct', 0)

        if format_fn:
            value_str = format_fn(value)
        else:
            value_str = str(value)

        # Determine trend indicator and color
        if delta > 0:
            trend = '▲'
            color_class = 'error' if invert_color else 'success'
        elif delta < 0:
            trend = '▼'
            color_class = 'success' if invert_color else 'error'
        else:
            trend = '→'
            color_class = 'muted'

        delta_str = f'{delta:+.1f}' if isinstance(delta, float) else f'{delta:+d}'

        return f'''
        <div class="comparison-item">
            <div class="comparison-label">{escape_html(label)}</div>
            <div class="comparison-value">{escape_html(value_str)}</div>
            <div class="comparison-delta {color_class}">
                <span class="trend-icon">{trend}</span>
                <span>{delta_str} ({delta_pct:+.1f}%)</span>
            </div>
        </div>'''

    # Format functions for different metric types
    def fmt_hours(val): return f"{val:.1f}h"
    def fmt_pct(val): return f"{val:.1f}%"
    def fmt_minutes(val): return f"{val:.1f}m"

    # Render key metrics
    sessions_html = render_delta(comparison.get('sessions', {}), 'Total Sessions')
    duration_html = render_delta(comparison.get('total_duration_hours', {}), 'Total Duration', fmt_hours)
    activity_rate_html = render_delta(comparison.get('activity_rate', {}), 'Activity Rate', fmt_pct)
    issue_rate_html = render_delta(comparison.get('issue_rate', {}), 'Issue Rate', fmt_pct, invert_color=True)
    avg_duration_html = render_delta(comparison.get('avg_duration', {}), 'Avg Duration', fmt_minutes)
    tool_calls_html = render_delta(comparison.get('total_tool_calls', {}), 'Total Tool Calls')

    return f'''
    <div class="card comparison-card">
        <div class="card-title">Period Comparison</div>
        <div class="comparison-subtitle">Previous: {escape_html(prev_start)} to {escape_html(prev_end)}</div>
        <div class="comparison-grid">
            {sessions_html}
            {duration_html}
            {activity_rate_html}
            {issue_rate_html}
            {avg_duration_html}
            {tool_calls_html}
        </div>
    </div>'''


def generate_features_table(claude_code_features: Dict) -> str:
    """Generate HTML table for Claude Code features."""
    skills = claude_code_features.get('skills_usage', {})
    agents = claude_code_features.get('agents_usage', {})
    slash_commands = claude_code_features.get('slash_commands_usage', {})

    if not skills and not agents and not slash_commands:
        return '<p class="text-muted">No Claude Code feature usage data available.</p>'

    rows = []

    # Skills
    for skill, count in list(skills.items())[:10]:
        rows.append(f'''
        <tr>
            <td><span class="feature-badge">Skill</span></td>
            <td><code>/{escape_html(skill)}</code></td>
            <td>{count}</td>
        </tr>''')

    # Agents
    for agent, count in list(agents.items())[:10]:
        rows.append(f'''
        <tr>
            <td><span class="feature-badge">Agent</span></td>
            <td>{escape_html(agent)}</td>
            <td>{count}</td>
        </tr>''')

    # Slash commands
    for cmd, count in list(slash_commands.items())[:10]:
        rows.append(f'''
        <tr>
            <td><span class="feature-badge">Command</span></td>
            <td><code>/{escape_html(cmd)}</code></td>
            <td>{count}</td>
        </tr>''')

    if not rows:
        return '<p class="text-muted">No Claude Code feature usage data available.</p>'

    return f'''
    <div class="table-container">
        <table>
            <thead>
                <tr>
                    <th>Type</th>
                    <th>Feature</th>
                    <th>Usage Count</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
    </div>'''


def generate_duration_chart(duration_distribution: Dict) -> str:
    """Generate duration distribution visualization."""
    if not duration_distribution:
        return '<p class="text-muted">No duration data available.</p>'

    stats = [
        ('Min', duration_distribution.get('min', 0)),
        ('P25', duration_distribution.get('p25', 0)),
        ('Median', duration_distribution.get('median', 0)),
        ('P75', duration_distribution.get('p75', 0)),
        ('P90', duration_distribution.get('p90', 0)),
        ('Max', duration_distribution.get('max', 0)),
    ]

    stat_items = []
    for label, value in stats:
        stat_items.append(f'''
        <div class="duration-stat">
            <div class="value">{value:.1f}m</div>
            <div class="label">{label}</div>
        </div>''')

    return f'''
    <div class="duration-stats">
        {''.join(stat_items)}
    </div>'''


def generate_duration_histogram_chart(duration_histogram: Dict[str, int]) -> str:
    """Generate CSS-based horizontal bar chart for duration histogram.

    Args:
        duration_histogram: Dict mapping bucket labels to counts
            e.g., {"<1min": 5, "1-5min": 10, ...}

    Returns:
        HTML string for the histogram visualization
    """
    if not duration_histogram:
        return '<p class="text-muted">No duration histogram data available.</p>'

    # Bucket order for display
    bucket_order = ["<1min", "1-5min", "5-15min", "15-30min", "30-60min", "60min+"]

    # Filter to buckets that exist in data
    buckets = [(b, duration_histogram.get(b, 0)) for b in bucket_order if b in duration_histogram]

    if not buckets:
        return '<p class="text-muted">No duration histogram data available.</p>'

    max_value = max(count for _, count in buckets) if buckets else 1

    # Color gradient from quick (blue) to long (orange/red)
    bucket_colors = {
        "<1min": "#58a6ff",    # Blue - quick lookups
        "1-5min": "#79c0ff",   # Light blue
        "5-15min": "#3fb950",  # Green - normal
        "15-30min": "#d29922", # Amber
        "30-60min": "#f78166", # Orange
        "60min+": "#f85149",   # Red - long running
    }

    bars = []
    for bucket, count in buckets:
        width_pct = (count / max_value) * 100 if max_value > 0 else 0
        color = bucket_colors.get(bucket, "#8b949e")

        bar = f'''
        <div class="bar-item">
            <span class="bar-label">{escape_html(bucket)}</span>
            <div class="bar-track">
                <div class="bar-fill" style="width: {width_pct}%; background: {color};">
                </div>
            </div>
            <span class="bar-value">{count}</span>
        </div>'''
        bars.append(bar)

    return f'''
    <div class="card-title">Duration Histogram</div>
    <div class="bar-chart">{"".join(bars)}</div>
    '''


def generate_time_series(by_date: Dict[str, Dict]) -> str:
    """Generate SVG sparkline for sessions over time."""
    if not by_date:
        return '<p class="text-muted">No time series data available.</p>'

    # Sort by date
    sorted_dates = sorted(by_date.items())

    if len(sorted_dates) < 2:
        return f'<p class="text-muted">Only {len(sorted_dates)} day(s) of data available.</p>'

    # Extract session counts
    values = [d[1].get('sessions', 0) for d in sorted_dates]
    max_val = max(values) if values else 1
    min_val = min(values) if values else 0

    # Normalize to 0-50 range for SVG
    width = 100
    height = 50
    points = []
    area_points = []

    for i, val in enumerate(values):
        x = (i / (len(values) - 1)) * width if len(values) > 1 else width / 2
        y = height - ((val - min_val) / (max_val - min_val) * height) if max_val > min_val else height / 2
        points.append(f'{x:.2f},{y:.2f}')
        area_points.append(f'{x:.2f},{y:.2f}')

    # Close the area path
    area_points.append(f'{width:.2f},{height:.2f}')
    area_points.append(f'0,{height:.2f}')

    # Date labels
    first_date = sorted_dates[0][0]
    last_date = sorted_dates[-1][0]

    return f'''
    <svg class="sparkline" viewBox="0 0 100 60" preserveAspectRatio="none">
        <defs>
            <linearGradient id="sparkline-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" style="stop-color: var(--accent-primary); stop-opacity: 0.3" />
                <stop offset="100%" style="stop-color: var(--accent-primary); stop-opacity: 0.05" />
            </linearGradient>
        </defs>
        <polygon class="area" points="{' '.join(area_points)}" />
        <polyline points="{' '.join(points)}" />
    </svg>
    <div class="distribution-labels">
        <span>{first_date}</span>
        <span>{len(sorted_dates)} days</span>
        <span>{last_date}</span>
    </div>'''


def expand_tilde(path: str) -> str:
    """Expand ~ to the full home directory path."""
    import os
    if path.startswith("~"):
        return os.path.expanduser(path)
    return path


def generate_sessions_detail_html(
    qualitative: Dict,
    report_sessions: Optional[List[Dict]] = None,
    max_per_category: int = 10,
    session_links: Optional[Dict[str, str]] = None
) -> str:
    """Generate HTML for the Session Details section.

    Args:
        qualitative: The qualitative_data.json data
        report_sessions: Optional list of sessions from report_data.json
        max_per_category: Maximum number of sessions to display per category
        session_links: Optional mapping of session_id -> relative HTML path

    Returns:
        HTML string for the sessions detail section
    """
    sessions_with_issues = qualitative.get('sessions_with_issues', [])
    successful_sessions = qualitative.get('successful_sessions', [])
    abandoned_sessions = qualitative.get('abandoned_sessions', [])
    # Use new name, fall back to old name for compatibility
    long_running_sessions = qualitative.get('long_running_sessions', qualitative.get('high_effort_sessions', []))

    def render_session_item(session: Dict, badge_class: str = None, badge_text: str = None) -> str:
        """Render a single session item.

        Args:
            session: Session data dictionary
            badge_class: Optional badge CSS class (overrides outcome-based badge)
            badge_text: Optional badge text (overrides outcome-based text)
        """
        session_id = session.get('session_id', '')
        session_id_short = session.get('session_id_short', session_id[:8] if session_id else '')
        session_file_path = session.get('session_file_path', '')
        project = session.get('project', 'unknown')
        date = session.get('date', '')
        duration = session.get('duration_minutes', 0)
        task_summary = session.get('task_summary', '')[:150]

        # Use actual outcome field to determine badge if not explicitly provided
        outcome = session.get('outcome', 'unclear')
        if not badge_class or not badge_text:
            # Map outcome values to badge classes and display text
            outcome_mapping = {
                'completed': ('success', 'Completed'),
                'completed_with_issues': ('warning', 'Completed with Issues'),
                'partially_completed': ('warning', 'Partial'),
                'exploration_complete': ('success', 'Exploration'),
                'lookup_complete': ('success', 'Lookup'),
                'abandoned': ('abandoned', 'Abandoned'),
                'blocked': ('error', 'Blocked'),
                'unclear': ('neutral', 'Unclear'),
            }
            badge_class, badge_text = outcome_mapping.get(outcome, ('neutral', outcome.replace('_', ' ').title()))

        # Check if we have a generated HTML page for this session
        html_link = None
        if session_links and session_id:
            html_link = session_links.get(session_id)

        if html_link:
            # Link to the generated session detail page
            link_html = f'<a href="{html_link}" class="session-link" title="View session details">{escape_html(session_id_short)}</a>'
        elif session_file_path:
            # Fallback to file:// link
            full_path = expand_tilde(session_file_path)
            link_html = f'<a href="file://{full_path}" class="session-link" title="{escape_html(session_file_path)}">{escape_html(session_id_short)}</a>'
        else:
            link_html = f'<code class="session-link">{escape_html(session_id_short)}</code>'

        summary_html = f'<div class="session-summary">{escape_html(task_summary)}...</div>' if task_summary else ''

        # Add confidence badge if available
        confidence = session.get('completion_confidence')
        confidence_html = ''
        if confidence is not None:
            conf_class = 'high' if confidence >= 70 else ('medium' if confidence >= 40 else 'low')
            confidence_html = f'<span class="confidence-badge {conf_class}" title="Completion confidence">{confidence}%</span>'

        return f'''
        <div class="session-item">
            {link_html}
            <div class="session-meta">
                <span class="session-badge {badge_class}">{badge_text}</span>
                {confidence_html}
                <span class="session-project">{escape_html(project)}</span>
                <span class="session-date">{escape_html(date)}</span>
                <span class="session-duration">{duration:.1f}m</span>
                {summary_html}
            </div>
        </div>'''

    def render_category_card(title: str, sessions: List[Dict]) -> str:
        """Render a card for a category of sessions.

        Badge class and text are now derived from each session's outcome field.
        """
        if not sessions:
            return ''

        total_count = len(sessions)
        displayed = sessions[:max_per_category]

        # Each session uses its own outcome for badge rendering
        items_html = ''.join(render_session_item(s) for s in displayed)

        count_html = ''
        if total_count > max_per_category:
            count_html = f'<div class="sessions-count">Showing {max_per_category} of {total_count} sessions</div>'

        return f'''
        <div class="card">
            <div class="card-title">{title} ({total_count})</div>
            {items_html}
            {count_html}
        </div>'''

    # Generate cards for each category (badges now auto-derived from outcome)
    issues_card = render_category_card(
        "Sessions with Issues",
        sessions_with_issues
    )

    success_card = render_category_card(
        "Successful Sessions",
        successful_sessions
    )

    long_running_card = render_category_card(
        "Long-Running Sessions (>60 min)",
        long_running_sessions
    )

    abandoned_card = render_category_card(
        "Abandoned/Blocked Sessions",
        abandoned_sessions
    )

    if not issues_card and not success_card and not long_running_card and not abandoned_card:
        return '<p class="text-muted">No session details available.</p>'

    return f'''
    <div class="two-col">
        {issues_card}
        {success_card}
    </div>
    <div class="two-col">
        {abandoned_card}
        {long_running_card}
    </div>
    '''


def generate_session_pages(
    report_data: Dict,
    output_dir: Path,
    back_link: str = "../analysis_report.html"
) -> Dict[str, str]:
    """Generate individual HTML pages for each session.

    Args:
        report_data: The report_data JSON containing sessions
        output_dir: Directory to write session pages to (e.g., reports/sessions/)
        back_link: Relative path back to the main report

    Returns:
        Mapping of session_id -> relative HTML path
    """
    import os

    sessions = report_data.get('sessions', [])
    if not sessions:
        print("No sessions found in report data")
        return {}

    # Create sessions directory
    sessions_dir = output_dir / 'sessions'
    sessions_dir.mkdir(parents=True, exist_ok=True)

    session_links = {}
    template = get_session_template()

    for session in sessions:
        session_id = session.get('session_id', '')
        if not session_id:
            continue

        session_id_short = session.get('session_id_short', session_id[:8])
        file_path = session.get('session_file_path', session.get('file_path', ''))

        # Skip if no file path
        if not file_path:
            continue

        # Expand tilde in path
        if file_path.startswith('~'):
            file_path = os.path.expanduser(file_path)

        # Read the JSONL file
        jsonl_data = []
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            jsonl_data.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except FileNotFoundError:
            print(f"Warning: Session file not found: {file_path}")
            continue
        except Exception as e:
            print(f"Warning: Error reading session file {file_path}: {e}")
            continue

        if not jsonl_data:
            continue

        # Extract metadata from session
        project_name = session.get('project', 'Unknown Project')
        duration_minutes = session.get('duration_minutes', 0)
        total_turns = session.get('total_turns', 0)
        tool_calls = session.get('tool_calls', 0)
        files_touched = session.get('files_touched', 0)
        git_branch = session.get('git_branch', '')

        # Format duration
        if duration_minutes >= 60:
            duration_str = f"{int(duration_minutes // 60)}h {int(duration_minutes % 60)}m"
        else:
            duration_str = f"{duration_minutes:.1f}m"

        # Get timestamp from first entry
        date_time = ''
        for entry in jsonl_data:
            if entry.get('timestamp'):
                try:
                    ts = entry['timestamp']
                    # Handle both ISO format and epoch milliseconds
                    if isinstance(ts, str):
                        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    else:
                        dt = datetime.fromtimestamp(ts / 1000)
                    date_time = dt.strftime('%b %d, %Y %I:%M %p')
                    break
                except:
                    pass

        # Token usage - try to extract from session or calculate
        input_tokens = session.get('input_tokens', 0)
        output_tokens = session.get('output_tokens', 0)
        if input_tokens or output_tokens:
            token_usage = f"{input_tokens // 1000}K in / {output_tokens // 1000}K out"
        else:
            token_usage = "N/A"

        # Git branch HTML
        git_branch_html = ''
        if git_branch:
            git_branch_html = f'''
            <span class="meta-divider">|</span>
            <div class="meta-item">
                <span class="label">Branch:</span>
                <span class="value">{escape_html(git_branch)}</span>
            </div>'''

        # Fill template
        try:
            html = template.format(
                session_id_short=escape_html(session_id_short),
                project_name=escape_html(project_name),
                back_link=back_link,
                date_time=escape_html(date_time) if date_time else 'N/A',
                duration=duration_str,
                total_turns=total_turns,
                token_usage=token_usage,
                tool_calls=tool_calls,
                files_touched=files_touched,
                git_branch_html=git_branch_html,
                jsonl_file_path=escape_html(session.get('session_file_path', session.get('file_path', ''))),
                session_data_json=json.dumps(jsonl_data)
            )
        except Exception as e:
            print(f"Warning: Error generating session page for {session_id_short}: {e}")
            continue

        # Write session page
        session_html_path = sessions_dir / f'session_{session_id_short}.html'
        with open(session_html_path, 'w') as f:
            f.write(html)

        # Store relative path for linking
        session_links[session_id] = f'sessions/session_{session_id_short}.html'

    print(f"Generated {len(session_links)} session detail pages in {sessions_dir}")
    return session_links


def _cos(degrees: float) -> float:
    """Cosine in degrees."""
    import math
    return math.cos(math.radians(degrees - 90))


def _sin(degrees: float) -> float:
    """Sine in degrees."""
    import math
    return math.sin(math.radians(degrees - 90))


def fill_template(
    aggregate: Dict,
    qualitative: Dict,
    report_metadata: Dict,
    partial: bool = True,
    sessions_detail_html: str = "",
    comparison: Dict = None
) -> str:
    """Fill the HTML template with quantitative data.

    Args:
        aggregate: The aggregate_report.json data
        qualitative: The qualitative_data.json data
        report_metadata: Metadata about the report period
        partial: If True, leave qualitative placeholders for Claude to fill
        sessions_detail_html: Pre-generated HTML for the sessions detail section
        comparison: Optional comparison data from report_data

    Returns:
        HTML string with quantitative data filled in
    """
    summary = aggregate.get('summary', {})
    averages = aggregate.get('averages', {})
    by_project = aggregate.get('by_project', {})
    by_task_type = aggregate.get('by_task_type', {})
    by_date = aggregate.get('by_date', {})
    tools_usage = aggregate.get('tools_usage', {})
    duration_distribution = aggregate.get('duration_distribution', {})
    claude_features = aggregate.get('claude_code_features', {})
    totals = claude_features.get('totals', {})
    activity_metrics = aggregate.get('activity_metrics', {})

    # Calculate derived values
    total_minutes = summary.get('total_duration_minutes', 0)
    total_hours = round(total_minutes / 60, 1)
    issue_rate = averages.get('issue_rate', 0)
    issue_rate_class = 'error' if issue_rate > 30 else ('warning' if issue_rate > 15 else '')

    # Compute outcome distribution for the stat card
    by_outcome = aggregate.get('by_outcome', {})
    outcome_completed_count = (
        by_outcome.get('completed', 0)
        + by_outcome.get('completed_with_issues', 0)
    )
    outcome_lookup_count = (
        by_outcome.get('lookup_complete', 0)
        + by_outcome.get('exploration_complete', 0)
    )
    outcome_unclear_count = by_outcome.get('unclear', 0)

    # Project badge
    project_filter = report_metadata.get('project_filter')
    project_badge = f'<span class="badge">Project: {escape_html(project_filter)}</span>' if project_filter else ''

    # Qualitative placeholders
    placeholder_text = '<p><em>Analysis pending...</em></p>' if partial else ''

    # Generate comparison section if available
    comparison_html = ''
    if comparison and comparison.get('has_comparison'):
        comparison_html = generate_comparison_section(comparison)

    # Generate chart HTML
    project_table_html = generate_project_table(by_project)
    tool_usage_chart_html = generate_tool_usage_chart(tools_usage)
    task_type_chart_html = generate_task_type_chart(by_task_type)
    task_type_bars_html = generate_task_type_bars(by_task_type)
    features_table_html = generate_features_table(claude_features)
    duration_chart_html = generate_duration_chart(duration_distribution)
    time_series_html = generate_time_series(by_date)

    # Duration histogram - show bucketed distribution if available
    duration_histogram = aggregate.get('duration_histogram', {})
    if duration_histogram:
        # Combine stats and histogram
        duration_chart_html = duration_chart_html + generate_duration_histogram_chart(duration_histogram)

    # Fill template
    html = HTML_TEMPLATE.format(
        # Header
        period=report_metadata.get('period', 'Custom'),
        start_date=report_metadata.get('start_date', 'N/A'),
        end_date=report_metadata.get('end_date', 'N/A'),
        project_badge=project_badge,

        # Executive Summary stats
        total_sessions=summary.get('total_sessions', 0),
        valid_sessions=summary.get('valid_sessions', 0),
        total_hours=total_hours,
        total_minutes=int(total_minutes),
        # Outcome distribution for stat card
        outcome_completed_count=outcome_completed_count,
        outcome_lookup_count=outcome_lookup_count,
        outcome_unclear_count=outcome_unclear_count,
        issue_rate=issue_rate,
        issue_rate_class=issue_rate_class,
        sessions_with_issues=aggregate.get('sessions_with_issues', 0),

        # Session Overview
        total_user_messages=summary.get('total_user_messages', 0),
        total_tool_calls=summary.get('total_tool_calls', 0),
        total_files_touched=summary.get('total_files_touched', 0),
        avg_duration=averages.get('avg_duration_minutes', 0),

        # Charts and tables
        project_table_html=project_table_html,
        tool_usage_chart_html=tool_usage_chart_html,
        task_type_chart_html=task_type_chart_html,
        task_type_bars_html=task_type_bars_html,
        features_table_html=features_table_html,
        duration_chart_html=duration_chart_html,
        time_series_html=time_series_html,

        # Comparison section
        comparison_html=comparison_html,

        # Claude Code features
        total_skills_invoked=totals.get('total_skills_invoked', 0),
        sessions_using_skills=totals.get('sessions_using_skills', 0),
        total_agents_spawned=totals.get('total_agents_spawned', 0),
        sessions_using_agents=totals.get('sessions_using_agents', 0),
        total_slash_commands=totals.get('total_slash_commands', 0),
        sessions_using_slash_commands=totals.get('sessions_using_slash_commands', 0),

        # Session details
        sessions_detail_html=sessions_detail_html or '<p class="text-muted">No session details available.</p>',

        # Qualitative placeholders
        key_findings_content=placeholder_text,
        root_cause_content=placeholder_text,
        success_patterns_content=placeholder_text,
        feature_effectiveness_content=placeholder_text,
        recommendations_content=placeholder_text,

        # Footer
        generation_timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    )

    return html


def extract_report_metadata(report_data_path: str) -> Dict:
    """Extract metadata from the report_data file."""
    with open(report_data_path, 'r') as f:
        data = json.load(f)

    metadata = data.get('report_metadata', {})
    return {
        'period': metadata.get('period', 'custom'),
        'start_date': metadata.get('start_date', 'N/A'),
        'end_date': metadata.get('end_date', 'N/A'),
        'project_filter': metadata.get('project_filter'),
        'total_projects': metadata.get('total_projects', 0),
    }


def main():
    parser = argparse.ArgumentParser(
        description='Generate HTML report from Claude Code usage analysis'
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
        default='analysis_report.html',
        help='Output HTML file path'
    )
    parser.add_argument(
        '--partial',
        action='store_true',
        default=True,
        help='Output partial HTML for Claude to complete (default: True)'
    )
    parser.add_argument(
        '--complete',
        action='store_true',
        help='Output complete HTML (skips Claude completion markers)'
    )

    args = parser.parse_args()

    # Load data
    print(f"Loading aggregate report from: {args.aggregate}")
    with open(args.aggregate, 'r') as f:
        aggregate = json.load(f)

    print(f"Loading qualitative data from: {args.qualitative}")
    with open(args.qualitative, 'r') as f:
        qualitative = json.load(f)

    print(f"Loading report metadata from: {args.report_data}")
    report_metadata = extract_report_metadata(args.report_data)

    # Load report_data for sessions and comparison data
    report_data = None
    report_sessions = None
    comparison_data = None
    try:
        with open(args.report_data, 'r') as f:
            report_data = json.load(f)
            report_sessions = report_data.get('sessions', [])
            comparison_data = report_data.get('comparison')
            if comparison_data and comparison_data.get('has_comparison'):
                print(f"Comparison data found: {comparison_data.get('previous_period', {}).get('start_date', 'N/A')} to {comparison_data.get('previous_period', {}).get('end_date', 'N/A')}")
    except Exception as e:
        print(f"Warning: Could not load sessions from report_data: {e}")

    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate individual session detail pages
    session_links = {}
    if report_data:
        print("Generating session detail pages...")
        # Calculate back link relative to sessions/ subdirectory
        back_link = f"../{output_path.name}"
        session_links = generate_session_pages(
            report_data,
            output_path.parent,
            back_link=back_link
        )

    # Generate sessions detail HTML with links to generated pages
    print("Generating session details section...")
    sessions_detail_html = generate_sessions_detail_html(
        qualitative,
        report_sessions,
        session_links=session_links
    )

    # Determine if partial or complete
    partial = not args.complete

    # Generate HTML
    print("Generating HTML report...")
    html = fill_template(
        aggregate,
        qualitative,
        report_metadata,
        partial=partial,
        sessions_detail_html=sessions_detail_html,
        comparison=comparison_data
    )

    # Save HTML
    with open(output_path, 'w') as f:
        f.write(html)

    print(f"HTML report saved to: {output_path}")

    if partial:
        print("\nPartial HTML generated with placeholders for qualitative sections.")
        print("Claude should now read the HTML file and qualitative_data.json,")
        print("then fill in the marked sections with analysis content.")


if __name__ == '__main__':
    main()
