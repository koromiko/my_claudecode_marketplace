# trip-notes

This plugin provides two manual-trigger skills: `build-itinerary` and `find-nearby`.

## build-itinerary

### What it does

Produces a verified travel itinerary as an Obsidian markdown note, in one of three modes:

- **drive** — an ordered route of 3–5 stops with driving times, distances, and parking closing times
- **train** — a ranked comparison of independent areas, each screened against the user's own criteria (shops along the route, restaurants open at night, seating, station walking time)
- **both** — two notes plus cross-link callouts explaining who each version is for

Common to both: per-stop Google Maps link + address, local-language and zh-tw blog references, **2–3 photos per stop** plus at most one embedded Instagram post, and a deduplicated 「延伸推薦」 list of extra nearby spots pulled from those blogs' own content — each of which also gets its own photos (Step 2.5, 1–2, no Instagram), not just the main stops.

The output is a note, not an app view: it carries frontmatter (`publish` / `publish-private`), `[[wikilinks]]` to sibling notes, and Obsidian callouts. That's what the plugin name refers to.

### Structure

```
skills/build-itinerary/
├── SKILL.md                              # orchestrator instructions
├── scripts/
│   ├── maps                              # Google Maps helper (also on PATH as trip-maps)
│   └── note-provenance                   # provenance gate: note's cids/「無資料」 vs the data
└── templates/
    ├── research-stop-brief.md            # per-stop research brief (drive mode)
    ├── research-area-train-brief.md      # per-area research brief (train mode)
    ├── image-extras-brief.md             # per-stop photos (2–3) + extra spots + Instagram brief
    ├── extra-spot-image-brief.md         # photo search (1–2) for each deduplicated 延伸推薦 spot (Step 2.5)
    ├── verify-facts-brief.md             # opening hours / last train / distances (Step 2.7)
    └── verify-brief.md                   # agent-browser URL + image verification (Step 4)
```

Pipeline: `-1 mode → 0A/0B → 1A/1B → 2 (streamed per stop) → 2.5 → 2.7 facts → 3 assemble → 3.5 curl sweep → 3.6 Instagram check → 3.9 lint → 4 browser verify → 5 fix (cap 2 rounds) → 6 report`.

### Design notes

