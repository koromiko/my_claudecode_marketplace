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
- `references/independent-review-gate.md` — the per-bead GO/NO-GO gate run by the parent after verification.
- `references/merge-verdict-and-landing.md` — the per-bead fork merge-verdict judge, then merging, the integration gate, pushing, and closing.

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

## Step 6 — Supervise (cache-warm, and terminating)

Poll with `TaskList` / `TaskGet`. Idle wait via `ScheduleWakeup` at **240s** with a `reason` describing the wave (`"waiting on wave-1 children: nt-a, nt-b, nt-c"`, `"waiting on review-gate round 2: nt-b"`). 240s stays inside the 5-minute cache window so the parent's own context cache also stays warm.

Pass the **original skill invocation verbatim** as `prompt` on every tick — it is replayed when the timer fires, so a drifting prompt restarts the batch from Step 1 instead of resuming supervision. Set `noop: true` on a tick where no child advanced. Keep exactly one wakeup outstanding.

If a child stalls > 5 minutes with no progress, send a nudge via `SendMessage`. If still stuck, stop and either retry (Step 7) or absorb.

Review-gate rounds (Step 9) and merge verdicts (Step 10) are part of the wave you are supervising — a wave is not converged when its children return, only when every bead in it has landed on `main` or has a stated reason it did not. Keep the same 240s cadence across gate and verdict rounds.

**The wakeup does not stop itself when the batch finishes.** Cancel it explicitly with

```
ScheduleWakeup({ stop: true })
```

as the **first** action at every terminal state, before your closing summary: the last wave verified, every bead through the review gate and merge verdict, merges landed and pushed, and Step 12 notes written; a systemic abort (sequential fallback exhausted, `Agent` unavailable); a blocking question put to the user; or a wakeup that fires onto a batch with no children in flight and Step 12's `batch-report.yaml` already written. Never end a batch with a live timer — it will keep replaying the invocation against completed work.

## Step 7 — Per-child failure handling

Follow `references/retry-and-fallback.md`. In short:

- **Status file is source of truth.** Every child writes `.agents/batch/${BATCH_ID}/status/<bead-id>.json`. Missing file = implicit failure.
- **Max 2 retries** per bead (3 attempts), each escalating prompt specificity. Diagnose before retrying.
- **ABSORB** on 3rd failure: parent runs `implement-beads-task` for that bead **inline** (same workspace, no nested Agent call).
- **Per-wave sequential fallback**: if `failures_after_retries / dispatched > 50%` in a wave, switch the rest of the batch to sequential (parent runs implement-beads-task inline, one bead at a time). Cause is usually systemic — re-dispatching wastes tokens.

## Step 8 — Per-child verification (mechanical re-derivation)

For each successful child, treat its report as a **claim**, not evidence. Re-derive:

1. Read the child's `.agents/reports/<bead-id>/report.yaml`.
2. Confirm gates: `build.exit_code=0`; `ui_surface=true ⇒ ui_qa.ran=true`; screenshots open and non-blank (Read each artifact path); `base_branch` matches the wave plan (chained beads must NOT report `base_branch: main`).
3. `git -C <worktree> diff <base_branch>` — confirm `files_changed` matches the diff (no surprise edits, no missing edits the report claimed).
4. **Re-run the build in the child's worktree** — same command the deploy runs, the only authoritative gate. Never trust the child's claim. If red, send the failure tail back through the child's review loop via `SendMessage`.
   - **Use the command the child reported, not a bare `npm run build`.** Monorepos often have no root `build` script; the gate lives in the app workspace (`npm run build --workspace=apps/web`, or from inside that directory). A `Missing script: "build"` at the root is your mistake, not the child's failure — re-run at the right scope before drawing any conclusion.
   - **Re-run the child's other suites too when the bead is not JS-only** — e.g. `uv run pytest apps/api` for a Python-side bead. The build gate proves nothing about a change that never touches the JS bundle; the suite the bead actually exercises is the real evidence.
   - **Run builds in parallel, capped at 2 concurrent.** Multiple successful children means multiple worktrees to verify; serial runs add 30–60s × N to the verification phase. Use `Bash(run_in_background: true)` and supervise with `Monitor` / `BashOutput`. Cap at 2 because each `next build` is CPU-heavy — more concurrent builds thrash on the same host and undo the speedup.
   - **`codex-exec`-routed beads skip this step.** Codex children don't run the full implement-beads-task and won't have the worktree-scoped report.yaml. Verify them via `npm run lint` + `tsc --noEmit` + a directly-relevant unit test instead.
