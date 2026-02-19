# Flow Recorder Agent Design

**Date:** 2026-02-19
**Status:** Approved
**Plugin:** ios-agentic-loop

## Summary

A new agent (`flow-recorder`) that takes a natural-language UI flow description, autonomously explores it via idb, generates a verified Maestro YAML test flow, and confirms correctness through injected Swift log verification.

## Agent Identity

- **File:** `agents/flow-recorder.md`
- **Model:** sonnet
- **Allowed tools:** `Task, Bash, Read, Write, Edit, Glob, Grep`
- **Trigger phrases:** "record a flow", "generate a test for [flow]", "create a Maestro flow from description", "test this UI flow", "test UI flows", "verify this flow works", "automate this flow", "turn this flow into a test", "record and verify [flow]", "create end-to-end test for [flow]"
- **Input:** Natural-language UI flow description (e.g., "Log in with email test@example.com and password 12345")

## Architecture

Team-orchestrated pipeline. The flow-recorder acts as the orchestrator, spawning `ui-explorer` via the Task tool for the exploration phase and handling all other phases inline.

## Six-Phase Pipeline

### Phase 1: Parse & Plan

- Parse the natural-language flow description into sub-goals
- Read `agentic-loop.config.yaml` for bundle ID, build command, project paths
- Create working directory: `/tmp/agentic/flow-recorder/<timestamp>/`

### Phase 2: Explore via ui-explorer

- Spawn `ios-agentic-loop:ui-explorer` as a sub-agent via Task tool
- Pass the flow description as a goal-directed instruction
- The ui-explorer runs the ORAV loop and writes the action log to `/tmp/agentic/action_log.json`
- Wait for the sub-agent to complete, then read the action log

### Phase 3: Export to Maestro YAML

- Read the action log from Phase 2
- Apply selector conversion rules:
  - `a11y_id` present → `tapOn: { id: "..." }`
  - `label` present (no a11y_id) → `tapOn: { text: "..." }`
  - Neither → `tapOn: { point: "X%,Y%" }` (pixel-to-percentage conversion)
- Convert `text` actions → `inputText:`
- Add `assertVisible:` steps for verified actions
- Generate Maestro YAML with frontmatter: appId, name, tags `[generated, regression]`
- Write to `tests/maestro/flows/generated/<flow_name>.yaml`

### Phase 4: Inject Verification Logs

- Analyze the action log to identify screens visited and actions taken
- Use Glob/Grep to find corresponding Swift files by searching for accessibility identifiers (e.g., `.accessibilityIdentifier("login_button_submit")`)
- Inject `print("[FlowVerify:<step>] <description>")` statements at:
  - SwiftUI `.onAppear { }` — inside the closure, first line
  - SwiftUI `Button(action: { })` — inside the action closure, first line
  - UIKit `viewDidAppear(_:)` — after `super.viewDidAppear(animated)`
  - UIKit `@IBAction func` — first line of method body
- Every injected line ends with `// [FlowVerify]` comment for cleanup
- Build an **expected log sequence** — ordered list of `[FlowVerify:N]` markers

### Phase 5: Build, Run & Verify

- Call `build_and_launch` MCP tool to rebuild with injected logs
- Start `idb log --udid <udid>` in background (Bash `&`, piped to `/tmp/agentic/flow-recorder/<timestamp>/idb_log.txt`)
- Run `maestro test <generated_flow.yaml>`
- Stop log capture
- Parse log output for `[FlowVerify:N]` markers
- Verify: all expected markers present and in correct order

### Phase 6: Cleanup & Report

- Remove all lines containing `// [FlowVerify]` from Swift source files
- Report results:
  - Maestro flow pass/fail
  - Log verification pass/fail (which markers fired, which missing)
  - Generated Maestro YAML path (kept for future regression)
  - Issues found during exploration

## Log Injection Detail

### Marker Format

```swift
print("[FlowVerify:1] LoginView appeared")  // [FlowVerify]
print("[FlowVerify:2] submitButton tapped")  // [FlowVerify]
```

Numbered marker `[FlowVerify:N]` corresponds to the action log step number. Trailing comment `// [FlowVerify]` is the cleanup anchor.

### File Discovery

The agent locates Swift files by grepping for accessibility identifiers from the action log:
- Action log entry: `a11y_id: "login_button_submit"`
- Search: `grep -r '.accessibilityIdentifier("login_button_submit")' **/*.swift`
- Result: `LoginView.swift` → inject log in the corresponding action handler

## Error Handling

| Failure | Recovery |
|---|---|
| ui-explorer can't complete the flow | Report which sub-goal failed, suggest checking if flow is reachable |
| No Swift files found for a screen | Skip log injection for that step, warn in report, still run Maestro |
| `build_and_launch` fails | Report build error, clean up injected logs, abort |
| Maestro flow fails | Report which step failed, still check logs for partial verification |
| Log markers missing | Report expected but absent markers — flow didn't reach that code path |
| Log markers out of order | Report actual vs expected order — flow executed differently |

## Output Artifacts

| Artifact | Path | Kept? |
|---|---|---|
| Maestro YAML flow | `tests/maestro/flows/generated/<flow_name>.yaml` | Yes (for regression) |
| Action log | `/tmp/agentic/flow-recorder/<timestamp>/action_log.json` | Yes (temp) |
| Log capture output | `/tmp/agentic/flow-recorder/<timestamp>/idb_log.txt` | Yes (temp) |
| Verification report | Printed to agent output | Yes |
| Injected Swift lines | Removed after verification | No |

## Design Decisions

1. **Team-orchestrated approach**: Leverages Claude Code's Task tool to spawn ui-explorer for exploration rather than duplicating the ORAV loop logic. Keeps agents focused and avoids instruction duplication.
2. **Log cleanup after verification**: Injected print statements are temporary — removed after the Maestro run succeeds, leaving no trace in source. Uses `// [FlowVerify]` comment anchors for reliable cleanup.
3. **idb log for log capture**: Uses `idb log` command to capture simulator logs during the Maestro run. Stays within the idb ecosystem used throughout the plugin.
4. **View lifecycle + action handler injection**: Injects at `onAppear`/`viewDidAppear` for screen arrival markers and button/action closures for user action markers. Covers the full flow without being overly invasive.
