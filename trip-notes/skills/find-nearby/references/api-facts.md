# API facts (validated 2026-09-05)

Validated by running the probes in the Task 1 of
`docs/superpowers/plans/2026-09-05-find-nearby.md` against the live API.
Re-run those probes before trusting this file after a Google API change.

## Valid includedType strings

All 25 candidate types returned OK (either results or a valid empty list — none
returned HTTP 400) when probed with `./maps nearby --limit 1 --no-cache "35.681,139.767" 500 "$t"`
against Tokyo Station:

- general: `tourist_attraction`, `historical_landmark`
- food: `restaurant`, `cafe`, `bakery`, `thai_restaurant`, `italian_restaurant`,
  `ramen_restaurant`, `sushi_restaurant`, `japanese_restaurant`,
  `chinese_restaurant`, `vegetarian_restaurant`
- retail: `home_goods_store`, `gift_shop`, `clothing_store`, `book_store`,
  `drugstore`, `supermarket`, `convenience_store`
- green: `park`, `national_park`, `dog_park`, `hiking_area`, `garden`,
  `botanical_garden`

Rejected (do not use): none — every candidate type in the probe list is a
valid `includedType`. Note that several green-space types returned zero
results at this urban point (`national_park`, `dog_park`, `hiking_area`,
`botanical_garden` all returned 0; `garden` returned 2) — that is an empty
result set, not an invalid type. Do not conclude those types are invalid from
low/zero result counts; only an HTTP 400 would indicate that, and none
occurred.

## Amenity fields

Probed via `places:searchNearby` at Tokyo Station (radius 500m, `maxResultCount: 20`),
one field at a time in the field mask alongside `places.id`.

| Field | Valid | Set on N of 20 sampled | Notes |
|---|---|---|---|
| outdoorSeating | yes | 1/20 | |
| allowsDogs | yes | 2/20 | |
| servesVegetarianFood | yes | 1/20 | |
| goodForChildren | yes | 3/20 | |
| restroom | yes | 13/20 | |
| goodForGroups | yes | 1/20 | |
| servesBreakfast | yes | 1/20 | |
| liveMusic | yes | 1/20 | |
| accessibilityOptions | yes | 20/20 | **Set on ALL 20 sampled places.** The three-state (true/false/no-data) case was NOT observed for this field in this sample — it may still occur for other places/regions, but this probe gives no evidence of a null case for `accessibilityOptions`. Treat it as effectively always-present here, not as proof it can never be absent. |
| parkingOptions | yes | 6/20 | |

