#!/usr/bin/env python3
"""
HTML template for Claude Code session detail pages.
Displays individual session JSONL files with a threaded conversation view.
Shared styles extracted from html_template.py for consistency.
"""

SESSION_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Session: {session_id_short} - {project_name}</title>
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

            /* Tool colors */
            --tool-read: #58a6ff;
            --tool-edit: #3fb950;
            --tool-write: #a371f7;
            --tool-bash: #d29922;
            --tool-grep: #f778ba;
            --tool-glob: #79c0ff;
            --tool-task: #56d364;
            --tool-web: #e3b341;
            --tool-other: #8b949e;
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

        /* Type scale */
        h1 {{
            font-size: 1.5rem;
            font-weight: 600;
            letter-spacing: -0.025em;
        }}

        h2 {{
            font-size: 1.125rem;
            font-weight: 600;
            letter-spacing: -0.02em;
        }}

        h3 {{
            font-size: 1rem;
            font-weight: 600;
        }}

        /* Tabular numbers for data */
        .value, .meta-value {{
            font-variant-numeric: tabular-nums;
        }}

        code, pre {{
            font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
        }}

        /* Header - sticky */
        .header {{
            position: sticky;
            top: 0;
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-default);
            padding: 1rem 2rem;
            z-index: 100;
        }}

        .header-top {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 0.75rem;
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
        }}

        .back-link:hover {{
            background: var(--bg-elevated);
            border-color: var(--accent-primary);
        }}

        .session-title {{
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }}

        .session-title h1 {{
            font-size: 1.25rem;
            color: var(--text-primary);
        }}

        .session-title .project {{
            font-size: 0.875rem;
            color: var(--text-secondary);
        }}

        .meta-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 1.5rem;
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
        }}

        .meta-divider {{
            color: var(--border-default);
        }}

        /* Main content */
        .container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 2rem;
        }}

        /* Conversation turns */
        .conversation {{
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }}

        .turn {{
            background: var(--bg-card);
            border: 1px solid var(--border-default);
            border-radius: 8px;
            overflow: hidden;
        }}

        .turn-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.75rem 1rem;
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-muted);
        }}

        .turn-header .role {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-weight: 600;
            font-size: 0.875rem;
        }}

        .turn-header .role.user {{
            color: var(--accent-primary);
        }}

        .turn-header .role.assistant {{
            color: var(--success);
        }}

        .turn-header .timestamp {{
            font-size: 0.75rem;
            color: var(--text-muted);
            font-variant-numeric: tabular-nums;
        }}

        .turn-content {{
            padding: 1rem;
        }}

        .message-text {{
            white-space: pre-wrap;
            word-break: break-word;
            font-size: 0.875rem;
            line-height: 1.6;
            color: var(--text-primary);
        }}

        .message-text.truncated::after {{
            content: '...';
            color: var(--text-muted);
        }}

        /* Tool calls container */
        .tool-calls {{
            margin-top: 1rem;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }}

        .tool-call {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-muted);
            border-radius: 6px;
            overflow: hidden;
        }}

        .tool-call-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.5rem 0.75rem;
            cursor: pointer;
            transition: background 0.15s;
        }}

        .tool-call-header:hover {{
            background: var(--bg-elevated);
        }}

        .tool-call-summary {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.8125rem;
        }}

        .tool-call-summary .expand-icon {{
            color: var(--text-muted);
            transition: transform 0.2s;
            font-size: 0.75rem;
        }}

        .tool-call.expanded .expand-icon {{
            transform: rotate(90deg);
        }}

        .tool-name {{
            font-weight: 600;
            padding: 0.125rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
        }}

        /* Tool-specific colors */
        .tool-name.Read {{ background: var(--tool-read); color: var(--bg-primary); }}
        .tool-name.Edit {{ background: var(--tool-edit); color: var(--bg-primary); }}
        .tool-name.Write {{ background: var(--tool-write); color: var(--bg-primary); }}
        .tool-name.Bash {{ background: var(--tool-bash); color: var(--bg-primary); }}
        .tool-name.Grep {{ background: var(--tool-grep); color: var(--bg-primary); }}
        .tool-name.Glob {{ background: var(--tool-glob); color: var(--bg-primary); }}
        .tool-name.Task {{ background: var(--tool-task); color: var(--bg-primary); }}
        .tool-name.WebFetch, .tool-name.WebSearch {{ background: var(--tool-web); color: var(--bg-primary); }}
        .tool-name.default {{ background: var(--tool-other); color: var(--bg-primary); }}

        .tool-target {{
            color: var(--text-secondary);
            font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
            font-size: 0.75rem;
            max-width: 500px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .tool-call-details {{
            display: none;
            border-top: 1px solid var(--border-muted);
            padding: 0.75rem;
            background: var(--bg-primary);
        }}

        .tool-call.expanded .tool-call-details {{
            display: block;
        }}

        .tool-section {{
            margin-bottom: 0.75rem;
        }}

        .tool-section:last-child {{
            margin-bottom: 0;
        }}

        .tool-section-label {{
            font-size: 0.6875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            margin-bottom: 0.375rem;
        }}

        .tool-section-content {{
            background: var(--bg-secondary);
            border-radius: 4px;
            padding: 0.75rem;
            font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
            font-size: 0.75rem;
            white-space: pre-wrap;
            word-break: break-word;
            max-height: 300px;
            overflow-y: auto;
            color: var(--text-secondary);
        }}

        .tool-section-content.result {{
            max-height: 200px;
        }}

        .show-more-btn {{
            display: inline-block;
            margin-top: 0.5rem;
            padding: 0.25rem 0.5rem;
            font-size: 0.75rem;
            color: var(--accent-primary);
            background: transparent;
            border: 1px solid var(--border-default);
            border-radius: 4px;
            cursor: pointer;
            transition: background 0.15s;
        }}

        .show-more-btn:hover {{
            background: var(--bg-elevated);
        }}

        /* Summary/system messages */
        .system-message {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-muted);
            border-radius: 6px;
            padding: 0.75rem 1rem;
            font-size: 0.8125rem;
            color: var(--text-muted);
            font-style: italic;
        }}

        .system-message .label {{
            font-weight: 600;
            color: var(--text-secondary);
            margin-right: 0.5rem;
        }}

        /* Footer */
        .footer {{
            margin-top: 3rem;
            padding: 1.5rem;
            border-top: 1px solid var(--border-muted);
            text-align: center;
            color: var(--text-muted);
            font-size: 0.8125rem;
        }}

        .footer .file-path {{
            font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
            font-size: 0.75rem;
            color: var(--text-secondary);
            margin-top: 0.5rem;
            word-break: break-all;
        }}

        /* Responsive */
        @media (max-width: 768px) {{
            .header {{
                padding: 1rem;
            }}

            .container {{
                padding: 1rem;
            }}

            .meta-row {{
                gap: 1rem;
            }}

            .tool-target {{
                max-width: 200px;
            }}
        }}

        /* Print styles */
        @media print {{
            .header {{
                position: static;
                background: white;
                border-bottom: 1px solid #d0d7de;
            }}

            body {{
                background: white;
                color: #1f2328;
            }}

            .turn, .tool-call {{
                background: white;
                border: 1px solid #d0d7de;
            }}

            .tool-call-details {{
                display: block !important;
            }}
        }}
    </style>
