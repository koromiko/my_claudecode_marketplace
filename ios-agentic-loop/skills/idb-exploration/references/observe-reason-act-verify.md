# Observe-Reason-Act-Verify (ORAV) Methodology

## Overview

The ORAV loop is the core cycle of the agentic iOS testing system. Each iteration captures the current UI state, reasons about what action to take, executes it, and verifies the outcome.

## Phase 1: Observe

Capture the current state through dual-channel observation:

```bash
# Visual capture -- screenshot for LLM vision analysis
idb screenshot /tmp/agentic/step_NNN.png

# Structural capture -- accessibility element tree
idb ui describe-all --format json > /tmp/agentic/step_NNN_a11y.json
```

### Accessibility JSON Structure

```json
[
  {
    "AXLabel": "Scene Setup",
    "AXFrame": "{{16, 120}, {100, 44}}",
    "AXType": "Button",
    "AXEnabled": true,
    "AXValue": null
  }
]
```

### Why Dual-Channel

| Channel | Provides | Misses |
|---------|----------|--------|
| Screenshot | Visual layout, colors, images, loading states | Precise coordinates, element metadata |
| Accessibility tree | Exact coordinates, types, labels, enabled state | Visual appearance, spatial relationships |

Together they form a complete picture of the screen state.

## Phase 2: Reason

Analyze the observation data to decide the next action:

### Decision Process

1. **Identify current screen** from element labels and screenshot context
2. **Evaluate progress** against the goal or exploration coverage
3. **Select target element** using priority heuristics
4. **Compute tap coordinates** from AXFrame:
   ```
   tap_x = frame.x + (frame.width / 2)
   tap_y = frame.y + (frame.height / 2)

   # For element at {{20, 280}, {170, 60}}:
   tap_x = 20 + (170 / 2) = 105
   tap_y = 280 + (60 / 2) = 310
   ```
5. **Decide action type**: tap, text input, swipe, or key press
6. **Output structured decision**:

```json
{
  "reasoning": "The 'Submit' button is visible and enabled. Tapping it should submit the form.",
  "action": "tap",
  "coordinates": { "x": 105, "y": 310 },
  "element_label": "Submit",
  "expected_outcome": "Form submitted, success message appears"
}
```

### Decision Heuristics (Priority Order)

1. **Recovery first**: If an error dialog or unexpected state is detected, recover before continuing
2. **Goal progress**: Take actions that advance toward the current goal/sub-goal
3. **Coverage gaps**: If no immediate goal action is obvious, explore untested areas
4. **Regression check**: Revisit previously working flows to detect regressions

## Phase 3: Act

Execute the decided action:

```bash
# Tap
idb ui tap 105 310

# Text input
idb ui text "user@example.com"

# Swipe (scroll down)
idb ui swipe 200 500 200 200 --duration 0.3

# Combined: tap field, then type
idb ui tap 200 150
sleep 0.3
idb ui text "Hello world"

# Press key
idb ui key 1 escape
```

**Timing**: Wait 300-500ms after each action for UI animations to settle before verifying. SwiftUI apps may need 600-800ms.

## Phase 4: Verify

Confirm the action had the expected effect:

```bash
idb screenshot /tmp/agentic/step_NNN_verify.png
idb ui describe-all --format json > /tmp/agentic/step_NNN_verify_a11y.json
```

Compare before/after:

```json
{
  "verification": "success",
  "observation": "The form was submitted. A success message is now visible.",
  "state_change": "Form submitted, success banner appeared",
  "next_action": "continue_exploring"
}
```

### On Failure

- **Retry** with adjusted coordinates (element may have shifted)
- **Try alternative** approach (different element, different path)
- **Report** the issue and move to next goal

## Loop Lifecycle

```
START
  |
  v
[Build & Install App]
  |
  v
[Launch App]
  |
  v
+---> [OBSERVE] -- screenshot + describe-all
|         |
|         v
|     [REASON] -- analyze state, decide action
|         |
|         v
|     [ACT] -- idb tap/text/swipe
|         |
|         v
|     [VERIFY] -- screenshot + describe-all, confirm outcome
|         |
|         +---> [Goal Complete?] -- YES --> [Export to Maestro]
|         |                                       |
|         v                                       v
|     [Max Steps?] -- YES --> [Report Results]   [DONE]
|         |
|         NO
|         |
+----<----+
```

## State Tracking

Maintain a running state model (reconstructed from observations, not pure memory):

```json
{
  "current_screen": "home",
  "steps_taken": 12,
  "screens_visited": ["home", "settings", "profile"],
  "errors_encountered": [],
  "coverage": {
    "screens_tested": 3,
    "elements_interacted": 15,
    "paths_explored": 8
  }
}
```

## Operating Modes

### Goal-Directed

```yaml
name: Login Flow
goal: "Log in with test credentials and verify authenticated state"
preconditions:
  - app_launched: true
  - logged_in: false
success_criteria:
  - logged_in: true
  - home_screen_visible: true
max_steps: 20
```

### Exploration

No specific goal. Systematically discover all reachable UI states:
- Identify all tappable elements on the current screen
- Try each one, recording the result
- Navigate deeper into discovered screens
- Track explored vs unexplored paths
- Prioritize unexplored paths
