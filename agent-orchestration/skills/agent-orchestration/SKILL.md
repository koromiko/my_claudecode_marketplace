---
name: Agent Orchestration Protocol
description: This skill should be used when dispatching subagents via the Task tool, using TeamCreate for multi-agent coordination, running parallel agents, setting up team swarms, coordinating teammates, or recovering from subagent failures. Also applies when the user asks to "dispatch agents", "create a team", "run tasks in parallel", "fan out work across agents", "coordinate agents", or mentions agent orchestration, retry policy, output contracts, or when agents keep failing.
version: 0.1.0
---

# Agent Orchestration Protocol

Reusable protocol for dispatching, monitoring, and recovering from subagent failures in Claude Code. Follow this protocol for all subagent dispatch operations.

## 1. Pre-Flight Checklist

Before dispatching **any** subagent (Task tool or TeamCreate teammate), verify all items:

### Tool Capability Match

| Task Requires | Valid Agent Types | Invalid Agent Types |
|---------------|-------------------|---------------------|
| Read-only search/research | Explore, Plan, general-purpose | — |
| File writes or edits | general-purpose, Bash | Explore, Plan |
| Bash command execution | Bash, general-purpose | Explore, Plan |
| Web search/fetch | general-purpose, Explore | Bash |
| Code review only | feature-dev:code-reviewer | Bash |
| Architecture analysis | feature-dev:code-architect, Plan | Bash |

**Rule:** If the task requires ANY write/edit/bash operation, the agent type MUST have that tool. Dispatching an Explore agent for a write task is a guaranteed failure.

### File Access

- [ ] All input files exist — verify with Glob before dispatch
- [ ] Output directories exist — create with `mkdir -p` if needed
- [ ] No path references outside the working directory tree
- [ ] Large files identified — pass specific line ranges, not "read the whole file"

### Prompt Self-Containment

- [ ] Task description includes ALL necessary context
- [ ] No references to "above", "earlier", "the conversation" — agents start fresh
- [ ] File paths are absolute, not relative
- [ ] Expected output format stated explicitly
- [ ] Output contract requirement included (see Section 4)

### Timeout Budget

| Task Complexity | Recommended max_turns | Use run_in_background? |
|-----------------|----------------------|------------------------|
| Simple search/read | 5-10 | No |
| Targeted code generation | 15-25 | No |
| Multi-file refactor | 30-50 | Yes |
| Deep codebase exploration | 20-30 | Optional |
| Full feature implementation | 40-60 | Yes |

**Rule:** Always set `max_turns`. Unbounded agents are the primary cause of timeout failures.

## 2. Retry Policy

Maximum **2 retries** per agent (3 total attempts). Each retry escalates prompt specificity.

### Attempt Progression

```
Attempt 1: Original dispatch
    | failure
Attempt 2: Diagnose -> revise prompt
    | failure
Attempt 3: Maximum specificity, simplest agent type
    | failure
ABSORB: Lead agent performs the work inline
```

### Retry Strategy by Failure Type

