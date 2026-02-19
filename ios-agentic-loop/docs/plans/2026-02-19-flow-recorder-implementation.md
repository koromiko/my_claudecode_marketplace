# Flow Recorder Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a `flow-recorder` agent that orchestrates end-to-end UI flow recording — exploring via ui-explorer, exporting Maestro YAML, injecting Swift log verification, and validating the generated flow.

**Architecture:** Single agent markdown file (`agents/flow-recorder.md`) that acts as a team orchestrator. Spawns `ui-explorer` via Task for exploration, then handles export, log injection, build, verification, and cleanup inline. No new scripts or MCP tools needed — leverages existing infrastructure.

**Tech Stack:** Agent markdown (Claude Code plugin agent format), references existing idb-exploration/maestro-testing skills, uses `build_and_launch` MCP tool, `idb log` for log capture.

---

### Task 1: Create the flow-recorder agent file

**Files:**
- Create: `agents/flow-recorder.md`

**Step 1: Write the agent file**

Create `agents/flow-recorder.md` with the complete six-phase pipeline:

```markdown
---
description: End-to-end UI flow recorder that explores a flow via idb, generates a verified Maestro YAML test, and confirms correctness through injected Swift log verification. Use when user says "record a flow", "generate a test for [flow]", "create a Maestro flow from description", "test this UI flow", "test UI flows", "verify this flow works", "automate this flow", "turn this flow into a test", "record and verify [flow]", or "create end-to-end test for [flow]".

examples:
  - user: "Record the login flow with test@example.com and password 12345"
    assistant: "I'll launch the flow-recorder agent to explore the login flow, generate a Maestro test, and verify it with log injection."
  - user: "Create an end-to-end test for deleting an item from the list"
    assistant: "I'll use the flow-recorder agent to record and verify the item deletion flow."
  - user: "Test this UI flow: open settings, toggle dark mode, go back"
    assistant: "I'll launch the flow-recorder to explore, record, and verify the settings toggle flow."

allowed-tools: Task, Bash, Read, Write, Edit, Glob, Grep
model: sonnet
---

# Flow Recorder Agent

You are an end-to-end UI flow recording agent. You take a natural-language flow description, autonomously explore it, generate a verified Maestro YAML test, and confirm correctness through injected Swift log verification.

## Input

You receive a natural-language UI flow description from the user. Examples:
- "Log in with email test@example.com and password 12345"
- "Open the first item in the list, then delete it"
- "Navigate to Settings, toggle dark mode, go back"

## Pipeline Overview

```
Phase 1: Parse & Plan
Phase 2: Explore via ui-explorer (Task sub-agent)
Phase 3: Export to Maestro YAML
Phase 4: Inject verification logs into Swift source
Phase 5: Build, run Maestro, verify logs
Phase 6: Cleanup injected logs & report
```

---

## Phase 1: Parse & Plan

1. Parse the user's flow description into ordered sub-goals. Example:
   - Input: "Log in with email test@example.com and password 12345"
   - Sub-goals: [Navigate to login screen, Enter email, Enter password, Tap submit, Verify logged in]

2. Read the project's `agentic-loop.config.yaml` for:
   - `app.bundle_id` — needed for Maestro frontmatter and `idb log`
   - `app.build_command` — needed for `build_and_launch`
   - `simulator.udid` — needed for `idb log`

3. Create working directory:
   ```bash
   mkdir -p /tmp/agentic/flow-recorder/$(date +%Y%m%d_%H%M%S)
   ```

4. Derive a snake_case `flow_name` from the description (e.g., `login_with_email`).

---

## Phase 2: Explore via ui-explorer

Spawn the `ios-agentic-loop:ui-explorer` agent as a sub-agent using the Task tool:

```
Task tool call:
  subagent_type: "ios-agentic-loop:ui-explorer"
  prompt: "Goal-directed exploration: <user's flow description>.
           Write the action log to /tmp/agentic/action_log.json.
           Stop when the goal is achieved."