5. Carry every `escalations` entry into your own batch report and final summary.

This step is re-derivation, not review — it proves the child's claims, not that the change is the
right change. That is Step 9's job, and Step 8 passing is its precondition.

## Step 9 — Independent Review Gate (per bead)

Follow `references/independent-review-gate.md`. A bead is **not done** — and its branch does not go
into the merge sequence — until an independent reviewer returns **GO**.

- The reviewer is a **fresh `general-purpose` Agent (`model: "opus"`) that did not write the code**.
  Never the implementing child (self-review), never `subagent_type: "fork"` (inherits your context),
  never you reading the diff (that was Step 8).
- Brief it with: the bead (`bd show <id>`), the session intent and your briefing decisions, the diff
  (`git -C <worktree> diff <base_branch>...HEAD`), the exact build/test commands, and the project's
  non-negotiable constraints copied verbatim from its AGENTS.md / CLAUDE.md.
- Require an explicit `VERDICT: GO` or `VERDICT: NO-GO` + a concrete blocking list.
- On **NO-GO**: forward every blocking item to the child via `SendMessage` (or fix inline if the bead
  was ABSORBed), re-run Step 8 on the new head, then dispatch a **fresh** reviewer. Repeat.
- **Cap: 3 rounds.** A third NO-GO marks the bead `review_blocked` — branch withheld from the merge
  list, final blocking list into `escalations`, surfaced to the user.
- Dispatch reviewers for all beads awaiting a round **in one parallel message**, capped at 4.
- Only the trivial carve-out in the reference (mechanical diff, no control-flow or data-shape change,
  `ui_surface: false`) may skip the gate; record it as `review_gate.skipped_reason: "trivial"`.
- ABSORBed beads get the gate too — there *you* are the author, so the independent eye matters most.

A GO means the branch is mergeable, not merged. It is the precondition for Step 10's merge verdict — a bead needs **both** before it lands.

## Step 10 — Merge Verdict Protocol (per bead)

Follow `references/merge-verdict-and-landing.md`. A GO says the code is good; the merge verdict says
the work is done. A bead needs **both** before it touches `main`.

- Dispatch **one `Agent(subagent_type: "fork")` per bead** — the fork inherits this session's
  transcript, which is what a session-level judgement needs. Pin each judge to its own bead by id;
  it can see every sibling's evidence and will use the wrong one otherwise.
- Dispatch judges for all beads awaiting one in a single parallel message, capped at 4. No `model`
  (a fork follows the parent), no worktree isolation (it reads, it does not build).
- Require exactly **MERGE** or **ESCALATE**. The fork **decides only** — it must not merge, close
  beads, edit files, or push.
- Run the verdict **as each bead earns its GO**, not as one phase at the end. Wave-1 beads can be
  judged and landed while wave-2 children are still writing code.
- **On ESCALATE:** do not merge. Report the reason, leave the bead `in_progress` with its worktree
  intact, keep it and anything chained behind it out of the merge sequence, and stop for the human.

## Step 11 — Land the merges

**Land per wave, not per bead.** Verdicts come in as beads earn them (Step 10), but merging one bead
at a time means one integration gate per bead — the gate is the expensive part. Collect a wave's
MERGE-verdict beads and land them as one sequence; a bead whose verdict arrives after its wave landed
goes into the next landing pass. Each landing pass runs the full sequence below.

