# Retry policy + fallback (self-contained)

This skill defines its own retry, ABSORB, and per-wave sequential-fallback rules. It does **not** depend on any cross-skill orchestration framework — the patterns below are inlined here on purpose, so this skill works standalone.

## Status file is the source of truth

Every child must, as its **last action**, write a JSON status file at `.agents/batch/<BATCH_ID>/status/<bead-id>.json`. Schema:

```json
{
  "bead_id": "<id>",
  "status": "success" | "partial" | "failed",
  "report_yaml_path": ".agents/reports/<bead-id>/report.yaml",
  "branch": "<branch-name>",
  "head_sha": "<sha>",
  "base_branch": "<branch you actually branched from>",
  "worktree": "<absolute path>",
  "build": { "ran": true, "exit_code": 0 },
  "ui_qa": { "ran": true, "artifacts_count": 5 },
  "escalations": [ "<NEEDS_ELEVATION:tool:path>", ... ],
  "error": { "type": "<class>", "message": "<short>" }   // omit on success
}
```

Rules:

- **Missing status file = implicit failure** — the parent treats it as `status: "failed"` with `error.type: "missing_status_file"`. This triggers retry policy.
- The status file is read by the parent **after** the child returns. The agent's prose response is informational only; the JSON is what decides retry / ABSORB / verification.
- The status file path home (`.agents/batch/<BATCH_ID>/status/`) is created by the parent at Step 4, before any dispatch. Children do not `mkdir` it themselves.

## Retry policy: max 2 retries (3 attempts total)

Each retry escalates prompt specificity. **Diagnose before retrying** — never re-fire the same prompt and hope.

```
Attempt 1: original dispatch
    | failure → diagnose
Attempt 2: revised prompt — inline the missing context
    | failure → diagnose
Attempt 3: maximum specificity — concrete examples, paths, expected output
    | failure → ABSORB
```

### Failure-type → retry-strategy table

| Failure type | Retriable? | Strategy |
|---|---|---|
| Missing status file | Yes | Re-dispatch with the contract re-emphasized in the per-bead tail. Inline an example status JSON. |
| Status `failed` with `error.type: "permission_denied"` | Yes (once) | Re-dispatch with `mode: "bypassPermissions"` and the elevation surfaced in the tail. If still denied, ABSORB. |
| Status `failed` with `error.type: "build_red"` | Yes | Forward the build log tail in the per-bead tail; re-dispatch. The child's own review loop should fix it; if not, ABSORB. |
| Status `failed` with `error.type: "ui_qa_missing"` | Yes | Re-dispatch with QA explicitly required; remind the child that `qa:skip` is the only opt-out. |
| Status `failed` with `error.type: "timeout"` / `max_turns` | Yes | Reduce scope (split the bead is too late — reduce the in-flight commitments) or increase `max_turns`. |
| Status `failed` with `error.type: "wrong_base_branch"` | Yes | Re-dispatch with `base_branch` repeated and bolded in the per-bead tail; cite the wave plan. |
| Status `failed` with `error.type: "user_denied"` | No | Skip retry. ABSORB — the parent has the user's session. |
| Status `failed` with `error.type: "file_not_found"` | No | The path was wrong — fix the manifest hint, then ABSORB. |
| Crash / Agent tool error before any status file | Yes | Re-dispatch once with no changes (transient); if it recurs, treat as missing status file. |

### Retry rules

1. **Read the status file (or absence) before retrying.** Blind retries are how token budgets explode.
2. **Each retry inlines more context** — file contents, examples, exact strings to use. Do not just append "please be more careful".
3. **Re-emphasize the cacheable preamble is unchanged** — only the per-bead tail grows on retries. This preserves the cross-sibling cache for the rest of the wave.
4. **A 3rd failure goes to ABSORB.** Do not push to attempt 4.

## ABSORB: parent runs implement-beads-task inline

When a bead fails 3 times **or** hits a non-retriable error, the **parent** runs `/implement-beads-task` for that bead, in the parent's own session, with no nested `Agent` call.

Rationale:

- Parent has full conversation context the child lacks.
- Parent has the user's actual permission grants — children get a derivative that may be tighter.
- Parent can ask the user directly (`AskUserQuestion`) about anything the child couldn't resolve.

Mechanics:

- The parent assumes the implement-beads-task role for that bead. Other beads in the batch (other waves, parallel siblings) keep running.
- Mark the bead in the batch report as `status: "absorbed"` — this is a successful outcome, just not the parallel one. Surface it in the orchestrator's final summary so the user knows.
- Worktree the child created may still be reusable; check it before tearing down. If reusable, continue from there. If not (e.g. corrupted state), make a fresh worktree.

## Per-wave sequential fallback

After a wave completes (all dispatches resolved one way or another, all retries exhausted, all ABSORBs done):

```
failure_rate = (beads in this wave that hit ABSORB or stayed failed) / (beads in this wave)

if failure_rate > 0.5:
    switch_remaining_batch_to_sequential()
```

What "switch to sequential" means:

- For every remaining bead in later waves, the **parent** runs `/implement-beads-task` inline, one at a time.
- No more parallel `Agent` dispatches for this batch.
- Cross-bead chaining still applies (later beads still branch off predecessor branches per the wave plan).

Why the trigger is the wave, not the whole batch:

- A high failure rate in wave-1 usually means something systemic — permission posture, environmental issue, dependency miscount in the manifest. Re-dispatching wave-2 into the same broken environment burns more tokens for the same outcome.
- One unlucky failure (e.g. a single flaky build) doesn't trigger this — only when failures dominate the wave.

User-facing log line:

```
wave-1 fallback: 3/4 children failed after retries — switching remaining batch to sequential.
Reason: <one-line diagnosis, e.g. "permission probe at parent ok, but children consistently denied write to .agents/reports/ — likely worktree-permissions inheritance bug">
```

After the line, proceed sequentially without further drama.

## What ABSORB and sequential fallback are NOT

- **Not** a license to skip verification. Step 8 (orchestrator review) still runs on absorbed and sequential beads. Build still has to be green; UI surface still needs QA.
- **Not** a license to skip the batch report. Beads that fall to ABSORB or sequential are recorded in the `fallbacks:` block of `batch-report.yaml`.
- **Not** a license to close beads. Project rule (`CLAUDE.md`) still applies: `bd close` only after merge to `main`.
