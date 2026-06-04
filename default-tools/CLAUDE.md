# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A Claude Code plugin that provides shell-based hooks: conditional tool auto-approval with sensitive-path guards, macOS permission-prompt notifications, session-completion notifications, and an opt-in Stop-hook code review with three pluggable reviewer modes (local LLM, generic CLI, in-session subagent).

## Architecture

Logic lives primarily in `hooks/`. The plugin also ships one skill (`skills/grill-me/`) and one agent (`agents/grill.md`) — see **grill-me Skill** below — a `scripts/` directory with the auto-approve usage reports (terminal + HTML), and a `commands/` directory with the `/auto-approve-report` slash command that wraps the HTML report script.

### Hook Pipeline

1. **`auto-approve.sh`** (PreToolUse, no matcher — runs on every tool call): Decides whether to auto-approve or fall through to the normal permission prompt. Reads tool input JSON from stdin, outputs a JSON permission decision to stdout.
2. **`permission-notification.sh`** (Notification, matcher: `permission_prompt`): Fires only when Claude actually shows a permission prompt. Writes a session marker file to `/tmp/claude-hook-session-{session_id}` so the Stop hook knows a prompt occurred.
3. **`stop-notification.sh`** (Stop, no matcher): Fires when Claude finishes. Only sends a notification if the session marker file exists (i.e., a permission prompt was shown). Cleans up the marker.
4. **`stop-review.sh`** (Stop, no matcher — sibling of `stop-notification.sh`): Opt-in code-review gate. Disabled by default. When enabled via `/review-config`, runs a second-pass review of the previous Claude turn before allowing the session to stop. See **Stop-hook Code Review** below.

### Auto-Approve Decision Logic

`auto-approve.sh` uses two helpers:

