#!/bin/bash
# Tests for trip-notes/skills/build-itinerary/scripts/maps.
#
# Every case runs the script with TRIP_MAPS_STUB_DIR pointing at a fixture
# directory, so no test ever calls the real Google API. Caching is disabled
# per-case with TRIP_MAPS_CACHE_DIR pointed at a temp dir.
#
# Exit code: 0 — all assertions pass; 1 — one or more failures.

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MAPS="$SCRIPT_DIR/../skills/build-itinerary/scripts/maps"
FIXTURES="$SCRIPT_DIR/fixtures"

PASSED=0
FAILED=0
FAIL_DETAILS=()

assert_pass() {
  PASSED=$(( PASSED + 1 ))
  printf "  PASS  %s\n" "$1"
}
assert_fail() {
  FAILED=$(( FAILED + 1 ))
  FAIL_DETAILS+=("$1 :: $2")
  printf "  FAIL  %s\n        %s\n" "$1" "$2"
}
assert_eq() {  # <name> <expected> <actual>
  if [[ "$2" == "$3" ]]; then assert_pass "$1"
  else assert_fail "$1" "expected [$2] got [$3]"; fi
}

# run_maps <args...> — runs maps against the fixtures with a throwaway cache.
run_maps() {
  local cache
  cache=$(mktemp -d)
  TRIP_MAPS_STUB_DIR="$FIXTURES" \
  TRIP_MAPS_CACHE_DIR="$cache" \
  GOOGLE_MAPS_API_KEY="test-key-not-used" \
    "$MAPS" "$@"
  local rc=$?
  rm -rf "$cache"
  return $rc
}

# run_maps_in <stub-dir> <args...> — same, but against an alternate fixture
# directory. Used where a case needs a DIFFERENT canned API response from the
# default one (batching, the TRANSIT no-route case).
run_maps_in() {
  local stub="$1"; shift
  local cache
  cache=$(mktemp -d)
  TRIP_MAPS_STUB_DIR="$stub" \
  TRIP_MAPS_CACHE_DIR="$cache" \
  GOOGLE_MAPS_API_KEY="test-key-not-used" \
    "$MAPS" "$@"
  local rc=$?
  rm -rf "$cache"
  return $rc
}

echo "== stub hook =="

out=$(run_maps nearby --limit 2 "35.681,139.767" 500 restaurant 2>&1)
assert_eq "nearby reads the stub instead of calling Google" \
  "2" "$(jq -r '.shown' <<<"$out" 2>/dev/null)"

echo "== existing behaviour (build-itinerary depends on all of this) =="

out=$(run_maps nearby --limit 8 "35.681,139.767" 500 restaurant 2>&1)

assert_eq "nearby sorts by review count, most-reviewed first" \
  "PLACE_A" "$(jq -r '.places[0].place_id' <<<"$out")"
assert_eq "nearby carries businessStatus through verbatim" \
  "CLOSED_PERMANENTLY" "$(jq -r '.places[] | select(.place_id=="PLACE_C") | .status' <<<"$out")"
assert_eq "nearby uses the API googleMapsUri verbatim" \
  "https://maps.google.com/?cid=1" "$(jq -r '.places[0].maps_url' <<<"$out")"
assert_eq "a place whose days differ keeps its full 7-line hours array" \
  "7" "$(jq -r '.places[] | select(.place_id=="PLACE_A") | .hours.hours | length' <<<"$out")"
assert_eq "a place whose open days share one range is collapsed to a string" \
  "11:00～21:00" "$(jq -r '.places[] | select(.place_id=="PLACE_B") | .hours.hours' <<<"$out")"
assert_eq "定休日 is preserved in the closed array" \
  "日" "$(jq -r '.places[] | select(.place_id=="PLACE_B") | .hours.closed[0]' <<<"$out")"
assert_eq "--limit truncates after sorting" \
  "1" "$(run_maps nearby --limit 1 "35.681,139.767" 500 restaurant 2>&1 | jq -r '.places | length')"
assert_eq "provenance fields are always attached" \
  "false" "$(jq -r '.from_cache' <<<"$out")"