All 10 candidate field names are valid (all returned HTTP 200; none returned
HTTP 400). The "set on N of 20" column is the evidence for the three-state
rule: for every field except `accessibilityOptions`, a majority of the 20
sampled places did NOT have the field set, confirming that a missing field
means Google has no data — not that the answer is "no" (e.g. "no outdoor
seating"). `accessibilityOptions` is the one exception observed: it was
present on all 20 samples, so for that field this sample offers no evidence
of the null case at all (unobserved, not absent — see note above).

## computeRouteMatrix

Endpoint: `https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix`
Response shape: **JSON array** — the raw response body starts with `[` and
ends with `]`, containing one JSON object per origin/destination pair,
comma-separated (pretty-printed, so each object spans multiple lines). This
was confirmed by inspecting the raw bytes of the response file (`head -c`/`tail -c`
and `jq 'type'` returned `"array"`), not by assuming from field-mask docs. It
is NOT newline-delimited JSON (NDJSON) — the elements are members of one JSON
array, not separate top-level JSON values one per line. A parser for this
response must parse the whole body as a single JSON array.

| Mode | Supported | Max destinations observed | Error at over-limit |
|---|---|---|---|
| WALK | yes | 60 observed directly (n=10 and n=60 both returned 200 with all elements `ROUTE_EXISTS`); cap inferred at 625 from DRIVE's mode-independent error text — NOT independently pushed to 626 for WALK, so 625 is an inference, not an observation, for this mode | `Request exceeded the maximum number of elements. The product of the number of origins and destinations must be <= 625.` (verified on DRIVE at n=626; the error text is about total element count, not mode-specific, so it should apply identically to WALK, but this has not been directly confirmed for WALK) |
| DRIVE | yes | 625 (1 origin × 625 destinations returned 200; 626 returned HTTP 400) | `Request exceeded the maximum number of elements. The product of the number of origins and destinations must be <= 625.` (verbatim, from the live 626-destination probe) |
| TRANSIT | **no — silently, not via an error** | n/a | HTTP 200 for both n=10 and n=60 destinations, but every single element came back with `"condition": "ROUTE_NOT_FOUND"` and no `duration`/`distanceMeters`. This was also confirmed on a real, far-apart, transit-served pair (Tokyo Station → Shibuya Station, ~6km), which still returned `ROUTE_NOT_FOUND` for the one element. computeRouteMatrix does not return an explicit "unsupported mode" error for TRANSIT — it accepts the request (HTTP 200) and reports every element as route-not-found. **Do not treat HTTP 200 as proof TRANSIT works** — inspect the per-element `condition` field. Treat TRANSIT as unsupported by this endpoint for planning purposes. |

Only DRIVE's cap was pushed to the actual breaking point (100 → 200 → 625 → 626 →
700 destinations, single origin). WALK was confirmed to work up to 60
destinations directly and up to 625 by extension, since the error text
explicitly states the limit is on the *product of origins and destinations*
(mode-independent), not a per-mode limit — this was not re-verified by
independently pushing WALK to 626 to save API calls once the mode-independent
nature of the cap was confirmed via the error message on DRIVE.

Chosen batch size per mode: **600** for WALK and DRIVE — comfortably at or
below the observed/documented cap of 625 total elements (origins ×
destinations), leaving headroom for a multi-origin matrix. TRANSIT should not
be batched through `computeRouteMatrix` at all; a later task needs a
different approach (e.g. `computeRoutes` per-pair, or treat transit times as
unavailable) since this endpoint reports `ROUTE_NOT_FOUND` for every TRANSIT
element regardless of real-world reachability.

## searchText location parameters

Probed via `places:searchText` with `textQuery: "タイ料理"`, `languageCode: "ja"`,
`regionCode: "JP"`, `maxResultCount: 20`, and a `circle` (center 35.681,139.767,
radius 1500m) passed under each parameter name in turn.

| Parameter | Circle accepted | Notes |
|---|---|---|
| locationBias | yes | HTTP 200, returned 20 results. |
| locationRestriction | **no** | HTTP 400: `Invalid JSON payload received. Unknown name "circle" at 'location_restriction': Cannot find field.` The API rejects the `circle` sub-field entirely under `locationRestriction` for `searchText` — it is not merely ignored, the request is malformed. |

Consequence for `trip-maps search`: `locationRestriction` cannot be given a
circle for `searchText` (confirming, not contradicting, the plan's
expectation), so `search` cannot be made a hard-bounded query via a circular
`locationRestriction`; it must continue to use `locationBias` (soft bias
only) and rely on post-filtering results by distance if a hard radius bound
is required.

## End-to-end smoke run

日期：2026-09-05　起點：清澄白河駅

