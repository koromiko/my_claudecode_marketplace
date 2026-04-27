# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A Claude Code plugin that provides three shell-based hooks: conditional tool auto-approval with sensitive-path guards, macOS permission-prompt notifications, and session-completion notifications.

## Architecture

All logic lives in `hooks/`. There are no skills, commands, or agents — only hook scripts registered in `hooks/hooks.json`.

### Hook Pipeline

1. **`auto-approve.sh`** (PreToolUse, no matcher — runs on every tool call): Decides whether to auto-approve or fall through to the normal permission prompt. Reads tool input JSON from stdin, outputs a JSON permission decision to stdout.
2. **`permission-notification.sh`** (Notification, matcher: `permission_prompt`): Fires only when Claude actually shows a permission prompt. Writes a session marker file to `/tmp/claude-hook-session-{session_id}` so the Stop hook knows a prompt occurred.
3. **`stop-notification.sh`** (Stop, no matcher): Fires when Claude finishes. Only sends a notification if the session marker file exists (i.e., a permission prompt was shown). Cleans up the marker.

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