# --out must keep the payload out of stdout — the whole point of Step 0.7.
tmp_out=$(mktemp)
summary=$(run_maps nearby --limit 8 --out "$tmp_out" "35.681,139.767" 500 restaurant 2>&1)
assert_eq "--out prints only a summary" "$tmp_out" "$(jq -r '.written' <<<"$summary")"
assert_eq "--out summary counts records" "3" "$(jq -r '.records' <<<"$summary")"
assert_eq "--out writes the full payload to the file" \
  "3" "$(jq -r '.places | length' "$tmp_out")"
assert_eq "--out summary does not leak place names" \
  "" "$(grep -o '喫茶アルファ' <<<"$summary")"
rm -f "$tmp_out"

echo "== details / reviews reach their own stubs =="

out=$(run_maps details PLACE_A 2>&1)
assert_eq "details reads its own stub and projects the website field" \
  "https://alpha-coffee.example.jp" "$(jq -r '.website' <<<"$out")"

out=$(run_maps reviews PLACE_A 2>&1)
assert_eq "reviews reads its own stub" \
  "PLACE_A" "$(jq -r '.place_id' <<<"$out")"
# The fixture is deliberately stored oldest-first so this assertion is only
# satisfied if the projection's `sort_by(.date) | reverse` actually runs — do
# not "tidy" the fixture back into chronological order.
assert_eq "reviews are sorted newest-first" \
  "2026-07-01 2025-08-01" "$(jq -r '[.reviews[].date] | join(" ")' <<<"$out")"

echo "== reviews (single vs multi) =="

single=$(run_maps reviews PLACE_A 2>&1)
assert_eq "one id keeps the existing top-level shape" \
  "PLACE_A" "$(jq -r '.place_id' <<<"$single")"
assert_eq "one id keeps the caveat field" \
  "true" "$(jq -r 'has("caveat")' <<<"$single")"

multi=$(run_maps reviews PLACE_A PLACE_B 2>&1)
assert_eq "two ids return a wrapped list" "2" "$(jq -r '.count' <<<"$multi")"
assert_eq "wrapped entries keep the single-id shape" \
  "PLACE_A" "$(jq -r '.places[0].place_id' <<<"$multi")"
assert_eq "the caveat is carried on every entry" \
  "true" "$(jq -r '.places[1] | has("caveat")' <<<"$multi")"
assert_eq "multi reviews honours --out and counts records" \
  "2" "$(t=$(mktemp); run_maps reviews --out "$t" PLACE_A PLACE_B | jq -r '.records'; rm -f "$t")"

echo "== nearby --fields (amenity fields are three-state) =="

out=$(run_maps nearby --limit 8 --fields outdoorSeating,allowsDogs \
        "35.681,139.767" 500 restaurant 2>&1)

assert_eq "a true amenity surfaces as true" \
  "true" "$(jq -r '.places[] | select(.place_id=="PLACE_A") | .amenities.outdoor_seating' <<<"$out")"
assert_eq "a false amenity surfaces as false" \
  "false" "$(jq -r '.places[] | select(.place_id=="PLACE_A") | .amenities.allows_dogs' <<<"$out")"
assert_eq "an unset amenity is ABSENT, not false" \
  "null" "$(jq -r '.places[] | select(.place_id=="PLACE_C") | .amenities.outdoor_seating' <<<"$out")"
assert_eq "a place with no amenity data gets an empty amenities object" \
  "0" "$(jq -r '.places[] | select(.place_id=="PLACE_C") | .amenities | length' <<<"$out")"

# Without --fields the output shape must be exactly what it was before.
plain=$(run_maps nearby --limit 8 "35.681,139.767" 500 restaurant 2>&1)
assert_eq "without --fields there is no amenities key at all" \
  "false" "$(jq -r '.places[0] | has("amenities")' <<<"$plain")"

# A typo must fail loudly rather than being silently dropped by the API.
if run_maps nearby --fields notAField "35.681,139.767" 500 restaurant >/dev/null 2>&1; then
  assert_fail "an unknown --fields name is rejected" "exited 0"
else
  assert_pass "an unknown --fields name is rejected"
fi

echo "== search (searchText channel) =="

out=$(run_maps search --limit 20 "35.681,139.767" 1500 "タイ料理 テラス席" 2>&1)

assert_eq "search returns the fixture's places" "2" "$(jq -r '.returned' <<<"$out")"
assert_eq "search output uses the same top-level keys as nearby" \
  "places returned shown" "$(jq -r 'del(.fetched,.from_cache) | keys | join(" ")' <<<"$out")"