| 檢查 | 結果 |
|---|---|
| place → nearby → search → reachable 全鏈 | 全部成功。`place` 解出 place_id `ChIJaX6cwT2JGGARKz3KrG7DRWU`、latlng `35.6822525,139.79877779999998`；`nearby --fields outdoorSeating`（cafe，20 筆）與 `search`（"焙煎 コーヒー"，20 筆）各自成功；`reachable --mode WALK --max-min 15` 成功合併兩個 pool 並回傳 21 筆。 |
| 去重後候選數 / 通過 15 分的數量 | `considered: 40`（= 兩個 pool 各 20 筆的 place_id 聯集，人工核對兩池無重複，聯集剛好 40，與 considered 相符）／`returned: 21` 通過 15 分鐘步行門檻。counter 恆等式核對：`returned(21) + dropped_over_limit(19) + unroutable(0) = 40 = considered`，完全吻合，沒有候選在計數中憑空消失。 |
| amenity 三態（true / false / 缺值）是否都出現 | **三態都真實出現**：`outdoor_seating` 為 `true` 5 筆、`false` 7 筆、缺值（`has` 為 false）9 筆。進一步核對缺值的 9 筆來源：7 筆來自 `search`（該管道本來就不帶 amenities，屬結構性缺席，不算三態證據），但另外 2 筆（ChIJZy2XZNeJGGARlRcCEKxTyqE、ChIJVVVFYByJGGARTOh1_yauRZ4）來自有明確傳 `--fields outdoorSeating` 的 `nearby` 池，這 2 筆才是「Google 真的沒有這欄位資料」的證據。結論：三態規則在本次 run 中**確實被觀察到**，不是理論上的。 |
| reviews 多 id | 對 reachable 結果前 12 筆呼叫 `maps reviews <12 ids>`，`count: 12`，與傳入的 id 數一致（≤12）。 |
| 第二次呼叫命中快取 | 命中。`--refresh` 強制刷新後 `from_cache: false`；緊接著同樣參數再呼叫一次 `from_cache: true` 且明顯變快。另外測了關鍵情境：同座標同半徑、只換 `--fields`（`outdoorSeating` → `allowsDogs`）→ `from_cache: false`，證明 `--fields` 確實參與 cache key，不會把換了欄位遮罩的請求誤判成快取命中。 |

**與 api-facts 上半部記載不符之處 / 額外發現：**

1. **（非本檔案上半部記載範圍，但值得記一筆）`maps reviews` 的多 id 呼叫在 zsh 互動測試中曾多次觸發 `curl: (3) URL rejected: Malformed input to a URL function`。追查後確認這不是腳本或即時 API 的缺陷，而是測試腳本自己的 zsh 用字陷阱**：把 id 清單存進純量變數（例如 `ids=$(jq -r '... | join(" ")')`）後未加引號展開（`$ids`）在 zsh 預設行為下**不會**依空白斷字（不同於 bash），整串帶空白的字串被當成單一個引數傳給 `maps`，place_id 裡混進空白自然讓 curl 判定 URL 不合法。改用 `${=ids}`（強制斷字）或直接列出字面 id 之後，同一支 12-id 指令一次就成功（`count: 12`，見上表）。**這是操作面的坑，不是 find-nearby 或 trip-maps 程式碼的 bug**，但如果之後有人在 zsh 下手動重跑這些多 id 指令，會踩到一樣的陷阱，值得記下來提醒。
2. `search` 回傳的紀錄形狀與 `nearby` 幾乎完全一致（`address, hours, latlng, maps_url, name, place_id, rating, reviews, status, type`），差異只有 `amenities` 這個 key：`nearby` 因為呼叫時帶了 `--fields outdoorSeating` 所以有；`search` 指令本身不支援 `--fields`（程式碼裡呼叫 `place_row({})`，傳空 amenities），所以永遠沒有這個 key。這是設計上的差異，不是 shape mismatch；`reachable` 合併兩池後兩種來源都能正常被後續程式碼消費（用 `has()` 判斷欄位存在與否本來就是三態設計的一部分）。
3. `reachable.json` 的 `status` 欄位在本次 run 中出現 `OPERATIONAL`（20 筆）與 `CLOSED_TEMPORARILY`（1 筆）兩種值，沒有出現 `UNKNOWN`——這點在本次 12 個地點的樣本中沒被觸發到，不影響三態規則本身（`UNKNOWN` 的行為已由先前任務的離線測試涵蓋），僅記錄本次實際觀察到的分布。
