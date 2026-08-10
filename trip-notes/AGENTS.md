# trip-notes

Manual-trigger skill that builds a verified travel itinerary as an Obsidian note, in **drive**, **train**, or **both** modes: a Google Maps link + address per stop, driving times and distances (drive) or station walking times and per-weekday opening hours (train), local-language and zh-tw blog references, a representative photo per stop, and a 「延伸推薦」 list of extra nearby spots pulled from those blogs' own content.

## Behavior contract

- Mode (drive / train / both) is settled before anything else. A request phrased as a **list of conditions** rather than a place name is train mode — the two pipelines ask different research questions and produce different file shapes.
- Research is parallelized per stop via subagents (`Agent` tool), not done serially by the orchestrator. Step 1→2 is pipelined per stop rather than gated on the whole wave.
- Model tier is set per step: Haiku for the mechanical Step 2.5 image search, Sonnet for research and image extraction, **Opus for verification**.
- Every claimed link, image, address, driving time, and opening hour must be independently verified by a subagent that actually uses the `agent-browser` skill to open pages in a real browser — text-only inference from a URL is not verification. Verify agents must **not** delegate to further subagents, must use `--load domcontentloaded --timeout 20000` (never `networkidle`), and must report per item as they go rather than batching one final report.
- Time-and-access facts are verified **before** the file is written (Step 2.7), because a corrected closing time can change a ranking, not just a sentence.
- The orchestrator fixes everything flagged, itself, before showing the file to the user. It does not relay raw error reports to the user as if they were the user's problem. Verification subagents never edit the file.
- Verification is capped at 2 rounds; anything still unresolved is disclosed in a 驗證狀態 section rather than hidden or silently dropped.
- Never fabricate a URL, address, phone number, driving time, or opening hour — "not found" and `UNVERIFIABLE` are always correct over a plausible-looking guess.
- Image captions are bare place names, never descriptions of what the photo shows.
