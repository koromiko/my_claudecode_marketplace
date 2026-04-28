---
description: Generate an HTML dashboard of auto-approve hook usage and open it in the browser
allowed-tools:
  - Bash(bash:*)
  - Bash(open:*)
---

# Auto-Approve Report

Generate a self-contained HTML report of auto-approve hook decisions from `~/.claude/logs/auto-approve.log` and open it in the default browser.

The report covers the **last 7 days by default**. Pass time-filter flags as command arguments to widen or narrow the window.

## Arguments

`$ARGUMENTS` is forwarded to the script verbatim. Supported flags:

- `--today` — only today's entries
- `--days N` — last N days
- `--since YYYY-MM-DD` — on or after a specific date
- `--all` — entire log (overrides default 7-day window)

## Instructions

Run the report script with `--open` plus any user-supplied flags. The script prints the output path to stdout and opens the file in the default browser.

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/auto-approve-report.sh" --open $ARGUMENTS
```

After the command completes, summarize:
- The output file path
- The time window covered
- One-line headline (total decisions, fast-path %)

If the script reports `No log files found`, tell the user the auto-approve hook hasn't logged anything yet and point them at `~/.claude/logs/auto-approve.log`.