</head>
<body>
    <header class="header">
        <div class="header-top">
            <a href="{back_link}" class="back-link">
                <span>&larr;</span> Back to Report
            </a>
            <div class="session-title">
                <h1>Session: {session_id_short}</h1>
                <span class="project">{project_name}</span>
            </div>
        </div>
        <div class="meta-row">
            <div class="meta-item">
                <span class="label">Date:</span>
                <span class="value">{date_time}</span>
            </div>
            <span class="meta-divider">|</span>
            <div class="meta-item">
                <span class="label">Duration:</span>
                <span class="value">{duration}</span>
            </div>
            <span class="meta-divider">|</span>
            <div class="meta-item">
                <span class="label">Turns:</span>
                <span class="value">{total_turns}</span>
            </div>
            <span class="meta-divider">|</span>
            <div class="meta-item">
                <span class="label">Tokens:</span>
                <span class="value">{token_usage}</span>
            </div>
            <span class="meta-divider">|</span>
            <div class="meta-item">
                <span class="label">Tool Calls:</span>
                <span class="value">{tool_calls}</span>
            </div>
            <span class="meta-divider">|</span>
            <div class="meta-item">
                <span class="label">Files:</span>
                <span class="value">{files_touched}</span>
            </div>
            {git_branch_html}
        </div>
    </header>

    <main class="container">
        <div class="conversation" id="conversation">
            <!-- Conversation will be rendered by JavaScript -->
            <noscript>
                <p>JavaScript is required to view the conversation.</p>
            </noscript>
        </div>
    </main>

    <footer class="footer">
        <p>Session Detail View - Claude Code Usage Analyzer</p>
        <div class="file-path">Source: {jsonl_file_path}</div>
    </footer>

    <script>
        // Session data embedded as JSON
        const sessionData = {session_data_json};

        // Tool target extraction logic
        function getToolTarget(toolName, input) {{
            if (!input) return '(no params)';

            switch (toolName) {{
                case 'Read':
                    return input.file_path || '(no path)';
                case 'Edit':
                    return input.file_path || '(no path)';
                case 'Write':
                    return input.file_path || '(no path)';
                case 'Grep':
                    return input.pattern || '(no pattern)';
                case 'Glob':
                    return input.pattern || '(no pattern)';
                case 'Bash':
                    const cmd = input.command || '';
                    return cmd.length > 50 ? cmd.substring(0, 50) + '...' : cmd;
                case 'Task':
                    const subagent = input.subagent_type || '';
                    const desc = input.description || '';
                    return subagent ? `${{subagent}}: ${{desc}}` : desc || '(no description)';
                case 'WebFetch':
                    return input.url || '(no url)';
                case 'WebSearch':
                    return input.query || '(no query)';
                case 'TodoWrite':
                    const todos = input.todos || [];
                    return `${{todos.length}} todo(s)`;
                case 'AskUserQuestion':
                    const questions = input.questions || [];
                    return `${{questions.length}} question(s)`;
                default:
                    // Return first parameter value
                    const keys = Object.keys(input);
                    if (keys.length > 0) {{
                        const val = input[keys[0]];
                        if (typeof val === 'string') {{
                            return val.length > 50 ? val.substring(0, 50) + '...' : val;
                        }}
                        return JSON.stringify(val).substring(0, 50);
                    }}
                    return '(no params)';
            }}
        }}

        // Get tool name CSS class
        function getToolClass(toolName) {{
            const knownTools = ['Read', 'Edit', 'Write', 'Bash', 'Grep', 'Glob', 'Task', 'WebFetch', 'WebSearch'];
            return knownTools.includes(toolName) ? toolName : 'default';
        }}

        // Escape HTML
        function escapeHtml(text) {{
            if (typeof text !== 'string') text = String(text);
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }}

        // Format JSON for display
        function formatJson(obj) {{
            try {{
                return JSON.stringify(obj, null, 2);
            }} catch (e) {{
                return String(obj);
            }}
        }}

        // Parse session data into structured turns
        function parseSessionData(data) {{
            const turns = [];
            let currentTurn = null;

            for (const entry of data) {{
                if (entry.type === 'user') {{
                    // Start a new user turn
                    if (currentTurn) {{
                        turns.push(currentTurn);
                    }}
                    currentTurn = {{
                        role: 'user',
                        timestamp: entry.timestamp,
                        message: entry.message?.content || '',
                        toolCalls: []
                    }};
                }} else if (entry.type === 'assistant') {{
                    // Add assistant response
                    if (currentTurn && currentTurn.role === 'user') {{
                        turns.push(currentTurn);
                    }}
                    currentTurn = {{
                        role: 'assistant',
                        timestamp: entry.timestamp,
                        message: '',
                        toolCalls: []
                    }};

                    // Parse message content
                    const message = entry.message;
                    if (message && message.content) {{
                        if (Array.isArray(message.content)) {{
                            for (const block of message.content) {{
                                if (block.type === 'text') {{
                                    currentTurn.message += block.text || '';
                                }} else if (block.type === 'tool_use') {{
                                    currentTurn.toolCalls.push({{
                                        id: block.id,
                                        name: block.name,
                                        input: block.input || {{}},
                                        result: null
                                    }});
                                }}
                            }}
                        }} else if (typeof message.content === 'string') {{
                            currentTurn.message = message.content;
                        }}
                    }}
                }} else if (entry.type === 'tool_result') {{
                    // Attach result to the corresponding tool call
                    if (currentTurn && currentTurn.toolCalls.length > 0) {{
                        const toolCallId = entry.tool_use_id;
                        const toolCall = currentTurn.toolCalls.find(tc => tc.id === toolCallId);
                        if (toolCall) {{
                            toolCall.result = entry.content || entry.result || '';
                        }}
                    }}
                }} else if (entry.type === 'summary') {{
                    // Add summary as a system message
                    if (currentTurn) {{
                        turns.push(currentTurn);
                    }}
                    turns.push({{
                        role: 'system',
                        type: 'summary',
                        message: entry.summary || 'Session summarized'
                    }});
                    currentTurn = null;
                }}
            }}

            // Push the last turn
            if (currentTurn) {{
                turns.push(currentTurn);
            }}

            return turns;
        }}

        // Format timestamp
        function formatTimestamp(ts) {{
            if (!ts) return '';
            try {{
                const date = new Date(ts);
                return date.toLocaleTimeString('en-US', {{
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                    hour12: true
                }});
            }} catch (e) {{
                return ts;
            }}
        }}

        // Render a tool call
        function renderToolCall(toolCall, index) {{
            const target = getToolTarget(toolCall.name, toolCall.input);
            const toolClass = getToolClass(toolCall.name);

            const inputJson = formatJson(toolCall.input);
            let resultContent = '';
            if (toolCall.result) {{
                if (typeof toolCall.result === 'string') {{
                    resultContent = toolCall.result;
                }} else if (Array.isArray(toolCall.result)) {{
                    resultContent = toolCall.result.map(r => {{
                        if (r.type === 'text') return r.text || '';
                        return formatJson(r);
                    }}).join('\\n');
                }} else {{
                    resultContent = formatJson(toolCall.result);
                }}
            }}

            // Truncate long results
            const maxResultLength = 5000;
            const truncatedResult = resultContent.length > maxResultLength
                ? resultContent.substring(0, maxResultLength) + '\\n... (truncated)'
                : resultContent;

            return `
                <div class="tool-call" data-index="${{index}}">
                    <div class="tool-call-header" onclick="toggleToolCall(this)">
                        <div class="tool-call-summary">
                            <span class="expand-icon">&#9654;</span>
                            <span class="tool-name ${{toolClass}}">${{escapeHtml(toolCall.name)}}</span>
                            <span class="tool-target">${{escapeHtml(target)}}</span>
                        </div>
                    </div>
                    <div class="tool-call-details">
                        <div class="tool-section">
                            <div class="tool-section-label">Input</div>
                            <pre class="tool-section-content">${{escapeHtml(inputJson)}}</pre>
                        </div>
                        ${{resultContent ? `
                        <div class="tool-section">
                            <div class="tool-section-label">Result</div>
                            <pre class="tool-section-content result">${{escapeHtml(truncatedResult)}}</pre>
                        </div>
                        ` : ''}}
                    </div>
                </div>
            `;
        }}

        // Render a conversation turn
        function renderTurn(turn, index) {{
            if (turn.role === 'system') {{
                return `
                    <div class="system-message">
                        <span class="label">${{turn.type === 'summary' ? 'Summary:' : 'System:'}}</span>
                        ${{escapeHtml(turn.message)}}
                    </div>
                `;
            }}

            const roleEmoji = turn.role === 'user' ? '&#128100;' : '&#129302;';
            const roleLabel = turn.role === 'user' ? 'User' : 'Assistant';
            const timestamp = formatTimestamp(turn.timestamp);

            // Truncate very long messages in display
            const maxMessageLength = 10000;
            let messageText = turn.message || '';
            const isTruncated = messageText.length > maxMessageLength;
            if (isTruncated) {{
                messageText = messageText.substring(0, maxMessageLength);
            }}

            const toolCallsHtml = turn.toolCalls && turn.toolCalls.length > 0
                ? `<div class="tool-calls">${{turn.toolCalls.map((tc, i) => renderToolCall(tc, i)).join('')}}</div>`
                : '';

            return `
                <div class="turn" data-turn="${{index}}">
                    <div class="turn-header">
                        <div class="role ${{turn.role}}">
                            <span>${{roleEmoji}}</span>
                            ${{roleLabel}}
                        </div>
                        <span class="timestamp">${{timestamp}}</span>
                    </div>
                    <div class="turn-content">
                        <div class="message-text${{isTruncated ? ' truncated' : ''}}">${{escapeHtml(messageText)}}</div>
                        ${{toolCallsHtml}}
                    </div>
                </div>
            `;
        }}

        // Toggle tool call expansion
        function toggleToolCall(header) {{
            const toolCall = header.closest('.tool-call');
            toolCall.classList.toggle('expanded');
        }}

        // Render the conversation
        function renderConversation() {{
            const container = document.getElementById('conversation');
            const turns = parseSessionData(sessionData);

            if (turns.length === 0) {{
                container.innerHTML = '<p class="system-message">No conversation data found in this session.</p>';
                return;
            }}

            container.innerHTML = turns.map((turn, i) => renderTurn(turn, i)).join('');
        }}

        // Initialize
        document.addEventListener('DOMContentLoaded', renderConversation);
    </script>
</body>
</html>
'''


def get_session_template() -> str:
    """Return the session detail HTML template."""
    return SESSION_TEMPLATE
