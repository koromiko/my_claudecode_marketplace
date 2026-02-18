# ios-agentic-loop

A Claude Code plugin for agentic iOS UI testing. Combines **idb** (iOS Development Bridge) for autonomous UI exploration with **Maestro** for deterministic regression testing.

The core idea: Claude explores your app through an observe-reason-act-verify loop using idb, then exports what it discovers as repeatable Maestro YAML flows you can run in CI.

## How It Works

```
 Exploration (idb + Claude)          Regression (Maestro)
┌─────────────────────────┐     ┌──────────────────────────┐
│  OBSERVE  screenshot +  │     │                          │
│           a11y tree     │     │  Deterministic YAML      │
│  REASON   pick action   │────▶│  flows generated from    │
│  ACT      tap/type/swipe│     │  exploration sessions    │
│  VERIFY   check result  │     │                          │
└─────────────────────────┘     └──────────────────────────┘
      AI-driven, ad-hoc              Repeatable, CI-ready
```

## Prerequisites

- macOS with Xcode installed
- idb (`pip3 install fb-idb` + `brew tap facebook/fb && brew install idb-companion`)
- Maestro (`curl -Ls 'https://get.maestro.mobile.dev' | bash`)
- Java 17+ (`brew install openjdk@21`) — required by Maestro. Set `JAVA_HOME` in `~/.zshrc`:
  ```bash
  export JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home
  export PATH="$JAVA_HOME/bin:$PATH"
  ```
- A booted iOS Simulator with your app installed

Run `/check-prerequisites` to verify your setup.

## Installation

Add to your Claude Code settings (`.claude/settings.json`):

```json
{
  "plugins": [
    "/path/to/ios-agentic-loop"
  ]
}
```

Then run `/setup-project` to configure the plugin for your iOS project.

## Slash Commands

| Command | Description |
|---------|-------------|
| `/check-prerequisites` | Verify idb, Maestro, Xcode, and simulator are ready |
| `/setup-project` | Interactive setup: creates config, Maestro workspace, and initial smoke test |
| `/audit-accessibility` | Audit accessibility identifier coverage on the running app |
| `/run-maestro` | Run Maestro test flows (accepts optional path or `--tags`) |
| `/reset-test-state` | Clear app state on the simulator for clean test runs |
| `/export-maestro-flow` | Convert an idb exploration action log to a Maestro YAML flow |

## Agents

### ui-explorer

Autonomous iOS UI testing agent. Navigates your app using the ORAV loop (Observe-Reason-Act-Verify) via idb. Supports two modes:

- **Goal-directed** -- give it a specific task like "test the login flow" and it pursues it step by step
- **Exploration** -- say "explore the app" and it systematically maps screens, taps every interactive element, and reports what it finds

Triggered by: "explore the app", "find bugs in the UI", "test the app autonomously"

### regression-runner

Runs the full Maestro regression suite, reports pass/fail results, and suggests fixes for failures. Runs smoke tests first as a gate before the full suite.

Triggered by: "run regression tests", "run all UI tests", "check for regressions"

## Skills

### idb-exploration

The ORAV loop methodology for autonomous UI exploration:

1. **Observe** -- screenshot + accessibility tree (dual-channel)
2. **Reason** -- identify screen state, pick target element, compute tap coordinates
3. **Act** -- execute via `idb ui tap`, `idb ui text`, `idb ui swipe`
4. **Verify** -- re-observe, compare before/after, retry on failure

Includes error recovery for app crashes, alert dialogs, stuck states, and keyboard blocking.

### accessibility-testing

Covers adding, naming, and auditing accessibility identifiers across SwiftUI and UIKit. Follows the `{scope}_{type}_{name}` naming convention (e.g., `login_button_submit`, `settings_toggle_dark_mode`). Includes common pitfalls for SwiftUI button styles, ForEach grouping, sheets, and image-only buttons.

### maestro-testing

Writing and maintaining Maestro YAML test flows. Covers selector priority (`id:` > `text:` > `point:`), key commands (tapOn, inputText, assertVisible, scroll), CI integration, and flow maintenance when UI changes.

## Hook

The plugin includes a `PostToolUse` hook that fires when any `*View.swift` file is edited. It checks whether all interactive elements in the edited view have accessibility identifiers and suggests additions following the naming convention.

## MCP Server

A TypeScript MCP server is scaffolded under `mcp-server/` with tool definitions for:

- **idb tools** -- screenshot, describe_all, tap, text, swipe, observe_screen
- **lifecycle tools** -- launch, terminate, install, build_and_launch
- **maestro tools** -- run, export_flow

> The MCP server is currently in stub form (Phase 2). The plugin works fully through its skills, commands, and agents using direct `idb` and `maestro` CLI calls via Bash.

## Project Configuration

After running `/setup-project`, an `agentic-loop.config.yaml` is created in your project root:

```yaml
simulator:
  device: "iPhone 16 Pro"
  runtime: "iOS 18.2"
  udid: auto

app:
  bundle_id: "com.example.myapp"
  build_command: "xcodebuild -scheme MyApp ..."

loop:
  max_steps_per_goal: 30
  max_retries_per_action: 3

maestro:
  output_dir: "tests/maestro/flows"
  prefer_id_selectors: true
```

## Typical Workflow

1. **Setup** -- `/check-prerequisites` then `/setup-project`
2. **Audit** -- `/audit-accessibility` to find missing identifiers, add them to your views
3. **Explore** -- "explore the app" or "test the login flow" to run the ui-explorer agent
4. **Export** -- `/export-maestro-flow` to convert the exploration into a Maestro YAML flow
5. **Regress** -- `/run-maestro` or trigger the regression-runner agent to run the full suite
6. **Iterate** -- fix failures, re-audit, re-explore as the UI evolves

## File Structure

```
ios-agentic-loop/
├── .claude-plugin/
│   └── plugin.json
├── .mcp.json
├── agents/
│   ├── ui-explorer.md
│   └── regression-runner.md
├── commands/
│   ├── check-prerequisites.md
│   ├── setup-project.md
│   ├── audit-accessibility.md
│   ├── run-maestro.md
│   ├── reset-test-state.md
│   └── export-maestro-flow.md
├── hooks/
│   └── hooks.json
├── mcp-server/
│   └── src/
│       ├── index.ts
│       ├── config.ts
│       └── tools/
│           ├── idb-tools.ts
│           ├── lifecycle-tools.ts
│           └── maestro-tools.ts
├── scripts/
│   ├── check-prerequisites.sh
│   ├── reset-test-state.sh
│   ├── find-app-bundle.sh
│   └── boot-simulator.sh
├── skills/
│   ├── idb-exploration/
│   ├── accessibility-testing/
│   └── maestro-testing/
└── templates/
    ├── agentic-loop.config.yaml.template
    ├── maestro-config.yaml.template
    ├── scenario.yaml.template
    └── github-workflow.yaml.template
```
