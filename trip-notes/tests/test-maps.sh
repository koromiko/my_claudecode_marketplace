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
assert_eq "reviews are sorted newest-first" \
  "2026-07-01 2025-08-01" "$(jq -r '[.reviews[].date] | join(" ")' <<<"$out")"

echo
echo "-- $PASSED passed, $FAILED failed --"
if [[ ${#FAIL_DETAILS[@]} -gt 0 ]]; then printf '%s\n' "${FAIL_DETAILS[@]}"; fi
[[ $FAILED -eq 0 ]]