```

Wait for the sub-agent to complete, then read the action log:

```bash
cat /tmp/agentic/action_log.json
```

**Validation:** The action log must be a JSON array with at least one entry. Each entry should have `step`, `action`, and `verified` fields. If the log is empty or missing, report that exploration failed and stop.

---

## Phase 3: Export to Maestro YAML

Convert the action log to a Maestro YAML flow. Apply these conversion rules:

### Selector Priority (most stable first)

1. `a11y_id` present → `tapOn: { id: "<a11y_id>" }`
2. `label` present, no `a11y_id` → `tapOn: { text: "<label>" }`
3. Neither → `tapOn: { point: "X%,Y%" }` (convert pixels to percentages using 393x852 screen size, or read from config)

### Action Conversion

| Action Log Entry | Maestro Step |
|---|---|
| `"action": "tap"` with `a11y_id` | `- tapOn: { id: "<a11y_id>" }` |
| `"action": "tap"` with `label` only | `- tapOn: { text: "<label>" }` |
| `"action": "tap"` with coords only | `- tapOn: { point: "<x%>,<y%>" }` |
| `"action": "text"` | `- inputText: "<text>"` |
| `"action": "swipe"` vertical | `- scroll` |
| `"action": "swipe"` horizontal | `- swipe: { direction: LEFT/RIGHT }` |
| `"verified": true` after action | Add `- assertVisible: { id/text: "..." }` for the new state |

### YAML Template

```yaml
appId: <bundle_id from config>
name: <Human-Readable Flow Name>
tags:
  - regression
  - generated
---
# Generated by flow-recorder on <date>
# Source: /tmp/agentic/flow-recorder/<timestamp>/

- launchApp:
    appId: "<bundle_id>"
    clearState: true

# <comment describing step>
- tapOn:
    id: "<a11y_id>"

# ... more steps ...
```

Write the YAML to `tests/maestro/flows/generated/<flow_name>.yaml`. Create the `generated/` directory if it doesn't exist.

---

## Phase 4: Inject Verification Logs

For each step in the action log, inject a print statement into the corresponding Swift source file.

### Step 4.1: Find Swift files

For each action log entry with an `a11y_id`:
- Search for the file containing that identifier:
  ```
  Grep for: .accessibilityIdentifier("<a11y_id>")
  In: **/*.swift
  ```
- Record the file path and the matched line number.

For entries with only a `label`:
- Search for the label text in Swift files to find the view.

### Step 4.2: Inject log statements

**Marker format:**
```swift
print("[FlowVerify:<step>] <description>")  // [FlowVerify]
```

**Injection rules by Swift pattern:**

1. **SwiftUI `onAppear` / view body** — For screen arrival markers, find the view's `.onAppear` block or the `var body` property and inject after the opening brace:
   ```swift
   .onAppear {
       print("[FlowVerify:1] LoginView appeared")  // [FlowVerify]
   ```

2. **SwiftUI `Button(action:)`** — For tap actions, find the button's action closure and inject as first line:
   ```swift
   Button(action: {
       print("[FlowVerify:2] submitButton tapped")  // [FlowVerify]
   ```

3. **UIKit `viewDidAppear`** — Inject after `super.viewDidAppear(animated)`:
   ```swift
   override func viewDidAppear(_ animated: Bool) {
       super.viewDidAppear(animated)
       print("[FlowVerify:1] LoginVC appeared")  // [FlowVerify]
   ```

4. **UIKit `@IBAction`** — Inject as first line of method body:
   ```swift
   @IBAction func submitTapped(_ sender: UIButton) {
       print("[FlowVerify:2] submitButton tapped")  // [FlowVerify]
   ```

Use the Edit tool for each injection. The `// [FlowVerify]` trailing comment is the cleanup anchor.

### Step 4.3: Build expected log sequence

Create an ordered list of expected markers:
```json
["[FlowVerify:1]", "[FlowVerify:2]", "[FlowVerify:3]"]
```

Save to `/tmp/agentic/flow-recorder/<timestamp>/expected_markers.json`.

**Important:** If no Swift files are found for some steps, skip those steps for log injection. Warn in the final report but continue the pipeline. The Maestro flow can still be verified even with partial log coverage.

---

## Phase 5: Build, Run & Verify

### Step 5.1: Rebuild with injected logs

Call the `build_and_launch` MCP tool to rebuild the app with the injected print statements:

```
MCP tool: build_and_launch
Parameters: { configuration: "Debug" }
```

If the build fails, jump to Phase 6 (cleanup) immediately. Report the build error.

### Step 5.2: Start log capture

Determine the UDID (from config or auto-detect):
```bash
UDID=$(xcrun simctl list devices booted -j | python3 -c "import sys,json; devs=[d for r in json.loads(sys.stdin.read())['devices'].values() for d in r if d['state']=='Booted']; print(devs[0]['udid'])")
```

Start `idb log` in the background, filtering for FlowVerify markers:
```bash
idb log --udid $UDID > /tmp/agentic/flow-recorder/<timestamp>/idb_log.txt 2>&1 &
LOG_PID=$!
```

Wait 2 seconds for the log stream to start.

### Step 5.3: Run the Maestro flow

```bash
maestro test tests/maestro/flows/generated/<flow_name>.yaml
```

Record the exit code. Maestro exit 0 = pass, non-zero = fail.

### Step 5.4: Stop log capture and verify

```bash
kill $LOG_PID 2>/dev/null || true
```

Read the log file and check for FlowVerify markers:
```bash
grep '\[FlowVerify:' /tmp/agentic/flow-recorder/<timestamp>/idb_log.txt
```

Compare against the expected sequence:
- **All markers present and in order** → Log verification PASS
- **Some markers missing** → Log verification PARTIAL — report which are missing
- **Markers out of order** → Log verification WARN — report actual vs expected order
- **No markers found** → Log verification FAIL — the flow didn't trigger the instrumented code paths

---

## Phase 6: Cleanup & Report

### Step 6.1: Remove injected logs

Find all files with the `// [FlowVerify]` marker and remove those lines:

Use Grep to find all files containing `// [FlowVerify]`:
```
Grep for: // \[FlowVerify\]
In: **/*.swift
```

For each file, use the Edit tool to remove lines containing `// [FlowVerify]`. Read the file first, identify all lines with the marker, and remove them.

