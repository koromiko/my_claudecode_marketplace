---
description: Check that idb, Maestro, Xcode, and simulator prerequisites are installed and configured for agentic iOS testing
allowed-tools: Bash
---

Run the prerequisites check script and report results:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/check-prerequisites.sh
```

If any checks fail, provide the specific install instructions shown in the script output. Help the user resolve any missing dependencies before proceeding with testing setup.

## If Java check fails

Maestro requires Java 17+. Two common scenarios:

**Java not installed at all:**
```bash
brew install openjdk@21
```

**Java installed but not detected** (older version as default, or `JAVA_HOME` not set):
```bash
export JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home
export PATH="$JAVA_HOME/bin:$PATH"
```

In both cases, add the `JAVA_HOME` and `PATH` exports to `~/.zshrc` for persistence. Then re-run the prerequisites check.
