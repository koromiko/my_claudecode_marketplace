# Independent Review Gate (per bead)

Every non-trivial bead in a batch must pass review by an **independent subagent — one that did not
write the code** — before the parent may call that bead done and list its branch as mergeable.

This gate is a **parent responsibility, not a child one**. Children in this skill have no `Agent`
tool: a child sub-orchestrator writes the code *and* does its own review pass inline. That is
self-review, and self-review does not satisfy the gate no matter how thorough the child's
`report.yaml` looks. The parent is the only level that can dispatch a genuinely independent
reviewer, so the parent runs this gate for every bead after Step 8's mechanical verification.

## Who may review

| Reviewer | Allowed? | Why |
|---|---|---|
| A fresh `general-purpose` Agent, `model: "opus"`, no prior context on this bead | **Yes** — this is the default | It did not write the code and has no stake in the diff |
| The child that implemented the bead (via `SendMessage`) | **No** | Author reviewing itself — the exact thing the gate exists to prevent |
| `Agent(subagent_type: "fork")` | **No** | A fork inherits the parent's context, including the parent's own conclusions about the bead |
| The parent (you) reading the diff | **No, not as the gate** | Step 8 verification is yours and still required — but it is mechanical re-derivation, not independent review |
| A reviewer that already returned NO-GO on this bead | **No** | Each round gets a **fresh** reviewer (see below) |

An **ABSORBed** bead — one the parent implemented inline after retries — still needs the gate, and
needs it *more*: there the parent is the author, so a fresh reviewer is the only independent eye on
the diff.

## Trivial-bead carve-out

The gate applies to non-trivial changes. A bead may skip it only when **all** hold:

- the diff is purely mechanical (copy/string change, config or version bump, type rename, codemod),
- no new control flow, no data-shape change, no new dependency, and
- `ui_surface: false`.

This is the same shape as the `codex-exec` routing row in `child-dispatch-template.md`. When in
doubt, run the gate — a reviewer round on a small diff is cheap; a missed correctness bug is not.
Record the skip in the batch report as `review_gate.skipped_reason: "trivial"`; anything else is not
a valid reason.

## Dispatching a reviewer

One reviewer per bead, dispatched **in parallel across beads** (all beads awaiting a round go out in
one message). Cap at 4 concurrent reviewers, same as the wave cap.

```ts
Agent({
  description: "Review bead <id>",
  subagent_type: "general-purpose",
  model: "opus",
  name: "review-<id>-r<round>",     // round number keeps names unique across rounds
  prompt: `<the reviewer brief below>`
})
```

Do **not** use `isolation: "worktree"` — the reviewer must read the child's actual worktree, not a
fresh copy of it.

## Reviewer brief (paste, filling the placeholders)

> You are an **independent code reviewer**. You did not write this code and you have no stake in it.
> Your job is to return one verdict: GO or NO-GO.
>
> **The bead.** Run `bd show <bead-id>` and read the title, description, design notes, and
> acceptance criteria.
>
> **The session intent.** <what the user asked for, in the parent's words, plus any key decision the
> parent made when briefing this bead — e.g. a chosen base branch, a deliberately deferred item>
>
> **The diff.** `git -C <worktree abs path> diff <base_branch>...HEAD`. The implementation branch is
> `<branch>` at `<head_sha>`, based on `<base_branch>`.
>
> **How to run the gates.** Build: `<exact build command the child reported>` from `<worktree>`.
> Tests: `<exact test/lint commands>`. Run them yourself if you need evidence; do not take the
> child's `report.yaml` claims on faith.
>
> **Project constraints.** <paste the project's non-negotiable constraints verbatim from its
> AGENTS.md / CLAUDE.md — data constraints, forbidden patterns, required conventions. If the project
> states none, say so here explicitly rather than leaving this blank.>
>
> **Blocking issues** (any one of these forces NO-GO):
> - the change does not match the session intent or the bead's acceptance criteria
> - a project data/security constraint is violated
> - tests are missing or inadequate for the behavior changed
> - an unhandled correctness or security bug
>
> Style and taste are **advisory** — mention them, but they never force NO-GO.
>
> End your final message with exactly one of:
> - `VERDICT: GO` — matches intent and bead criteria, constraints upheld, tests adequate.
> - `VERDICT: NO-GO` — followed by a numbered list of concrete blocking items, each naming the file
>   and what must change.

## The loop

```
round 1: fresh reviewer  ──GO──▶ bead passes the gate
   │ NO-GO
   ▼
parent forwards the blocking list to the implementing child via SendMessage
   (or fixes inline if the bead was ABSORBed / the child is gone)
   │ fixes land, parent re-runs Step 8 verification on the new head
   ▼
round 2: **a fresh reviewer** (never the round-1 reviewer) ──GO──▶ passes
   │ NO-GO
   ▼
round 3: same shape ──GO──▶ passes
   │ NO-GO
   ▼
gate exhausted → bead is NOT mergeable (see below)
```

- **A fresh reviewer every round.** Re-using the round-N reviewer for round N+1 turns the gate into
  a negotiation with someone already invested in their earlier findings. New `name`, new Agent.
- **Cap: 3 rounds.** After a third NO-GO, stop dispatching. Mark the bead
  `status: "review_blocked"` in the batch report, keep its branch out of the merge sequence,
  carry the final reviewer's blocking list into `escalations`, and surface it to the user. Do not
  argue the reviewer down, and do not declare the bead done.
- **Re-verify between rounds.** Fixes from a NO-GO change the head sha; re-run Step 8's build/diff
  checks on the new head before dispatching the next reviewer. A reviewer handed a stale sha reviews
  code that no longer exists.
- **The bead stays `in_progress` through the gate.** A GO means the branch is mergeable, not merged;
  it is closed at Step 11, after the merge verdict and after the merge actually lands on `main`.

## What a GO does and does not mean

A GO says the code is good. It does not say the *work* is done, and it is not the merge decision —
that is Step 10's fork merge-verdict judge (`merge-verdict-and-landing.md`). A bead needs both before
the orchestrator merges it. A bead that holds a GO but draws an ESCALATE does not land.
