---
name: accessibility-testing
description: Use this skill when adding accessibility identifiers to iOS views, auditing existing accessibility coverage, preparing an iOS app for idb or Maestro testing, or when a user mentions "accessibility identifiers", "a11y", "testability", or "UI testing prerequisites".
version: 1.0.0
context: fork
---

# Accessibility Testing Skill

Accessibility identifiers are the foundation of reliable automated iOS testing. Without them, tools like `idb` and Maestro cannot find or interact with UI elements consistently. This skill covers how to add, name, audit, and maintain accessibility identifiers across SwiftUI and UIKit codebases.

## Why Accessibility Identifiers Matter

### For Automated Testing
- **idb** (`idb ui describe-all`) uses the accessibility hierarchy to discover UI elements. Elements without `accessibilityIdentifier` are invisible to coordinate-free interaction.
- **Maestro** `id:` selectors are the most stable way to target elements. They survive layout changes, text changes, and localization — unlike `text:` or coordinate-based selectors.
- **XCUITest** uses `app.buttons["identifier"]` to locate elements. Without identifiers, tests rely on fragile index-based or label-based queries.

### For Real Users
- VoiceOver reads `accessibilityLabel` to describe elements to blind and low-vision users.
- Switch Control uses the accessibility tree to present actionable elements.
- Proper accessibility benefits roughly 15-20% of users who rely on assistive technology.

### Key Distinction
| Property | Purpose | Localized? | User-Facing? |
|----------|---------|------------|--------------|
| `accessibilityIdentifier` | Testing / automation | No | No |
| `accessibilityLabel` | VoiceOver description | Yes | Yes |
| `accessibilityHint` | VoiceOver usage hint | Yes | Yes |
| `accessibilityTraits` | Element role/behavior | N/A | Yes (implicit) |

**Rule**: Every interactive element needs an `accessibilityIdentifier` for testing. Every user-facing element also needs an `accessibilityLabel` for VoiceOver.

## Naming Convention

Use the `{scope}_{type}_{name}` pattern consistently:

```
login_button_submit
login_field_email
login_field_password
settings_toggle_notifications
composer_card_scene_setup
keyboard_tab_characters
```

### Scope
The screen, feature, or logical area: `login`, `settings`, `composer`, `keyboard`, `profile`, `onboarding`.

### Type
The element kind: `button`, `field`, `tab`, `card`, `cell`, `label`, `toggle`, `picker`, `section`, `image`, `scroll`, `list`.

### Name
A descriptive, stable identifier: `submit`, `email`, `save`, `dark_mode`, `scene_setup`.

### Dynamic Identifiers
For repeated elements in lists or grids, append the unique identifier:

```swift
.accessibilityIdentifier("composer_card_\(block.id)")
.accessibilityIdentifier("category_tab_\(category.slug)")
```

See `references/naming-conventions.md` for the full naming reference.

## SwiftUI Patterns

### Basic Usage

```swift
Button("Save") { save() }
    .accessibilityIdentifier("settings_button_save")

TextField("Email", text: $email)
    .accessibilityIdentifier("login_field_email")

Toggle("Dark Mode", isOn: $isDarkMode)
    .accessibilityIdentifier("settings_toggle_dark_mode")
```

### Common Pitfalls

**1. `.buttonStyle(.plain)` hides button role**

```swift
// BAD: The button may lose its .button trait
Button { action() } label: {
    HStack { Image(systemName: "star"); Text("Favorite") }
}
.buttonStyle(.plain)

// FIX: Add explicit trait and identifier
Button { action() } label: {
    HStack { Image(systemName: "star"); Text("Favorite") }
}
.buttonStyle(.plain)
.accessibilityIdentifier("detail_button_favorite")
.accessibilityAddTraits(.isButton)
```

**2. Group/ForEach hiding children**

```swift
// BAD: ForEach children may be grouped
ForEach(items) { item in
    Text(item.name)
}

// FIX: Add identifiers to each child
ForEach(items) { item in
    Text(item.name)
        .accessibilityIdentifier("list_cell_\(item.id)")
}
```

