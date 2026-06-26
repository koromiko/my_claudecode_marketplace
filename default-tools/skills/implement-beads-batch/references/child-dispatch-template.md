# Child dispatch template

The exact `Agent({...})` envelope the parent uses for each bead in a wave. All children in one wave are dispatched in **one message** with parallel `Agent` tool calls — that's how you get the actual parallelism.

## Per-bead model routing

Pick `subagent_type` and `model` per bead from the manifest the parent built at Step 1. **Vary this per bead within a single wave** — it does not invalidate the prompt cache (model is part of the envelope, not the prompt string).

| Signal (from the bead's manifest)                                                                              | `subagent_type`     | `model`   | Why                                                                                       |
|----------------------------------------------------------------------------------------------------------------|---------------------|-----------|-------------------------------------------------------------------------------------------|
| Pure mechanical: CSS-only diff, copy/text change, type rename, regex codemod. No new logic, no UI behavior.   | `codex-exec`        | —         | Faster + cheaper than a sub-orchestrator round trip. The bead doesn't need plan/review.   |
| Small + non-UI: `files_hint` ≤ 2 AND `ui_surface=false` AND `acceptance_criteria` ≤ 3                         | `general-purpose`   | `sonnet`  | Sonnet handles dev + build + report.yaml indistinguishably; Opus is overpaid here.        |
| **Default** — anything else (UI surface, multi-file, ≥4 ACs, edge function, migration, test scaffolding)       | `general-purpose`   | `opus`    | The child collapses planner + dev + QA + reviewer into one stream — Opus reasoning pays. |

**Edge cases.** When unsure between sonnet and opus, pick opus — a misclassified bead that fails on Sonnet has to be ABSORBed and re-run, which costs more than the model premium. When unsure between codex-exec and general-purpose, pick general-purpose — codex-exec children skip the worktree-scoped report.yaml and need a different verification path at Step 8 (lint + tsc + targeted unit test instead of `npm run build`).

## Envelope

```ts
Agent({
  description: "Implement bead <id>",
  subagent_type: "<picked from table above>",
  model: "<opus | sonnet — omit for codex-exec>",
  isolation: "worktree",            // each bead in its own clean worktree
  name: "bead-<id>",                // SendMessage target
  run_in_background: <true for the single longest bead in the wave; false otherwise>,
  prompt: `<verbatim preamble from templates/child-brief.md>

---

## Your assignment

bead_id: <id>
title: <one-line title from bd show>
base_branch: <main | predecessor-bead-branch>
batch_id: <BATCH_ID>
status_file_path: .agents/batch/<BATCH_ID>/status/<id>.json
worktree: <set by Agent isolation:worktree — refer to it as "your worktree">

manifest_excerpt:
  files_hint:
    - <path>
    - <path>
  acceptance_criteria:
    - <one-line each>

Now read ${CLAUDE_PLUGIN_ROOT}/skills/implement-beads-task/SKILL.md and execute it for the bead above. When you finish, write the status file and stop.`
})
```

## Field notes

- **`subagent_type`** — `general-purpose` for the standard sub-orchestrator path; `codex-exec` only for tightly-scoped mechanical work per the routing table. `Plan` and `Explore` lack write tools and cannot be used here.
- **`model`** — chosen per the routing table above; `opus` is the default. The model varies per bead, the prompt does not.
- **`isolation: "worktree"`** — required. Without it, parallel children would clobber each other's working tree. The skill does not support skipping isolation for parallel dispatch; if a bead truly must run in-place, it has to be a wave of one and the parent handles it differently (effectively ABSORB).
- **`name: "bead-<id>"`** — `SendMessage({to: "bead-<id>", ...})` is how the parent nudges or sends review feedback during the child's review loop. Keep names unique within the batch.
- **`run_in_background`** — set `true` for **exactly one** bead per wave: the longest-expected one (most files_hint, most ACs, or `ui_surface=true` when others aren't). Lets the parent supervise faster siblings without idling on the slowest. The completion notification fires automatically. Don't backgrounded everything — you lose the ability to react to fast failures.

## Budget guidance

The child internally drives planner / dev / QA / reviewer **inline** (no Task tool). Budget accordingly:

| Bead complexity              | Recommended `max_turns` if you set one |
|------------------------------|----------------------------------------|
| Single-file CSS or copy fix  | 30                                     |
| Component change with QA     | 50                                     |
| Multi-file feature with QA   | 80                                     |
| Migration / edge function    | 60                                     |

If `max_turns` is omitted, Claude Code uses its default — fine for most cases. Setting it explicitly makes timeout failures recoverable (you know it timed out vs. hung).

## Why parallel-Agent-calls and not TeamCreate

`TeamCreate` is for persistent multi-agent teams that share a task list and message each other directly. For this skill, each bead is independent (file partition guarantees no shared state) and the parent is the only coordinator — TeamCreate's overhead isn't worth it here. Plain parallel `Agent` calls in one message give us the fan-out and the prompt-cache hit on the preamble.

If a future use case appears where children need to talk to each other (e.g. a UI bead and a data bead negotiating a shared type), revisit and consider TeamCreate.

## Per-bead tail length

Keep the tail under ~30 lines. The longer the tail, the smaller the cacheable preamble's share of the total prompt — diminishing returns. The manifest excerpt should hit the must-knows (files_hint, acceptance criteria) and stop. The child can `bd show <id>` itself to get the full picture.