- **`is_sensitive_path()`** — returns true for paths matching sensitive directories (`.ssh/`, `.aws/`, `.gnupg/`, `.kube/`, `.docker/`) or file patterns (`.env*`, `*secret*`, `*credential*`, `*private_key*`, `*.pem`, key files). Used by Read, Glob, and Grep handlers.
- **`is_readonly_bash_command()`** — returns true for commands matching a prefix allowlist (git read-only, `ls`, `pwd`, `gh` read-only, version checks) AND containing no shell metacharacters (`|`, `;`, `&&`, `` ` ``, `$(`, `>`, `<`).

Exit conventions:
- `allow "reason"` → outputs JSON with `permissionDecision: "allow"` and exits 0
- `exit 0` with no output → no decision, falls through to default permission prompt

### Ollama LLM Evaluator

`ollama-evaluate.sh` is a fallback for tool calls not handled by the fast path. It sends the tool JSON to a local Ollama model for a binary allow/deny decision.

**Tools routed to the LLM:**
- `Edit` / `Write` — after passing sensitive-path and project-scope hard guards
- `Bash` — non-readonly commands (after the allowlist check fails)
- `*` catch-all — any tool not explicitly handled (Agent, NotebookEdit, etc.)

**Configuration (environment variables):**
- `OLLAMA_MODEL` — default `gemma4:latest`
- `OLLAMA_HOST` — default `http://localhost:11434`
- `OLLAMA_TIMEOUT` — default `15` (seconds)
- `OLLAMA_TEST_MODE` — set to `1` by the test harness so deny decisions are emitted as JSON (never set in production)

**Failure behavior:** If Ollama is unavailable, times out, or returns a deny/malformed response, the script exits silently and the tool falls through to the normal permission prompt.

### Notification Flow

Both notification scripts derive a project name from the git root of `cwd`. They use `terminal-notifier` (activating iTerm2) and `say` for audio. The Stop hook guards against re-entry via `stop_hook_active` and only fires if the session marker exists.

## Stop-hook Code Review

`stop-review.sh` runs a second-pass review of the previous Claude turn at Stop time. Disabled by default (`reviewHook.enabled=false`); enabled per-project via `/review-config enable`.

### Reviewer types

| Type | What it does | When to use |
|---|---|---|
| `ollama` | POST the assembled prompt to `http://localhost:11434/api/generate`, parse `.response`, look for `ALLOW:` / `BLOCK:` on the first line. Reuses the curl pattern from `ollama-evaluate.sh`. | You want a private, free, local-only second pass. |
| `cli` | Spawn an external CLI (`codex task --json`, `gemini ...`) with the prompt as the final positional argument. Optionally extract a JSON field via `outputField`. Same ALLOW/BLOCK first-line contract. | You want to delegate review to a different cloud LLM you already have a CLI for. |
| `subagent` | Block-and-instruct: the hook emits `decision:block` with a reason telling Claude to dispatch a named in-session subagent. Claude does the review with full session context; no fresh process. | You want the reviewer to see the original conversation, tool history, and skills. |

### Loop guard

- **`stop_hook_active=true`** (Claude Code re-fires Stop after our previous block) → exit 0, clear any session marker.
- **Marker file** `/tmp/claude-review-${session_id}` (subagent mode) — touched on the first block emitted; presence on subsequent stops in the same session means the review was already requested.
- **Iteration counter file** `/tmp/claude-review-iter-${session_id}` (ollama/cli modes) — incremented per `BLOCK` emitted, cleared on `ALLOW`. When `iter > maxIterations`, emit one final "manual review needed" block and bump the counter past the cap so subsequent stops are silent.

### Skip conditions (exit 0 silently)

- `reviewHook.enabled=false` (default)
- `stop_hook_active=true` (re-entry)
- `cwd` is sensitive (`.ssh/`, `.aws/`, `.gnupg/`, `.kube/`, `.docker/`) — never send those to a third-party reviewer
- `last_assistant_message` is empty
- `skipIfNoChanges=true` (default) and `git status --porcelain` is empty
- Iteration counter past cap

### Fail-open principle

Every infrastructure failure path logs `PASS_REVIEW <cause>` and exits 0 — never blocks. Causes: missing CLI, missing jq, ollama unreachable, reviewer timeout, malformed reviewer output. The gate only blocks on a literal `BLOCK:` first line from the reviewer.

## Configuration via `/review-config`

The `/review-config` slash command reads/writes `${git-root}/.claude/settings.local.json` under the `reviewHook` key. Schema:

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

Common workflows:

```
/review-config enable
/review-config type ollama
/review-config model qwen2.5-coder:7b

/review-config type cli
/review-config command codex
/review-config args ["task","--json"]
/review-config field rawOutput

/review-config type subagent
/review-config agent code-review-engineer

/review-config disable
```

`promptOverride` is an optional absolute path to a custom prompt template. The bundled template lives at `hooks/stop-review-prompt.md` and follows the same ALLOW/BLOCK first-line contract used in `openai/codex-plugin-cc`'s `stop-review-gate.md`.

`redactSecrets` (default on) strips AWS access key IDs (`AKIA…`), OpenAI-style keys (`sk-…`), GitHub tokens (`ghp_…`), and `key=value` pairs where the key looks like `api_key`/`secret`/`token`/`bearer`/`password` from `last_assistant_message` before sending it to a third-party reviewer.

## Code-review Logging

`stop-review.sh` writes its own log at `~/.claude/logs/code-review.log` (separate from `auto-approve.log`) in tab-separated format:

```
TIMESTAMP	DECISION	REVIEWER	SESSION_ID	ITER	REASON	DURATION_MS
```

Decisions: `ALLOW_OLLAMA`, `ALLOW_CLI`, `ALLOW_CLEAN` (clean working tree, skipped), `BLOCK_OLLAMA`, `BLOCK_CLI`, `BLOCK_SUBAGENT`, `BLOCK_FINAL` (manual review threshold hit), `PASS_REVIEW` (fail-open: missing CLI, timeout, malformed output, etc.), `SKIP_REVIEW` (counter past cap).

Same 1MB rotation + 3 backups as the auto-approve log. Log helpers live in `hooks/review-lib.sh`.

```bash
# Tail the review log
tail -f ~/.claude/logs/code-review.log

# All BLOCK decisions
grep $'\tBLOCK' ~/.claude/logs/code-review.log
```

## Test Harness

`tests/test-ollama-evaluator.sh` runs 23 fixture cases from `tests/fixtures/ollama-test-cases.json` against `ollama-evaluate.sh` and reports pass/fail/skip per case.

```bash
bash tests/test-ollama-evaluator.sh
```

Results are written to `tests/results/run-<ISO-timestamp>.json` (gitignored; directory kept via `.gitkeep`).

The runner sets `OLLAMA_TEST_MODE=1` so deny decisions are emitted as JSON and counted as `pass`/`fail` rather than `skip`. If Ollama is unavailable, all cases are skipped and the runner exits 0.

Fixture categories: `bash-git`, `bash-curl`, `bash-misc`, `edit`, `agent`, `mcp`, `meta`, `bash-destructive`, `bash-exfiltrate`.

## Testing Changes

After modifying hook scripts:

```bash
# Validate JSON structure
jq . hooks/hooks.json

# Test auto-approve with sample input
echo '{"tool_name":"Read","tool_input":{"file_path":"/some/file.txt"}}' | bash hooks/auto-approve.sh

# Test sensitive path detection (should produce no output = fall through)
echo '{"tool_name":"Read","tool_input":{"file_path":"/home/user/.ssh/id_rsa"}}' | bash hooks/auto-approve.sh

# Clear plugin cache to pick up changes
../../scripts/bump-plugin.sh default-tools

# Test LLM evaluation of an Edit (should allow — file is in project scope)
echo '{"tool_name":"Edit","tool_input":{"file_path":"'$(git rev-parse --show-toplevel)'/src/main.py","old_string":"foo","new_string":"bar"}}' | bash hooks/auto-approve.sh

# Test LLM evaluation with Ollama down (should fall through silently)
OLLAMA_HOST=http://localhost:99999 echo '{"tool_name":"Agent","tool_input":{"prompt":"do something"}}' | bash hooks/auto-approve.sh

# Test ollama-evaluate.sh directly
echo '{"tool_name":"Write","tool_input":{"file_path":"/project/README.md","content":"hello"}}' | bash hooks/ollama-evaluate.sh

# Test stop-review.sh — disabled by default, expect no output
echo '{"session_id":"smoke","cwd":"'$PWD'","last_assistant_message":"I refactored auth.","stop_hook_active":false}' | bash hooks/stop-review.sh

# Test stop-review.sh — subagent mode (write a config first), expect decision:block JSON
mkdir -p .claude && cat > .claude/settings.local.json <<'JSON'
{"reviewHook":{"enabled":true,"reviewer":{"type":"subagent","subagent":{"name":"code-reviewer"}},"skipIfNoChanges":false}}
JSON
echo '{"session_id":"smoke","cwd":"'$PWD'","last_assistant_message":"I refactored auth.","stop_hook_active":false}' | bash hooks/stop-review.sh

# Test stop-review.sh — ollama mode with mocked output (no real LLM call)
STOP_REVIEW_TEST_OUTPUT="ALLOW: looks fine" \
  echo '{"session_id":"smoke","cwd":"'$PWD'","last_assistant_message":"x","stop_hook_active":false}' \
  | STOP_REVIEW_TEST_OUTPUT="ALLOW: looks fine" bash hooks/stop-review.sh
```

## Auto-Approve Logging

All tool use decisions are logged to `~/.claude/logs/auto-approve.log` in tab-separated format:

```
TIMESTAMP	DECISION	TOOL_NAME	INPUT_SUMMARY	REASON	DURATION_MS
```

Decisions: `ALLOW` (fast path), `PASS` (deferred to prompt), `ALLOW_LLM` (Ollama approved), `PASS_LLM` (Ollama denied/unavailable).

`DURATION_MS` is the end-to-end turnaround time of the hook measured from the moment `auto-approve.sh` is invoked to the moment the decision is written. It captures the total permission-check overhead the tool call incurred, including Ollama round-trip time for LLM branches. Fast-path decisions typically run in <50ms; LLM-branch decisions track the local model's latency (~800–1200ms on `gemma4:latest`). Rows written before this column was added have an empty 6th field and are ignored by the report.

Log files rotate at 1MB with 3 backups (`.1`, `.2`, `.3`). Logging utilities live in `hooks/log-utils.sh` (sourced by `auto-approve.sh`).

```bash
# Tail the log in real time
tail -f ~/.claude/logs/auto-approve.log

# View only LLM decisions
grep 'LLM' ~/.claude/logs/auto-approve.log

# View only fall-through (permission prompt) decisions
grep 'PASS' ~/.claude/logs/auto-approve.log
```

### Auto-Approve Usage Report (terminal)

`scripts/auto-approve-usage.sh` aggregates the log into a human-readable summary with decision/tool breakdowns and a fast-path vs LLM split.

```bash
# All-time report
bash scripts/auto-approve-usage.sh

# Today only
bash scripts/auto-approve-usage.sh --today

# Last N days
bash scripts/auto-approve-usage.sh --days 7

# Since a specific date
bash scripts/auto-approve-usage.sh --since 2026-04-01
```

Output sections:
- **Decisions** — counts and bar charts for ALLOW, PASS, ALLOW_LLM, PASS_LLM
- **Tool Calls** — per-tool breakdown sorted by volume
- **Fast-path vs LLM** — aggregate split showing how often Ollama was invoked
- **Turnaround time (ms)** — count, avg, p50, p95, max per decision type (skips pre-timing rows)

### Auto-Approve Usage Report (HTML)

`scripts/auto-approve-report.sh` generates a self-contained HTML dashboard with KPI cards, decision/tool bar charts, a fast-path vs LLM donut, and a turnaround table. The report works offline (Chart.js is vendored at `scripts/vendor/chart.umd.min.js`).

```bash
# Default: last 7 days, written to /tmp/auto-approve-report-<ISO>.html
bash scripts/auto-approve-report.sh

# Generate and open in the browser
bash scripts/auto-approve-report.sh --open

# Filter by time window (mirrors the terminal report's flags)
bash scripts/auto-approve-report.sh --today
bash scripts/auto-approve-report.sh --days 30
bash scripts/auto-approve-report.sh --since 2026-04-01
bash scripts/auto-approve-report.sh --all          # override default 7-day window

# Custom output path
bash scripts/auto-approve-report.sh --out ~/Desktop/auto-approve.html --open
```

Slash command: `/auto-approve-report [flags]` runs the script with `--open` and forwards any flags as arguments.

The default time window is **last 7 days** (the terminal report defaults to all-time). Use `--all` to match the terminal report's default.

## Prerequisites

macOS with `jq`, `terminal-notifier` (`brew install terminal-notifier`), and iTerm2 for notifications. The `say` command is used for audio alerts. Ollama (`brew install ollama`) with Gemma4 8B (`ollama pull gemma4:latest`) for LLM-based tool evaluation.

## grill-me Skill

`skills/grill-me/SKILL.md` is an auto-triggering skill that stress-tests a plan
or design before implementation. It triggers on explicit grill intent ("grill
me", "stress-test this plan", "poke holes in this design") and on
pre-implementation contexts where a concrete plan is about to be built.

The skill conducts a **relay loop** with a separate read-only **grill agent**
(`agents/grill.md` — the first agent in this marketplace):

1. The main agent spawns the grill agent once (`subagent_type: "grill"`), then
   addresses it across rounds by the `agentId` the Agent tool returns on spawn,
   passing the plan and code pointers.
2. The grill agent returns ONE question per turn (`QUESTION / WHY / RECOMMENDED`).
3. The main agent answers it autonomously from the codebase/conventions, and
   escalates to the human via `AskUserQuestion` only for costly-to-reverse
   decisions (schema/contract, public API, data migration, security boundary).
4. The answer is fed back via `SendMessage(to: "grill", ...)`; repeat until the
   grill agent emits `DONE` or a 15-round safety cap is hit.
5. On completion the main agent prints the decision log and revises the plan to
   fold in the resolved decisions.

The grill agent's `tools` are restricted to `Read, Grep, Glob` so it is
strictly read-only and never trips a permission prompt mid-loop (background
agents cannot handle permission prompts — see the marketplace CLAUDE.md).

The loop continues the same grill agent across rounds by capturing the `agentId`
the Agent tool returns on spawn and passing it to `SendMessage(to: "<agentId>", …)`
— the documented way to resume a previously-spawned agent with its context
intact. (This differs from the `agent-orchestration` plugin, where `SendMessage`
coordinates teammates inside a `TeamCreate` swarm.)
