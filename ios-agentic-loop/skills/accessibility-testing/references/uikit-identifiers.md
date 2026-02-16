# UIKit Accessibility Identifiers Reference

## Core Properties

| Property | Purpose | Localized? | User-visible? |
|----------|---------|-----------|--------------|
| `accessibilityIdentifier` | Testing -- stable selector for idb/Maestro | No | No |
| `accessibilityLabel` | VoiceOver -- read aloud to users | Yes | Yes |
| `accessibilityTraits` | Element role/behavior | N/A | Yes (implicit) |

Always set **both** identifier and label on interactive elements.

## Custom UIView Subclasses

Custom views are **not accessible by default**. You must opt in:

```swift
class BlockCell: UIView {
    func configure(with block: Block) {
        isAccessibilityElement = true
        accessibilityIdentifier = "block_cell_\(block.id)"
        accessibilityLabel = block.title
        accessibilityTraits = .button
    }

    func setSelected(_ selected: Bool) {
        accessibilityTraits = selected ? [.button, .selected] : .button
    }
}
```

### Why `isAccessibilityElement = true` Matters

Without it, `idb ui describe-all` only reports inner UILabel/UIImageView children, not the tappable container. Tap coordinates from a child's frame may miss the interactive area.

## UIButton

UIButton is inherently accessible but SF Symbol buttons lack text labels:

```swift
let closeButton = UIButton(type: .system)
closeButton.setImage(UIImage(systemName: "xmark"), for: .normal)
closeButton.accessibilityLabel = "Close"
closeButton.accessibilityIdentifier = "modal_button_close"
```

## UICollectionView Cells

```swift
class ItemCell: UICollectionViewCell {
    func configure(with item: Item) {
        isAccessibilityElement = true
        accessibilityIdentifier = "collection_cell_\(item.id)"
        accessibilityLabel = item.title
        accessibilityTraits = .button
    }
}
```

## Gesture Recognizer Views

Views with `UITapGestureRecognizer` are **not automatically reported as buttons**:

```swift
class TappableCard: UIView {
    func setup() {
        addGestureRecognizer(UITapGestureRecognizer(target: self, action: #selector(handleTap)))
        isAccessibilityElement = true
        accessibilityTraits = .button
        accessibilityIdentifier = "card_\(id)"
    }
}
```

## Container Views

For containers that group child elements, do NOT make the container itself an accessibility element:

```swift
class ActionBar: UIView {
    func setup() {
        isAccessibilityElement = false  // Children are individually accessible
        copyButton.accessibilityIdentifier = "action_button_copy"
        copyButton.accessibilityLabel = "Copy"
        shareButton.accessibilityIdentifier = "action_button_share"
        shareButton.accessibilityLabel = "Share"
    }
}
```

## Keyboard Extension Specifics

Keyboard extensions run in a separate process. Elements appear alongside the host app in `idb describe-all`. Use the `keyboard_` prefix:

```swift
blockCell.accessibilityIdentifier = "keyboard_block_\(block.id)"
categoryTab.accessibilityIdentifier = "keyboard_tab_\(category.id)"
copyButton.accessibilityIdentifier = "keyboard_button_copy"
```

Keyboard elements appear in the bottom half of the screen (`y > screen_height * 0.5`).
