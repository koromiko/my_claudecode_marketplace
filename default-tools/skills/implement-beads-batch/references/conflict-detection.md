# Conflict detection + wave construction

Goal: turn a flat list of bead IDs into an ordered list of **waves**, each containing beads safe to run in parallel (no shared files, no unresolved `bd dep` blockers from earlier waves). Beads that overlap with an earlier-wave bead are **chained** — their worktree is branched from that bead's branch, not from `main`.

## Step A — Extract file hints per bead

For each bead in the manifest, scan its `description`, `design` notes, and any plan-pinned-as-design output for path-shaped strings. Concrete heuristic:

- Regex over `bd show <id>` output for tokens matching:
  - `src/[A-Za-z0-9_./-]+\.(tsx?|jsx?|css|module\.css|md)`
  - `supabase/[A-Za-z0-9_./-]+\.(ts|sql)`
  - `tests/[A-Za-z0-9_./-]+\.(spec|test)\.(tsx?|js)`
  - `api-tests/[A-Za-z0-9_./-]+`
  - bare `package.json`, `tailwind.config.js`, `next.config.js`, `tsconfig.json`, etc.
- Also pick up code blocks fenced as ` ```diff ` or ` ```ts ` and extract paths from them.

Store as `files_hint: Set<string>` per bead. If a bead has zero hits, treat it as **broad scope** — it conflicts with every other bead until proven otherwise. Surface this case to the user and recommend they refine the description, or accept that this bead will be put in its own solo wave.

## Step B — Build the overlap graph

Undirected graph `G = (V=beads, E)` where there is an edge between two beads iff:

- `files_hint` sets intersect, **OR**
- one bead has `bd dep` "blocks" or "blocked_by" the other within the batch (treat the dep edge as a directed-into-undirected overlap for this graph; the directed edge is recorded separately for ordering).

## Step C — Greedy wave construction

```
remaining = all beads, ordered by (priority desc, id)
waves = []

while remaining:
    wave = []
    candidates = [b for b in remaining if all bd-dep blockers of b are already in earlier waves]
    for b in candidates:
        if no edge in G from b to any bead already in `wave`:
            wave.append(b)
        if len(wave) == 4:               # FAN-OUT CAP
            break
    if not wave:
        # cycle or systemic conflict — surface to user, do not dispatch
        raise "wave construction stuck on remaining beads: <list>"
    waves.append(wave)
    remaining -= wave
```

### Why the cap is 4

- Anthropic agent-teams guidance: 2–4 parallel workers is the sweet spot.
- Empirical: bursting ≥10 Claude Code sessions back-to-back trips server-side rate limits — only the first 3–4 succeed.
- Each child opens its own worktree; coordination overhead grows non-linearly.

If wave construction wants to put 5+ beads in one wave, split into back-to-back waves of ≤4. The second wave's children inherit the same verbatim preamble within the 5-minute cache window, so the cache benefit holds.

## Step D — Chained worktree base_branch assignment

For each bead `b` in wave `N` (N > 1):

- Find its predecessor `p`: the bead in any earlier wave with which it has an overlap edge in `G`. If multiple, pick the one with the longest overlap (most shared files); ties broken by lowest wave index, then by bead id.
- Set `b.base_branch = p.branch` (the branch `p`'s worktree is on, not `main`).
- If `b` has no overlap with any earlier-wave bead but **is** blocked by one via `bd dep`, still chain its base to the blocker — the dep is the human's signal that the order matters.
- If `b` has no overlap and no dep, `base_branch = main`.

Record this in the wave plan and pass it explicitly into the child's per-bead tail. The child's `report.yaml` must echo the same `base_branch`; a child that reports `base_branch: main` for a chained bead is a verification failure (Step 8).

## Step E — Surface the plan

Before dispatching, emit one user-facing line:

```
wave plan: wave-1 nt-a nt-b nt-c (parallel from main) | wave-2 nt-d (from nt-a/branch) | wave-3 nt-e (from nt-d/branch)
```

If the plan triggers an unusual case (a "broad scope" solo wave, a wave that hit the fan-out cap and was split, a deep chain), include a one-line note. Do not stall waiting for approval unless the user explicitly asked to review the plan first.

## Common failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| Cycle in `bd dep` within batch | Two beads block each other | Surface to user; refuse to dispatch |
| All beads "broad scope" (no hints) | Descriptions too vague | Surface; either improve descriptions or run sequentially |
| Wave keeps fitting only 1 bead | Heavy file overlap across the batch | Probably should be one bead, not many — surface to user |
| Child reports `base_branch: main` for a chained bead | Child ignored the per-bead tail | Step 8 verification fails; re-dispatch with the tail re-emphasized |
