# trip-notes

This plugin provides two manual-trigger skills: `build-itinerary` and `find-nearby`.

## build-itinerary

### What it does

Produces a verified travel itinerary as an Obsidian markdown note, in one of three modes:

- **drive** — an ordered route of 3–5 stops with driving times, distances, and parking closing times
- **train** — a ranked comparison of independent areas, each screened against the user's own criteria (shops along the route, restaurants open at night, seating, station walking time)
- **both** — two notes plus cross-link callouts explaining who each version is for

Common to both: per-stop Google Maps link + address, local-language and zh-tw blog references, a representative photo per stop, and a deduplicated 「延伸推薦」 list of extra nearby spots pulled from those blogs' own content — each of which also gets its own photo (Step 2.5), not just the main stops.

The output is a note, not an app view: it carries frontmatter (`publish` / `publish-private`), `[[wikilinks]]` to sibling notes, and Obsidian callouts. That's what the plugin name refers to.

### Structure

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

### Design notes

- **Parallel, not serial, research.** Each stop (and later each stop's image/extras pass) is a separate subagent, following this repo's subagent-fanout convention — the orchestrator does not do all the WebSearch/WebFetch calls itself. Step 1→2 is **pipelined per stop**, not a barrier; the only barrier that earns its cost is Step 2→2.5, where the extra-spot list must be deduplicated across all stops at once.
- **Model tiering.** Step 2.5 (mechanical, batched, largest agent count) runs on Haiku; Step 1/2 on Sonnet; Step 4 verification on **Opus**. A wrong image costs the reader a missing photo; a wrong closing time costs them the evening. Spend at the gate that stops errors from shipping.
- **Verification is mandatory and must use a real browser.** `verify-brief.md` invokes the `agent-browser` skill and actually opens every URL. Two hard-won rules live there: the exact invocation is mandated (`--load domcontentloaded --timeout 20000`; `networkidle` is banned outright after a ~50-minute hang that a *prose warning had already failed to prevent*), and verify agents are forbidden to delegate to further subagents after one returned "I'm waiting on the five verification agents to finish" as its final answer.
- **Verify the prose, not just the links.** The original pipeline checked link integrity only, while the real defect mass was in text the pipeline never read — opening hours, closing days, walking times. Step 2.7 fact-checks those against official sources **before** the file is written, because discovering a Friday-only closing time after the comparison table is built means rewriting the table, the ranking, and the summary.
- **The orchestrator owns fixes.** Verification subagents only report; Step 5 requires the orchestrator to apply every fix itself and re-verify, capped at 2 rounds. Never forward a raw error list to the user as the deliverable. (Also why verify agents must not edit the file: with N of them running in parallel, concurrent writes would corrupt it.)
- **Honesty over completeness.** "No image found" and `UNVERIFIABLE` are required outputs when nothing real exists — fabricating a plausible URL or repeating a blog's number as if it were official is treated as worse than an admitted gap. Notes carry a 驗證狀態 section separating what was browser-confirmed from what wasn't.
- **Captions are bare place names.** Never a description of what's in the photo. A caption that only restates a name cannot name the wrong bridge — which it did, twice, when captions described the view.
- **延伸推薦 spots need their own image search.** Extra spots surface as asides inside a *different* stop's article, so there's no blog of their own to WebFetch. Before Step 2.5 existed, an eval run produced a 延伸推薦 section where every entry was "no image found" — not because no photos existed, but because nothing had looked for them.

### Extending

If a future need arises for a "compare against an already-produced itinerary and only re-verify" mode (skip to Step 4), that's a natural entry point — both verify briefs already take a file path plus URL/claim lists as inputs, so they can be invoked standalone.

## find-nearby

### What it does

Finds restaurants, cafés, shops, parks, or any other kind of place near a given location, ranked against the user's own saved preference file, and delivers a verified Obsidian note with Google Maps links, per-weekday hours, real walking/driving/transit minutes, photos, and blog references. Range is a time budget (walk 15 min by default) enforced by an actual travel-time check, not a straight-line radius.

Where `build-itinerary` answers "how do I travel this route", `find-nearby` answers "what is around this one point that is worth going to and matches my taste".

### Pipeline

`0 resolve inputs → 0.2 type/condition resolution → 0.5 read preferences.md → 1 resolve origin → 2 pool fetch (nearby/search) → 3 reachable (the real time gate) → 4 structured pre-rank, top 12 → 5 scoring subagent → 6a tiered research (top 3–4) / 6b structured-only rest → 7 time-and-access fact check → 8 assemble note → 9 curl sweep → lint gate → browser verify → fix (cap 2 rounds) → 10 deliver → 11 feedback round updates preferences.md`.

### Design notes

- 範圍是時間預算不是直線半徑 —— 直線距離在有河、鐵道、高速公路切斷處會嚴重騙人；`reachable` 換到可信的分鐘數（WALK／DRIVE 用一次 batched matrix 呼叫；TRANSIT 的 `computeRouteMatrix` 對每個 element 都回 200 加 `ROUTE_NOT_FOUND`，即使是真的有車可搭的路線，所以改成逐一目的地個別 route 查詢）。
- 只有「反感」能刷掉候選 —— 排序錯了看得見，篩掉錯了看不見。
- 結構化欄位一律三態，不只 amenity —— `status`、`hours` 和每個 amenity 欄位都一樣：`null` 或空值是「Google 沒資料」，不是「沒有」。`status` 的無資料值是字面上的 `"UNKNOWN"`（script 在沒有 `businessStatus` 時就寫這個值，所以這個欄位永遠不會缺席），只有 `CLOSED_PERMANENTLY`／`CLOSED_TEMPORARILY` 兩個明確值才刷掉候選；把 `UNKNOWN` 當「非營業中」處理，會悄悄刷掉每一家 Google 沒有登記營業狀態的店——正是這整套設計想保護的獨立小店。一家真的有陽台但沒被記錄的獨立店，也是使用者最想要的那種。
- 評論決定排序，不決定筆記正文 —— 評論線索變成待確認問題交給研究 agent，這正是 `build-itinerary` Step 0.6 規則 1 的用法。
- 雙管道的 fallback 是「兩邊都發」—— 「什麼時候用哪個」這種判斷容易被略過，略過時掉進的必須是完整的那條路。
- 偏好檔只能 `Edit` 不能 `Write` —— 使用者手改的內容必須存活。

## Key conventions

`find-nearby` 以相對路徑引用 `build-itinerary/templates/verify-brief.md` 與 `verify-facts-brief.md`。改動那兩份時要同時考慮兩個呼叫端。引用而非複製，是因為其中的規則（`networkidle` 禁令、verify agent 不得再開 subagent）是用真實事故換來的，第二份副本等於允許漂移。

## Tests

```bash
trip-notes/tests/test-maps.sh              # maps script, offline via fixtures
trip-notes/tests/test-skill-integrity.sh   # markdown cross-references
```
