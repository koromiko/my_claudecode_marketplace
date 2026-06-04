---
description: Configure the Stop-hook code review in default-tools (enable/disable, choose reviewer type, set model/CLI/subagent)
allowed-tools:
  - Bash(jq:*)
  - Bash(mkdir:*)
  - Bash(mv:*)
  - Bash(test:*)
  - Bash(cat:*)
  - Read
  - Write
---

# Review Config

Configure the Stop-hook code review for the current project. Reads and writes `${CLAUDE_PROJECT_DIR}/.claude/settings.local.json` under the `reviewHook` key.

## Subcommands ($ARGUMENTS)

- `show` — print the current `reviewHook` block
- `enable` / `disable` — toggle the gate
- `type <ollama|cli|subagent>` — choose the reviewer
- `model <name>` — set `reviewer.ollama.model` (e.g. `gemma4:latest`, `qwen2.5-coder:7b`)
- `host <url>` — set `reviewer.ollama.host` (default `http://localhost:11434`)
- `command <bin>` — set `reviewer.cli.command` (e.g. `codex`, `gemini`)
- `args <json-array>` — set `reviewer.cli.args` (e.g. `'["task","--json"]'`)
- `field <name>` — set `reviewer.cli.outputField` for CLIs that wrap their reply in JSON (e.g. `rawOutput` for codex)
- `agent <name>` — set `reviewer.subagent.name` (block-and-instruct mode)
- `max-iter <n>` — set `maxIterations` (default 3, cap before manual review needed)
- `redact <on|off>` — toggle secret redaction before sending to third-party reviewers
- `skip-clean <on|off>` — skip review when working tree has no changes (default on)

## Schema

```json
{
  "reviewHook": {
    "enabled": false,
    "reviewer": {
      "type": "ollama",
      "ollama":   { "model": "gemma4:latest", "host": "http://localhost:11434", "timeout": 60 },
      "cli":      { "command": "codex", "args": ["task","--json"], "timeout": 900, "outputField": "rawOutput" },
      "subagent": { "name": "code-reviewer" }
    },
    "maxIterations": 3,
    "skipIfNoChanges": true,
    "redactSecrets": true,
    "promptOverride": null
  }
}
```

## Instructions

Parse `$ARGUMENTS` to determine the subcommand. Use these exact bash steps:

1. Resolve the settings path:
   ```bash
   ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")
   SETTINGS="$ROOT/.claude/settings.local.json"
   mkdir -p "$ROOT/.claude"
   ```

2. If `$SETTINGS` doesn't exist, scaffold an empty object:
   ```bash
   [ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"
   ```

3. Apply the requested change with a jq filter, writing atomically:
   ```bash
   TMP=$(mktemp)
   jq '<filter>' "$SETTINGS" > "$TMP" && mv -f "$TMP" "$SETTINGS"
   ```

4. After applying, always print the resulting `reviewHook` block:
   ```bash
   jq '.reviewHook // {}' "$SETTINGS"
   ```

### jq filters by subcommand

| Subcommand | jq filter |
|---|---|
| `show` | (skip step 3, just print) |
| `enable` | `.reviewHook.enabled = true` |
| `disable` | `.reviewHook.enabled = false` |
| `type ollama` | `.reviewHook.reviewer.type = "ollama"` |
| `type cli` | `.reviewHook.reviewer.type = "cli"` |
| `type subagent` | `.reviewHook.reviewer.type = "subagent"` |
| `model <name>` | `.reviewHook.reviewer.ollama.model = $arg` (pass with `--arg arg "<name>"`) |
| `host <url>` | `.reviewHook.reviewer.ollama.host = $arg` |
| `command <bin>` | `.reviewHook.reviewer.cli.command = $arg` |
| `args <json>` | `.reviewHook.reviewer.cli.args = ($arg \| fromjson)` (pass `--arg arg '<json>'`) |
| `field <name>` | `.reviewHook.reviewer.cli.outputField = $arg` |
| `agent <name>` | `.reviewHook.reviewer.subagent.name = $arg` |
| `max-iter <n>` | `.reviewHook.maxIterations = ($arg \| tonumber)` |
| `redact on` | `.reviewHook.redactSecrets = true` |
| `redact off` | `.reviewHook.redactSecrets = false` |
| `skip-clean on` | `.reviewHook.skipIfNoChanges = true` |
| `skip-clean off` | `.reviewHook.skipIfNoChanges = false` |

For `type subagent`, also remind the user to confirm a subagent named `<reviewer.subagent.name>` exists in their plugin set (default: `code-reviewer`). For `type cli`, verify `command -v <command>` so the user gets an immediate "not on PATH" warning.

If `$ARGUMENTS` is empty, show usage (the Subcommands list above) and the current `reviewHook` block.

## Examples

```
/review-config show
/review-config enable
/review-config type ollama
/review-config model qwen2.5-coder:7b
/review-config type cli
/review-config command codex
/review-config args ["task","--json"]
/review-config field rawOutput
/review-config type subagent
/review-config agent code-review-engineer
/review-config max-iter 5
/review-config disable
```

## Safety

- All writes go through `mktemp` + `mv -f` for atomicity.
- Never write secrets into `settings.local.json`. The reviewer's API keys (if any) live in the reviewer's own config (e.g. `~/.codex/auth.json`), not here.
- If jq is missing, surface that to the user — `default-tools` already requires jq for auto-approve.
