---
description: Run Maestro test flows for the current iOS project. Accepts optional path to specific flows or tags.
argument-hint: [flow-path] [--tags tag1,tag2]
allowed-tools: Bash
---

# Run Maestro Tests

Run Maestro test flows. If a specific path is given, run those flows. Otherwise run all flows.

## Default: Run All Flows

```bash
maestro test tests/maestro/flows/
```

## With Arguments

- If `$ARGUMENTS` contains a path, run that path:
  ```bash
  maestro test "$ARGUMENTS"
  ```

- If `$ARGUMENTS` contains `--tags`, extract tags and filter:
  ```bash
  maestro test tests/maestro/flows/ --include-tags=smoke
  ```

## Common Invocations

```bash
# Smoke tests only
maestro test tests/maestro/flows/smoke/

# Specific feature
maestro test tests/maestro/flows/auth/

# With tags
maestro test tests/maestro/flows/ --include-tags=regression

# Continuous mode (re-runs on changes)
maestro test --continuous tests/maestro/flows/smoke/
```

Report the results clearly: total flows, passed, failed, and details of any failures.