- **Parallel, not serial, research.** Each stop (and later each stop's image/extras pass) is a separate subagent, following this repo's subagent-fanout convention — the orchestrator does not do all the WebSearch/WebFetch calls itself. Step 1→2 is **pipelined per stop**, not a barrier; the only barrier that earns its cost is Step 2→2.5, where the extra-spot list must be deduplicated across all stops at once.
- **Model tiering.** Step 2.5 (mechanical, batched, largest agent count) runs on Haiku; Step 1/2 on Sonnet; Step 4 verification on **Opus**; Step 3.6 runs on no agent at all — a browser and two greps. A wrong image costs the reader a missing photo; a wrong closing time costs them the evening. Spend at the gate that stops errors from shipping — and spend nothing where there is no judgment to buy.
- **Verification is mandatory and must use a real browser.** `verify-brief.md` invokes the `agent-browser` skill and actually opens every URL. Two hard-won rules live there: the exact invocation is mandated (`--load domcontentloaded --timeout 20000`; `networkidle` is banned outright after a ~50-minute hang that a *prose warning had already failed to prevent*), and verify agents are forbidden to delegate to further subagents after one returned "I'm waiting on the five verification agents to finish" as its final answer.
- **Verify the prose, not just the links.** The original pipeline checked link integrity only, while the real defect mass was in text the pipeline never read — opening hours, closing days, walking times. Step 2.7 fact-checks those against official sources **before** the file is written, because discovering a Friday-only closing time after the comparison table is built means rewriting the table, the ranking, and the summary.
- **One check is pointed at the orchestrator, not at the subagents.** Everything else in this pipeline guards against an *agent* inventing something; nothing guarded the process that actually writes the file. That gap shipped: a finished 結論表 carried eight invented Google Maps cids and six invented "Google 無資料" hours cells, written from memory for rows that were never looked up — all eight cids wrong, and every existing check passed (well-formed links, a lint gate that only reads shape, and a verify brief that explicitly tells the browser agent not to open map links). `scripts/note-provenance` closes it, and only because both halves are mechanically decidable: `maps_url` is a copy-verbatim field, so a cid in no data file was copied from nowhere; and "no data" is a claim *about* the data, so a record with `hours` refutes it. It runs beside the lint gate after every write, in both skills. Its own test asserts the honest case too — a genuinely null `hours` written up as 「無資料」 must not be flagged, because a check that punishes honesty is worse than the bug it replaced.

- **The orchestrator owns fixes.** Verification subagents only report; Step 5 requires the orchestrator to apply every fix itself and re-verify, capped at 2 rounds. Never forward a raw error list to the user as the deliverable. (Also why verify agents must not edit the file: with N of them running in parallel, concurrent writes would corrupt it.)
- **Honesty over completeness.** "No image found" and `UNVERIFIABLE` are required outputs when nothing real exists — fabricating a plausible URL or repeating a blog's number as if it were official is treated as worse than an admitted gap. Notes carry a 驗證狀態 section separating what was browser-confirmed from what wasn't.
- **Captions are bare place names.** Never a description of what's in the photo. A caption that only restates a name cannot name the wrong bridge — which it did, twice, when captions described the view.
- **Photo counts are targets, never quotas.** Stops aim for 2–3 photos and extra spots for 1–2, but every brief and both SKILL.md files repeat that one good photo beats two where the second is padding, and that "no image found" beats one stretched for. A floor is the one framing that makes fabricating a URL the cheapest way to comply — precisely what the rest of this pipeline exists to prevent. Near-identical frames from one article's photo run count as one photo, not two.
- **Instagram posts are discovered and checked by the orchestrator's browser, never by an agent.** Two measurements shaped this. First, Instagram returns `200 text/html` for a *fabricated* post code — a real post and an invented one differ by 7 bytes — with no `og:` tags and no caption in the body, so the curl sweep cannot touch it and every `instagram.com` URL is excluded there; loading `…/p/<code>/embed/captioned` as a top-level page in a logged-out browser is what works, since a live post renders handle/venue/likes/caption and a dead one renders a fixed "may be broken, or the post may have been removed" card. Second, and the reason discovery moved here too: WebSearch finds a venue's *account* reliably but almost never an individual *post* for a small venue, because Google does not index individual posts for an account with a few hundred of them. On three small Shibuya bars, all three research agents found the official account and all three correctly reported no post — and a browser opening those same account pages yielded eight live post codes each. So agents report **handles only** and are forbidden to report post URLs at all, which makes "never fabricate a post URL" a structural property rather than a rule to remember. Both halves are `grep`, so Step 3.6 / 9.2b runs with no subagent, and `verify-brief.md` tells the opus agent to skip Instagram — its budget is for the wrong-bridge-in-a-caption problem.
- **An empty post list is a question, not an answer.** Discovery coming back empty never means "this account has no posts". Measured on a real run: three bar accounts read fine logged-out while `@tower_records_beer` returned `Restricted profile — It's unavailable for certain audiences. Log in to continue.` — Instagram age-gates alcohol accounts per-account, so a 精釀啤酒/居酒屋/bar note hits this far more than a café one would. The step therefore reads the page text on an empty result and distinguishes an age-restricted account (the note says so, naming the handle, because the reader can still open it themselves) from a genuine no-result. "We could not read it" and "there is nothing there" are different sentences and only one is true.

- **Broken is judged on a positive match only.** Live embeds vary ~750–2200 bytes because the caption has not always rendered at the 3s mark, so absence of expected text means "could not check", never "removed" — inferring removal from silence would delete good posts every time Instagram is slow. The handle on the first line renders reliably even when the caption does not, which is why attribution is matched on the handle rather than the caption text.
- **An iframe never ships without its fallback link.** The embed renders nothing in Obsidian's editing mode and nothing offline, so the `[在 Instagram 開啟]` line beneath it is what keeps those states navigable. The lint gate counts `<iframe>` against that string and fails on a mismatch.
- **Multi-photo groups are labelled by heading, not by repeated captions.** The hard-won rule is that a name must be *visible* on the page, not only in alt text; with 2–3 photos per stop, repeating `**name**` under each is noise, so the gallery uses a `####` heading per stop (`###` per venue in find-nearby) and the existing heading exception covers the group. Exactly two routes are legal — a caption line, or a name-bearing heading above the group — and never neither.
- **延伸推薦 spots need their own image search.** Extra spots surface as asides inside a *different* stop's article, so there's no blog of their own to WebFetch. Before Step 2.5 existed, an eval run produced a 延伸推薦 section where every entry was "no image found" — not because no photos existed, but because nothing had looked for them.

### Extending

If a future need arises for a "compare against an already-produced itinerary and only re-verify" mode (skip to Step 4), that's a natural entry point — both verify briefs already take a file path plus URL/claim lists as inputs, so they can be invoked standalone.

## find-nearby

### What it does

Finds restaurants, cafés, shops, parks, or any other kind of place near a given location, ranked against the user's own saved preference file, and delivers a verified Obsidian note with Google Maps links, per-weekday hours, real walking/driving/transit minutes, 2–3 photos per 首選 plus an embedded Instagram post where one exists, and blog references. Range is a time budget (walk 15 min by default) enforced by an actual travel-time check, not a straight-line radius.

Where `build-itinerary` answers "how do I travel this route", `find-nearby` answers "what is around this one point that is worth going to and matches my taste".

### Pipeline

`0 resolve inputs → 0.2 type/condition resolution → 0.5 read preferences.md → 1 resolve origin → 2 pool fetch (nearby/search) → 3 reachable (the real time gate) → 4 structured pre-rank, top 12 → 5 scoring subagent → 6a tiered research (top 3–4) / 6b structured-only rest → 7 time-and-access fact check → 8 assemble note → 9 curl sweep → lint gate → Instagram check → browser verify → fix (cap 2 rounds) → 10 deliver → 11 feedback round updates preferences.md`.

### Design notes

- 範圍是時間預算不是直線半徑 —— 直線距離在有河、鐵道、高速公路切斷處會嚴重騙人；`reachable` 換到可信的分鐘數（WALK／DRIVE 用一次 batched matrix 呼叫；TRANSIT 的 `computeRouteMatrix` 對每個 element 都回 200 加 `ROUTE_NOT_FOUND`，即使是真的有車可搭的路線，所以改成逐一目的地個別 route 查詢）。
- 只有「反感」能刷掉候選 —— 排序錯了看得見，篩掉錯了看不見。
- **粗排不用 `travel_min` 當主鍵，改用 `pool_hits`（查詢一致性）→ `rating`，取前 14。** 範圍在 Step 3 已經用一次真實路線呼叫守住了；粗排再用同一個量當主軸，等於把同一個條件用兩次，而且用的是使用者沒要求的粒度。實測翻車過：渋谷駅 15 分內的 23 家精釀店分佈在 1–8 分，舊排序選出的 12 家恰好就是 1–3 分的全部 —— 整份名單被 15 分鐘預算裡的一個 2 分鐘窗口決定，`rating` 一次都沒被用到，該區最知名的三家精釀店全部出局，擠進來的是水煙店與吃到飽燒肉店。`pool_hits`（本次幾個查詢獨立回傳了這家店）救回全部三家外加一家沒人注意到的 4.9 分店，成本 +$0.05。它不牴觸「評論數不進粗排」的禁令，因為它算的是使用者自己的查詢詞而不是別人的人氣 —— 實測 1 次命中組裡同時有 1,318 則評論的連鎖與 34 則評論的小店。弱點是 pool 少於 3 個時會退化成常數，此時退回評分排序並在 排序依據 說明。
- **pool 寫檔不得按評論數排序。** `maps` 的 `nearby`／`search` 原本在寫 pool 前做 `sort_by(-(.reviews))`，等於在更早、更看不見的地方做了 Step 4 明令禁止的事；只因為 `--limit 20` 剛好等於 API 上限才沒出事，任何更小的 `--limit` 都會讓評論數變成篩選器而非排序。現在改為原樣保留 API 回傳順序（`searchText` 是相關性順序），並有專用 fixture（API 順序刻意與評論數相反）在測試裡守住。
- 結構化欄位一律三態，不只 amenity —— `status`、`hours` 和每個 amenity 欄位都一樣：`null` 或空值是「Google 沒資料」，不是「沒有」。`status` 的無資料值是字面上的 `"UNKNOWN"`（script 在沒有 `businessStatus` 時就寫這個值，所以這個欄位永遠不會缺席），只有 `CLOSED_PERMANENTLY`／`CLOSED_TEMPORARILY` 兩個明確值才刷掉候選；把 `UNKNOWN` 當「非營業中」處理，會悄悄刷掉每一家 Google 沒有登記營業狀態的店——正是這整套設計想保護的獨立小店。一家真的有陽台但沒被記錄的獨立店，也是使用者最想要的那種。
- 評論決定排序；進入正文只走「評論印象」這一條掛著標籤的路 —— 事實類線索仍然變成待確認問題交給研究 agent（`build-itinerary` Step 0.6 規則 1 的用法）；評論獨有的質地（氣氛、座位、排隊、招牌）則以 `<店名>（N 則評論，未驗證）：…` 的形式進筆記，兩個 skill 共用同一套寫法與禁令。標籤是這個例外唯一的安全機制，所以它跟句子一起走，不得被搬進結論表、事實句或圖說。
- 雙管道的 fallback 是「兩邊都發」—— 「什麼時候用哪個」這種判斷容易被略過，略過時掉進的必須是完整的那條路。
- 偏好檔只能 `Edit` 不能 `Write` —— 使用者手改的內容必須存活。

## Key conventions

`find-nearby` 以相對路徑引用 `build-itinerary/templates/verify-brief.md` 與 `verify-facts-brief.md`。改動那兩份時要同時考慮兩個呼叫端。引用而非複製，是因為其中的規則（`networkidle` 禁令、verify agent 不得再開 subagent）是用真實事故換來的，第二份副本等於允許漂移。

## Tests

```bash
trip-notes/tests/test-maps.sh              # maps script, offline via fixtures
trip-notes/tests/test-skill-integrity.sh   # markdown cross-references + the provenance gate is wired in
trip-notes/tests/test-note-provenance.sh   # the provenance gate itself
```
