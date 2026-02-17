# Plugin Verification Guide

Step-by-step guide to verify every ios-agentic-loop plugin component using the AgenticTodo demo app.

## Prerequisites

1. macOS with Xcode 16+
2. XcodeGen: `brew install xcodegen`
3. idb: `pip3 install fb-idb` + `brew tap facebook/fb && brew install idb-companion`
4. Maestro: `curl -Ls 'https://get.maestro.mobile.dev' | bash`

Run the plugin's prerequisite check:

```bash
bash scripts/check-prerequisites.sh
```

## Step 1: Build and Install the Demo App

```bash
# Generate Xcode project
cd demo-app && xcodegen generate

# Boot simulator
bash ../scripts/boot-simulator.sh 'iPhone 16 Pro'

# Build the app
xcodebuild -project AgenticTodoDemo.xcodeproj \
  -scheme AgenticTodoDemo \
  -sdk iphonesimulator \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro' \
  build

# Find and install the built app
APP_PATH=$(find ~/Library/Developer/Xcode/DerivedData/AgenticTodoDemo-*/Build/Products/Debug-iphonesimulator -name "AgenticTodoDemo.app" -type d | head -1)
xcrun simctl install booted "$APP_PATH"

# Launch to verify
xcrun simctl launch booted com.agentic-loop.demo
```

## Step 2: Plugin Setup (verifies /setup-project command)

The demo ships with a pre-configured `agentic-loop.config.yaml`. To test the setup command from scratch:

```
/setup-project
```

Enter when prompted:
- Bundle ID: `com.agentic-loop.demo`
- Build command: `cd demo-app && xcodebuild -project AgenticTodoDemo.xcodeproj -scheme AgenticTodoDemo -sdk iphonesimulator -destination 'platform=iOS Simulator,name=iPhone 16 Pro' build`

## Step 3: ORAV Exploration (verifies ui-explorer agent)

Ask Claude to explore the app autonomously:

```
Explore the AgenticTodo demo app. Start by logging in with any credentials, then explore all screens.
```

This invokes the `ui-explorer` agent which will:
1. Screenshot the login screen
2. Read the accessibility tree via `idb ui describe-all`
3. Type credentials and tap Sign In
4. Navigate through tabs
5. Interact with tasks, settings, and the add-task modal
6. Record every action to `/tmp/agentic/action_log.json`

**What to verify:**
- Agent takes screenshots at each step
- Agent reads accessibility tree JSON
- Agent computes tap coordinates from element frames
- Agent recovers from keyboard blocking or unexpected states

## Step 4: Goal-Directed Test (verifies goal mode)

Test a specific flow:

```
Test the login flow: enter email "user@test.com" and password "secret", tap sign in, verify the task list appears.
```

**What to verify:**
- Agent breaks the goal into sub-goals
- Agent tracks progress against success criteria
- Agent reports success/failure

## Step 5: Export to Maestro (verifies /export-maestro-flow command)

After exploration, export the recorded actions:

```
/export-maestro-flow
```

**What to verify:**
- Reads `/tmp/agentic/action_log.json`
- Generates a Maestro YAML flow file
- Uses `id:` selectors (from accessibility identifiers) over `text:` or `point:`

## Step 6: Run Maestro Tests (verifies /run-maestro command)

Run the smoke test:

```
/run-maestro
```

Or run directly:

```bash
maestro test demo-app/tests/maestro/flows/smoke/app_launch.yaml
```

**What to verify:**
- Maestro launches the app
- Login flow completes
- Tab assertions pass
- Screenshot captured

## Step 7: Accessibility Audit (verifies /audit-accessibility command)

```
/audit-accessibility
```

**What to verify:**
- Scans all `*View.swift` files in `demo-app/`
- Reports all interactive elements
- Flags any missing accessibility identifiers
- All elements should pass (demo app has full coverage)

## Step 8: Hook Verification (verifies PostToolUse hook)

Edit any View.swift file in the demo app — for example, add a new button without an accessibility identifier:

```swift
// In SettingsView.swift, add inside the "About" section:
Button("Rate App") {
    // no-op
}
```

**What to verify:**
- The PostToolUse hook fires after the Edit tool completes
- Claude warns about the missing `.accessibilityIdentifier()` on the new button
- Suggests adding `.accessibilityIdentifier("settings_button_rate")`

## Step 9: Reset Test State (verifies /reset-test-state command)

```
/reset-test-state
```

**What to verify:**
- Clears `/tmp/agentic/` directory
- Uninstalls and reinstalls the app (fresh state)
- Ready for another exploration run

## Plugin Component Coverage

| Component | Type | Verified In |
|-----------|------|-------------|
| ui-explorer | Agent | Steps 3, 4 |
| regression-runner | Agent | Step 6 |
| /check-prerequisites | Command | Prerequisites |
| /setup-project | Command | Step 2 |
| /audit-accessibility | Command | Step 7 |
| /run-maestro | Command | Step 6 |
| /reset-test-state | Command | Step 9 |
| /export-maestro-flow | Command | Step 5 |
| idb-exploration | Skill | Steps 3, 4 |
| accessibility-testing | Skill | Step 7 |
| maestro-testing | Skill | Steps 5, 6 |
| PostToolUse hook | Hook | Step 8 |
| check-prerequisites.sh | Script | Prerequisites |
| boot-simulator.sh | Script | Step 1 |
| Config template | Template | Step 2 |
| Maestro template | Template | Step 6 |
