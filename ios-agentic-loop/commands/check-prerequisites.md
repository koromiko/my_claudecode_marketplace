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

Maestro 2.0+ requires Java 17+. A common issue is having an older Java (e.g., Java 8) as the default while a newer version is installed elsewhere.

**Fix:** Set `JAVA_HOME` to the newer installation and add it to `PATH`:
```bash
export JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home
export PATH="$JAVA_HOME/bin:$PATH"
```

Add these to `~/.zshrc` to make permanent. Then re-run the prerequisites check.
