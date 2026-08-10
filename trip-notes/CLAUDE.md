# trip-notes

This plugin provides one manual-trigger skill: `build-itinerary`.

## What it does

Produces a verified travel itinerary as an Obsidian markdown note, in one of three modes:

- **drive** — an ordered route of 3–5 stops with driving times, distances, and parking closing times
- **train** — a ranked comparison of independent areas, each screened against the user's own criteria (shops along the route, restaurants open at night, seating, station walking time)
- **both** — two notes plus cross-link callouts explaining who each version is for

Common to both: per-stop Google Maps link + address, local-language and zh-tw blog references, a representative photo per stop, and a deduplicated 「延伸推薦」 list of extra nearby spots pulled from those blogs' own content — each of which also gets its own photo (Step 2.5), not just the main stops.

The output is a note, not an app view: it carries frontmatter (`publish` / `publish-private`), `[[wikilinks]]` to sibling notes, and Obsidian callouts. That's what the plugin name refers to.

## Structure

```
skills/build-itinerary/
├── SKILL.md                              # orchestrator instructions
└── templates/
    ├── research-stop-brief.md            # per-stop research brief (drive mode)
    ├── research-area-train-brief.md      # per-area research brief (train mode)
    ├── image-extras-brief.md             # per-stop image + extra-spot extraction brief
    ├── extra-spot-image-brief.md         # photo search for each deduplicated 延伸推薦 spot (Step 2.5)
    ├── verify-facts-brief.md             # opening hours / last train / distances (Step 2.7)
    └── verify-brief.md                   # agent-browser URL + image verification (Step 4)
```

Pipeline: `-1 mode → 0A/0B → 1A/1B → 2 (streamed per stop) → 2.5 → 2.7 facts → 3 assemble → 3.5 curl sweep → 3.9 lint → 4 browser verify → 5 fix (cap 2 rounds) → 6 report`.

## Design notes

- **Parallel, not serial, research.** Each stop (and later each stop's image/extras pass) is a separate subagent, following this repo's subagent-fanout convention — the orchestrator does not do all the WebSearch/WebFetch calls itself. Step 1→2 is **pipelined per stop**, not a barrier; the only barrier that earns its cost is Step 2→2.5, where the extra-spot list must be deduplicated across all stops at once.
- **Model tiering.** Step 2.5 (mechanical, batched, largest agent count) runs on Haiku; Step 1/2 on Sonnet; Step 4 verification on **Opus**. A wrong image costs the reader a missing photo; a wrong closing time costs them the evening. Spend at the gate that stops errors from shipping.
- **Verification is mandatory and must use a real browser.** `verify-brief.md` invokes the `agent-browser` skill and actually opens every URL. Two hard-won rules live there: the exact invocation is mandated (`--load domcontentloaded --timeout 20000`; `networkidle` is banned outright after a ~50-minute hang that a *prose warning had already failed to prevent*), and verify agents are forbidden to delegate to further subagents after one returned "I'm waiting on the five verification agents to finish" as its final answer.
- **Verify the prose, not just the links.** The original pipeline checked link integrity only, while the real defect mass was in text the pipeline never read — opening hours, closing days, walking times. Step 2.7 fact-checks those against official sources **before** the file is written, because discovering a Friday-only closing time after the comparison table is built means rewriting the table, the ranking, and the summary.
- **The orchestrator owns fixes.** Verification subagents only report; Step 5 requires the orchestrator to apply every fix itself and re-verify, capped at 2 rounds. Never forward a raw error list to the user as the deliverable. (Also why verify agents must not edit the file: with N of them running in parallel, concurrent writes would corrupt it.)
- **Honesty over completeness.** "No image found" and `UNVERIFIABLE` are required outputs when nothing real exists — fabricating a plausible URL or repeating a blog's number as if it were official is treated as worse than an admitted gap. Notes carry a 驗證狀態 section separating what was browser-confirmed from what wasn't.
- **Captions are bare place names.** Never a description of what's in the photo. A caption that only restates a name cannot name the wrong bridge — which it did, twice, when captions described the view.
- **延伸推薦 spots need their own image search.** Extra spots surface as asides inside a *different* stop's article, so there's no blog of their own to WebFetch. Before Step 2.5 existed, an eval run produced a 延伸推薦 section where every entry was "no image found" — not because no photos existed, but because nothing had looked for them.

## Extending

If a future need arises for a "compare against an already-produced itinerary and only re-verify" mode (skip to Step 4), that's a natural entry point — both verify briefs already take a file path plus URL/claim lists as inputs, so they can be invoked standalone.