For every bead in the pass, in wave order, with `git -C <abs path>` for every command:

1. Record `PRE_BATCH_SHA` on the main checkout, `pull --rebase origin main`.
2. Merge the branches **one at a time, locally, in wave order** — a chained bead after its
   predecessor. A conflict aborts the sequence for that bead and everything behind it: the wave
   plan's file partition was wrong, and resolving it yourself would ship code no reviewer has seen.
3. **Run the integration gate once on merged `main`** — build plus the suites the batch's beads
   actually exercised. Each branch was green *in isolation*; nothing has yet proven they are green
   *together*. This is the batch's own failure mode and does not exist in the single-bead protocol.
4. If it is red: `reset --hard $PRE_BATCH_SHA`, re-merge one at a time with a build after each to
   find the culprit, exclude it (and its dependents), keep the rest, report it as
   `integration_failed`.
5. **Push** once green, then verify `status` shows up to date with `origin/main`. Retry through
   `pull --rebase` if rejected. Never force-push, never skip hooks, never end with "ready to push
   when you are" — you push.
6. After the push: `bd close <id>` each merged bead, `git worktree remove` its worktree, `bd create`
   the follow-up beads the verdicts proposed, then commit the bd state (the project's
   `scripts/bd-commit.sh` or its documented `bd sync` path) and push again.
7. Every bead **not** merged — ESCALATE, `review_blocked`, `integration_failed`, or blocked behind
   one — gets `bd update <id> --notes="<branch> @ <sha> — not merged: <reason> — see .agents/reports/${BATCH_ID}/batch-report.yaml"`,
   stays `in_progress`, and keeps its worktree.

## Step 12 — Cross-bead report + handoff

Write `.agents/reports/${BATCH_ID}/batch-report.yaml` per the contract in `templates/batch-report.yaml`:

- Wave plan (waves + dependencies).
- Per-bead row: id, branch, head_sha, gate results, review-gate verdict + rounds, merge verdict,
  merge outcome, screenshot paths, status (merged / escalated / review-blocked / integration-failed /
  failed).
- Aggregate escalations and the follow-up beads filed.
- The **merged list** (bead, branch, merge commit) and the **not-merged list**, each with its reason.

Final user-facing message: the one-line phase log, what landed on `origin/main`, every merge verdict,
the follow-up beads filed, and anything left unmerged with the reason a human needs to act on it.

## Guardrails

- **Top-level only** — refuse if `Agent` is not available.
- **Never merge, close a bead, or push without BOTH** a **GO** from the independent review gate
  (Step 9) and a **MERGE** verdict from the fork judge (Step 10). Either one alone is not enough.
- **Never** force-push, skip hooks, or resolve a cross-bead merge conflict on your own judgement.
- **Never merge without the integration gate.** Branches green in isolation are not evidence that
  they are green merged together.
- **Trust but verify** every child report. Read the diff, open the screenshots, re-run `npm run build`.
- **No bead ships without a GO** from an independent reviewer that did not write it (Step 9). A child's own inline review pass is self-review and does not count; neither does your Step 8 pass.
- **Parent stays Opus.** The orchestrator's leverage is in plan classification, failure diagnosis, Step-8 verification, and the landing sequence — exactly the work where Opus pulls ahead. Don't downgrade the parent to save tokens; the children are where cost moves.
- A merged bead's worktree is removed; an unmerged bead's worktree **stays** — the human needs it, and its path travels in the batch report.
- **Never end a batch with a live wakeup.** Success, abort, or blocking question — every exit path calls `ScheduleWakeup({ stop: true })` first (Step 6).
- Keep user-facing updates terse: one line per phase transition (`probe ok`, `wave plan ready`, `wave-1 dispatched (3)`, `wave-1 converged 3/3`, `review gate 3/3 GO`, `verdicts 3 MERGE`, `wave-2 dispatched (1)`, `integration gate green`, `pushed — N merged, M escalated`).