| Failure Type | Retriable? | Retry Strategy |
|-------------|------------|----------------|
| Permission denied | Yes | Switch to agent type with required tools |
| Timeout / max_turns hit | Yes | Reduce scope OR increase max_turns |
| Empty or malformed output | Yes | Add explicit output format + examples to prompt |
| Missing status file | Yes | Re-emphasize output contract in prompt |
| File not found | No | Fix path, then absorb inline |
| User denied tool | No | Absorb inline (don't re-prompt user) |
| Invalid task description | No | Absorb inline |

### Retry Rules

1. **Diagnose before retrying.** Read the agent's output to understand WHY it failed. Never retry blindly with the same prompt.
2. **Escalate specificity.** Each retry should inline more context — file contents, explicit instructions, concrete examples.
3. **Downgrade agent type on permission failures.** If a specialized agent lacks tools, retry with `general-purpose`.
4. **Non-retriable failures skip straight to ABSORB.** Don't waste tokens on failures that won't resolve with prompt changes.
5. **ABSORB means the lead does the work.** The lead agent has full conversation context and user-granted permissions that subagents lack.

## 3. Fallback Strategy: Parallel to Sequential

### Trigger Condition

```
failure_rate = (failed agents after retries) / (total dispatched agents)

If failure_rate > 50% -> SWITCH TO SEQUENTIAL MODE
```

### Decision Flow

After collecting all parallel results and applying retry policy:

- **failure_rate > 50%**: Keep successful results. Log the failure. Execute remaining tasks sequentially AS LEAD. Do NOT dispatch new agents.
- **failure_rate <= 50%**: Keep successful results. Lead absorbs each failed task inline.

### Why Lead Executes Sequentially

When >50% of parallel agents fail, the cause is usually systemic — permission model mismatch, wrong path assumptions, or context only the lead has. Re-dispatching agents into the same broken environment wastes tokens.

### Logging

When fallback triggers, inform the user:

```
Parallel dispatch: {success_count}/{total} succeeded.
Switching to sequential execution for remaining {remaining_count} tasks.
Reason: {brief diagnosis of common failure pattern}
```

## 4. Output Contract

Every subagent MUST write a structured JSON status file as its **last action** before returning.

### File Location

```
/tmp/claude-agents/<task-id>.json
```

Create `/tmp/claude-agents/` via `mkdir -p` before dispatching any agents.

**Core principle:** Missing status file = implicit failure, triggering the retry policy. The status file is the source of truth — not the agent's prose response.

For the full JSON schema, field definitions, and the prompt template to include in dispatches, consult `references/full-protocol.md`.

## 5. Team Swarm Protocol

Extends sections 1-4 for TeamCreate-based multi-agent coordination.

### Team Lifecycle

```
1. TeamCreate          -> create team + shared task list
2. TaskCreate (xN)     -> populate work items with dependencies
3. Task tool (xN)      -> spawn teammates with team_name
4. TaskUpdate          -> assign tasks to teammates
5. Monitor             -> read status files + idle notifications
6. SendMessage         -> coordinate, unblock, reassign
7. shutdown_request    -> graceful teammate shutdown
8. TeamDelete          -> clean up team + task directories
```

### File Conflict Prevention

This is the #1 source of swarm failures:

| Strategy | When to Use |
|----------|-------------|
| **Partition by directory** | Tasks touch different directories -> safe to parallelize |
| **Partition by file** | Tasks touch different files in same directory -> safe |
| **Serialize by dependency** | Tasks touch the same file -> use `addBlockedBy` |
| **Never partition by function** | Two agents editing different functions in same file -> race condition |

For detailed team pre-flight checks, teammate dispatch rules, and shutdown sequence, consult `references/full-protocol.md`.

## 6. Common Failure Modes

| Symptom | Root Cause | Solution |
|---------|-----------|----------|
| Agent returns empty output | Prompt too vague | Add explicit output format + examples |
| "Permission denied" errors | Wrong agent type | Switch to `general-purpose` or `Bash` |
| Agent times out | max_turns too low or scope too broad | Increase budget or split tasks |
| Agent edits wrong files | Relative paths in prompt | Use absolute paths only |
| Agent "doesn't know" context | Prompt references conversation | Inline all required context |
| Status file missing | Agent didn't follow contract | Re-dispatch with contract emphasized |
| Two agents conflict on file | No file partitioning | Add `addBlockedBy` dependency |
| Background agent stuck | No timeout | Set max_turns, check output_file |
| Team deadlock | Circular dependencies | Review dependency graph before dispatch |

## Additional Resources

### Reference Files

For detailed schemas, templates, and the complete protocol:

- **`references/full-protocol.md`** — Complete output contract schema, field definitions, and prompt template for including in agent dispatches
- **`references/dispatch-template.md`** — Copy-paste pre-flight checklist and dispatch template for quick use during agent orchestration
