# idb CLI Command Reference

## Simulator Management

### List Targets

```bash
idb list-targets
# Output: UDID | Name | State | OS | Architecture
```

### Connect to Simulator

```bash
idb connect <UDID>
# Required before using --udid flag on other commands
# Without connect: auto-detection works for the first booted simulator
```

## Observation Commands

### Screenshot

```bash
idb screenshot /tmp/screenshot.png
idb screenshot --udid <UDID> /tmp/screenshot.png
```

Returns a PNG file. Typical latency: 200-500ms.

### Describe All (Accessibility Tree)

```bash
idb ui describe-all --format json
idb ui describe-all --udid <UDID> --format json
```

Returns a flat JSON array of accessibility elements:

```json
[
  {
    "AXLabel": "Submit",
    "AXFrame": "{{120, 680}, {180, 44}}",
    "AXType": "Button",
    "AXEnabled": true,
    "AXValue": null,
    "AXUniqueId": "form_button_submit"
  }
]
```

**Key fields:**
- `AXLabel` -- visible text or accessibility label
- `AXFrame` -- bounding rect as `{{x, y}, {width, height}}`
- `AXType` -- element type (Button, StaticText, TextField, etc.)
- `AXEnabled` -- whether the element is interactive
- `AXValue` -- current value (for text fields, switches)
- `AXUniqueId` -- accessibility identifier (if set)

**Note**: Returns a **flat list**, not a hierarchy. No parent-child relationships. Use spatial reasoning (frame containment) to infer structure.

Typical latency: 500ms-5s depending on element count.

## Action Commands

### Tap

```bash
idb ui tap <x> <y>
idb ui tap 200 400
```

Tap at exact pixel coordinates. Compute center from AXFrame:
```
x = frame.x + frame.width / 2
y = frame.y + frame.height / 2
```

### Text Input

```bash
idb ui text "<string>"
idb ui text "user@example.com"
```

Types into the currently focused text field. Tap a field first to focus it.

### Swipe

```bash
idb ui swipe <x1> <y1> <x2> <y2> --duration <seconds>
idb ui swipe 200 500 200 200 --duration 0.3    # Swipe up (scroll down)
idb ui swipe 200 200 200 500 --duration 0.3    # Swipe down (scroll up)
idb ui swipe 300 400 50 400 --duration 0.3     # Swipe left
```

### Key Press

```bash
idb ui key 1 escape       # Press Escape (dismiss keyboard)
idb ui key 1 return        # Press Return
```

## App Lifecycle

### Launch

```bash
idb launch <bundle_id>
idb launch com.example.myapp
```

### Terminate

```bash
idb terminate <bundle_id>
idb terminate com.example.myapp
```

### Install

```bash
idb install --bundle-path /path/to/App.app
```

### Check Running Apps

```bash
idb list-apps --running
```

## Performance Notes

| Command | Typical Latency | Notes |
|---------|----------------|-------|
| `screenshot` | 200-500ms | Fast, reliable |
| `describe-all` | 500ms-5s | Slower with more elements |
| `tap` | 50-200ms | Very fast |
| `text` | 100-500ms | Depends on string length |
| `swipe` | 200-500ms | Duration parameter adds to total |
| `launch` | 1-3s | Cold launch is slower |

## Common Patterns

### Tap a text field and type

```bash
idb ui tap 200 300       # Focus the field
sleep 0.3                # Wait for keyboard
idb ui text "Hello"      # Type text
```

### Scroll and find element

```bash
for i in {1..5}; do
    if idb ui describe-all --format json | grep -q "target_element"; then
        break
    fi
    idb ui swipe 200 500 200 200 --duration 0.3
    sleep 0.5
done
```

### Wait for element to appear

```bash
for i in {1..10}; do
    if idb ui describe-all --format json | grep -q "expected_id"; then
        echo "Element found"
        break
    fi
    sleep 0.5
done
```
