# API facts (validated 2026-09-05)

Validated by running the probes in the Task 1 of
`docs/superpowers/plans/2026-09-05-find-nearby.md` against the live API.
Re-run those probes before trusting this file after a Google API change.

## Valid includedType strings

All 24 candidate types returned OK (either results or a valid empty list — none
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
