# Permissions probe + escalation playbook

Permission denial mid-flow is the #1 stall pattern in multi-agent runs. This skill catches it up-front and refuses to loop on retries.

## Single sentinel

Sub-agents emit **`NEEDS_ELEVATION:<tool>:<path>`** as their first user-visible line and exit when any required tool (Edit / Write / Bash) is denied.

- Do **not** loop on "please grant permission" — that wastes minutes per agent.
- Do **not** rephrase the request hoping a different wording slips through.

## Probe (Step 1.5 of SKILL.md)

Before `bd update --status=in_progress`, the **first** dispatched agent runs a sentinel write/edit/delete cycle inside the worktree (or working tree, if isolation skipped):

```sh
echo > .agents/.permission-probe && rm .agents/.permission-probe
```

If any tool is denied during the probe, the agent emits `NEEDS_ELEVATION:<tool>:<path>` and exits — no further work.

Only after probe success: `bd update <id> --status=in_progress`.

## Orchestrator response on `NEEDS_ELEVATION`

Pick **one** path and move on:

1. **Re-dispatch with elevation** — `mode: "bypassPermissions"` plus explicit allow rules patched into `.claude/settings.local.json`.
2. **Take the edit yourself** — small diffs only; QA still dispatched as planned.
3. **Surface to the user** — describe the denied tool/path and what you need.

Always carry every `NEEDS_ELEVATION` event into the final report's `escalations:` block, and surface them explicitly in your own final summary (Step 7 / Step 8).
