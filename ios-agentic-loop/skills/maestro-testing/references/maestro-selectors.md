# Maestro Selectors Reference

## Selector Types

### `id:` -- Accessibility Identifier (Recommended)

Matches the element's `accessibilityIdentifier`. Most stable selector.

```yaml
- tapOn:
    id: "login_button_submit"

- assertVisible:
    id: "home_content_section"
```

**Advantages**: Survives text changes, localization, layout shifts.
**Requires**: `accessibilityIdentifier` set in code.

### `text:` -- Visible Text

Matches the element's visible text or `accessibilityLabel`.

```yaml
- tapOn:
    text: "Submit"

- assertVisible:
    text: "Welcome back"
```

**Advantages**: Human-readable, no code changes needed.
**Disadvantages**: Breaks on localization, text rewording.

### `containsText:` -- Partial Text Match

```yaml
- assertVisible:
    containsText: "Welcome"    # Matches "Welcome back, John"
```

### `point:` -- Percentage Coordinates

Percentage-based coordinates relative to screen size. Last resort.

```yaml
- tapOn:
    point: "50%,90%"    # Center horizontally, near bottom
```

**Disadvantages**: Fragile across screen sizes, orientations.

## Combining Selectors

### `index:` for Duplicates

When multiple elements match, use `index:` to select one:

```yaml
# Tap the first "Delete" button
- tapOn:
    text: "Delete"
    index: 0

# Tap the second one
- tapOn:
    text: "Delete"
    index: 1
```

### Relative Positioning

Position elements relative to others:

```yaml
# Tap "Edit" below the "Profile" heading
- tapOn:
    text: "Edit"
    below:
      text: "Profile"

# Tap "Save" above the "Cancel" button
- tapOn:
    text: "Save"
    above:
      text: "Cancel"
```

Available: `below:`, `above:`, `leftOf:`, `rightOf:`

## Priority Guide

Always prefer selectors in this order:

| Priority | Selector | Stability | Readability |
|----------|----------|-----------|-------------|
| 1 | `id:` | Highest | Medium |
| 2 | `text:` | Medium | Highest |
| 3 | `text:` + `index:` | Medium | Medium |
| 4 | `text:` + relative | Medium | Good |
| 5 | `point:` | Lowest | Lowest |

## Localization Impact

Apps with multiple languages must use `id:` selectors:

```yaml
# BREAKS in Japanese:
- tapOn:
    text: "Settings"

# WORKS in all languages:
- tapOn:
    id: "tab_settings"
```

## Common UI Patterns

### Tab Bar

```yaml
- tapOn:
    id: "tab_home"
- tapOn:
    id: "tab_profile"
```

### Grid/Collection

```yaml
- tapOn:
    id: "grid_cell_42"
```

### Form

```yaml
- tapOn:
    id: "form_field_email"
- inputText: "user@example.com"
- tapOn:
    id: "form_field_password"
- inputText: "password123"
- tapOn:
    id: "form_button_submit"
```

### List with Scroll

```yaml
- scrollUntilVisible:
    element:
      id: "list_item_99"
    direction: DOWN
- tapOn:
    id: "list_item_99"
```
