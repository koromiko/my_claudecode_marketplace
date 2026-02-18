# default-tools

Default tool auto-approval with sensitive-path guards and macOS permission/stop notification hooks.

## Hooks

### Auto-Approve (`PreToolUse`)

Conditionally auto-approves tools that need path/content guards beyond simple allow rules:

| Tool | Auto-approve when | Prompt when |
|------|-------------------|-------------|
| `Read` | Non-sensitive file path | Path matches `.ssh/`, `.aws/`, `.env`, `*secret*`, `*private_key*`, etc. |
| `Glob` | Non-sensitive path/pattern | Path or pattern matches sensitive patterns |
| `Grep` | Non-sensitive search path | Search path matches sensitive patterns |
| `WebFetch` | URL has no credential params | URL contains `token=`, `password=`, `secret=`, `api_key=` |
| `Bash` | Read-only command (git status, ls, etc.) with no shell metacharacters | Commands with `\|`, `;`, `&&`, `>`, `<` or non-allowlisted commands |

Unconditional allows (WebSearch, ToolSearch, MCP tools) are handled by native `permissions.allow` in settings.json.

### Permission Notification (`Notification`, matcher: `permission_prompt`)

When a permission prompt appears:
- Sends a macOS notification via `terminal-notifier`
- Speaks the notification via `say`
- Writes a session marker to `/tmp/` for the Stop hook

### Stop Notification (`Stop`)

When Claude finishes and a permission prompt occurred during the session:
- Sends a macOS completion notification
- Speaks the completion status
- Cleans up the session marker file

## Prerequisites

- **macOS** (uses `say` for speech)
- **jq** (JSON parsing in hook scripts)
- **terminal-notifier** (`brew install terminal-notifier`) for macOS notifications
- **iTerm2** (notifications activate iTerm2 window)
