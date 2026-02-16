---
name: idb-exploration
description: Use this skill when performing autonomous UI exploration of an iOS app, using the idb observe-reason-act-verify loop, analyzing accessibility trees, or when a user mentions "idb", "explore the app", "agentic testing", "ORAV loop", "observe-reason-act-verify", or "autonomous UI testing".
version: 1.0.0
context: fork
---

# idb Exploration — Observe-Reason-Act-Verify Loop

This skill enables autonomous UI exploration of iOS apps running in the Simulator using **idb** (iOS Development Bridge) and a structured **ORAV loop** (Observe → Reason → Act → Verify).

## When to Use This Skill

- Exploratory testing of an iOS app without pre-written test scripts
- Edge case discovery by systematically navigating all UI paths
- Accessibility validation (missing labels, untappable elements, broken VoiceOver)
- Generating deterministic Maestro flows from exploratory sessions
- Verifying UI state after code changes
- Bug reproduction via step-by-step recorded actions

## Prerequisites

- **idb** installed (`brew install idb-companion`)
- A booted iOS Simulator (`xcrun simctl boot <UDID>`)
- The target app installed on the simulator
- A working directory for screenshots (default: `/tmp/agentic/`)

## The ORAV Loop

The core methodology is a four-phase cycle that repeats until the goal is achieved or exploration is complete:

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ OBSERVE │────▶│ REASON  │────▶│   ACT   │────▶│ VERIFY  │
│         │     │         │     │         │     │         │
│ screen- │     │ identify │     │ tap,    │     │ re-     │
│ shot +  │     │ state,   │     │ type,   │     │ observe │
│ a11y    │     │ plan     │     │ swipe   │     │ + diff  │
│ tree    │     │ action   │     │         │     │         │
└─────────┘     └─────────┘     └─────────┘     └────┬────┘
     ▲                                                │
     └────────────────────────────────────────────────┘
                    loop until done
```

### Phase 1: Observe

Capture the current state through **dual-channel observation**:

1. **Screenshot** — Visual context of what the user sees
   ```bash
   idb screenshot /tmp/agentic/step_001.png
   ```

2. **Accessibility tree** — Precise element data with coordinates
   ```bash
   idb ui describe-all --format json
   ```

Both channels are required because:
- Screenshots show visual layout, colors, images, and spatial relationships that accessibility data misses
- Accessibility trees provide exact coordinates, element types, labels, and enabled states that screenshots can't convey programmatically
- Together they form a complete picture of the screen state

### Phase 2: Reason

Analyze the observation data to decide the next action:

1. **Identify current screen** from element labels and screenshot context
2. **Evaluate progress** against the goal or exploration coverage
3. **Select target element** based on priority heuristics
4. **Compute tap coordinates** from AXFrame: `tap_x = frame.x + frame.width/2`, `tap_y = frame.y + frame.height/2`
5. **Decide action type**: tap, text input, swipe, or key press
6. **Output structured decision** with rationale

### Phase 3: Act

Execute the chosen action via idb:

| Action | Command |
|--------|---------|
| Tap | `idb ui tap <x> <y>` |
| Type text | `idb ui text "<string>"` |
| Swipe | `idb ui swipe <x1> <y1> <x2> <y2> --duration 0.3` |
| Press key | `idb ui key 1 escape` |

Wait **300–500ms** after each action for animations to settle.

### Phase 4: Verify

Confirm the action had the expected effect:

1. Re-observe (screenshot + describe-all)
2. Compare before/after states
3. Determine success or failure
4. On failure: retry with adjusted coordinates, try alternative approach, or report the issue

## Operating Modes

### Goal-Directed Mode

Given a specific scenario with preconditions and success criteria:

```yaml
goal: "Complete the user login flow"
preconditions:
  - App is on the login screen
  - Valid test credentials available
success_criteria:
  - User is logged in
  - Home screen is visible
```

The agent pursues the goal through targeted ORAV cycles until success criteria are met or max steps are reached.

### Exploration Mode

Systematic discovery of all reachable UI states:

- Track visited screens and elements
- Prioritize unexplored paths
- Build a coverage map of the app
- Record all actions for potential Maestro export

## Key idb Commands

| Command | Purpose |
|---------|---------|
| `idb screenshot <path>` | Capture current screen |
| `idb ui describe-all --format json` | Get accessibility tree |
| `idb ui tap <x> <y>` | Tap at coordinates |
| `idb ui text "<string>"` | Type text |
| `idb ui swipe <x1> <y1> <x2> <y2>` | Swipe gesture |
| `idb launch <bundle_id>` | Launch app |
| `idb terminate <bundle_id>` | Kill app |

## Known Limitations

1. **Flat accessibility list**: `describe-all` returns a flat array, not a hierarchy — you must infer parent-child relationships from frame containment
2. **Missing nested elements**: Some deeply nested elements may not appear in the accessibility tree; use screenshots to identify them
3. **Coordinate-only tapping**: idb requires exact pixel coordinates; there's no "tap element by label" — you must compute center points from AXFrame
4. **idb_companion age**: The idb companion can occasionally hang or lose connection; restart it if commands time out
5. **Animation timing**: Fast-moving animations may cause describe-all to return transitional states; add delays after triggering animations

## Reference Files

For detailed methodology, commands, error handling, and flow recording:

- `references/observe-reason-act-verify.md` — Full ORAV methodology and state tracking
- `references/idb-command-reference.md` — Complete idb CLI reference with examples
- `references/error-recovery.md` — Error types, detection, and recovery strategies
- `references/flow-recording.md` — Action log format and Maestro export rules
