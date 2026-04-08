# Ollama-Powered PreToolUse Auto-Approval

**Date**: 2026-04-09
**Plugin**: default-tools
**Status**: Design approved

## Summary

Add an Ollama-based LLM evaluator as a fallback in the `default-tools` PreToolUse hook. The existing hard-coded fast path handles obvious cases (read-only tools, bash allowlist). Tool calls that would otherwise fall through to a permission prompt are routed to a local Qwen3:0.6b model for a binary allow/deny decision.

## Architecture

```
Tool call arrives
    │
    ├─ Sensitive path? ──────────► fall through to permission prompt
    │
    ├─ Read/Glob/Grep (non-sensitive)? ──► ALLOW (existing fast path)
    ├─ WebFetch (no creds in URL)? ──────► ALLOW (existing fast path)
    ├─ Bash (read-only allowlist)? ──────► ALLOW (existing fast path)
    │
    ├─ Edit/Write outside git root? ────► fall through to permission prompt
    ├─ Edit/Write on sensitive path? ───► fall through to permission prompt
    │
    └─ Everything else ──► ollama-evaluate.sh
                                │
                                ├─ Ollama responds "allow" ──► ALLOW
                                ├─ Ollama responds "deny" ───► fall through
                                └─ Ollama error/timeout ────► fall through
```

### Decision: Hard-coded fast path + LLM fallback

The existing fast-path logic is reliable and sub-millisecond. The LLM handles nuanced cases the bash script can't: Edit/Write within project scope, settings updates, Agent tool calls, etc.

## Components

### 1. `hooks/ollama-evaluate.sh` (new)

Standalone script called by `auto-approve.sh` for unhandled tool calls.

**Input**: Hook JSON on stdin (`{"tool_name": "...", "tool_input": {...}}`)

**Configuration** (environment variables with defaults):
- `OLLAMA_MODEL` — default `qwen3:0.6b`
- `OLLAMA_HOST` — default `http://localhost:11434`
- `OLLAMA_TIMEOUT` — default `4` (seconds; leaves ~1s for the rest of the hook)

**Ollama API call**:
```json
{
  "model": "qwen3:0.6b",
  "prompt": "<system prompt>\n\nEvaluate this tool use request:\n<tool JSON>",
  "stream": false,
  "think": false,
  "format": {
    "type": "object",
    "properties": {
      "decision": {"type": "string", "enum": ["allow", "deny"]},
      "reason": {"type": "string"}
    },
    "required": ["decision", "reason"]
  }
}
```

**System prompt**:
```
You are a security evaluator for a code editor's tool use requests.
Given a tool name and its parameters, decide if the operation should be auto-approved.

APPROVE if the operation is:
- Editing or writing files within the project directory: {git_root}
- Web search or documentation lookup
- Updating non-critical settings (editor config, formatting, linting)
- Creating or updating task/todo items
- Reading or searching any non-sensitive content

DENY if the operation is:
- Modifying files outside the project directory
- Touching sensitive paths (.ssh, .aws, .env, credentials, private keys)
- Running destructive or irreversible system commands
- Accessing or modifying authentication tokens/secrets
- Network operations that could exfiltrate data

Respond with ONLY valid JSON: {"decision": "allow" or "deny", "reason": "brief explanation"}
```

**Output**: Same JSON format as `auto-approve.sh` (`allow` decision) or silent exit (fall through).

### 2. `hooks/auto-approve.sh` (modified)

Changes to the existing script:

- **Edit tool**: New case — run `is_sensitive_path()` on `file_path`, check path is under git root, then delegate to `ollama-evaluate.sh`
- **Write tool**: Same logic as Edit
- **`*)` catch-all**: Changes from `exit 0` to calling `ollama-evaluate.sh` with the full input JSON
- Add deterministic git-root prefix check for Edit/Write before LLM call

### 3. `hooks/hooks.json` (unchanged)

Timeout stays at 5000ms. The curl timeout (4s) handles the LLM budget internally.

## Error Handling

| Failure mode | Behavior |
|---|---|
| Ollama not running | `curl` fails → exit 0 → permission prompt |
| Model not pulled | Ollama returns error → no valid decision → permission prompt |
| Timeout (>4s) | `curl --max-time 4` kills request → permission prompt |
| Malformed model output | `jq` extraction fails → permission prompt |
| Decision is "deny" | Script exits silently → permission prompt |

All failure modes fall through to the permission prompt. Never an accidental allow.

## Hard Guards (deterministic, never bypassed)

1. **Sensitive path veto**: `is_sensitive_path()` runs before the LLM for Edit/Write. Matches `.ssh/`, `.aws/`, `.env`, credentials, private keys, etc.
2. **Project scope check**: Edit/Write file paths must start with the git root (`git rev-parse --show-toplevel`). Anything outside → fall through, LLM never consulted.

## Model Choice

**Default: Qwen3:0.6b** (523 MB)
- 0.880 agent score on tool-calling benchmark (measures judgment — knowing when NOT to call a tool)
- ~1-2s inference on Apple Silicon with Ollama MLX backend
- Native tool-calling support
- `think: false` disables thinking mode for faster, cleaner output
- Structured output mode (`format` schema) enforces valid JSON

Configurable via `OLLAMA_MODEL` env var to swap in larger models (e.g., `qwen3:1.7b` for better accuracy at higher latency).

## Prerequisites

- Ollama installed and running (`ollama serve`)
- Model pulled (`ollama pull qwen3:0.6b`)
- `curl` and `jq` available (already required by existing hooks)

## Testing

```bash
# Test with an Edit inside project scope (should allow)
echo '{"tool_name":"Edit","tool_input":{"file_path":"/path/to/project/src/main.py","old_string":"foo","new_string":"bar"}}' | bash hooks/auto-approve.sh

# Test with an Edit outside project scope (should fall through)
echo '{"tool_name":"Edit","tool_input":{"file_path":"/etc/hosts","old_string":"foo","new_string":"bar"}}' | bash hooks/auto-approve.sh

# Test with Ollama down (should fall through gracefully)
OLLAMA_HOST=http://localhost:99999 echo '{"tool_name":"Agent","tool_input":{"prompt":"do something"}}' | bash hooks/auto-approve.sh

# Test ollama-evaluate.sh directly
echo '{"tool_name":"Write","tool_input":{"file_path":"/project/README.md","content":"hello"}}' | OLLAMA_MODEL=qwen3:0.6b bash hooks/ollama-evaluate.sh
```
