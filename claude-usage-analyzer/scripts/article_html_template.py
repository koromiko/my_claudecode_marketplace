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
            content: "\u2192";
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
