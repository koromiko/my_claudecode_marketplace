# default-tools

Default tool auto-approval with sensitive-path guards and macOS permission/stop notification hooks.

## grill-me Skill

`skills/grill-me/` auto-triggers when you want a plan or design stress-tested
before building it — say "grill me", "stress-test this plan", or "poke holes in
this design", or it fires when a concrete plan is on the table pre-implementation.

It spawns a separate **read-only grill agent** (`agents/grill.md`) that
interrogates the plan one question at a time. The main agent answers each
question from the codebase and only escalates costly-to-reverse decisions
(schema/contract, public API, data migration, security boundary) to you. The
loop runs via `SendMessage` until the agent is satisfied or a 15-round safety
cap is reached, then the plan is revised with the resolved decisions.

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
| `Edit` / `Write` | File is inside the project directory and not a sensitive path | Outside project or sensitive path |
| `Agent` / others | Deferred to Ollama LLM evaluator | LLM returns deny or is unavailable |

Unconditional allows (WebSearch, ToolSearch, MCP tools) are handled by native `permissions.allow` in settings.json.

#### Ollama LLM Evaluator

For tool calls not resolved by the fast path, `ollama-evaluate.sh` sends the tool name and parameters to a local Ollama model for a binary allow/deny decision. Uses a DENY-first prompt so security rules take precedence.

- Default model: `gemma4:latest` (8B) — average ~1s per call, 100% on the test suite
- Falls through silently (no output) if Ollama is unavailable or returns deny
- Override with `OLLAMA_MODEL`, `OLLAMA_HOST`, `OLLAMA_TIMEOUT`

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

## Testing

```bash
bash tests/test-ollama-evaluator.sh
```

Runs 23 fixture cases (allow + deny) against the Ollama evaluator. Results written to `tests/results/`. Requires Ollama to be running; skips all cases if unavailable.

## Prerequisites

- **macOS** (uses `say` for speech)
- **jq** (JSON parsing in hook scripts)
- **terminal-notifier** (`brew install terminal-notifier`) for macOS notifications
- **iTerm2** (notifications activate iTerm2 window)
- **Ollama** (`brew install ollama`) with `gemma4:latest` (`ollama pull gemma4:latest`) for LLM-based evaluation
