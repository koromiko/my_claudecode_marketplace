---
name: implement-beads-task
description: Manual trigger. Implement a beads task by orchestrating a team of dev, QA, and code-reviewer agents that iterate until the work is verified. Use when the user says "implement <bead-id>", "ship <bead-id>", "team up on <bead-id>", or otherwise asks to drive a beads task to completion through a multi-agent team.
---

# Implement a beads task with an agent team

You are the **orchestrator**. You do not write the implementation yourself — you dispatch a team, supervise it, and verify the result before reporting back.

Skill assets (load on demand at the step that uses them):

- `templates/planner-brief.md`, `plan-reviewer-brief.md`, `dev-brief.md`, `qa-brief.md`, `reviewer-brief.md` — paste-in briefs for each role
- `templates/report.yaml` — Step 6 final-report contract (gates marked inline)
- `references/permissions.md` — probe + escalation playbook (single sentinel: `NEEDS_ELEVATION:<tool>:<path>`)

## Inputs

A single beads issue id (e.g. `nt-7kk`). If the user did not pass one, ask. Do not guess.

## Step 1 — Load + isolate

1. `bd show <id>` — read title, description, design notes, acceptance criteria.
2. Skim relevant code paths so you can brief the team. Do **not** start implementing.
3. **Default to a git worktree** (`isolation: "worktree"` on the dev Agent call). Skip only if the task explicitly requires editing in-place (e.g. config under the user's working tree).
4. **Conflict scan.** Grep this bead's description and any sibling beads dispatched in the same round for shared file paths. If two beads touch the same file, either serialize them (the second branched from the first, **not** from `main`) or split along non-overlapping file boundaries. Declare overlaps **before** spawning agents — never let two parallel worktrees race the same file.
5. **Ambiguity gate.** Read the bead description critically — *before* dispatching the planner / starting code. Bead authors are humans; descriptions sometimes contain contradictions, under-specified placement, or conflicting acceptance criteria. Common shapes:
   - **Position-vs-intent contradictions** — e.g. "innermost so other providers can read auth" (innermost prevents siblings from reading; outermost enables it). The *position* clause and the *intent* clause disagree.
   - **Under-specified ordering / placement** — "wire it up" without saying where; "innermost" / "outermost" / "after X" omitted entirely.
   - **Conflicting acceptance criteria** — AC #2 and AC #5 imply different shapes of the same artifact.

   When you spot one, **resolve before dispatch — do not ship a literal-but-broken interpretation and label it "callout for human reviewer." That defeats the orchestrator's job.** Resolution order:
   1. Read the codebase for established precedent (existing patterns in similar files, prior beads in `bd list --status=closed`, conventions in `CLAUDE.md` / `DESIGN_SYSTEM.md`).
   2. When a position clause and an intent clause conflict, **the intent clause typically wins** — pick the placement that achieves the stated outcome.
   3. Record the resolution: one-line bd note (`bd update <id> --notes="interp: <which way> (reason: <why>)"`) and propagate it into the planner brief as a constraint (so the plan loop doesn't re-litigate it).
   4. Only ask the user when (a) precedent doesn't decide, OR (b) the two interpretations have materially different scope, OR (c) the wrong choice is hard to reverse after merge.

   This step also runs in `/implement-beads-batch` sub-orchestrator children. Children don't have a plan loop (no `Task` / `Agent`), so this is **the** ambiguity checkpoint for them — collapse it into your own pre-coding read of the bead.

## Step 1.5 — Permission probe

Run the probe described in `references/permissions.md` **before** `bd update --status=in_progress`. Only after probe success: mark the bead in_progress.

## Step 2 — Plan loop (must converge before dev starts)

Dispatch in order, in parallel where possible:

- **Planner** — `subagent_type: Plan`, `model: "opus"`. Brief from `templates/planner-brief.md`. May explore (read / grep / glob); must not write code.
- **Plan reviewer** — `subagent_type: general-purpose`, `model: "opus"`. Brief from `templates/plan-reviewer-brief.md`. Critiques; does not rewrite.

Loop:
1. Send reviewer feedback to planner via `SendMessage`.
2. Planner revises **or** declines with reasoning (the planner owns the design and may decline a suggestion that's out of scope or premature optimization).
3. Send revised plan + push-backs back to reviewer.
4. Repeat until reviewer reports no blocking issues. Declined nice-to-haves are acceptable.
5. **Hard cap: 3 rounds.** If still not converging, surface the disagreement to the user — do not hand off to dev.
6. On approval: `bd update <id> --design=...` (or `--notes=...`) capturing the final plan, then proceed.

## Step 3 — Dispatch the team

Spawn agents in **a single message with parallel Agent tool calls**. Give each a `name` so you can address them with `SendMessage`.

- **Dev agent(s)** — `subagent_type: general-purpose`, `model: "sonnet"` (or `codex-exec` for tightly-scoped work). One dev for a focused task; **two devs in separate worktrees only when the task naturally splits** (e.g. UI + data layer). `isolation: "worktree"` unless skipped. Brief from `templates/dev-brief.md`, with the approved plan pasted in full.
- **QA** — `subagent_type: general-purpose`, `model: "sonnet"`, with the `agent-browser` skill. Runs after dev's first pass (or in parallel if instructed to wait for the orchestrator's signal). Brief from `templates/qa-brief.md` — render `{{BEAD_ID}}`, `{{BRANCH}}`, `{{SHA}}`, **and `{{SHA_SHORT}}`** (first 7 chars of `{{SHA}}`) so the QA agent gets a unique `AGENT_BROWSER_SESSION=qa-<bead>-<sha>` (parallel beads must each get a distinct session — the bead-id keyed name guarantees that). Runs against the dev's commit SHA in its own worktree.
- **Code reviewer** — `subagent_type: general-purpose`, `model: "opus"`. Brief from `templates/reviewer-brief.md`.

## Step 4 — Supervise (do not idle)

Poll every few minutes via `TaskList` / `TaskGet`. If an agent has produced no progress for ~5 minutes, or is stuck waiting on input, send a nudge via `SendMessage` or stop and respawn. Use `ScheduleWakeup` (180–270s, stay in the cache window) when waiting; include a `reason` describing what you're waiting on.

## Step 5 — Review loop

When dev reports a pass:

1. Forward the diff/worktree to QA and reviewer in parallel.
2. **A red `npm run build` is a blocking issue.** If the dev's report shows `build.exit_code != 0` or the log path is missing/empty, that's a hard failure — forward the build log tail to dev along with QA/reviewer feedback. Do not advance the round until the build is green.
3. Consolidate QA failures + reviewer suggestions into one feedback message.
4. Send to dev via `SendMessage`. The dev may fix or push back with reasoning (see Guardrails).
5. Re-run QA and reviewer on the updated diff.
6. Repeat until QA is green and reviewer has no blocking concerns.

**Hard cap: 3 review rounds.** If still not converging, surface to the user.

## Step 6 — Final report

Dev fills `.agents/reports/<bead-id>/report.yaml` per the contract in `templates/report.yaml`. **All evidence paths must resolve inside the worktree** (e.g. `<worktree>/.agents/reports/<bead-id>/...`), not in the parent repo. Writes that land in `<parent-repo>/.agents/reports/` stay untracked, do not travel with the merge commit, and get lost on cleanup. If the agent-browser session resolves CWD to the parent repo, fix it (e.g. `cd <worktree>` or pass an absolute output path rooted in the worktree) before capturing — do not silently let evidence land outside the branch.

The gates are marked inline; the orchestrator refuses to declare success if any fail. In short:

- `build.ran=true AND build.exit_code=0` (Vercel runs `npm run build`; lint warnings tolerated, lint **errors** and tsc errors are not)
- `ui_surface=true ⇒ ui_qa.ran=true` (only a `qa:skip` bead label opts out)
- `ui_qa.ran=true ⇒ artifacts non-empty AND files exist on disk`
- `base_branch` declared (chained beads → previous bead's branch, not `main`)
- `escalations` non-empty ⇒ surface in your own summary (Step 7)

QA reuses its verification run for screenshots — no separate pass. For pure non-UI tasks (edge functions, scripts, migrations) `ui_surface: false`; substitute CLI / test / DB evidence in the `tests` block.

If a UI task returns with `ui_qa.ran: false`, send QA back to capture screenshots. Do not proceed.

## Step 7 — Orchestrator review

Treat the YAML report as a *claim*, not evidence. Re-derive each field:

1. Validate every required field is present and non-empty. Missing field = send back, not "minor".
2. `git -C <worktree> diff <base_branch>` — confirm `files_changed` matches reality (no surprise edits, no missing edits the report claimed).
3. **Open the screenshots yourself** (Read on the image paths). If `ui_surface=true` and screenshots are missing, blank, or show an error state, send QA back. Do not paper over with "the diff looks reasonable".
4. Confirm acceptance criteria are met against the diff *and* screenshots — both must agree.
5. **Always run `npm run build` yourself** in the dev's worktree before declaring success — never trust the dev's claim. This is the same command Vercel runs, so a green build here is the only authoritative deploy gate. If it fails, send the failure tail back through Step 5 (review loop); do not advance. Re-run `npm run lint` and directly-relevant tests too if the report's `lint`/`tests` blocks look thin, but the build is the non-negotiable gate.
6. **Invoke `/simplify` on the diff yourself** before declaring success — this is the orchestrator's last reuse / dead-code / over-abstraction pass on top of the reviewer agent's earlier sweep. Treat blocking findings the same as a Step 5 reviewer-flagged issue and re-enter the review loop; nice-to-haves can be deferred to a new bead.
7. Surface every `escalations` entry explicitly in your own final summary.

## Step 8 — Bead lifecycle (project rule overrides default)

**Project CLAUDE.md rule**: do **NOT** `bd close` until the code is merged into `main`.

- After Step 7 passes, leave the bead `in_progress`. Run `bd update <id> --notes=...` capturing branch, SHA, screenshot paths, deferred items, and escalations.
- Surface unmerged branches as a single list (`<id> · <branch> · <sha> · <worktree path>`), in merge order if multiple beads chain.
- After the human merges to `main`: `bd close <id> --reason="..."` then `bd sync`.

## Guardrails

- **Trust but verify** every agent summary. Read the diff. Open the screenshots.
- Agents may decline feedback with reasoning — don't relay every reviewer comment as a mandate. Devs **cannot** decline the QA leg or the structured-report contract.
- **Never** skip hooks, force-push, or merge to `main` without explicit user approval.
- A worktree with no changes auto-cleans; otherwise report its path.
- Keep your own user-facing updates terse: one sentence per phase transition (probe ok, plan converged, dispatched, round 1 review, converged, awaiting merge).
- On `NEEDS_ELEVATION`: re-dispatch elevated, take the edit yourself, or surface to the user — pick one and move on. Do **not** loop.
