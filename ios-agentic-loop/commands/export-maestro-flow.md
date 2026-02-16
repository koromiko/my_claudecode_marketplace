---
description: Export a recorded idb exploration action log as a Maestro YAML flow file. Converts tap/text/swipe actions to Maestro steps with optimal selectors.
argument-hint: <action-log-path> [--output <flow-path>]
allowed-tools: Bash, Read, Write
---

# Export Maestro Flow

Convert an idb exploration action log to a Maestro YAML flow.

## Workflow

### Step 1: Read the Action Log

Read the JSON action log file provided as `$1` argument. The log contains entries like:

```json
[
  { "step": 1, "action": "tap", "x": 66, "y": 142, "label": "Home", "type": "Button", "a11y_id": "tab_home" }
]
```

### Step 2: Convert to Maestro YAML

Apply conversion rules (see `${CLAUDE_PLUGIN_ROOT}/skills/idb-exploration/references/flow-recording.md`):

- **Selector priority**: `id:` > `text:` > `point:`
- If `a11y_id` is present, use `tapOn: { id: "..." }`
- If only `label` is present, use `tapOn: { text: "..." }`
- If neither, convert pixel coords to percentages: `tapOn: { point: "X%,Y%" }`
- Convert `text` actions to `inputText:`
- Add `assertVisible:` for verified steps
- Add flow frontmatter with appId, name, tags

### Step 3: Write Output

Write the YAML to the output path (default: `tests/maestro/flows/generated/<flow_name>.yaml`).

### Step 4: Validate

Run the generated flow to verify it works:

```bash
maestro test <output_path>
```

Report pass/fail.
