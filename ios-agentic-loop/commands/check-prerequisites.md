---
description: Check that idb, Maestro, Xcode, and simulator prerequisites are installed and configured for agentic iOS testing
allowed-tools: Bash
---

Run the prerequisites check script and report results:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/check-prerequisites.sh
```

If any checks fail, provide the specific install instructions shown in the script output. Help the user resolve any missing dependencies before proceeding with testing setup.