assert_eq "search output uses the same per-place keys as nearby" \
  "$(run_maps nearby --limit 1 "35.681,139.767" 500 restaurant | jq -r '.places[0] | keys | join(" ")')" \
  "$(jq -r '.places[0] | keys | join(" ")' <<<"$out")"
assert_eq "search sorts by review count like nearby" \
  "PLACE_A" "$(jq -r '.places[0].place_id' <<<"$out")"
assert_eq "search honours --out" \
  "2" "$(t=$(mktemp); run_maps search --limit 20 --out "$t" "35.681,139.767" 1500 "タイ料理" >/dev/null; jq -r '.places|length' "$t"; rm -f "$t")"

# SKILL.md tells the agent to give `search` a WIDER --limit than `nearby`,
# because search's circle is only a bias and part of the pool is spent out of
# range. searchText is capped at 20 all the same, so --limit 30 quietly returns
# 20. `nearby` prints a cap note in exactly this situation; `search` must too.
cap=$(run_maps search --limit 30 "35.681,139.767" 1500 "タイ料理" 2>&1 >/dev/null)
case "$cap" in
  *"capped to 20"*) assert_pass "search warns on stderr when --limit exceeds the API cap" ;;
  *) assert_fail "search warns on stderr when --limit exceeds the API cap" "stderr was [$cap]" ;;
esac

echo "== reachable (merge + dedupe + travel-time filter) =="

pool_a=$(mktemp); pool_b=$(mktemp)
run_maps nearby --limit 20 --out "$pool_a" "35.681,139.767" 1500 cafe >/dev/null
run_maps search --limit 20 --out "$pool_b" "35.681,139.767" 1500 "タイ料理" >/dev/null

out=$(run_maps reachable --from "35.681,139.767" --mode WALK --max-min 15 "$pool_a" "$pool_b" 2>&1)

assert_eq "duplicate place_id across pools collapses to one record" \
  "4" "$(jq -r '.considered' <<<"$out")"
assert_eq "candidates over the time budget are dropped" \
  "2" "$(jq -r '.returned' <<<"$out")"
assert_eq "the drop count is reported, not silent" \
  "1" "$(jq -r '.dropped_over_limit' <<<"$out")"
assert_eq "an unroutable candidate is counted separately from an over-budget one" \
  "1" "$(jq -r '.unroutable' <<<"$out")"
assert_eq "travel_min is rounded minutes, not seconds" \
  "3" "$(jq -r '.places[] | select(.place_id=="PLACE_A") | .travel_min' <<<"$out")"
assert_eq "distance_km is present and in km" \
  "0.6" "$(jq -r '.places[] | select(.place_id=="PLACE_B") | .distance_km' <<<"$out")"
assert_eq "results are sorted nearest-first" \
  "PLACE_A PLACE_B" "$(jq -r '[.places[].place_id] | join(" ")' <<<"$out")"
assert_eq "pool record fields survive the merge" \
  "喫茶アルファ" "$(jq -r '.places[] | select(.place_id=="PLACE_A") | .name' <<<"$out")"
assert_eq "amenities survive the merge when the pool had them" \
  "true" "$(pa=$(mktemp); run_maps nearby --limit 20 --fields outdoorSeating --out "$pa" "35.681,139.767" 1500 cafe >/dev/null; run_maps reachable --from "35.681,139.767" --mode WALK --max-min 15 "$pa" | jq -r '.places[] | select(.place_id=="PLACE_A") | .amenities.outdoor_seating'; rm -f "$pa")"
assert_eq "reachable honours --out" \
  "2" "$(t=$(mktemp); run_maps reachable --from "35.681,139.767" --mode WALK --max-min 15 --out "$t" "$pool_a" "$pool_b" >/dev/null; jq -r '.places|length' "$t"; rm -f "$t")"
assert_eq "--out record count matches the returned places, not the pool" \
  "2" "$(t=$(mktemp); run_maps reachable --from "35.681,139.767" --mode WALK --max-min 15 --out "$t" "$pool_a" "$pool_b" | jq -r '.records'; rm -f "$t")"

# A missing pool file must be an error, not an empty-but-plausible result.
if run_maps reachable --from "35.681,139.767" --mode WALK --max-min 15 /nonexistent/pool.json >/dev/null 2>&1; then
  assert_fail "a missing pool file is rejected" "exited 0"
else
  assert_pass "a missing pool file is rejected"
fi

echo "== reachable TRANSIT does not use computeRouteMatrix =="

