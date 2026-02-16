# Flow Recording and Maestro Export

## Action Log Format

During exploration, every action is recorded in a JSON action log:

```json
[
  {
    "step": 1,
    "action": "tap",
    "x": 66,
    "y": 142,
    "label": "Home",
    "type": "Button",
    "a11y_id": "tab_home",
    "timestamp": "2026-02-16T14:30:22Z",
    "verified": true
  },
  {
    "step": 2,
    "action": "tap",
    "x": 105,
    "y": 310,
    "label": "Item Card",
    "type": "StaticText",
    "a11y_id": "item_card_42",
    "timestamp": "2026-02-16T14:30:24Z",
    "verified": true
  },
  {
    "step": 3,
    "action": "text",
    "text": "Test description",
    "target_label": "Description",
    "target_a11y_id": "form_field_description",
    "timestamp": "2026-02-16T14:30:26Z",
    "verified": true
  }
]
```

## Conversion Rules

| idb Action | Maestro Equivalent | Notes |
|-----------|-------------------|-------|
| `tap` on element with `a11y_id` | `tapOn: { id: "a11y_id" }` | Most stable selector |
| `tap` on element with `label` only | `tapOn: { text: "label" }` | Prefer text over coords |
| `tap` on unlabeled element | `tapOn: { point: "X%,Y%" }` | Convert to percentages |
| `text` input | `inputText: "string"` | Direct text input |
| `swipe` up/down | `scroll` | Direction inferred |
| `swipe` left/right | `swipe: { direction: LEFT }` | Horizontal swipe |
| Verification step | `assertVisible:` or `assertWithAI:` | Assert expected state |

## Selector Priority

When converting, choose the most stable selector available:

1. **`id:`** -- If `a11y_id` is present in the action log
2. **`text:`** -- If `label` is present but no `a11y_id`
3. **`point:`** -- Last resort, convert pixel coordinates to percentage:
   ```
   x_percent = (x / screen_width) * 100
   y_percent = (y / screen_height) * 100
   ```

## Generated Maestro YAML

```yaml
appId: com.example.myapp
name: Item Selection Flow
tags:
  - regression
  - generated
---
# Generated from agentic exploration on 2026-02-16
# Source: tests/agentic/results/run_20260216_143022/

- launchApp:
    appId: "com.example.myapp"
    clearState: true

# Navigate to Home tab
- tapOn:
    id: "tab_home"

# Select an item
- tapOn:
    id: "item_card_42"

# Verify item is selected
- assertVisible:
    id: "item_detail"

# Enter description
- tapOn:
    id: "form_field_description"
- inputText: "Test description"
```

## Post-Export Validation

Always run the exported flow immediately to verify it works deterministically:

```bash
maestro test tests/maestro/flows/generated/item_selection.yaml
```

If the flow fails:
1. Check which step failed
2. Review the selector (is the element still accessible?)
3. Adjust the selector or add missing accessibility identifiers
4. Re-run to confirm
