#!/bin/bash
# PostToolUse hook: soft-check accessibility identifiers in Swift view files.
# Always approves (never blocks). Emits a message only when interactive UI
# elements appear to lack .accessibilityIdentifier() modifiers.
#
# Input (stdin): JSON with tool_input.file_path
# Output (stdout): JSON with decision "approve" and optional message

APPROVE='{"decision":"approve"}'

# Read hook payload
input=$(cat)

file_path=$(echo "$input" | /usr/bin/python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input',{}).get('file_path',''))
except Exception:
    print('')
" 2>/dev/null)

# Guard: no file path or file gone
if [[ -z "$file_path" || ! -f "$file_path" ]]; then
  echo "$APPROVE"
  exit 0
fi

# Guard: not a Swift file (extra safety beyond filePattern)
if [[ "$file_path" != *.swift ]]; then
  echo "$APPROVE"
  exit 0
fi

# --- Static analysis ---

# SwiftUI interactive elements
SWIFTUI_PATTERN='Button\(|TextField\(|SecureField\(|Toggle\(|Slider\(|Stepper\(|DatePicker\(|Picker\(|NavigationLink\(|Link\(|\.onTapGesture|Menu\('
# UIKit interactive elements
UIKIT_PATTERN='UIButton|UITextField|UISwitch|UISlider|UIStepper|UIDatePicker|UISegmentedControl'

COMBINED="($SWIFTUI_PATTERN|$UIKIT_PATTERN)"

interactive_count=$(grep -cE "$COMBINED" "$file_path" 2>/dev/null) || interactive_count=0
a11y_count=$(grep -c '\.accessibilityIdentifier(' "$file_path" 2>/dev/null) || a11y_count=0

# No interactive elements → nothing to check
if [[ "$interactive_count" -eq 0 ]]; then
  echo "$APPROVE"
  exit 0
fi

# All covered → silent approve
if [[ "$a11y_count" -ge "$interactive_count" ]]; then
  echo "$APPROVE"
  exit 0
fi

# Gap detected → approve with advisory message
missing=$((interactive_count - a11y_count))
basename=$(basename "$file_path")

cat <<EOF
{"decision":"approve","reason":"[a11y soft-check] ${basename}: found ${interactive_count} interactive element(s) but only ${a11y_count} .accessibilityIdentifier() call(s). ~${missing} may be uncovered. Convention: {scope}_{type}_{name}."}
EOF
exit 0
