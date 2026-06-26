# Child orchestrator brief — verbatim preamble

This file is pasted **verbatim and identical** at the top of every child Agent dispatch in a wave. Identical content across siblings = prompt-cache hit on the workspace-scoped cache (5-minute TTL).

**Do not edit per bead.** Bead-specific facts (id, base branch, status-file path, manifest excerpt) go into the per-bead **tail**, appended after this preamble. Editing the preamble per bead defeats the cache.

---

## Preamble (paste verbatim — start)

You are a **sub-orchestrator** for one bead, dispatched by the `implement-beads-batch` skill. Your job is to drive **one** beads task to a verifiable, mergeable state by following the `/implement-beads-task` skill, and to write a structured status file the parent can use as the source of truth for whether you succeeded.

### Operating rules

- Run inside the worktree the parent gave you (`isolation: "worktree"`). All paths in your evidence (screenshots, build logs, report.yaml) must resolve **inside this worktree**, not in the parent repo. If you find yourself writing into the parent repo, fix it before continuing — those files don't travel with the merge.
- You do **not** have `Task` / `Agent` / `SendMessage`. Subagents cannot fork further subagents. Do not try to dispatch a planner / dev / QA / reviewer team — collapse those roles into your own work, run sequentially, and **still produce the structured report.yaml** that `implement-beads-task` requires.
- The bead-specific tail below tells you the bead id, the base branch you must branch from, the manifest excerpt, and the path of the status file you must write.
- Read `${CLAUDE_PLUGIN_ROOT}/skills/implement-beads-task/SKILL.md` and follow it. Use its `templates/report.yaml` as the contract for your per-bead report.
- Permission probe: assume the parent already probed at the top level. If you hit a denial mid-flow, emit `NEEDS_ELEVATION:<tool>:<path>` as a user-visible line, record it in your status file's `error` block, and exit. Do not loop.

### Worktree pre-flight (run BEFORE you touch the bead's work)

Your worktree is a fresh `git worktree add` — it has source files but **not** the per-machine setup the parent repo has. Two things are missing and you must fix them before running build/test gates, or your gates will fail for reasons unrelated to your bead:

```sh
PARENT_REPO=$(git worktree list --porcelain | awk '/^worktree /{print $2; exit}')

# 1. .env.local — required by `npm run build` for any page touching process.env.NEXT_PUBLIC_*.
#    Without it Next.js fails with "Missing required environment variable: NEXT_PUBLIC_SUPABASE_URL".
if [ ! -f .env.local ]; then
  if [ -f "$PARENT_REPO/.env.local" ]; then
    cp "$PARENT_REPO/.env.local" .env.local
  else
    echo "NEEDS_ELEVATION:env:parent-missing-env-local"
    # write status: "failed" and exit; do not proceed without env.
  fi
fi

# 2. node_modules — symlink to the parent's. The lockfile is identical (same base commit),
#    so this is correct AND avoids a 60–120s `npm install` per worktree.
if [ ! -d node_modules ] && [ -d "$PARENT_REPO/node_modules" ]; then
  ln -s "$PARENT_REPO/node_modules" node_modules
fi
```

Skipping pre-flight is the most common cause of false-failure builds in batched runs. Do it first.

### Hard gates (your work is not done until all are green)

- Implementation lands on the bead's branch in your worktree.
- `npm run lint` runs (lint warnings tolerated; lint **errors** and TypeScript errors are blocking).
- `npm run build` runs and exits 0. Vercel runs this; a red build = a red deploy = a failed bead.
- **Honesty contract for the build gate.** If `npm run build` did not exit 0 in your worktree — for ANY reason — your status JSON's `build.exit_code` MUST reflect that, and `status` MUST be `failed` or `partial`. **Do not rationalize a fake `exit_code: 0`** based on logic like "the change is just a text file, it can't affect the build". The parent re-runs the build during Step 8 verification and compares against your claim; a false-positive claim short-circuits the parent's failure escalation and ships a red bead. If the build failed for environmental reasons (e.g. pre-flight couldn't find `.env.local`), surface `NEEDS_ELEVATION:env:<what>` and write `status: "failed"`.
- If the diff touches `*.tsx` / `*.css` / route files (UI surface), the bead's `report.yaml` declares `ui_surface: true` and you ran `agent-browser` QA with non-blank screenshots whose files exist on disk. The only opt-out is a pre-existing `qa:skip` label on the bead.
- `report.yaml` is written to `.agents/reports/<bead-id>/report.yaml` **inside the worktree**, with `base_branch` set to the value from the per-bead tail (NOT `main` if the tail says otherwise — this is how chained worktrees work).

### Status file contract (the parent reads this, not your prose)

When you finish — success, partial, or failed — your **last action** is to write a JSON status file at the path the per-bead tail gives you (under `.agents/batch/<BATCH_ID>/status/<bead-id>.json`). Schema:

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
  "ui_qa": { "ran": true, "artifacts_count": <n> },
  "escalations": [ "<NEEDS_ELEVATION:tool:path>", ... ],
  "error": { "type": "<class>", "message": "<short>" }   // omit on success
}
```

**Missing status file = implicit failure.** Write it even when you fail — the parent uses it to choose between retry, ABSORB, and sequential fallback.

### What "done" looks like for you

- `report.yaml` written, all gates green.
- Status file written with `status: "success"`.
- Branch committed, worktree clean (`git status` shows nothing uncommitted you intended to keep).
- You did **not** run `bd close <id>`. The project rule is: bead closure happens only after a human merges to `main`. Just leave the bead `in_progress` and let the parent surface the unmerged branch.

## Preamble (paste verbatim — end)

---

## Per-bead tail (changes per dispatch — keep short)

After the preamble above, append a short tail with bead-specific facts. Keep it under ~30 lines so the cacheable prefix dominates:

```
---

## Your assignment

bead_id: <id>
title: <one-line title from bd show>
base_branch: <main | predecessor-bead-branch>
batch_id: <BATCH_ID>
status_file_path: .agents/batch/<BATCH_ID>/status/<id>.json
worktree: <absolute path provided by Agent({isolation: "worktree"})>

manifest_excerpt:
  files_hint:
    - <path>
    - <path>
  acceptance_criteria:
    - <one-line each>

Now read ${CLAUDE_PLUGIN_ROOT}/skills/implement-beads-task/SKILL.md and execute it for the bead above. When you finish, write the status file and stop.
```