# computeRouteMatrix returns HTTP 200 for TRANSIT and then reports
# ROUTE_NOT_FOUND on every element (see references/api-facts.md), so TRANSIT
# must fall back to computeRoutes per destination. The two fixtures carry
# deliberately different durations — matrix says PLACE_A is 3 min, computeRoutes
# says 12 — so this number alone identifies which endpoint was used.
out=$(run_maps reachable --from "35.681,139.767" --mode TRANSIT --max-min 15 "$pool_a" "$pool_b" 2>&1)

assert_eq "TRANSIT reads computeRoutes, not the matrix (12m fixture, not 3m)" \
  "12" "$(jq -r '.places[] | select(.place_id=="PLACE_A") | .travel_min' <<<"$out")"
assert_eq "TRANSIT resolves every candidate rather than reporting none reachable" \
  "4" "$(jq -r '.returned' <<<"$out")"
assert_eq "TRANSIT reports no unroutable candidates when every route resolves" \
  "0" "$(jq -r '.unroutable' <<<"$out")"
assert_eq "TRANSIT distance comes from the computeRoutes response" \
  "3" "$(jq -r '.places[] | select(.place_id=="PLACE_A") | .distance_km' <<<"$out")"
assert_eq "the mode is echoed back unchanged" \
  "TRANSIT" "$(jq -r '.mode' <<<"$out")"

# HTTP 200 with an empty `routes` array is the computeRoutes equivalent of
# condition != ROUTE_EXISTS. It must be counted, not silently treated as 0 min.
out=$(run_maps_in "$FIXTURES/transit-noroute" reachable \
        --from "35.681,139.767" --mode TRANSIT --max-min 15 "$pool_a" "$pool_b" 2>&1)
assert_eq "a computeRoutes 200 with no route counts as unroutable" \
  "4" "$(jq -r '.unroutable' <<<"$out")"
assert_eq "an unresolved TRANSIT route is never reported as a 0-minute walk" \
  "0" "$(jq -r '.returned' <<<"$out")"

echo "== reachable treats a missing duration as unroutable, not 0 minutes =="

# A leg with a resolved condition but NO duration is the same failure class as
# an unresolved one, and a worse-looking one: `.duration // "0s"` renders it as
# 0 min / 0 km, which sorts FIRST and reads as the nearest candidate. A leg is
# only usable if it resolved AND carries a duration.
out=$(run_maps_in "$FIXTURES/matrix-noduration" reachable \
        --from "35.681,139.767" --mode WALK --max-min 15 "$pool_a" "$pool_b" 2>&1)
assert_eq "a matrix leg with ROUTE_EXISTS but no duration counts as unroutable" \
  "4" "$(jq -r '.unroutable' <<<"$out")"
assert_eq "a matrix leg with no duration never reaches places as a 0-minute trip" \
  "0" "$(jq -r '.places | length' <<<"$out")"

out=$(run_maps_in "$FIXTURES/transit-noduration" reachable \
        --from "35.681,139.767" --mode TRANSIT --max-min 15 "$pool_a" "$pool_b" 2>&1)
assert_eq "a TRANSIT route present but without a duration counts as unroutable" \
  "4" "$(jq -r '.unroutable' <<<"$out")"
assert_eq "a TRANSIT route with no duration never reaches places as a 0-minute trip" \
  "0" "$(jq -r '.places | length' <<<"$out")"

echo "== reachable rejects a numeric duration, which rtrimstr cannot clean =="

# `.duration | rtrimstr("s") | tonumber` looks like it validates, but rtrimstr is
# a NO-OP on a non-string: a raw JSON number sails straight into tonumber and
# becomes a real leg. `duration: 0` then renders as a 0-minute trip that SORTS
# FIRST — the nearest candidate in the list. The type must be checked, not the
# suffix.
out=$(run_maps_in "$FIXTURES/matrix-numduration" reachable \
        --from "35.681,139.767" --mode WALK --max-min 15 "$pool_a" "$pool_b" 2>&1)
assert_eq "a matrix leg whose duration is a number counts as unroutable" \
  "4" "$(jq -r '.unroutable' <<<"$out")"
assert_eq "a numeric duration never reaches places as a 0-minute trip" \
  "0" "$(jq -r '.places | length' <<<"$out")"

