# Maestro Flow Writing Reference

## Flow Structure

```yaml
# Frontmatter (metadata)
appId: com.example.myapp
name: Human-Readable Flow Name
tags:
  - smoke
  - regression
  - feature-name
---
# Steps (actions and assertions)
- launchApp:
    appId: "com.example.myapp"
    clearState: true

- tapOn:
    id: "element_id"
```

## App Lifecycle

```yaml
# Launch app (optionally clear state)
- launchApp:
    appId: "com.example.myapp"
    clearState: true           # Reset UserDefaults, caches

# Stop app
- stopApp:
    appId: "com.example.myapp"

# Open URL
- openLink: "myapp://deep/link"
```

## Tap Actions

```yaml
# Tap by accessibility identifier (most stable)
- tapOn:
    id: "login_button_submit"

# Tap by visible text
- tapOn:
    text: "Submit"

# Tap by percentage coordinates (fragile)
- tapOn:
    point: "50%,90%"

# Long press
- longPressOn:
    id: "item_card_42"

# Tap with index (for duplicate text)
- tapOn:
    text: "Delete"
    index: 0
```

## Text Input

```yaml
# Type into currently focused field
- inputText: "user@example.com"

# Clear field then type
- clearText
- inputText: "new text"

# Copy and paste
- copyTextFrom:
    id: "field_output"
- pasteText
```

## Assertions

```yaml
# Assert element is visible
- assertVisible:
    id: "home_content"

- assertVisible:
    text: "Welcome"

# Assert element is NOT visible
- assertNotVisible:
    id: "error_banner"

# AI-powered visual assertion
- assertWithAI: "The login form shows email and password fields"
```

## Navigation

```yaml
# Press back button
- back

# Hide keyboard
- hideKeyboard

# Press hardware key
- pressKey: home
- pressKey: backspace
- pressKey: enter
```

## Scrolling

```yaml
# Scroll down
- scroll

# Scroll until element is visible
- scrollUntilVisible:
    element:
      id: "section_footer"
    direction: DOWN
    timeout: 10000

# Swipe gesture
- swipe:
    direction: LEFT
    duration: 300
```

## Timing

```yaml
# Wait for animations to complete
- waitForAnimationToEnd

# Fixed delay (use sparingly)
- delay: 2000    # milliseconds
```

## Flow Control

```yaml
# Repeat steps
- repeat:
    times: 3
    commands:
      - tapOn:
          text: "Next"

# Run another flow file
- runFlow: "flows/shared/login.yaml"

# Conditional (optional element)
- tapOn:
    id: "popup_dismiss"
    optional: true
```

## Variables

```yaml
# Environment variables
- inputText: "${TEST_EMAIL}"
- inputText: "${TEST_PASSWORD}"

# Set at runtime:
# maestro test flow.yaml -e TEST_EMAIL=user@example.com
```

## Screenshots

```yaml
- takeScreenshot: "step_name"
# Saved to ~/.maestro/tests/<run>/screenshots/
```

## Tags

Use tags to organize and filter tests:

```yaml
tags:
  - smoke          # Quick sanity checks (< 30s)
  - regression     # Full feature validation
  - auth           # Authentication flows
  - critical       # Must-pass tests
```

```bash
# Run only smoke tests
maestro test flows/ --include-tags=smoke

# Exclude slow tests
maestro test flows/ --exclude-tags=slow
```
