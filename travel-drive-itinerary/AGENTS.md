# travel-drive-itinerary

Manual-trigger skill that builds a self-drive day-trip itinerary starting from a single place name, in the same shape as the itineraries previously produced by hand in conversation: a Google Maps link + address per stop, driving times between stops, local-language (and zh-tw where it exists) blog references, a representative photo per stop, and a "延伸推薦" list of extra nearby spots pulled from those blogs' own content.

## Behavior contract

- Research is parallelized per stop via subagents (`Agent` tool), not done serially by the orchestrator.
- Every claimed link, image, address, and driving time must be independently verified by a dedicated subagent that actually uses the `agent-browser` skill to open pages in a real browser — text-only inference from a URL is not verification.
- The orchestrator fixes everything the verification subagent flags itself (re-search, swap broken images/links, recompute driving times) before showing the file to the user. It does not relay raw error reports to the user as if they were the user's problem.
- Verification is capped at 2 rounds; anything still unresolved after that is disclosed honestly in the final summary rather than hidden or silently dropped.
- Never fabricate a URL, address, phone number, or driving time — "not found" is always the correct fallback over a plausible-looking guess.
