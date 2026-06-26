# Prompt-cache strategy for batch dispatch

The Anthropic prompt cache is **workspace-scoped** with a **5-minute TTL** (since March 2026). For this skill's fan-out pattern that means real, measurable savings — but only if we don't accidentally invalidate the cache.

## The two cache surfaces this skill uses

### 1. The parent's own context cache (the orchestrator's conversation)

The parent stays in the same Claude Code session for the whole batch. Its system prompt + the back-and-forth so far are cached. The cache is reset every ~5 minutes of inactivity, with each new turn resetting the timer.

**Implication for `Step 6 — Supervise`:** when waiting on a wave, use `ScheduleWakeup` at **240s**, not 300s+. 240s keeps the parent's cache warm; 300s is the worst-of-both-worlds (you pay the cache miss without amortizing it). 1200–1800s is fine for genuinely idle long waits, but during active orchestration (waves running, children producing output) we want to stay in the cache window.

### 2. The cross-child shared preamble

Every child Agent dispatch in a wave starts a **fresh** session, but the API still sees the prompt and can hit the cache if the prefix matches a recently-sent prompt prefix in the same workspace.

**Implication:** the **first ~N tokens** of every child's prompt — the role, the operating rules, the gates, the status-file contract — must be **byte-identical** across siblings. Per-bead facts go into the **tail**, after the cacheable prefix.

`templates/child-brief.md` codifies this:

- Everything between `## Preamble (paste verbatim — start)` and `## Preamble (paste verbatim — end)` is the cacheable prefix. Paste it untouched.
- The `## Per-bead tail` section is the only thing that varies between siblings.

### What invalidates the cache

- Any change to the preamble between two children in the same wave: a typo fix, "personalizing" the bead name into the rules, anything. Don't.
- Reordering paragraphs in the preamble across waves. Edit the template in one place; the next batch picks up the new version, but a single batch's preamble must be stable.
- Whitespace changes count. If you copy-paste the preamble into the prompt builder, ensure no tab→space conversion or trailing-whitespace trim on one but not the other.

### What does NOT invalidate the cache

- Different per-bead tails (that's the whole point).
- The order of the per-bead Agent calls within the parallel message.
- Different `name`, `model`, `subagent_type`, or `isolation` arguments in the `Agent({...})` envelope — those aren't part of the prompt the API caches against; the `prompt` string is.

## Wave-splitting interaction with cache

When a wave has > 4 beads, we split into back-to-back waves of ≤ 4 (`conflict-detection.md` step C). Run wave-1's 4 beads, wait, then wave-2's remainder. Each wave dispatches all its beads in **one parallel message**, so all four child prompts hit the API within the same second — the second-through-fourth dispatch hit cache on the preamble.

The next wave fires shortly after, well within the 5-minute TTL — so wave-2's first child also hits cache (assuming preamble unchanged).

If a wave drags out past 5 minutes (slow children) and the next wave fires after the TTL has expired, the next wave's first child rewrites the cache. That's fine — the second-through-Nth in that wave still benefit. The only real lossy case is "1 bead per wave for many waves", but our wave construction won't produce that pattern unless the batch is mostly chained — and chained batches are sequential by nature.

## Measuring it (Step 6 sanity check)

After a wave runs, glance at `TaskGet` output for the children. The first child's input-token count should be high; the second-through-Nth should show meaningfully lower input tokens (the cached prefix is billed at 0.1× base). If they're all equally high, the preamble drifted between dispatches — diff the prompts and find the difference.

## Rule of thumb

> If you find yourself thinking "I'll just tweak the preamble for this one bead", stop. Push the per-bead detail into the tail. The cache is the cheap part of this skill; preserve it.