out=$(run_maps_in "$FIXTURES/transit-numduration" reachable \
        --from "35.681,139.767" --mode TRANSIT --max-min 15 "$pool_a" "$pool_b" 2>&1)
assert_eq "a TRANSIT route whose duration is a number counts as unroutable" \
  "4" "$(jq -r '.unroutable' <<<"$out")"
assert_eq "a numeric TRANSIT duration never reaches places as a 0-minute trip" \
  "0" "$(jq -r '.places | length' <<<"$out")"

echo "== a missing distance is null, never a confident 0.0 km =="

# A leg that resolves and carries a duration but no distanceMeters used to
# render as "0.0 km" beside a real travel time — a plausible number with
# nothing behind it, the same failure shape as the 0-minute leg above.
out=$(run_maps_in "$FIXTURES/matrix-nodistance" reachable \
        --from "35.681,139.767" --mode WALK --max-min 15 "$pool_a" "$pool_b" 2>&1)
assert_eq "a matrix leg with no distanceMeters still resolves on duration" \
  "0" "$(jq -r '.unroutable' <<<"$out")"
assert_eq "a matrix leg with no distanceMeters reports distance_km null, not 0" \
  "null" "$(jq -r '[.places[].distance_km] | unique | .[0] | tostring' <<<"$out")"

out=$(run_maps_in "$FIXTURES/transit-nodistance" reachable \
        --from "35.681,139.767" --mode TRANSIT --max-min 15 "$pool_a" "$pool_b" 2>&1)
assert_eq "a TRANSIT route with no distanceMeters reports distance_km null, not 0" \
  "null" "$(jq -r '[.places[].distance_km] | unique | .[0] | tostring' <<<"$out")"

echo "== reachable merges same-place records field-wise, whatever the file order =="

# `unique_by(.place_id)` kept only the FIRST record for a repeated id. `search`
# calls place_row({}) and carries no `amenities` key at all, and under SKILL.md's
# own file naming `pool-text-*.json` sorts BEFORE `pool-<type>.json` under the
# documented `pool-*.json` glob — so the amenity-less record won and a confirmed
# `true` silently became "Google has no data". File order must not decide that.
amen_pool=$(mktemp); plain_pool=$(mktemp)
run_maps nearby --limit 20 --fields outdoorSeating --out "$amen_pool" \
  "35.681,139.767" 1500 cafe >/dev/null
run_maps search --limit 20 --out "$plain_pool" "35.681,139.767" 1500 "タイ料理" >/dev/null

# The amenity-LESS pool is listed FIRST here on purpose. That is the ordering the
# old code got wrong; with a single pool, or with the amenity pool first, the bug
# is invisible.
out=$(run_maps reachable --from "35.681,139.767" --mode WALK --max-min 15 \
        "$plain_pool" "$amen_pool" 2>&1)
assert_eq "an amenity survives when the amenity-less pool is listed FIRST" \
  "true" "$(jq -r '.places[] | select(.place_id=="PLACE_A") | .amenities.outdoor_seating' <<<"$out")"
# The merge must still SORT by place_id — unique_by did, and every
# destinationIndex sent to computeRouteMatrix is an index into THAT order. If the
# merged order became file order instead, the legs would still all be consumed,
# but each would attach to the wrong place: silently wrong travel times rather
# than an error. The observable is the leg each place ends up with, checked with
# the two pools in BOTH orders — a file-order merge gives different answers.
legs() { jq -r '[.places[] | "\(.place_id)=\(.travel_min)"] | sort | join(" ")'; }
fwd=$(run_maps reachable --from "35.681,139.767" --mode WALK --max-min 15 \
        "$plain_pool" "$amen_pool" 2>&1 | legs)
rev=$(run_maps reachable --from "35.681,139.767" --mode WALK --max-min 15 \
        "$amen_pool" "$plain_pool" 2>&1 | legs)
assert_eq "each place keeps its own leg: the merged order is sorted by place_id" \
  "PLACE_A=3 PLACE_B=9" "$fwd"
assert_eq "the merged order does not depend on the file order" "$fwd" "$rev"

echo "== reachable carries the POOL's fetch date, not this run's =="

