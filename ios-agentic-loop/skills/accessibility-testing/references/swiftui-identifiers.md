# SwiftUI Accessibility Identifiers Reference

## Basic Patterns

### Button

```swift
Button("Submit") { handleSubmit() }
    .accessibilityIdentifier("form_button_submit")

// Image-only button (needs label too)
Button(action: { dismiss() }) {
    Image(systemName: "xmark")
}
.accessibilityIdentifier("modal_button_close")
.accessibilityLabel("Close")
```

### TextField and TextEditor

```swift
TextField("Email", text: $email)
    .accessibilityIdentifier("login_field_email")

SecureField("Password", text: $password)
    .accessibilityIdentifier("login_field_password")

TextEditor(text: $description)
    .accessibilityIdentifier("form_field_description")
```

### Toggle and Picker

```swift
Toggle("Dark Mode", isOn: $isDarkMode)
    .accessibilityIdentifier("settings_toggle_darkmode")

Picker("Sort Order", selection: $sortOrder) {
    Text("Name").tag(SortOrder.name)
    Text("Date").tag(SortOrder.date)
}
.accessibilityIdentifier("list_picker_sort")
```

### NavigationLink

```swift
NavigationLink(destination: DetailView(item: item)) {
    ItemRow(item: item)
}
.accessibilityIdentifier("list_link_\(item.id)")
```

## Dynamic Identifiers

### ForEach with IDs

```swift
ForEach(categories) { category in
    CategoryTab(category: category)
        .accessibilityIdentifier("category_tab_\(category.id)")
}

ForEach(blocks) { block in
    BlockCard(block: block)
        .accessibilityIdentifier("block_card_\(block.id)")
}
```

### Indexed items (when no stable ID)

```swift
ForEach(Array(items.enumerated()), id: \.offset) { index, item in
    ItemView(item: item)
        .accessibilityIdentifier("item_\(index)")
}
```

## TabView

```swift
TabView(selection: $selectedTab) {
    HomeView()
        .tabItem {
            Image(systemName: "house")
            Text("Home")
        }
        .tag(0)
        .accessibilityIdentifier("tab_home")

    SettingsView()
        .tabItem {
            Image(systemName: "gear")
            Text("Settings")
        }
        .tag(1)
        .accessibilityIdentifier("tab_settings")
}
```

> **Maestro caveat:** `.accessibilityIdentifier("tab_settings")` sets the ID on the *content view*, not the tab bar button. SwiftUI only mounts active tab content in the accessibility tree, so Maestro `id:` selectors **cannot find inactive tabs**. Use `text:` selectors for tab bar navigation:
> ```yaml
> - tapOn:
>     text: "Settings"   # Targets visible tab bar label
> ```

## Modifiers That Affect Accessibility

### `.buttonStyle(.plain)`

Plain button style can change how the button appears in the accessibility tree. The button may be reported as a generic `Other` type rather than `Button`. Always add `.accessibilityIdentifier()` regardless of button style.

```swift
Button(action: onTap) {
    CustomCardView()
}
.buttonStyle(.plain)
.accessibilityIdentifier("card_button_\(item.id)")
```

### `.accessibilityElement(children:)`

Controls how children are exposed:

```swift
HStack {
    Image(systemName: "star")
    Text("Favorite")
}
.accessibilityElement(children: .combine)
.accessibilityIdentifier("action_favorite")
```

### `.accessibilityAddTraits()`

Restore traits lost by style overrides:

```swift
Button { action() } label: { CustomLabel() }
    .buttonStyle(.plain)
    .accessibilityAddTraits(.isButton)
    .accessibilityIdentifier("detail_button_action")
```

## Sheet and Modal Considerations

Elements inside a `.sheet()` or `.fullScreenCover()` exist in a **separate accessibility hierarchy**. When a sheet is presented:

- Parent view elements may not appear in `describe-all`
- Sheet elements are reported independently
- `.interactiveDismissDisabled()` prevents swipe-to-dismiss

```swift
.sheet(isPresented: $showDetail) {
    DetailView()
        .accessibilityIdentifier("sheet_detail")
}
```

## List and LazyVGrid

```swift
List(items) { item in
    ItemRow(item: item)
        .accessibilityIdentifier("list_row_\(item.id)")
}

LazyVGrid(columns: columns) {
    ForEach(items) { item in
        GridCell(item: item)
            .accessibilityIdentifier("grid_cell_\(item.id)")
    }
}
```

## Custom Components

When creating reusable components, accept an identifier parameter:

```swift
struct ActionButton: View {
    let title: String
    let identifier: String
    let action: () -> Void

    var body: some View {
        Button(title, action: action)
            .accessibilityIdentifier(identifier)
    }
}
```
