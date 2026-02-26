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
