---
name: implement-beads-batch
description: Manual trigger. Ship a batch of beads tasks as a parallel team-of-teams. Each bead is driven through `/implement-beads-task`; non-conflicting beads run in parallel waves, conflicting beads are auto-serialized. Use when the user says "implement batch <ids>", "team up on <ids> <ids>", "ship batch <ids>", or otherwise asks to ship multiple beads in one orchestration. Requires running at the top-level Claude Code session — subagents cannot fork further subagents.
---

# Batch-implement beads with a team-of-teams

You are the **batch orchestrator**. You do not write code, you do not run `implement-beads-task` yourself — you dispatch one child Agent per bead, supervise the wave, verify their reports, and produce a cross-bead summary.

Skill assets (load on demand at the step that uses them):

- `templates/child-brief.md` — the verbatim preamble pasted into every child Agent dispatch (identical across siblings → prompt-cache hit).
- `templates/batch-report.yaml` — the cross-bead final-report contract.
- `references/conflict-detection.md` — file-overlap scan, wave construction, fan-out cap.
- `references/prompt-cache-strategy.md` — verbatim-prefix pattern + ScheduleWakeup cadence.
- `references/child-dispatch-template.md` — the exact `Agent({...})` envelope to use per bead.
- `references/retry-and-fallback.md` — status-file contract, retry policy, ABSORB, sequential fallback (self-contained — no dependency on other orchestration skills).

## Inputs

A list of **two or more** bead IDs (e.g. `nt-aaa nt-bbb nt-ccc`). If only one ID is given, tell the user to use `/implement-beads-task` directly. If none, ask. Do not guess.

## Step 0 — Self-check

This skill must run at the **top-level Claude Code session**. Subagents do not have access to `Task` / `Agent` / `SendMessage`, so a nested invocation will silently fail to fan out.

If the `Agent` tool is not available in your environment, refuse and tell the user to invoke from the top-level session.

## Step 1 — Manifest

For each bead id:

```sh
bd show <id>
```

Harvest title, description, design notes, acceptance criteria, and `depends_on_id` edges. Build an in-memory manifest you can scan:

```
{ id, title, files_hint: [<paths extracted from description/design>], deps: [<ids>] }
```

Skim relevant code paths only enough to brief — do **not** start implementing.

## Step 2 — File-overlap scan + wave plan

Follow `references/conflict-detection.md`. Output a **wave plan**:

- Wave-N is a maximal independent set of remaining beads (no shared files, no `bd dep` blockers from earlier waves still open).
- Beads in wave-N+1 that overlap a wave-N bead are **branched from that bead's branch**, not from `main`.
- Hard cap: **4 beads per wave**. Excess goes to the next wave.

Surface the plan to the user as one line, e.g.:

```
wave plan: wave-1 nt-a nt-b nt-c (parallel from main) | wave-2 nt-d (from nt-a/branch)
```

Do not dispatch yet.

## Step 3 — Permission probe (once)

Run the probe described in `${CLAUDE_PLUGIN_ROOT}/skills/implement-beads-task/references/permissions.md` at the parent level **once**:

```sh
mkdir -p .agents && echo > .agents/.permission-probe && rm .agents/.permission-probe
```

Children inherit the parent's permission posture, so probing N times is wasteful. If denied, escalate to the user before any child dispatch.

## Step 4 — Mark beads in_progress

After probe success, batch update:

```sh
for id in <bead-ids>; do bd update "$id" --status=in_progress; done
```

Allocate a batch id: `BATCH_ID=batch-$(date -u +%Y%m%dT%H%M%SZ)`. Create the status-file home:

```sh
mkdir -p .agents/batch/${BATCH_ID}/status .agents/reports/${BATCH_ID}
```

## Step 5 — Wave dispatch loop

For each wave, dispatch in **a single message with parallel `Agent` tool calls** — one per bead. Use the envelope in `references/child-dispatch-template.md`:

- `subagent_type` and `model` — **routed per bead** by the size-based table in `child-dispatch-template.md` (small + non-UI → Sonnet; mechanical-only → `codex-exec`; default → Opus). Do this classification at dispatch time using the manifest from Step 1; mixing models inside one wave is fine and does not affect the prompt cache.
- `isolation: "worktree"`
- `name: "bead-<id>"` so `SendMessage` can target it
- `run_in_background: true` for the **single longest-expected bead** in the wave (most files_hint, most acceptance criteria, or `ui_surface=true`). Lets the parent supervise faster siblings without idling on the worst case.
- `prompt`: the **verbatim preamble** from `templates/child-brief.md` followed by a per-bead tail (id, title, manifest excerpt, base_branch, status-file path).