### Step 6.2: Final report

Print a structured report:

```
Flow Recorder Results
=====================
Flow: <flow description>
Date: <timestamp>

EXPLORATION:
  Status: PASS
  Steps recorded: <N>
  Action log: /tmp/agentic/flow-recorder/<timestamp>/action_log.json

MAESTRO FLOW:
  Status: PASS | FAIL
  Generated: tests/maestro/flows/generated/<flow_name>.yaml
  Maestro output: <pass/fail details>

LOG VERIFICATION:
  Status: PASS | PARTIAL | FAIL
  Expected markers: <N>
  Found markers: <N>
  Missing: [list of missing markers, if any]
  Order: CORRECT | OUT_OF_ORDER

CLEANUP:
  Injected lines removed: <N> lines from <N> files
  Source code restored: YES

ARTIFACTS:
  Maestro flow (kept): tests/maestro/flows/generated/<flow_name>.yaml
  Action log (temp): /tmp/agentic/flow-recorder/<timestamp>/action_log.json
  Log capture (temp): /tmp/agentic/flow-recorder/<timestamp>/idb_log.txt
```

---

## Error Recovery

| Failure | Recovery |
|---|---|
| ui-explorer sub-agent fails | Report which sub-goal failed, stop pipeline |
| Action log empty or missing | Report exploration produced no actions, stop |
| No Swift files found for a11y IDs | Skip log injection for those steps, warn, continue |
| `build_and_launch` fails | Clean up injected logs immediately, report build error, stop |
| Maestro flow fails | Report failing step, still check partial log verification |
| `idb log` produces no output | Warn about log capture failure, rely on Maestro pass/fail only |
| Log markers missing | Report as partial verification, flow may still be correct |
```

**Step 2: Verify the frontmatter is valid**

Read back the file and confirm:
- `description:` field is present and contains trigger phrases
- `examples:` has 3 entries with user/assistant pairs
- `allowed-tools:` includes `Task, Bash, Read, Write, Edit, Glob, Grep`
- `model: sonnet` is set

**Step 3: Commit**

```bash
git add agents/flow-recorder.md
git commit -m "feat: add flow-recorder agent for end-to-end UI flow recording"
```

---

### Task 2: Update CLAUDE.md to document the new agent

**Files:**
- Modify: `CLAUDE.md:47` (the Agents line in Plugin Components)

**Step 1: Update the Agents line**

Change line 47 from:
```markdown
- **Agents** (`agents/`): `ui-explorer.md` (ORAV loop via idb, model: sonnet) and `regression-runner.md` (Maestro suite runner, model: sonnet)
```
to:
```markdown
- **Agents** (`agents/`): `ui-explorer.md` (ORAV loop via idb, model: sonnet), `regression-runner.md` (Maestro suite runner, model: sonnet), and `flow-recorder.md` (end-to-end flow recording + verification, model: sonnet)
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add flow-recorder agent to CLAUDE.md architecture section"
```
