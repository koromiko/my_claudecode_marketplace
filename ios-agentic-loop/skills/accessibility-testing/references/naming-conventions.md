# Accessibility Identifier Naming Conventions

## Pattern

```
{scope}_{type}_{name}
```

### Scope

| Scope | Usage |
|-------|-------|
| `login` | Login/authentication |
| `signup` | Registration |
| `settings` | Settings/preferences |
| `profile` | User profile |
| `home` | Main/home screen |
| `detail` | Detail view |
| `composer` | Content composition |
| `library` | Content browser |
| `search` | Search interface |
| `keyboard` | Keyboard extension (reserved) |
| `modal` | Modal/sheet/popup |
| `nav` | Navigation elements |

### Type

| Type | Elements |
|------|----------|
| `button` | Buttons, tappable views |
| `field` | Text fields, text editors |
| `toggle` | Switches, toggles |
| `tab` | Tab bar items, segment tabs |
| `card` | Tappable card views |
| `cell` | Collection/table cells |
| `label` | Static text (only when targeted by assertions) |
| `section` | Content sections |
| `picker` | Pickers, dropdowns |
| `scroll` | Scroll views |
| `list` | List/table views |
| `grid` | Grid/collection views |

### Name

A short, descriptive name: `save`, `email`, `dark_mode`, `scene_setup`

## Dynamic Identifiers

```
block_card_42              # Entity ID
category_tab_motion        # Slug name
list_row_user_123          # Composite
```

Prefer stable IDs over array indices (IDs survive reordering).

## Anti-Patterns

| Bad | Why | Good |
|-----|-----|------|
| `btn1` | Not descriptive | `login_button_submit` |
| `UUID-string` | Unstable, unreadable | `item_card_\(item.id)` |
| `the_big_save_button` | Too long | `form_button_save` |
| `Save` | Conflicts with label | `settings_button_save` |
| Same ID on multiple views | Ambiguous | Unique per instance |

## Localization Note

`accessibilityIdentifier` is **never localized**. This is why `id:` selectors are the most stable:

```yaml
# Breaks on locale change:
- tapOn:
    text: "Scene Setup"

# Works in all locales:
- tapOn:
    id: "category_tab_scene_setup"
```