# nearby/search cache for 7 days, so a pool file can be a week old while the
# reachable run is today. `emit` stamps `fetched` = now on reachable's own
# output; without a separate key the note would quote today and overstate the
# freshness of opening hours. pool_fetched is the MINIMUM across the inputs —
# the oldest datum governs.
old_pool=$(mktemp); older_pool=$(mktemp)
jq '.fetched = "2020-01-02T00:00:00Z"' "$amen_pool" > "$old_pool"
jq '.fetched = "2019-05-06T00:00:00Z"' "$plain_pool" > "$older_pool"
out=$(run_maps reachable --from "35.681,139.767" --mode WALK --max-min 15 \
        "$old_pool" "$older_pool" 2>&1)
assert_eq "pool_fetched reflects the pool, not the run" \
  "2019-05-06T00:00:00Z" "$(jq -r '.pool_fetched' <<<"$out")"
assert_eq "pool_fetched is the OLDEST of the pools, not the newest" \
  "true" "$(jq -r '(.pool_fetched == "2019-05-06T00:00:00Z")
                   and (.pool_fetched != "2020-01-02T00:00:00Z")
                   and (.pool_fetched < .fetched)' <<<"$out")"
rm -f "$amen_pool" "$plain_pool" "$old_pool" "$older_pool"

echo "== reachable batching re-bases destinationIndex =="

# The stub replays the SAME canned response for every call, so a chunked run is
# exactly the shape that exposes an off-by-one: chunk 1 must have its indices
# shifted by the number of destinations already sent, or a leg lands on the
# wrong place. fixtures/batch/computeRouteMatrix.json holds two elements with
# distinct durations (60s -> 1 min, 480s -> 8 min).
#
# pool-batch.json holds three places, so --batch 2 sends:
#   chunk 0 = [PLACE_A, PLACE_B] at offset 0 -> A=1min, B=8min
#   chunk 1 = [PLACE_C]          at offset 2 -> C=1min  (only element 0 applies)
# The expected triple 1/8/1 is unique to a correct offset:
#   offset always 0     -> C never gets a leg (unroutable), returned 2
#   offset i+1          -> A never gets a leg (unroutable), B=1min not 8
#   no re-base at all   -> same as offset 0
out=$(run_maps_in "$FIXTURES/batch" reachable --from "35.681,139.767" \
        --mode WALK --max-min 15 --batch 2 "$FIXTURES/pool-batch.json" 2>&1)

assert_eq "every place in a chunked run gets a leg" \
  "3" "$(jq -r '.returned' <<<"$out")"
assert_eq "no place is left unroutable by chunking" \
  "0" "$(jq -r '.unroutable' <<<"$out")"
assert_eq "chunk 0 element 0 lands on the first place" \
  "1" "$(jq -r '.places[] | select(.place_id=="PLACE_A") | .travel_min' <<<"$out")"
assert_eq "chunk 0 element 1 lands on the second place, not the first" \
  "8" "$(jq -r '.places[] | select(.place_id=="PLACE_B") | .travel_min' <<<"$out")"
assert_eq "chunk 1 element 0 is re-based onto the third place" \
  "1" "$(jq -r '.places[] | select(.place_id=="PLACE_C") | .travel_min' <<<"$out")"
assert_eq "distances are re-based with the same offset as durations" \
  "0.1 0.8 0.1" "$(jq -r '[.places[] | {k:.place_id, d:.distance_km}] | sort_by(.k) | map(.d|tostring) | join(" ")' <<<"$out")"

# Chunking must not change the candidate set — only how it is queried.
assert_eq "chunking does not change how many candidates were considered" \
  "3" "$(jq -r '.considered' <<<"$out")"

# --batch 1 degenerates to one call per destination: three chunks, offsets 0,1,2.
out=$(run_maps_in "$FIXTURES/batch" reachable --from "35.681,139.767" \
        --mode WALK --max-min 15 --batch 1 "$FIXTURES/pool-batch.json" 2>&1)
assert_eq "--batch 1 still reaches every place" \
  "3" "$(jq -r '.returned' <<<"$out")"
assert_eq "--batch 1 gives every place the single-element response, not a shifted one" \
  "1 1 1" "$(jq -r '[.places[] | {k:.place_id, t:.travel_min}] | sort_by(.k) | map(.t|tostring) | join(" ")' <<<"$out")"

rm -f "$pool_a" "$pool_b"

echo
echo "-- $PASSED passed, $FAILED failed --"
if [[ ${#FAIL_DETAILS[@]} -gt 0 ]]; then printf '%s\n' "${FAIL_DETAILS[@]}"; fi
[[ $FAILED -eq 0 ]]
