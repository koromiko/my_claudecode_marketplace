---
description: Set up agentic testing for an iOS project. Creates config file, Maestro workspace, and initial test flows.
allowed-tools: Bash, Read, Write, Glob, Grep, AskUserQuestion
---

# Agentic Testing Setup

Interactive setup for the ios-agentic-loop testing system.

## Step 1: Check Prerequisites

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/check-prerequisites.sh
```

If any fail, help the user install them before continuing.

## Step 2: Gather Project Info

Ask the user for:
1. **Bundle ID** (e.g., `com.example.myapp`)
2. **Build command** (e.g., `xcodebuild -scheme MyApp ...` or `./project-tools.sh build`)
3. **App group** (if any, for shared data between targets)
4. **Extension bundle IDs** (if any)

## Step 3: Create Configuration

Copy the template and fill in values:

```bash
cp ${CLAUDE_PLUGIN_ROOT}/templates/agentic-loop.config.yaml.template agentic-loop.config.yaml
```

Edit `agentic-loop.config.yaml` with the gathered values.

## Step 4: Create Maestro Workspace

```bash
mkdir -p tests/maestro/flows/smoke
cp ${CLAUDE_PLUGIN_ROOT}/templates/maestro-config.yaml.template tests/maestro/config.yaml
```

Edit `tests/maestro/config.yaml` with the bundle ID.

## Step 5: Create Initial Smoke Test

Create `tests/maestro/flows/smoke/app_launch.yaml` based on the example in `${CLAUDE_PLUGIN_ROOT}/skills/maestro-testing/examples/smoke-test.yaml`, customized with the project's bundle ID and main screen elements.

## Step 6: Create Directory Structure

```bash
mkdir -p tests/agentic/scenarios
mkdir -p tests/agentic/results
echo "tests/agentic/results/" >> .gitignore
```

## Step 7: Verify

Run the smoke test to verify setup:

```bash
maestro test tests/maestro/flows/smoke/app_launch.yaml
```

Report success or failure and next steps.