**3. Sheet/popover separate hierarchy**

```swift
// Sheets create a separate accessibility hierarchy
.sheet(isPresented: $showSettings) {
    // These identifiers exist in a DIFFERENT tree than the parent
    SettingsView()
        .accessibilityIdentifier("settings_sheet_root")
}
```

**4. Image-only buttons need labels**

```swift
Button { dismiss() } label: {
    Image(systemName: "xmark")
}
.accessibilityIdentifier("modal_button_close")
.accessibilityLabel("Close")  // VoiceOver needs this
```

See `references/swiftui-identifiers.md` for comprehensive SwiftUI patterns.

## UIKit Patterns

### Basic Usage

```swift
let saveButton = UIButton(type: .system)
saveButton.accessibilityIdentifier = "settings_button_save"
saveButton.isAccessibilityElement = true

let emailField = UITextField()
emailField.accessibilityIdentifier = "login_field_email"
```

### Custom Views

```swift
class BlockView: UIView {
    override init(frame: CGRect) {
        super.init(frame: frame)
        isAccessibilityElement = true
        accessibilityTraits = .button
    }

    func configure(with block: Block) {
        accessibilityIdentifier = "keyboard_card_\(block.id)"
        accessibilityLabel = block.title
    }
}
```

See `references/uikit-identifiers.md` for comprehensive UIKit patterns.

## Audit Workflow

### Step 1: Capture Current State

```bash
# Take a screenshot for visual reference
idb screenshot --udid booted /tmp/audit_screenshot.png

# Dump the full accessibility hierarchy
idb ui describe-all --udid booted --format json > /tmp/a11y_tree.json
```

### Step 2: Identify Gaps

Parse the JSON output and look for:
- Elements with `accessibilityIdentifier: null` that are interactive
- Buttons without identifiers
- Text fields without identifiers
- Custom views that should be accessibility elements but aren't in the tree

### Step 3: Search the Codebase

```bash
# Find views missing identifiers
grep -rn "Button\|TextField\|Toggle\|NavigationLink" --include="*.swift" | grep -v accessibilityIdentifier

# Find existing identifiers for naming consistency
grep -rn "accessibilityIdentifier" --include="*.swift"
```

### Step 4: Add Identifiers by Priority

**Priority 1 — Interactive elements (must have)**:
- Buttons, links, toggles, pickers, text fields, sliders
- Tappable cards or cells
- Navigation controls (back, close, tabs)

**Priority 2 — Containers and sections**:
- ScrollView, List, TabView
- Section headers
- Modal/sheet root views

**Priority 3 — Informational elements**:
- Status labels, error messages
- Progress indicators
- Badges, counts

**Priority 4 — Decorative (skip unless needed)**:
- Decorative images, dividers, spacers
- Background views

### Step 5: Verify

```bash
# Re-run describe-all and confirm new identifiers appear
idb ui describe-all --udid booted --format json | python3 -c "
import json, sys
tree = json.load(sys.stdin)
def count_ids(node, total=0, with_id=0):
    if node.get('AXUniqueId') or node.get('identifier'):
        with_id += 1
    total += 1
    for child in node.get('children', []):
        t, w = count_ids(child, 0, 0)
        total += t
        with_id += w
    return total, with_id
t, w = count_ids(tree)
print(f'Total elements: {t}, With identifier: {w}, Coverage: {w/t*100:.1f}%')
"
```

## Use the `/audit-accessibility` Command

Run `/audit-accessibility` to perform an automated audit of the currently running simulator app. It will:

1. Take a screenshot
2. Dump the accessibility hierarchy
3. Identify elements missing identifiers
4. Search your codebase for the corresponding views
5. Suggest identifiers using the naming convention
6. Report findings with file paths and priority order

## Reference Files

- `references/swiftui-identifiers.md` — Comprehensive SwiftUI accessibility identifier patterns
- `references/uikit-identifiers.md` — Comprehensive UIKit accessibility patterns
- `references/naming-conventions.md` — Full naming convention reference with examples and anti-patterns
