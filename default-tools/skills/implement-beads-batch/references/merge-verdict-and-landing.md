# Merge Verdict Protocol + landing a batch

A **GO** from the Independent Review Gate (Step 9) says the *code* is good. The merge verdict says
the *work* is done. Both are required before a branch touches `main`.

This runs **per bead**, after that bead holds a GO, and it is the last decision point before the
orchestrator merges, pushes, and closes.

## Why the judge is a fork here

`Agent(subagent_type: "fork")` inherits the parent's conversation context — which is exactly wrong
for the review gate (it would inherit your conclusions about the code) and exactly right here. The
merge verdict is a judgement about the *session*: was the scope actually finished, were gates
actually run, did a real reviewer actually say GO. Only something that can read the transcript can
answer that, and the transcript is what a fork gets.

The fork **decides only**. It must not merge, close beads, edit files, or push.

## Dispatching the judges

One fork per bead. Dispatch all beads awaiting a verdict in **one parallel message**, capped at 4 —
the same cap as a wave. Each fork inherits the whole batch transcript, so the prompt must pin it to
one bead or it will reason about the wrong evidence.

```ts
Agent({
  description: "Merge verdict for bead <id>",
  subagent_type: "fork",
  name: "verdict-<id>",
  prompt: `<the judge brief below>`
})
```

Do not pass `model` — a fork always runs on the parent's model. Do not pass
`isolation: "worktree"` — the judge reads, it does not build.

## Judge brief (paste, filling the placeholders)

> You are the **merge-verdict judge** for bead `<bead-id>` in batch `<BATCH_ID>`. This session
> orchestrated several beads in parallel; **judge only `<bead-id>`** and ignore the evidence
> belonging to its siblings.
>
> Re-read this conversation's conclusion for that bead, its `report.yaml`
> (`<report_yaml_path>`), its status file (`<status_file_path>`), and the project's AGENTS.md /
> CLAUDE.md. Then independently verify **from the transcript** — claims without evidence do not
> count:
>
> 1. the bead's stated scope is done (`bd show <bead-id>` acceptance criteria, all of them);
> 2. quality gates — tests, linters, build, and the visual smoke check where the bead has a UI
>    surface — were **actually run and passed**, including the parent's own re-run at Step 8;
> 3. the Independent Review Gate returned a **GO** from a non-fork reviewer that did not write the
>    code (a child's self-review does not count);
> 4. no project rule was violated, including the non-negotiable data constraints.
>
> Return exactly one verdict as your final message:
> - **MERGE** — the task is complete and verified. Optionally list minor undone items that are safe
>   to defer, each as a proposed follow-up bead (title + one-line description).
> - **ESCALATE** — undone items are significant, evidence is missing, or a rule was violated. State
>   the reason; do not propose merging.
>
> You decide only. Do not merge, close beads, edit files, or push.

## Executing the verdicts

**On ESCALATE:** do not merge that bead. Report the fork's reason to the user, leave the bead
`in_progress`, keep its worktree, and keep its branch out of the merge sequence. An ESCALATE is not
retried automatically — it is a human decision.

**On MERGE:** the orchestrator lands it. Batch-specific rules below.

### Landing order and the integration gate

The per-bead protocol merges one branch and is done. A batch merges several branches that were built
in parallel against the same base, so each one was green **in isolation** and nothing has yet proven
they are green **together**. That is the batch's own failure mode, and the integration gate is how
you catch it.

```sh
MAIN=<abs path to the main checkout>
PRE_BATCH_SHA=$(git -C "$MAIN" rev-parse HEAD)   # record BEFORE the first merge — your undo point
git -C "$MAIN" pull --rebase origin main
```

1. **Merge in wave order, one at a time, locally.** Wave-1 beads first, then wave-2, and a chained
   bead always after the predecessor it branched from. Use `git -C <abs path>` for every command —
   never `cd`, you have many worktrees in play.
   ```sh
   git -C "$MAIN" merge <branch>
   ```
2. **Do not push yet.** Local merges are cheap to undo; pushed ones are not.
3. **A merge conflict stops the sequence.** The wave plan's file partition should make conflicts
   rare — one appearing means the partition was wrong. Abort it (`git -C "$MAIN" merge --abort`),
   leave that bead and everything chained behind it unmerged, and report. Do not resolve a conflict
   between two beads' work on your own judgement; that is new code no reviewer has seen.
4. **Run the integration gate once, on merged `main`** — the full build plus the suites the batch's
   beads actually exercised (a Python-side bead's pytest run is not covered by a JS build).
5. **If the integration gate is red**, reset and bisect:
   ```sh
   git -C "$MAIN" reset --hard "$PRE_BATCH_SHA"
   ```
   then re-merge one bead at a time, running the build after each, until the gate goes red. The bead
   that turned it red is the culprit: exclude it (and anything chained behind it), keep the rest,
   report it as `integration_failed` with the failure tail. Do not attempt a cross-bead fix inline —
   it has passed neither the review gate nor a verdict.
6. **Push once the gate is green.**
   ```sh
   git -C "$MAIN" push origin main
   git -C "$MAIN" status      # MUST show up to date with origin/main
   ```
   If the push is rejected, `pull --rebase` and retry until it lands. Never force-push, never skip
   hooks. "Ready to push when you are" is not an acceptable ending — once the gates are green, you
   push.

### After the push

For every merged bead:

```sh
bd close <id>
git worktree remove <worktree abs path>
```

Then file the follow-up beads each MERGE verdict proposed (`bd create ...`), and commit the bd state.
Closing beads and creating follow-ups are bd writes, so they leave the JSONL stale and the next push
fails if you skip this:

```sh
scripts/bd-commit.sh "chore: close <ids>, file follow-ups"   # if the project has this helper
git -C "$MAIN" push origin main
```

If the project has no `bd-commit.sh`, use its documented bd-sync path (`bd sync`) and commit the
JSONL the way its CLAUDE.md says to. Do not invent one.

For every bead **not** merged — ESCALATE, `review_blocked`, `integration_failed`, or blocked behind
one of those:

```sh
bd update <id> --notes="<branch> @ <sha> — not merged: <reason> — see .agents/reports/${BATCH_ID}/batch-report.yaml"
```

Leave it `in_progress` and leave its worktree in place; the human needs both.

## Ordering note: verdicts per bead, landings per wave

Run the **verdicts** per bead, as each one earns its GO — a wave-1 bead can be judged while wave-2
children are still writing code. That is the whole point of the parallel structure.

Run the **landings** per wave, not per bead. The integration gate is the expensive step, and one gate
covering a wave's worth of merges costs the same as one covering a single merge. Collect the wave's
MERGE-verdict beads, land them as one sequence, gate once, push once. A verdict that arrives after
its wave has landed joins the next landing pass.

The only hard ordering constraint is the dependency chain: a chained bead never lands before the
predecessor it branched from. If that predecessor draws an ESCALATE or never earns a GO, the
dependent does not land either — report it as `blocked_by:<predecessor-id>`.