The verbatim preamble is identical across siblings in a wave — workspace-scoped prompt cache (5-minute TTL) means the second-through-Nth dispatch hit cache. Do not "personalize" the preamble per bead. Per-bead model choice is part of the `Agent({...})` envelope, not the prompt — varying it does **not** invalidate the cache.

## Step 6 — Supervise (cache-warm)

Poll with `TaskList` / `TaskGet`. Idle wait via `ScheduleWakeup` at **240s** with a `reason` describing the wave (`"waiting on wave-1 children: nt-a, nt-b, nt-c"`). 240s stays inside the 5-minute cache window so the parent's own context cache also stays warm.

If a child stalls > 5 minutes with no progress, send a nudge via `SendMessage`. If still stuck, stop and either retry (Step 7) or absorb.

## Step 7 — Per-child failure handling

Follow `references/retry-and-fallback.md`. In short:

- **Status file is source of truth.** Every child writes `.agents/batch/${BATCH_ID}/status/<bead-id>.json`. Missing file = implicit failure.
- **Max 2 retries** per bead (3 attempts), each escalating prompt specificity. Diagnose before retrying.
- **ABSORB** on 3rd failure: parent runs `implement-beads-task` for that bead **inline** (same workspace, no nested Agent call).
- **Per-wave sequential fallback**: if `failures_after_retries / dispatched > 50%` in a wave, switch the rest of the batch to sequential (parent runs implement-beads-task inline, one bead at a time). Cause is usually systemic — re-dispatching wastes tokens.

## Step 8 — Per-child verification (orchestrator review)

For each successful child, treat its report as a **claim**, not evidence. Re-derive:

1. Read the child's `.agents/reports/<bead-id>/report.yaml`.
2. Confirm gates: `build.exit_code=0`; `ui_surface=true ⇒ ui_qa.ran=true`; screenshots open and non-blank (Read each artifact path); `base_branch` matches the wave plan (chained beads must NOT report `base_branch: main`).
3. `git -C <worktree> diff <base_branch>` — confirm `files_changed` matches the diff (no surprise edits, no missing edits the report claimed).
4. **Re-run `npm run build` in the child's worktree** — same command Vercel runs, the only authoritative deploy gate. Never trust the child's claim. If red, send the failure tail back through the child's review loop via `SendMessage`.
   - **Run builds in parallel, capped at 2 concurrent.** Multiple successful children means multiple worktrees to verify; serial runs add 30–60s × N to the verification phase. Use `Bash(run_in_background: true)` and supervise with `Monitor` / `BashOutput`. Cap at 2 because each `next build` is CPU-heavy — more concurrent builds thrash on the same host and undo the speedup.
   - **`codex-exec`-routed beads skip this step.** Codex children don't run the full implement-beads-task and won't have the worktree-scoped report.yaml. Verify them via `npm run lint` + `tsc --noEmit` + a directly-relevant unit test instead.
5. Carry every `escalations` entry into your own batch report and final summary.

## Step 9 — Cross-bead report

Write `.agents/reports/${BATCH_ID}/batch-report.yaml` per the contract in `templates/batch-report.yaml`:

- Wave plan (waves + dependencies).
- Per-bead row: id, branch, head_sha, gate results, screenshot paths, status (success / absorbed / sequential-fallback).
- Aggregate escalations.
- **Unmerged-branches list in merge order**, respecting wave dependencies.

## Step 10 — Bead lifecycle (project rule)

Per project `CLAUDE.md`: **do not `bd close` anything in this batch**. The work isn't done until merged to `main`.

For every bead in the run:

```sh
bd update <id> --notes="<branch> @ <sha> — see .agents/reports/${BATCH_ID}/batch-report.yaml"
```

Final user-facing message: a one-line phase log plus the unmerged-branches list in merge order, each annotated with its base (`nt-d ← nt-a` for chained beads).

Then run `bd sync` to push the bead state changes (notes + in_progress flips) to git.

## Guardrails

- **Top-level only** — refuse if `Agent` is not available.
- **Never** close beads. **Never** merge to `main`. **Never** force-push or skip hooks.
- **Trust but verify** every child report. Read the diff, open the screenshots, re-run `npm run build`.
- **Parent stays Opus.** The orchestrator's leverage is in plan classification, failure diagnosis, and Step-8 verification — exactly the work where Opus pulls ahead. Don't downgrade the parent to save tokens; the children are where cost moves.
- A child whose worktree has no changes auto-cleans; otherwise its path travels in the batch report.
- Keep user-facing updates terse: one line per phase transition (`probe ok`, `wave plan ready`, `wave-1 dispatched (3)`, `wave-1 converged 3/3`, `wave-2 dispatched (1)`, `done — N branches awaiting merge`).
