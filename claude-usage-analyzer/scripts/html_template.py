#!/usr/bin/env python3
"""
HTML template for Claude Code usage analysis reports.
Contains the complete HTML structure with CSS styling and placeholder markers.
Modernized with clean minimalist design, sticky TOC sidebar, and scroll progress.
"""

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Claude Code Usage Report: {period}</title>
    <style>
        :root {{
            /* Softer, more refined dark palette */
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-card: #21262d;
            --bg-elevated: #30363d;

            /* Text with better contrast */
            --text-primary: #e6edf3;
            --text-secondary: #8b949e;
            --text-muted: #6e7681;

            /* Cleaner accent colors */
            --accent-primary: #58a6ff;
            --accent-secondary: #79c0ff;

            /* Status colors (muted) */
            --success: #3fb950;
            --success-bg: rgba(63, 185, 80, 0.1);
            --warning: #d29922;
            --warning-bg: rgba(210, 153, 34, 0.1);
            --error: #f85149;
            --error-bg: rgba(248, 81, 73, 0.1);

            /* Borders */
            --border-default: #30363d;
            --border-muted: #21262d;

            /* Chart colors */
            --chart-1: #58a6ff;
            --chart-2: #3fb950;
            --chart-3: #a371f7;
            --chart-4: #f778ba;
            --chart-5: #d29922;
            --chart-6: #2ea043;
            --chart-7: #bf4b8a;
            --chart-8: #79c0ff;
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

        /* Type scale (major third - 1.25) */
        h1 {{
            font-size: 1.75rem;
            font-weight: 600;
            letter-spacing: -0.025em;
        }}

        h2 {{
            font-size: 1.25rem;
            font-weight: 600;
            letter-spacing: -0.02em;
        }}

        h3 {{
            font-size: 1.125rem;
            font-weight: 600;
        }}

        /* Tabular numbers for data */
        .value, .bar-value, td:nth-child(n+2) {{
            font-variant-numeric: tabular-nums;
        }}

        /* Scroll progress bar */
        .scroll-progress {{
            position: fixed;
            top: 0;
            left: 0;
            height: 2px;
            background: var(--accent-primary);
            width: 0%;
            z-index: 1000;
            transition: width 0.1s;
        }}

        /* Layout with sidebar */
        .layout {{
            display: flex;
            max-width: 1400px;
            margin: 0 auto;
        }}

        /* TOC Sidebar */
        .toc {{
            position: sticky;
            top: 1.5rem;
            width: 200px;
            height: fit-content;
            padding: 1rem;
            margin-right: 2rem;
            flex-shrink: 0;
            margin-top: 2rem;
        }}

        .toc-header {{
            font-size: 0.6875rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            margin-bottom: 1rem;
        }}

        .toc-list {{
            list-style: none;
            padding: 0;
        }}

        .toc-link {{
            display: block;
            padding: 0.375rem 0;
            color: var(--text-secondary);
            text-decoration: none;
            font-size: 0.8125rem;
            border-left: 2px solid transparent;
            padding-left: 0.75rem;
            transition: color 0.15s, border-color 0.15s;
        }}

        .toc-link:hover {{
            color: var(--text-primary);
        }}

        .toc-link.active {{
            color: var(--accent-primary);
            border-left-color: var(--accent-primary);
        }}

        /* Main container */
        .container {{
            flex: 1;
            max-width: 1000px;
            padding: 2rem;
            padding-left: 0;
        }}

        /* Header */
        .header {{
            text-align: left;
            margin-bottom: 3rem;
            padding-bottom: 2rem;
            border-bottom: 1px solid var(--border-default);
        }}

        .header h1 {{
            color: var(--text-primary);
            margin-bottom: 0.25rem;
        }}

        .header .period {{
            font-size: 0.875rem;
            color: var(--text-secondary);
        }}

        .header .badge {{
            display: inline-block;
            background: var(--bg-elevated);
            color: var(--accent-primary);
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            margin-top: 0.75rem;
            border: 1px solid var(--border-default);
        }}

        /* Section styling */
        .section {{
            margin-bottom: 3rem;
            padding-bottom: 2rem;
            border-bottom: 1px solid var(--border-muted);
        }}

        .section:last-of-type {{
            border-bottom: none;
        }}

        .section-title {{
            font-size: 1.125rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        /* Stat cards */
        .stat-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1rem;
            margin-bottom: 1.5rem;
        }}

        .stat-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-default);
            border-radius: 6px;
            padding: 1.25rem;
            transition: background 0.15s, border-color 0.15s;
        }}

        .stat-card:hover {{
            border-color: var(--border-muted);
            background: var(--bg-elevated);
        }}

        .stat-card .label {{
            font-size: 0.6875rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }}

        .stat-card .value {{
            font-size: 1.75rem;
            font-weight: 600;
            color: var(--text-primary);
            line-height: 1.2;
        }}

        .stat-card .subtext {{
            font-size: 0.8125rem;
            color: var(--text-muted);
            margin-top: 0.25rem;
        }}

        .stat-card.success .value {{
            color: var(--success);
        }}

        .stat-card.warning .value {{
            color: var(--warning);
        }}

        .stat-card.error .value {{
            color: var(--error);
        }}

        /* Card container */
        .card {{
            background: var(--bg-card);
            border: 1px solid var(--border-default);
            border-radius: 6px;
            padding: 1.5rem;
            margin-bottom: 1rem;
        }}

        .card-title {{
            font-size: 0.875rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: var(--text-primary);
        }}

        /* Comparison section */
        .comparison-card {{
            margin-top: 1.5rem;
        }}

        .comparison-subtitle {{
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-bottom: 1rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .comparison-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
        }}

        .comparison-item {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-default);
            border-radius: 6px;
            padding: 1rem;
        }}

        .comparison-label {{
            font-size: 0.6875rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }}

        .comparison-value {{
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 0.5rem;
        }}

        .comparison-delta {{
            font-size: 0.8125rem;
            display: flex;
            align-items: center;
            gap: 0.25rem;
        }}

        .comparison-delta.success {{
            color: var(--success);
        }}

        .comparison-delta.error {{
            color: var(--error);
        }}

        .comparison-delta.muted {{
            color: var(--text-muted);
        }}

        .trend-icon {{
            font-size: 1rem;
            font-weight: 600;
        }}

        /* Tables */
        .table-container {{
            overflow-x: auto;
            border-radius: 6px;
            border: 1px solid var(--border-default);
        }}

        table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            background: var(--bg-card);
        }}

        th {{
            font-size: 0.6875rem;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            padding: 0.75rem 1rem;
            text-align: left;
            border-bottom: 1px solid var(--border-default);
            background: transparent;
        }}

        td {{
            padding: 0.75rem 1rem;
            border-bottom: 1px solid var(--border-muted);
            font-size: 0.875rem;
        }}

        tr:last-child td {{
            border-bottom: none;
        }}

        /* Subtle zebra striping */
        tbody tr:nth-child(even) {{
            background: rgba(255, 255, 255, 0.02);
        }}

        /* Hover state */
        tbody tr:hover {{
            background: rgba(255, 255, 255, 0.04);
        }}

        /* Progress bars */
        .progress-bar {{
            height: 6px;
            background: var(--bg-secondary);
            border-radius: 3px;
            overflow: hidden;
            margin-top: 0.25rem;
        }}

        .progress-bar .fill {{
            height: 100%;
            border-radius: 3px;
            transition: width 0.3s ease;
        }}

        .progress-bar .fill.success {{
            background: var(--success);
        }}

        .progress-bar .fill.error {{
            background: var(--error);
        }}

        .progress-bar .fill.primary {{
            background: var(--accent-primary);
        }}

        /* Bar chart (CSS-based) */
        .bar-chart {{
            display: flex;
            flex-direction: column;
            gap: 0.625rem;
        }}

        .bar-item {{
            display: flex;
            align-items: center;
            gap: 1rem;
        }}

        .bar-label {{
            width: 140px;
            font-size: 0.8125rem;
            color: var(--text-secondary);
            flex-shrink: 0;
            text-overflow: ellipsis;
            overflow: hidden;
            white-space: nowrap;
        }}

        .bar-track {{
            flex: 1;
            height: 8px;
            background: var(--bg-secondary);
            border-radius: 4px;
            overflow: hidden;
        }}

        .bar-fill {{
            height: 100%;
            border-radius: 4px;
            transition: width 0.5s ease;
        }}

        .bar-value {{
            width: 50px;
            text-align: right;
            font-size: 0.8125rem;
            color: var(--text-primary);
            font-weight: 500;
            flex-shrink: 0;
        }}

        /* Distribution chart */
        .distribution-chart {{
            display: flex;
            align-items: flex-end;
            gap: 3px;
            height: 80px;
            padding: 1rem 0;
        }}

        .distribution-bar {{
            flex: 1;
            background: var(--accent-primary);
            border-radius: 3px 3px 0 0;
            min-width: 16px;
            transition: height 0.3s ease;
            opacity: 0.8;
        }}

        .distribution-bar:hover {{
            opacity: 1;
        }}

        .distribution-labels {{
            display: flex;
            justify-content: space-between;
            font-size: 0.6875rem;
            color: var(--text-muted);
            margin-top: 0.5rem;
        }}

        /* Donut/Pie chart container */
        .pie-chart-container {{
            display: flex;
            align-items: center;
            gap: 2rem;
            flex-wrap: wrap;
        }}

        .pie-chart {{
            width: 180px;
            height: 180px;
            position: relative;
        }}

        .pie-center-text {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            text-align: center;
        }}

        .pie-center-text .value {{
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--text-primary);
            display: block;
        }}

        .pie-center-text .label {{
            font-size: 0.6875rem;
            color: var(--text-muted);
            text-transform: uppercase;
        }}

        .pie-legend {{
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.8125rem;
            color: var(--text-secondary);
        }}

        .legend-color {{
            width: 10px;
            height: 10px;
            border-radius: 2px;
            flex-shrink: 0;
        }}

        /* Qualitative sections */
        .qualitative-content {{
            background: var(--bg-secondary);
            border-radius: 6px;
            padding: 1.5rem;
            border: 1px solid var(--border-muted);
        }}

        .qualitative-content h4 {{
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-top: 1.5rem;
            margin-bottom: 0.75rem;
        }}

        .qualitative-content h4:first-child {{
            margin-top: 0;
        }}

        .qualitative-content ul {{
            list-style: none;
            padding: 0;
        }}

        .qualitative-content li {{
            padding: 0.5rem 0;
            padding-left: 1rem;
            position: relative;
            color: var(--text-secondary);
            font-size: 0.875rem;
        }}

        .qualitative-content li::before {{
            content: '•';
            position: absolute;
            left: 0;
            color: var(--text-muted);
        }}

        .qualitative-content p {{
            margin-bottom: 0.75rem;
            color: var(--text-secondary);
            font-size: 0.875rem;
        }}

        .qualitative-content strong {{
            color: var(--text-primary);
        }}

        /* Recommendation cards */
        .recommendation {{
            background: var(--bg-card);
            border-radius: 6px;
            padding: 1rem 1.25rem;
            margin-bottom: 0.75rem;
            border-left: 3px solid var(--success);
            display: flex;
            align-items: flex-start;
            gap: 1rem;
        }}

        .recommendation.warning {{
            border-left-color: var(--warning);
        }}

        .recommendation .number {{
            background: var(--success);
            color: var(--bg-primary);
            width: 20px;
            height: 20px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            font-size: 0.75rem;
            flex-shrink: 0;
        }}

        .recommendation.warning .number {{
            background: var(--warning);
        }}

        /* Two column layout */
        .two-col {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 1rem;
        }}

        /* Feature badges */
        .feature-badge {{
            display: inline-flex;
            align-items: center;
            gap: 0.375rem;
            background: var(--bg-secondary);
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            margin: 0.25rem;
            border: 1px solid var(--border-default);
            color: var(--text-secondary);
        }}

        .feature-badge .count {{
            background: var(--accent-primary);
            color: var(--bg-primary);
            padding: 0.125rem 0.375rem;
            border-radius: 9999px;
            font-weight: 600;
            font-size: 0.6875rem;
        }}

        /* Session links */
        .session-link {{
            font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
            font-size: 0.75rem;
            color: var(--accent-primary);
            text-decoration: none;
            padding: 0.125rem 0.375rem;
            background: var(--bg-secondary);
            border-radius: 4px;
            border: 1px solid var(--border-default);
            transition: background 0.15s, border-color 0.15s;
        }}

        .session-link:hover {{
            background: var(--bg-elevated);
            border-color: var(--accent-primary);
        }}

        .session-item {{
            display: flex;
            align-items: flex-start;
            gap: 1rem;
            padding: 0.75rem 1rem;
            border-bottom: 1px solid var(--border-muted);
        }}

        .session-item:last-child {{
            border-bottom: none;
        }}

        .session-item:hover {{
            background: rgba(255, 255, 255, 0.02);
        }}

        .session-meta {{
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 0.5rem;
            flex: 1;
        }}

        .session-badge {{
            font-size: 0.6875rem;
            font-weight: 500;
            padding: 0.125rem 0.5rem;
            border-radius: 9999px;
            text-transform: uppercase;
            letter-spacing: 0.025em;
        }}

        .session-badge.issue {{
            background: var(--error-bg);
            color: var(--error);
        }}

        .session-badge.success {{
            background: var(--success-bg);
            color: var(--success);
        }}

        .session-badge.warning {{
            background: var(--warning-bg);
            color: var(--warning);
        }}

        .session-badge.neutral {{
            background: rgba(139, 148, 158, 0.15);
            color: #8b949e;
        }}

        .session-badge.long-running {{
            background: var(--warning-bg);
            color: var(--warning);
        }}

        /* Alias for backward compatibility */
        .session-badge.high-effort {{
            background: var(--warning-bg);
            color: var(--warning);
        }}

        .session-badge.abandoned {{
            background: rgba(139, 148, 158, 0.15);
            color: #8b949e;
        }}

        .session-badge.blocked {{
            background: rgba(163, 113, 247, 0.15);
            color: #a371f7;
        }}

        .session-badge.exploration {{
            background: rgba(88, 166, 255, 0.15);
            color: #58a6ff;
        }}

        .session-badge.partial {{
            background: rgba(210, 153, 34, 0.15);
            color: #d29922;
        }}

        .session-badge.completed {{
            background: var(--success-bg);
            color: var(--success);
        }}

        .session-badge.completed_with_issues {{
            background: rgba(210, 153, 34, 0.15);
            color: #d29922;
        }}

        .session-badge.exploration_complete {{
            background: rgba(88, 166, 255, 0.15);
            color: #58a6ff;
        }}

        .session-badge.partially_completed {{
            background: rgba(210, 153, 34, 0.15);
            color: #d29922;
        }}

        .session-badge.unclear {{
            background: rgba(139, 148, 158, 0.15);
            color: #8b949e;
        }}

        /* Confidence badges */
        .confidence-badge {{
            font-size: 0.625rem;
            font-weight: 600;
            padding: 0.125rem 0.375rem;
            border-radius: 4px;
            margin-left: 0.25rem;
        }}

        .confidence-badge.high {{
            background: var(--success-bg);
            color: var(--success);
        }}

        .confidence-badge.medium {{
            background: var(--warning-bg);
            color: var(--warning);
        }}

        .confidence-badge.low {{
            background: var(--error-bg);
            color: var(--error);
        }}

        .session-project {{
            font-size: 0.8125rem;
            color: var(--text-secondary);
        }}

        .session-date {{
            font-size: 0.75rem;
            color: var(--text-muted);
        }}

        .session-duration {{
            font-size: 0.75rem;
            color: var(--text-muted);
        }}

        .session-summary {{
            font-size: 0.8125rem;
            color: var(--text-secondary);
            margin-top: 0.25rem;
            line-height: 1.4;
        }}

        .sessions-count {{
            font-size: 0.8125rem;
            color: var(--text-muted);
            padding: 0.5rem 1rem;
            border-top: 1px solid var(--border-muted);
        }}

        /* Time series sparkline */
        .sparkline {{
            width: 100%;
            height: 60px;
        }}

        .sparkline polyline {{
            fill: none;
            stroke: var(--accent-primary);
            stroke-width: 2;
        }}

        .sparkline .area {{
            fill: url(#sparkline-gradient);
            stroke: none;
        }}

        /* Duration stats */
        .duration-stats {{
            display: flex;
            gap: 2rem;
            flex-wrap: wrap;
            justify-content: center;
            padding: 1rem 0;
        }}

        .duration-stat {{
            text-align: center;
        }}

        .duration-stat .value {{
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--accent-secondary);
        }}

        .duration-stat .label {{
            font-size: 0.6875rem;
            color: var(--text-muted);
            text-transform: uppercase;
        }}

        /* Footer */
        .footer {{
            text-align: center;
            padding: 2rem 0;
            margin-top: 2rem;
            border-top: 1px solid var(--border-muted);
            color: var(--text-muted);
            font-size: 0.8125rem;
        }}

        .footer p {{
            margin: 0.25rem 0;
        }}

        /* Responsive */
        @media (max-width: 900px) {{
            .toc {{
                display: none;
            }}

            .layout {{
                display: block;
            }}

            .container {{
                max-width: 100%;
                padding: 1.5rem;
            }}
        }}

        @media (max-width: 600px) {{
            .container {{
                padding: 1rem;
            }}

            .header h1 {{
                font-size: 1.375rem;
            }}

            .stat-card .value {{
                font-size: 1.5rem;
            }}

            .two-col {{
                grid-template-columns: 1fr;
            }}

            .bar-label {{
                width: 100px;
            }}

            .pie-chart-container {{
                flex-direction: column;
                align-items: flex-start;
            }}
        }}

        /* Print styles */
        @media print {{
            .toc, .scroll-progress {{
                display: none;
            }}

            body {{
                background: white;
                color: #1f2328;
                font-size: 11pt;
            }}

            .layout {{
                display: block;
            }}

            .container {{
                max-width: 100%;
                padding: 0;
            }}

            .card, .stat-card, .table-container {{
                background: white;
                border: 1px solid #d0d7de;
                break-inside: avoid;
            }}

            .qualitative-content {{
                background: #f6f8fa;
                border: 1px solid #d0d7de;
            }}

            .section {{
                break-before: avoid;
            }}

            .header {{
                break-after: avoid;
            }}

            .stat-card .value,
            .stat-card.success .value,
            .stat-card.warning .value,
            .stat-card.error .value {{
                color: #1f2328;
            }}

            .bar-fill {{
                print-color-adjust: exact;
                -webkit-print-color-adjust: exact;
            }}
        }}
    </style>
