---
description: Reset simulator app state for clean test runs. Clears UserDefaults, caches, and optionally Keychain data.
allowed-tools: Bash
---

# Reset Test State

Reset app state on the simulator for clean test runs.

Read the project's `agentic-loop.config.yaml` to get the bundle ID and app group, then run the reset script:

```bash
# Read config for bundle_id and app_group
BUNDLE_ID=$(grep 'bundle_id:' agentic-loop.config.yaml | awk '{print $2}' | tr -d '"')
APP_GROUP=$(grep 'app_group:' agentic-loop.config.yaml | awk '{print $2}' | tr -d '"')

# Build the command
CMD="bash ${CLAUDE_PLUGIN_ROOT}/scripts/reset-test-state.sh $BUNDLE_ID"
if [ -n "$APP_GROUP" ]; then
    CMD="$CMD --app-group $APP_GROUP"
fi

# Add --keychain if user requested it
# $ARGUMENTS may contain --keychain
if echo "$ARGUMENTS" | grep -q "keychain"; then
    CMD="$CMD --keychain"
fi

eval $CMD
```

Report what was cleared.
