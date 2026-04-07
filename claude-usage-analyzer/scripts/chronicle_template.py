#!/usr/bin/env python3
"""
HTML template for Claude Code session chronicle timeline pages.
Displays a visual timeline of tool calls, API turns, and user idle periods
for a single session. Follows the same pattern as html_template.py and
session_template.py.
"""


CHRONICLE_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chronicle: {session_id_short} - {project_name}</title>
    <style>
        :root {{
            /* Dark theme base palette */
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-card: #21262d;
            --bg-elevated: #30363d;

            /* Text */
            --text-primary: #e6edf3;
            --text-secondary: #8b949e;
            --text-muted: #6e7681;

            /* Accent */
            --accent-primary: #58a6ff;
            --accent-secondary: #79c0ff;

            /* Status */
            --success: #3fb950;
            --success-bg: rgba(63, 185, 80, 0.1);
            --warning: #d29922;
            --warning-bg: rgba(210, 153, 34, 0.1);
            --error: #f85149;
            --error-bg: rgba(248, 81, 73, 0.1);

            /* Borders */
            --border-default: #30363d;
            --border-muted: #21262d;

            /* Tool colors */
            --tool-read: #58a6ff;
            --tool-edit: #3fb950;
            --tool-write: #a371f7;
            --tool-bash: #d29922;
            --tool-grep: #f778ba;
            --tool-glob: #79c0ff;
            --tool-skill: #f0883e;
            --tool-agent: #56d364;
            --tool-mcp: #e3b341;
            --tool-web: #e3b341;
            --tool-other: #8b949e;

            /* Timeline-specific */
            --thinking: #58a6ff;
            --user-idle: #484f58;
            --slow-warning: #d29922;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI',
                         'Noto Sans', Helvetica, Arial, sans-serif;
            font-size: 14px;
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
        }}

        h1 {{ font-size: 1.5rem; font-weight: 600; letter-spacing: -0.025em; }}
        h2 {{ font-size: 1.125rem; font-weight: 600; letter-spacing: -0.02em; }}
        h3 {{ font-size: 1rem; font-weight: 600; }}

        code, pre {{
            font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
        }}

        /* ── Sticky header ─────────────────────────────────────────── */
        .header {{
            position: sticky;
            top: 0;
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-default);
            padding: 0.875rem 2rem;
            z-index: 100;
        }}

        .header-top {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 0.625rem;
        }}

        .back-link {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            color: var(--accent-primary);
            text-decoration: none;
            font-size: 0.875rem;
            padding: 0.375rem 0.75rem;
            border-radius: 6px;
            background: var(--bg-card);
            border: 1px solid var(--border-default);
            transition: background 0.15s, border-color 0.15s;
            white-space: nowrap;
        }}

        .back-link:hover {{
            background: var(--bg-elevated);
            border-color: var(--accent-primary);
        }}

        .session-title {{
            display: flex;
            flex-direction: column;
            gap: 0.2rem;
        }}

        .session-title h1 {{
            font-size: 1.125rem;
            color: var(--text-primary);
        }}

        .session-title .project {{
            font-size: 0.8125rem;
            color: var(--text-secondary);
        }}

        .meta-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 1.25rem;
            font-size: 0.8125rem;
            color: var(--text-secondary);
        }}

        .meta-item {{
            display: flex;
            align-items: center;
            gap: 0.375rem;
        }}

        .meta-item .label {{
            color: var(--text-muted);
        }}

        .meta-item .value {{
            color: var(--text-primary);
            font-weight: 500;
            font-variant-numeric: tabular-nums;
        }}

        .meta-divider {{
            color: var(--border-default);
        }}

        /* ── Legend bar ────────────────────────────────────────────── */
        .legend-bar {{
            background: var(--bg-card);
            border-bottom: 1px solid var(--border-muted);
            padding: 0.5rem 2rem;
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            align-items: center;
            font-size: 0.75rem;
            color: var(--text-secondary);
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            gap: 0.375rem;
        }}

        .legend-swatch {{
            width: 10px;
            height: 10px;
            border-radius: 2px;
            flex-shrink: 0;
        }}

        .legend-swatch.thinking   {{ background: var(--thinking); }}
        .legend-swatch.tool-read  {{ background: var(--tool-read); }}
        .legend-swatch.tool-edit  {{ background: var(--tool-edit); }}
        .legend-swatch.tool-write {{ background: var(--tool-write); }}
        .legend-swatch.tool-bash  {{ background: var(--tool-bash); }}
        .legend-swatch.tool-grep  {{ background: var(--tool-grep); }}
        .legend-swatch.tool-glob  {{ background: var(--tool-glob); }}
        .legend-swatch.tool-skill {{ background: var(--tool-skill); }}
        .legend-swatch.tool-agent {{ background: var(--tool-agent); }}
        .legend-swatch.tool-mcp   {{ background: var(--tool-mcp); }}
        .legend-swatch.user-idle  {{ background: var(--user-idle); }}

        /* ── Main layout ───────────────────────────────────────────── */
        .container {{
            max-width: 1100px;
            margin: 0 auto;
            padding: 2rem;
        }}

        /* ── Timeline container ────────────────────────────────────── */
        .timeline {{
            display: flex;
            flex-direction: column;
            gap: 0;
            position: relative;
        }}

        /* Timeline left-rail line */
        .timeline::before {{
            content: '';
            position: absolute;
            left: 80px;
            top: 0;
            bottom: 0;
            width: 2px;
            background: var(--border-default);
            z-index: 0;
        }}

        /* ── Timeline event ────────────────────────────────────────── */
        .timeline-event {{
            display: flex;
            align-items: flex-start;
            gap: 0;
            position: relative;
            padding: 0.25rem 0;
        }}

        /* Timestamp label (left of rail) */
        .timeline-event::before {{
            content: attr(data-time);
            display: block;
            width: 72px;
            min-width: 72px;
            text-align: right;
            font-size: 0.6875rem;
            color: var(--text-muted);
            font-variant-numeric: tabular-nums;
            padding-right: 0.75rem;
            padding-top: 0.4rem;
            flex-shrink: 0;
            line-height: 1.2;
        }}

        /* Dot on the rail */
        .timeline-event::after {{
            content: '';
            display: block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--border-default);
            border: 2px solid var(--bg-primary);
            position: absolute;
            left: 76px;
            top: 0.6rem;
            z-index: 1;
            flex-shrink: 0;
        }}

        .timeline-event.event-thinking::after   {{ background: var(--thinking); }}
        .timeline-event.event-tool-read::after  {{ background: var(--tool-read); }}
        .timeline-event.event-tool-edit::after  {{ background: var(--tool-edit); }}
        .timeline-event.event-tool-write::after {{ background: var(--tool-write); }}
        .timeline-event.event-tool-bash::after  {{ background: var(--tool-bash); }}
        .timeline-event.event-tool-grep::after  {{ background: var(--tool-grep); }}
        .timeline-event.event-tool-glob::after  {{ background: var(--tool-glob); }}
        .timeline-event.event-tool-skill::after {{ background: var(--tool-skill); }}
        .timeline-event.event-tool-agent::after {{ background: var(--tool-agent); }}
        .timeline-event.event-tool-mcp::after   {{ background: var(--tool-mcp); }}
        .timeline-event.event-user-idle::after  {{ background: var(--user-idle); }}
        .timeline-event.event-tool-other::after {{ background: var(--tool-other); }}

        /* Event body (right of rail) */
        .event-body {{
            margin-left: 20px;
            flex: 1;
            min-width: 0;
        }}

        /* ── Bar row (horizontal duration bar) ─────────────────────── */
        .bar-row {{
            display: flex;
            align-items: center;
            gap: 0.625rem;
            padding: 0.3rem 0.5rem;
            border-radius: 5px;
            transition: background 0.1s;
        }}

        .bar-row:hover {{
            background: var(--bg-card);
        }}

        .bar-name {{
            font-size: 0.8125rem;
            color: var(--text-primary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            min-width: 80px;
            max-width: 220px;
            flex-shrink: 0;
        }}

        .bar-track {{
            flex: 1;
            height: 8px;
            background: var(--bg-elevated);
            border-radius: 4px;
            overflow: hidden;
            min-width: 60px;
        }}

        .bar-fill {{
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s;
        }}

        .bar-fill.thinking   {{ background: var(--thinking); }}
        .bar-fill.tool-read  {{ background: var(--tool-read); }}
        .bar-fill.tool-edit  {{ background: var(--tool-edit); }}
        .bar-fill.tool-write {{ background: var(--tool-write); }}
        .bar-fill.tool-bash  {{ background: var(--tool-bash); }}
        .bar-fill.tool-grep  {{ background: var(--tool-grep); }}
        .bar-fill.tool-glob  {{ background: var(--tool-glob); }}
        .bar-fill.tool-skill {{ background: var(--tool-skill); }}
        .bar-fill.tool-agent {{ background: var(--tool-agent); }}
        .bar-fill.tool-mcp   {{ background: var(--tool-mcp); }}
        .bar-fill.user-idle  {{ background: var(--user-idle); }}
        .bar-fill.tool-other {{ background: var(--tool-other); }}

        .bar-duration {{
            font-size: 0.75rem;
            color: var(--text-muted);
            font-variant-numeric: tabular-nums;
            white-space: nowrap;
            min-width: 50px;
            text-align: right;
            flex-shrink: 0;
        }}

        .bar-duration.slow {{
            color: var(--slow-warning);
            font-weight: 600;
        }}

        /* ── Parallel group ─────────────────────────────────────────── */
        .parallel-group {{
            border-left: 3px solid var(--border-default);
            padding-left: 0.75rem;
            margin: 0.25rem 0;
            display: flex;
            flex-direction: column;
            gap: 0.15rem;
        }}

        .parallel-group-label {{
            font-size: 0.6875rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.25rem;
        }}

        /* ── Token info ─────────────────────────────────────────────── */
        .token-info {{
            display: inline-flex;
            align-items: center;
            gap: 0.375rem;
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-left: 0.25rem;
        }}

        .token-info .token-in  {{ color: var(--accent-primary); }}
        .token-info .token-out {{ color: var(--success); }}

        /* ── Event details (collapsible) ───────────────────────────── */
        .event-details {{
            display: none;
            margin-top: 0.375rem;
            margin-left: 0.5rem;
            padding: 0.625rem 0.75rem;
            background: var(--bg-card);
            border: 1px solid var(--border-muted);
            border-radius: 6px;
            font-size: 0.8125rem;
        }}

        .event-details.open {{
            display: block;
        }}

        .event-details pre {{
            font-size: 0.75rem;
            color: var(--text-secondary);
            white-space: pre-wrap;
            word-break: break-word;
            max-height: 250px;
            overflow-y: auto;
        }}

        .details-toggle {{
            background: none;
            border: none;
            color: var(--accent-primary);
            font-size: 0.75rem;
            cursor: pointer;
            padding: 0;
            margin-left: 0.5rem;
            text-decoration: underline;
        }}

        .details-toggle:hover {{
            color: var(--accent-secondary);
        }}

        /* ── Summary section ────────────────────────────────────────── */
        .summary-section {{
            margin-top: 3rem;
            padding-top: 2rem;
            border-top: 1px solid var(--border-default);
        }}

        .summary-section h2 {{
            margin-bottom: 1.25rem;
            color: var(--text-primary);
        }}

        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
            gap: 1rem;
        }}

        /* ── Summary card ───────────────────────────────────────────── */
        .summary-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-default);
            border-radius: 8px;
            padding: 1rem 1.125rem;
        }}

        .summary-card h3 {{
            font-size: 0.875rem;
            color: var(--text-secondary);
            margin-bottom: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}

        /* ── Breakdown bar (inside summary card) ───────────────────── */
        .breakdown-bar {{
            height: 10px;
            border-radius: 5px;
            overflow: hidden;
            display: flex;
            margin-bottom: 0.625rem;
        }}

        .breakdown-bar-segment {{
            height: 100%;
            transition: width 0.3s;
        }}

        .breakdown-legend {{
            display: flex;
            flex-direction: column;
            gap: 0.375rem;
        }}

        .breakdown-legend-item {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.8125rem;
        }}

        .breakdown-legend-swatch {{
            width: 10px;
            height: 10px;
            border-radius: 2px;
            flex-shrink: 0;
        }}

        .breakdown-legend-label {{
            flex: 1;
            color: var(--text-secondary);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .breakdown-legend-value {{
            color: var(--text-primary);
            font-variant-numeric: tabular-nums;
            font-size: 0.8125rem;
        }}

        /* ── Slowest ops list ───────────────────────────────────────── */
        .slow-ops-list {{
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }}

        .slow-ops-item {{
            display: flex;
            align-items: center;
            gap: 0.625rem;
            font-size: 0.8125rem;
        }}

        .slow-ops-rank {{
            font-size: 0.6875rem;
            color: var(--text-muted);
            width: 1.25rem;
            text-align: right;
            flex-shrink: 0;
        }}

        .slow-ops-name {{
            flex: 1;
            color: var(--text-secondary);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .slow-ops-duration {{
            color: var(--slow-warning);
            font-variant-numeric: tabular-nums;
            font-weight: 600;
            flex-shrink: 0;
        }}

        /* ── Feature list ────────────────────────────────────────────── */
        .feature-list {{
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }}

        .feature-item {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.8125rem;
        }}

        .feature-icon {{
            width: 18px;
            height: 18px;
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.6875rem;
            flex-shrink: 0;
            color: var(--bg-primary);
        }}

        .feature-label {{
            flex: 1;
            color: var(--text-secondary);
        }}

        .feature-count {{
            color: var(--text-primary);
            font-variant-numeric: tabular-nums;
        }}

        /* ── Footer ──────────────────────────────────────────────────── */
        .footer {{
            margin-top: 3rem;
            padding: 1.5rem;
            border-top: 1px solid var(--border-muted);
            text-align: center;
            color: var(--text-muted);
            font-size: 0.8125rem;
        }}

        /* ── Responsive ──────────────────────────────────────────────── */
        @media (max-width: 768px) {{
            .header {{
                padding: 0.875rem 1rem;
            }}
            .legend-bar {{
                padding: 0.5rem 1rem;
            }}
            .container {{
                padding: 1rem;
            }}
            .timeline::before {{
                left: 60px;
            }}
            .timeline-event::before {{
                width: 52px;
                min-width: 52px;
            }}
            .timeline-event::after {{
                left: 56px;
            }}
            .bar-name {{
                max-width: 120px;
            }}
        }}
    </style>
</head>
<body>

    <!-- Sticky header -->
    <header class="header">
        <div class="header-top">
            <a href="javascript:history.back()" class="back-link">&larr; Back</a>
            <div class="session-title">
                <h1>Chronicle: {session_id_short}</h1>
                <span class="project">{project_name}</span>
            </div>
        </div>
        <div class="meta-row">
            <div class="meta-item">
                <span class="label">Duration:</span>
                <span class="value">{total_duration}</span>
            </div>
            <span class="meta-divider">|</span>
            <div class="meta-item">
                <span class="label">Turns:</span>
                <span class="value">{total_turns}</span>
            </div>
            <span class="meta-divider">|</span>
            <div class="meta-item">
                <span class="label">Tool calls:</span>
                <span class="value">{total_tool_calls}</span>
            </div>
            <span class="meta-divider">|</span>
            <div class="meta-item">
                <span class="label">Input tokens:</span>
                <span class="value">{total_input_tokens}</span>
            </div>
            <span class="meta-divider">|</span>
            <div class="meta-item">
                <span class="label">Output tokens:</span>
                <span class="value">{total_output_tokens}</span>
            </div>
        </div>
    </header>

    <!-- Legend bar -->
    <div class="legend-bar">
        <span style="color: var(--text-muted); font-size: 0.6875rem; text-transform: uppercase; letter-spacing: 0.05em;">Legend:</span>
        <div class="legend-item"><div class="legend-swatch thinking"></div><span>API thinking</span></div>
        <div class="legend-item"><div class="legend-swatch tool-read"></div><span>Read</span></div>
        <div class="legend-item"><div class="legend-swatch tool-edit"></div><span>Edit</span></div>
        <div class="legend-item"><div class="legend-swatch tool-write"></div><span>Write</span></div>
        <div class="legend-item"><div class="legend-swatch tool-bash"></div><span>Bash</span></div>
        <div class="legend-item"><div class="legend-swatch tool-grep"></div><span>Grep</span></div>
        <div class="legend-item"><div class="legend-swatch tool-glob"></div><span>Glob</span></div>
        <div class="legend-item"><div class="legend-swatch tool-skill"></div><span>Skill</span></div>
        <div class="legend-item"><div class="legend-swatch tool-agent"></div><span>Agent</span></div>
        <div class="legend-item"><div class="legend-swatch tool-mcp"></div><span>MCP</span></div>
        <div class="legend-item"><div class="legend-swatch user-idle"></div><span>User idle</span></div>
    </div>

    <!-- Main content -->
    <main class="container">

        <!-- Timeline -->
        <div class="timeline" id="timeline">
            {timeline_html}
        </div>

        <!-- Summary section -->
        <div class="summary-section">
            <h2>Session Summary</h2>
            <div class="summary-grid">
                {time_breakdown_card}
                {token_breakdown_card}
                {slowest_ops_card}
                {features_card}
            </div>
        </div>

    </main>

    <footer class="footer">
        Session Chronicle &mdash; Claude Code Usage Analyzer
    </footer>

    <script>
        // Toggle collapsible event details
        function toggleDetails(btn) {{
            const details = btn.parentElement.querySelector('.event-details');
            if (!details) return;
            details.classList.toggle('open');
            btn.textContent = details.classList.contains('open') ? 'hide' : 'show';
        }}
    </script>

</body>
</html>
'''


def get_tool_color_var(tool_name: str) -> str:
    """Return the CSS variable name (without --) for a given tool name.

    Examples:
        get_tool_color_var('Read')   -> 'tool-read'
        get_tool_color_var('mcp__x') -> 'tool-mcp'
        get_tool_color_var('Unknown') -> 'tool-other'
    """
    if tool_name.startswith('mcp__'):
        return 'tool-mcp'

    mapping = {
        'Read': 'tool-read',
        'Edit': 'tool-edit',
        'Write': 'tool-write',
        'MultiEdit': 'tool-edit',
        'NotebookEdit': 'tool-write',
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
    }

    return mapping.get(tool_name, 'tool-other')