</head>
<body>
    <!-- Scroll progress bar -->
    <div class="scroll-progress" id="scroll-progress"></div>

    <div class="layout">
        <!-- Sticky TOC sidebar -->
        <aside class="toc" id="toc">
            <nav>
                <div class="toc-header">Contents</div>
                <ul class="toc-list">
                    <li><a href="#executive-summary" class="toc-link">Executive Summary</a></li>
                    <li><a href="#session-overview" class="toc-link">Session Overview</a></li>
                    <li><a href="#by-project" class="toc-link">By Project</a></li>
                    <li><a href="#task-distribution" class="toc-link">Task Distribution</a></li>
                    <li><a href="#tool-usage" class="toc-link">Tool Usage</a></li>
                    <li><a href="#features" class="toc-link">Claude Code Features</a></li>
                    <li><a href="#sessions-detail" class="toc-link">Session Details</a></li>
                    <li><a href="#analysis" class="toc-link">Qualitative Analysis</a></li>
                    <li><a href="#recommendations" class="toc-link">Recommendations</a></li>
                </ul>
            </nav>
        </aside>

        <!-- Main content -->
        <main class="container">
            <header class="header">
                <h1>Claude Code Usage Report</h1>
                <p class="period">{start_date} to {end_date}</p>
                {project_badge}
            </header>

            <!-- Executive Summary -->
            <section class="section" id="executive-summary">
                <h2 class="section-title">Executive Summary</h2>

                <div class="stat-grid">
                    <div class="stat-card">
                        <div class="label">Total Sessions</div>
                        <div class="value">{total_sessions}</div>
                        <div class="subtext">{valid_sessions} valid</div>
                    </div>
                    <div class="stat-card">
                        <div class="label">Total Time</div>
                        <div class="value">{total_hours}h</div>
                        <div class="subtext">{total_minutes} minutes</div>
                    </div>
                    <div class="stat-card">
                        <div class="label">Session Outcomes</div>
                        <div class="value">{outcome_completed_count}</div>
                        <div class="subtext">{outcome_lookup_count} lookups, {outcome_unclear_count} unclear</div>
                    </div>
                    <div class="stat-card {issue_rate_class}">
                        <div class="label">Issue Rate</div>
                        <div class="value">{issue_rate}%</div>
                        <div class="subtext">{sessions_with_issues} with issues</div>
                    </div>
                </div>

                <div class="card">
                    <div class="card-title">Key Findings</div>
                    <div class="qualitative-content">
                        <!-- CLAUDE_QUALITATIVE key_findings -->
                        {key_findings_content}
                        <!-- /CLAUDE_QUALITATIVE -->
                    </div>
                </div>

                <!-- Period Comparison (if available) -->
                {comparison_html}
            </section>

            <!-- Session Overview -->
            <section class="section" id="session-overview">
                <h2 class="section-title">Session Overview</h2>

                <div class="two-col">
                    <div class="card">
                        <div class="card-title">Activity Totals</div>
                        <div class="stat-grid">
                            <div class="stat-card">
                                <div class="label">User Messages</div>
                                <div class="value">{total_user_messages}</div>
                            </div>
                            <div class="stat-card">
                                <div class="label">Tool Calls</div>
                                <div class="value">{total_tool_calls}</div>
                            </div>
                            <div class="stat-card">
                                <div class="label">Files Touched</div>
                                <div class="value">{total_files_touched}</div>
                            </div>
                            <div class="stat-card">
                                <div class="label">Avg Duration</div>
                                <div class="value">{avg_duration}m</div>
                            </div>
                        </div>
                    </div>

                    <div class="card">
                        <div class="card-title">Duration Distribution</div>
                        {duration_chart_html}
                    </div>
                </div>

                <div class="card">
                    <div class="card-title">Sessions Over Time</div>
                    {time_series_html}
                </div>
            </section>

            <!-- By Project -->
            <section class="section" id="by-project">
                <h2 class="section-title">By Project</h2>
                {project_table_html}
            </section>

            <!-- Task Type Distribution -->
            <section class="section" id="task-distribution">
                <h2 class="section-title">Task Type Distribution</h2>
                <div class="two-col">
                    <div class="card">
                        {task_type_chart_html}
                    </div>
                    <div class="card">
                        <div class="card-title">Task Type Breakdown</div>
                        {task_type_bars_html}
                    </div>
                </div>
            </section>

            <!-- Tool Usage -->
            <section class="section" id="tool-usage">
                <h2 class="section-title">Tool Usage</h2>
                <div class="card">
                    <div class="card-title">Top 15 Tools</div>
                    {tool_usage_chart_html}
                </div>
            </section>

            <!-- Claude Code Features -->
            <section class="section" id="features">
                <h2 class="section-title">Claude Code Features</h2>
                <div class="stat-grid">
                    <div class="stat-card">
                        <div class="label">Skills Invoked</div>
                        <div class="value">{total_skills_invoked}</div>
                        <div class="subtext">in {sessions_using_skills} sessions</div>
                    </div>
                    <div class="stat-card">
                        <div class="label">Agents Spawned</div>
                        <div class="value">{total_agents_spawned}</div>
                        <div class="subtext">in {sessions_using_agents} sessions</div>
                    </div>
                    <div class="stat-card">
                        <div class="label">Slash Commands</div>
                        <div class="value">{total_slash_commands}</div>
                        <div class="subtext">in {sessions_using_slash_commands} sessions</div>
                    </div>
                </div>
                {features_table_html}
            </section>

            <!-- Session Details -->
            <section class="section" id="sessions-detail">
                <h2 class="section-title">Session Details</h2>
                {sessions_detail_html}
            </section>

            <!-- Qualitative Analysis -->
            <section class="section" id="analysis">
                <h2 class="section-title">Qualitative Analysis</h2>

                <div class="card">
                    <div class="card-title">Root Cause Analysis</div>
                    <div class="qualitative-content">
                        <!-- CLAUDE_QUALITATIVE root_cause -->
                        {root_cause_content}
                        <!-- /CLAUDE_QUALITATIVE -->
                    </div>
                </div>

                <div class="card">
                    <div class="card-title">Success Patterns</div>
                    <div class="qualitative-content">
                        <!-- CLAUDE_QUALITATIVE success_patterns -->
                        {success_patterns_content}
                        <!-- /CLAUDE_QUALITATIVE -->
                    </div>
                </div>

                <div class="card">
                    <div class="card-title">Claude Code Feature Effectiveness</div>
                    <div class="qualitative-content">
                        <!-- CLAUDE_QUALITATIVE feature_effectiveness -->
                        {feature_effectiveness_content}
                        <!-- /CLAUDE_QUALITATIVE -->
                    </div>
                </div>
            </section>

            <!-- Recommendations -->
            <section class="section" id="recommendations">
                <h2 class="section-title">Recommendations</h2>
                <div class="qualitative-content">
                    <!-- CLAUDE_QUALITATIVE recommendations -->
                    {recommendations_content}
                    <!-- /CLAUDE_QUALITATIVE -->
                </div>
            </section>

            <footer class="footer">
                <p>Generated by Claude Code Usage Analyzer</p>
                <p>Report generated: {generation_timestamp}</p>
            </footer>
        </main>
    </div>

    <script>
        // Scroll progress and active TOC link highlighting
        document.addEventListener('DOMContentLoaded', function() {{
            const sections = document.querySelectorAll('section[id]');
            const tocLinks = document.querySelectorAll('.toc-link');
            const progressBar = document.getElementById('scroll-progress');

            function updateScrollProgress() {{
                const scrollTop = window.scrollY;
                const docHeight = document.documentElement.scrollHeight - window.innerHeight;
                const progress = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
                progressBar.style.width = progress + '%';

                // Update active TOC link
                let current = '';
                sections.forEach(function(section) {{
                    const sectionTop = section.offsetTop - 100;
                    if (scrollTop >= sectionTop) {{
                        current = section.getAttribute('id');
                    }}
                }});

                tocLinks.forEach(function(link) {{
                    link.classList.remove('active');
                    if (link.getAttribute('href') === '#' + current) {{
                        link.classList.add('active');
                    }}
                }});
            }}

            window.addEventListener('scroll', updateScrollProgress);
            updateScrollProgress(); // Initial call
        }});
    </script>
</body>
</html>
'''

# Chart color palette (muted, refined)
CHART_COLORS = [
    '#58a6ff',  # Blue
    '#3fb950',  # Green
    '#a371f7',  # Purple
    '#f778ba',  # Pink
    '#d29922',  # Amber
    '#2ea043',  # Dark Green
    '#bf4b8a',  # Magenta
    '#79c0ff',  # Light Blue
    '#56d364',  # Light Green
    '#db61a2',  # Rose
    '#e3b341',  # Gold
    '#388bfd',  # Royal Blue
    '#8b949e',  # Gray
    '#f78166',  # Coral
    '#7ee787',  # Mint
]


def get_chart_color(index: int) -> str:
    """Get a chart color by index, cycling through the palette."""
    return CHART_COLORS[index % len(CHART_COLORS)]
