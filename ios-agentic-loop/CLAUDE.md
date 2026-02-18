# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A Claude Code plugin for agentic iOS UI testing. Combines **idb** (iOS Development Bridge) for autonomous UI exploration with **Maestro** for deterministic regression testing. Claude explores apps via an observe-reason-act-verify (ORAV) loop using idb, then exports discoveries as repeatable Maestro YAML flows for CI.

## Prerequisites

- macOS with Xcode
- idb: `pip3 install fb-idb` + `brew tap facebook/fb && brew install idb-companion`
- Maestro: `curl -Ls 'https://get.maestro.mobile.dev' | bash`
- Java 17+ (required by Maestro): `brew install openjdk@21`, then set `JAVA_HOME`:
  ```bash
  export JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home
  export PATH="$JAVA_HOME/bin:$PATH"
  ```
  Add both to `~/.zshrc` for persistence. Without `JAVA_HOME`, the system `java` may point to an older version.
- A booted iOS Simulator with the target app installed

Verify setup: `bash scripts/check-prerequisites.sh`

## MCP Server

```bash
cd mcp-server && npm install && npm run build && npm test
```

16 tools across 4 categories:
- **idb** (6): `idb_screenshot`, `idb_describe_all`, `idb_tap`, `idb_text`, `idb_swipe`, `observe_screen`
- **lifecycle** (4): `idb_launch`, `idb_terminate`, `idb_install`, `build_and_launch`
- **maestro** (2): `maestro_run`, `maestro_export_flow`
- **utility** (4): `idb_key_press`, `reset_test_state`, `boot_simulator`, `check_prerequisites`

Uses `McpServer` from `@modelcontextprotocol/sdk` v1 with Zod schemas. Config loaded from `agentic-loop.config.yaml` with deep-merge defaults. UDID auto-resolved from booted simulators.

## Architecture

### Two-Phase Testing Model

1. **Exploration phase** (idb + Claude) — Autonomous, adaptive, AI-driven via the ORAV loop
2. **Regression phase** (Maestro) — Deterministic YAML flows generated from exploration, CI-ready

### Plugin Components

- **Agents** (`agents/`): `ui-explorer.md` (ORAV loop via idb, model: sonnet) and `regression-runner.md` (Maestro suite runner, model: sonnet)
- **Commands** (`commands/`): Six slash commands — `/check-prerequisites`, `/setup-project`, `/audit-accessibility`, `/run-maestro`, `/reset-test-state`, `/export-maestro-flow`
- **Skills** (`skills/`): Three methodology guides — `idb-exploration/` (ORAV loop), `accessibility-testing/` (identifier naming/auditing), `maestro-testing/` (flow authoring)
- **Scripts** (`scripts/`): Bash utilities — `check-prerequisites.sh`, `reset-test-state.sh`, `boot-simulator.sh`, `find-app-bundle.sh`
- **Hook** (`hooks/hooks.json`): PostToolUse hook fires when `*View.swift` files are edited, checks for missing accessibility identifiers
- **Templates** (`templates/`): YAML templates for config, Maestro flows, CI workflows

### ORAV Loop (Core Methodology)

The central pattern used by the `ui-explorer` agent:

1. **Observe** — `idb screenshot` + `idb ui describe-all --format json` (dual-channel: visual + accessibility tree)
2. **Reason** — Identify screen state, pick target element, compute tap coordinates (`x = frame.x + width/2`, `y = frame.y + height/2`)
3. **Act** — `idb ui tap`, `idb ui text`, `idb ui swipe`
4. **Verify** — Re-observe and compare before/after state

Action logs are written to `/tmp/agentic/action_log.json` and can be exported to Maestro flows.

### Key Conventions

- **Accessibility identifier naming**: `{scope}_{type}_{name}` (e.g., `login_button_submit`, `settings_toggle_dark_mode`)
- **Maestro selector priority**: `id:` (accessibility ID, preferred) > `text:` (visible text) > `point:` (percentage coords, last resort)
- **Scripts use** `set -euo pipefail` for safety
- **Shell version parsing**: When writing sed/awk patterns that extract version numbers, test with actual command output. Use `\.` (escaped dot) to match literal dots in version strings — an unescaped `.` causes greedy matching that silently produces empty output.
- **Config file**: `agentic-loop.config.yaml` in the target project root (created by `/setup-project`)

### Action Log Format

Each exploration step is recorded as:
```json
{"step": 1, "action": "tap", "x": 200, "y": 400, "label": "Submit", "a11y_id": "form_button_submit", "verified": true}
```

### Error Recovery Patterns

- App crash: detect via empty `describe-all`, relaunch with `idb launch`
- Alert dialog: find and tap "OK" or "Dismiss"
- Stuck state: retry with adjusted coordinates
- Keyboard blocking: `idb ui key 1 escape`
