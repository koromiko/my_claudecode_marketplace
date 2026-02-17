# Dispatch Template — Quick Reference

Copy-paste checklist for use when dispatching a subagent.

## Pre-Flight

```
[ ] Agent type: [type] — has tools: [list required tools]
[ ] Input files verified: [paths]
[ ] Output dir exists: /tmp/claude-agents/
[ ] Prompt is self-contained: [yes/no]
[ ] max_turns: [N]
[ ] run_in_background: [true/false]
```

## Dispatch

```
Task tool call:
  description: "<3-5 word summary>"
  prompt: "<full self-contained prompt with output contract>"
  subagent_type: "<agent type>"
  max_turns: <N>
  run_in_background: <bool>
```

## Post-Dispatch

```
[ ] Read /tmp/claude-agents/<task-id>.json
[ ] Verify status field
[ ] If failed: apply retry policy (max 2 retries, escalate specificity)
[ ] If >50% parallel failures: switch to sequential, lead executes inline
```

## Tool Capability Quick Reference

| Task Requires | Use These Agent Types |
|---------------|----------------------|
| Read-only search/research | Explore, Plan, general-purpose |
| File writes or edits | general-purpose, Bash |
| Bash command execution | Bash, general-purpose |
| Web search/fetch | general-purpose, Explore |
| Code review only | feature-dev:code-reviewer |
| Architecture analysis | feature-dev:code-architect, Plan |

## Timeout Quick Reference

| Complexity | max_turns | Background? |
|-----------|-----------|-------------|
| Simple search | 5-10 | No |
| Code generation | 15-25 | No |
| Multi-file refactor | 30-50 | Yes |
| Deep exploration | 20-30 | Optional |
| Full feature | 40-60 | Yes |
