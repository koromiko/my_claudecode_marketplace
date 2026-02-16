---
name: maestro-testing
description: Use this skill when writing Maestro test flows, running Maestro regression tests, converting idb exploration logs to Maestro YAML, setting up Maestro for an iOS project, or when a user mentions "Maestro", "regression tests", "UI tests", "YAML test flows", or "deterministic testing".
version: 1.0.0
context: fork
---

# Maestro Testing Skill

Maestro is a declarative YAML-based mobile UI testing framework. It provides deterministic regression tests that run without AI and are suitable for CI.

## When to Use Maestro

- **Regression testing**: Verify that existing flows still work after code changes
- **Smoke tests**: Quick validation that the app launches and basic UI is functional
- **CI integration**: Automated tests that block PRs on failure
- **Flow validation**: Verify that Maestro flows exported from idb exploration work deterministically

## Flow Structure

```yaml
appId: com.example.myapp
name: Flow Name
tags:
  - smoke
  - regression
---
- launchApp:
    appId: "com.example.myapp"
    clearState: true

- tapOn:
    id: "tab_home"

- assertVisible:
    id: "home_content"
```

## Selector Priority

Always prefer the most stable selector:

1. **`id:`** -- Accessibility identifier. Most stable. Survives text changes and localization.
2. **`text:`** -- Visible text. Human-readable but breaks on localization.
3. **`point:`** -- Percentage coordinates. Last resort. Fragile across screen sizes.

```yaml
# Best: id selector
- tapOn:
    id: "login_button_submit"

# OK: text selector (only for single-language apps)
- tapOn:
    text: "Submit"

# Avoid: coordinate selector
- tapOn:
    point: "50%,90%"
```

See `references/maestro-selectors.md` for the full selector reference.

## Key Commands

| Command | Purpose |
|---------|---------|
| `tapOn` | Tap an element |
| `inputText` | Type text into focused field |
| `assertVisible` | Assert element is on screen |
| `assertNotVisible` | Assert element is NOT on screen |
| `assertWithAI` | Vision-based assertion using AI |
| `scroll` | Scroll in a direction |
| `swipe` | Swipe gesture |
| `launchApp` | Launch/restart the app |
| `waitForAnimationToEnd` | Wait for UI to settle |
| `takeScreenshot` | Capture screenshot |

See `references/maestro-flow-writing.md` for the complete command reference.

## Running Flows

```bash
# Run all flows in a directory
maestro test tests/maestro/flows/

# Run a specific flow
maestro test tests/maestro/flows/smoke/app_launch.yaml

# Continuous mode (re-runs on file change)
maestro test --continuous tests/maestro/flows/smoke/

# Filter by tags
maestro test tests/maestro/flows/ --include-tags=smoke
```

## Configuration

Create `tests/maestro/config.yaml`:

```yaml
appId: "com.example.myapp"
tags:
  - smoke
  - regression
flows:
  - "flows/**/*.yaml"
```

## Flow Maintenance

When flows break after UI changes:

1. **Identify failure**: Check which step failed and why
2. **Update selector**: If text changed, switch to `id:` selector
3. **Re-record**: If flow structure changed, re-run idb exploration to generate new flow
4. **Validate**: Run `maestro test` on the updated flow

See `references/maestro-ci-integration.md` for CI setup.

## Example Flows

See `examples/` for generic flow templates:
- `smoke-test.yaml` -- App launch verification
- `form-flow.yaml` -- Form input and submission
- `navigation-flow.yaml` -- Tab/screen navigation

## Reference Files

- `references/maestro-flow-writing.md` -- Complete step type reference
- `references/maestro-selectors.md` -- Selector types and best practices
- `references/maestro-ci-integration.md` -- GitHub Actions and CI setup
