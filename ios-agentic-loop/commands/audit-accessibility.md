---
description: Audit accessibility identifier coverage for an iOS app running in the simulator. Compares idb describe-all output against visual elements to find missing identifiers.
allowed-tools: Bash, Read, Glob, Grep
---

# Audit Accessibility Identifiers

Perform a comprehensive accessibility audit of the currently running iOS app.

## Workflow

### Step 1: Capture Current State

```bash
mkdir -p /tmp/agentic
idb screenshot /tmp/agentic/audit_screenshot.png
idb ui describe-all --format json > /tmp/agentic/audit_a11y.json
```

### Step 2: Analyze the Accessibility Tree

Read `/tmp/agentic/audit_a11y.json` and identify:
- Elements with `AXType` of Button, TextField, or other interactive types that lack `AXUniqueId` (accessibility identifier)
- Interactive elements with only `AXLabel` but no identifier
- Elements that `idb describe-all` may be missing (compare count against screenshot visual elements)

### Step 3: Search the Codebase

Search for Swift view files that create interactive elements without accessibility identifiers:

```bash
# Find interactive views without identifiers
grep -rn "Button\|TextField\|TextEditor\|Toggle\|NavigationLink\|tapGesture" --include="*.swift" | grep -v accessibilityIdentifier | grep -v "test\|Test\|spec\|Spec"
```

### Step 4: Report Findings

For each missing identifier, report:
1. **File path and line number** where the element is created
2. **Element type** (Button, TextField, custom view, etc.)
3. **Suggested identifier** following `{scope}_{type}_{name}` convention
4. **Priority** (P0 for interactive, P1 for navigation, P2 for containers)

### Step 5: Show the Screenshot

Display the screenshot at `/tmp/agentic/audit_screenshot.png` so the user can visually verify which elements need identifiers.

Prioritize interactive elements (buttons, fields, tappable cards) over decorative elements (images, dividers).
