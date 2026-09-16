#!/bin/bash
# sightings: does every shown candidate become one honest, complete record?
#
# The failure this guards: the old preference file stored only the two or three
# venues the user marked, so the gap between the rank we showed and the choice
# they made — the one signal that says where we were wrong — was thrown away
# every single run.

set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SIGHTINGS="$SCRIPT_DIR/../skills/find-nearby/scripts/sightings"
F="$SCRIPT_DIR/fixtures/sightings"

PASSED=0; FAILED=0; FAIL_DETAILS=()
assert_pass() { PASSED=$((PASSED+1)); printf "  PASS  %s\n" "$1"; }
assert_fail() { FAILED=$((FAILED+1)); FAIL_DETAILS+=("$1 :: $2"); printf "  FAIL  %s\n        %s\n" "$1" "$2"; }
assert_eq() { if [[ "$2" == "$3" ]]; then assert_pass "$1"; else assert_fail "$1" "expected [$2] got [$3]"; fi; }
assert_has() { if grep -qF "$2" <<<"$3"; then assert_pass "$1"; else assert_fail "$1" "missing [$2] in: $3"; fi; }

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
LOG="$TMP/sightings.jsonl"

echo "== the script exists and is executable =="
if [[ -x "$SIGHTINGS" ]]; then assert_pass "sightings is executable"
else assert_fail "sightings is executable" "not found or not +x at $SIGHTINGS"; fi

echo "== every shown candidate becomes exactly one record =="
out=$("$SIGHTINGS" append --log "$LOG" --run "$F/run.json" --top14 "$F/top14.json" \
        --shown "$F/shown.json" --pool "$F/pool-a.json" --pool "$F/pool-b.json" 2>&1); rc=$?
assert_eq "append exits 0" "0" "$rc"
assert_eq "four shown candidates, four lines" "4" "$(wc -l < "$LOG" | tr -d ' ')"
assert_has "the summary counts the verdicts" "1 👍 / 1 👎 / 2 unmarked" "$out"

echo "== unmarked candidates are recorded too =="
assert_eq "the unpicked #2 is in the log" "1" \
  "$(jq -sr '[.[] | select(.place_id=="P_HAKU")] | length' "$LOG")"
assert_eq "its verdict is null, not absent" "null" \
  "$(jq -sr '.[] | select(.place_id=="P_HAKU") | .verdict' "$LOG")"
assert_eq "rank_shown survives so we can measure our own error" "2" \
  "$(jq -sr '.[] | select(.place_id=="P_HAKU") | .rank_shown' "$LOG")"

echo "== matched_queries comes from the pools, in the user's own words =="
assert_eq "a place both queries hit lists both" "クラフトビール,角打ち" \
  "$(jq -sr '.[] | select(.place_id=="P_NAKA") | .matched_queries | sort | join(",")' "$LOG")"
assert_eq "a place one query hit lists one" "角打ち" \
  "$(jq -sr '.[] | select(.place_id=="P_HAKU") | .matched_queries | join(",")' "$LOG")"
assert_eq "a place no pool hit gets an empty list, not null" "0" \
  "$(jq -sr '.[] | select(.place_id=="P_BUMBLE") | .matched_queries | length' "$LOG")"

echo "== hours are derived for the TARGET weekday, not today =="
# 2026-09-19 is a Saturday. なかむらえん opens 13:00 on Saturdays, 15:00 on weekdays.
assert_eq "per-weekday hours pick the target day" "13:00" \
  "$(jq -sr '.[] | select(.place_id=="P_NAKA") | .open_from' "$LOG")"
assert_eq "span is computed from the target day" "8" \
  "$(jq -sr '.[] | select(.place_id=="P_NAKA") | .hours_span_h' "$LOG")"
# 飛来haku has one string for every day.
assert_eq "a single-string schedule applies to every day" "19:00" \
  "$(jq -sr '.[] | select(.place_id=="P_HAKU") | .open_from' "$LOG")"
assert_eq "a schedule crossing midnight spans forward, not negative" "5" \
  "$(jq -sr '.[] | select(.place_id=="P_HAKU") | .hours_span_h' "$LOG")"

echo "== missing data stays missing =="
assert_eq "no hours means null open_from, never a guess" "null" \
  "$(jq -sr '.[] | select(.place_id=="P_BUMBLE") | .open_from' "$LOG")"
assert_eq "and it is flagged rather than silently empty" "true" \
  "$(jq -sr '.[] | select(.place_id=="P_BUMBLE") | .hours_missing' "$LOG")"
assert_eq "a non-首選 row carries no invented research block" "null" \
  "$(jq -sr '.[] | select(.place_id=="P_TIGER") | .research' "$LOG")"
assert_eq "a 首選 row keeps the research it really had" "false" \
  "$(jq -sr '.[] | select(.place_id=="P_NAKA") | .research.own_production' "$LOG")"

echo "== 定休日 on the target day is recorded as closed =="
# 小倉タイガー is closed Sundays; the target date is a Saturday, so it is open.
assert_eq "an open target day is not marked closed" "false" \
  "$(jq -sr '.[] | select(.place_id=="P_TIGER") | .closed_on_target' "$LOG")"

echo "== run context is copied onto every record =="
assert_eq "every record carries the run_id" "4" \
  "$(jq -sr '[.[] | select(.run_id=="2026-09-16-kokura-craftbeer")] | length' "$LOG")"
assert_eq "every record carries the user's original words" "4" \
  "$(jq -sr '[.[] | select(.request | test("精釀啤酒"))] | length' "$LOG")"

echo "== append never rewrites =="
"$SIGHTINGS" append --log "$LOG" --run "$F/run.json" --top14 "$F/top14.json" \
  --shown "$F/shown.json" --pool "$F/pool-a.json" >/dev/null 2>&1
assert_eq "a second run appends rather than replacing" "8" "$(wc -l < "$LOG" | tr -d ' ')"

echo "== usage errors are distinguishable =="
assert_eq "no subcommand exits 64" "64" "$("$SIGHTINGS" >/dev/null 2>&1; echo $?)"
assert_eq "a missing --run file exits 64" "64" \
  "$("$SIGHTINGS" append --log "$LOG" --run "$F/nope.json" --top14 "$F/top14.json" --shown "$F/shown.json" >/dev/null 2>&1; echo $?)"
assert_eq "a shown place_id absent from top14 exits 65" "65" \
  "$(echo '[{"place_id":"P_GHOST","rank_shown":1,"tier":"首選","verdict":null}]' > "$TMP/ghost.json"
    "$SIGHTINGS" append --log "$LOG" --run "$F/run.json" --top14 "$F/top14.json" --shown "$TMP/ghost.json" >/dev/null 2>&1; echo $?)"

echo
if [[ $FAILED -gt 0 ]]; then
  printf -- "-- %d passed, %d failed --\n" "$PASSED" "$FAILED"
  for d in "${FAIL_DETAILS[@]}"; do printf "   %s\n" "$d"; done
  exit 1
fi
printf -- "-- %d passed --\n" "$PASSED"
