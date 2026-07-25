# travel-drive-itinerary

This plugin provides one manual-trigger skill: `build-drive-itinerary`.

## What it does

Given a single place name, produces a markdown self-drive day-trip itinerary matching the shape hand-built earlier in this project's conversations: per-stop Google Maps link + address, driving times between stops, local-language and zh-tw blog references, a representative photo per stop, and a deduplicated "延伸推薦" list of extra nearby spots pulled from those blogs' own content — each of which also gets its own photo (Step 2.5), not just the main stops.

## Structure

```
skills/build-drive-itinerary/
├── SKILL.md                              # orchestrator instructions (Steps 0–6)
└── templates/
    ├── research-stop-brief.md            # per-stop research subagent brief
    ├── image-extras-brief.md             # per-stop image + extra-spot extraction brief
    ├── extra-spot-image-brief.md         # photo search for each deduplicated 延伸推薦 spot (Step 2.5)
    └── verify-brief.md                   # agent-browser verification subagent brief
```

## Design notes

- **Parallel, not serial, research.** Each stop (and later each stop's image/extras pass) is a separate subagent dispatched in one batch, following this repo's general subagent-fanout convention — do not have the orchestrator do all the WebSearch/WebFetch calls itself serially.
- **Verification is mandatory and must use a real browser.** The `verify-brief.md` subagent is instructed to invoke the `agent-browser` skill and actually open every Google Maps / image / blog URL, not just eyeball the URL string. This is the one part of the pipeline that must not be skipped or downgraded to a text-only check, since broken Maps pins and dead image links were the main failure mode observed when this process was first done by hand.
- **The orchestrator owns fixes.** The verification subagent only reports; Step 5 in SKILL.md requires the orchestrator to apply every fix itself (re-search, swap links/images, recompute times) and re-verify, capped at 2 rounds, before showing the user anything. Never forward a raw error list to the user as the deliverable.
- **Honesty over completeness.** Every template explicitly instructs "no image/link found" as an acceptable, required output when nothing real exists — fabricating a plausible-looking URL is treated as worse than an admitted gap.
- **延伸推薦 spots need their own image search, not a byproduct of Step 2.** Extra spots surface as asides inside a *different* stop's blog article, so there's no blog link of their own to WebFetch for a hero photo. Step 2.5 exists specifically to close this gap with a fresh WebSearch pass per extra spot (batched, since it's a lighter task than full per-stop research). Before this step existed, an eval run of the skill produced a 延伸推薦 section where every single entry was "no image found" — not because no photos existed, but because nothing had ever looked for them.

## Extending

If a future need arises for a "compare against an already-produced itinerary and only re-verify" mode (i.e. skip Steps 0–3 and jump to Step 4), that's a natural follow-up entry point — Step 4's verify-brief template already takes a file path + URL lists as inputs, so it can be invoked standalone.
