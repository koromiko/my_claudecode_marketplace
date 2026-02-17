# Output Contract — Full Schema and Prompt Template

## Status File Schema

Every subagent writes a JSON status file to `/tmp/claude-agents/<task-id>.json` as its last action.

`<task-id>` = slugified version of the Task tool's `description` parameter.

```json
{
  "agent_id": "string",
  "task": "string",
  "status": "success | partial | failed",
  "started_at": "ISO-8601",
  "completed_at": "ISO-8601",
  "outputs": {
    "files_created": ["absolute/path"],
    "files_modified": ["absolute/path"],
    "files_read": ["absolute/path"],
    "key_findings": ["string, max 5 items"]
  },
  "error": null | {
    "type": "permission | timeout | not_found | invalid | other",
    "message": "human-readable description",
    "retriable": true | false
  }
}
```

## Field Definitions

| Field | Required | Description |
|-------|----------|-------------|
| `agent_id` | Yes | Agent ID returned by the Task tool (for resume) |
| `task` | Yes | Short description matching the dispatch |
| `status` | Yes | `success` = fully complete, `partial` = some work done, `failed` = no useful output |
| `started_at` | Yes | ISO-8601 timestamp when agent began work |
| `completed_at` | Yes | ISO-8601 timestamp when agent finished |
| `outputs.files_created` | Yes | New files written (empty array if none) |
| `outputs.files_modified` | Yes | Existing files changed (empty array if none) |
| `outputs.files_read` | Yes | Files consulted for context (empty array if none) |
| `outputs.key_findings` | Yes | Summary bullets, max 5 items |
| `error` | Yes | `null` if success/partial, populated object if failed |

## Contract Rules

1. Agent writes status file as its **last action** before returning
2. Lead agent reads status files to collect and assess results
3. **Missing status file = implicit failure** — triggers retry policy
4. For background agents (`run_in_background: true`): lead polls `output_file`, then reads status JSON after agent completion
5. **Status file is the source of truth** — not the agent's prose response, which may be summarized or truncated by the system
6. Agents with `partial` status: lead reviews `key_findings` to determine if the partial work is usable

## Prompt Template for Output Contract

Include this block in every agent dispatch prompt:

```
REQUIRED: Before completing, write a JSON status file to
/tmp/claude-agents/<task-id>.json following this schema:
{
  "agent_id": "<your agent ID>",
  "task": "<task description>",
  "status": "success | partial | failed",
  "started_at": "<ISO-8601>",
  "completed_at": "<ISO-8601>",
  "outputs": {
    "files_created": [],
    "files_modified": [],
    "files_read": [],
    "key_findings": []
  },
  "error": null
}
```

## Team Swarm — Additional Pre-Flight Checks

In addition to the base pre-flight checklist:

- [ ] Team name is descriptive and unique (no collisions with existing teams)
- [ ] Task dependencies mapped correctly (`addBlockedBy` / `addBlocks`)
- [ ] No circular dependencies in the task graph
- [ ] Each teammate has a distinct, non-overlapping file scope
- [ ] File conflict zones identified — **no two teammates edit the same file simultaneously**

## Teammate Dispatch Rules

1. **One active task per teammate.** Don't assign multiple concurrent tasks.
2. **Teammate prompts must include:**
   - `team_name` parameter
   - Unique teammate `name`
   - Output contract requirement with their specific status file path
   - Their scope boundaries (which files/directories they own)
3. **Use `SendMessage` (type: "message") for 1:1 coordination.** Reserve `broadcast` for critical blocking issues only.
4. **Teammates discover each other** via team config at `~/.claude/teams/{team-name}/config.json`.

## Shutdown Sequence

```
1. TaskList            -> verify all tasks show status: completed
2. Read status files   -> confirm no partial statuses
3. shutdown_request    -> send to each teammate individually
4. Wait for responses  -> each teammate approves or rejects
5. Handle rejections   -> if teammate rejects, review their reason
6. TeamDelete          -> clean up after all teammates confirmed
```
