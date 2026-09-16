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

echo "== closed_on_target is evidence-backed, never guessed =="
SUNLOG="$TMP/sunday.jsonl"
"$SIGHTINGS" append --log "$SUNLOG" --run "$F/run-sunday.json" --top14 "$F/top14.json" \
  --shown "$F/shown-sunday.json" >/dev/null 2>&1
# 2026-09-20 is a Sunday. 小倉タイガー's own Sunday line says 定休日.
assert_eq "a real 定休日 on the target day is true, not just an open flag" "true" \
  "$(jq -sr '.[] | select(.place_id=="P_TIGER") | .closed_on_target' "$SUNLOG")"
# なかむらえん has an empty closed[] and its Sunday line is normal hours —
# there is no closure evidence either way, so this must be null, not false.
assert_eq "no closure evidence at all is null, not an invented false" "null" \
  "$(jq -sr '.[] | select(.place_id=="P_NAKA") | .closed_on_target' "$SUNLOG")"

echo "== an unknown target weekday nullifies rather than guesses =="
NOTGTLOG="$TMP/no-target.jsonl"
"$SIGHTINGS" append --log "$NOTGTLOG" --run "$F/run-no-target.json" --top14 "$F/top14.json" \
  --shown "$F/shown.json" >/dev/null 2>&1
assert_eq "with no target_date, every closed_on_target is null" "4" \
  "$(jq -sr '[.[] | select(.closed_on_target==null)] | length' "$NOTGTLOG")"
assert_eq "with no target_date, every open_from is null" "4" \
  "$(jq -sr '[.[] | select(.open_from==null)] | length' "$NOTGTLOG")"
assert_eq "with no target_date, hours_missing is true for everyone, even 飛来haku's single-string schedule" "4" \
  "$(jq -sr '[.[] | select(.hours_missing==true)] | length' "$NOTGTLOG")"

echo "== a split 中休み schedule sums the ranges, not last-minus-first =="
SPLITLOG="$TMP/split.jsonl"
"$SIGHTINGS" append --log "$SPLITLOG" --run "$F/run.json" --top14 "$F/top14-split.json" \
  --shown "$F/shown-split.json" >/dev/null 2>&1
assert_eq "open_from is the first range's open time" "11:00" \
  "$(jq -sr '.[] | select(.place_id=="P_LUNCH") | .open_from' "$SPLITLOG")"
assert_eq "close_at is the last range's close time" "21:00" \
  "$(jq -sr '.[] | select(.place_id=="P_LUNCH") | .close_at' "$SPLITLOG")"
assert_eq "hours_span_h sums both ranges (3+4), not 21-11" "7" \
  "$(jq -sr '.[] | select(.place_id=="P_LUNCH") | .hours_span_h' "$SPLITLOG")"
assert_eq "hours_split says a break happened" "true" \
  "$(jq -sr '.[] | select(.place_id=="P_LUNCH") | .hours_split' "$SPLITLOG")"
assert_eq "a single-range record is not marked split" "false" \
  "$(jq -sr '.[] | select(.place_id=="P_NAKA") | .hours_split' "$LOG")"

echo "== an empty shown.json appends nothing =="
EMPTYLOG="$TMP/empty.jsonl"
: > "$EMPTYLOG"
eout=$("$SIGHTINGS" append --log "$EMPTYLOG" --run "$F/run.json" --top14 "$F/top14.json" \
        --shown "$F/shown-empty.json" 2>&1); erc=$?
assert_eq "an empty shown.json still exits 0" "0" "$erc"
assert_has "the summary says zero records, not a blank one" "appended 0 record(s)" "$eout"
assert_eq "the log file gains no lines" "0" "$(wc -l < "$EMPTYLOG" | tr -d ' ')"

echo "== a missing flag value exits 64, not 1 =="
assert_eq "--run with no value exits 64" "64" \
  "$("$SIGHTINGS" append --log "$LOG" --run >/dev/null 2>&1; echo $?)"

echo "== run context is copied onto every record =="
assert_eq "every record carries the run_id" "4" \
  "$(jq -sr '[.[] | select(.run_id=="2026-09-16-kokura-craftbeer")] | length' "$LOG")"
assert_eq "every record carries the user's original words" "4" \
  "$(jq -sr '[.[] | select(.request | test("精釀啤酒"))] | length' "$LOG")"

echo "== append never rewrites =="
"$SIGHTINGS" append --log "$LOG" --run "$F/run.json" --top14 "$F/top14.json" \
  --shown "$F/shown.json" --pool "$F/pool-a.json" >/dev/null 2>&1
assert_eq "a second run appends rather than replacing" "8" "$(wc -l < "$LOG" | tr -d ' ')"

echo "== backfill converts the legacy evidence log without inventing fields =="
BLOG="$TMP/backfill.jsonl"
out=$("$SIGHTINGS" backfill --from "$F/legacy-preferences.md" --log "$BLOG" 2>&1); rc=$?
assert_eq "backfill exits 0" "0" "$rc"
assert_eq "three evidence lines, three records" "3" "$(wc -l < "$BLOG" | tr -d ' ')"
assert_has "the summary says how many" "backfilled 3" "$out"
assert_eq "👍 entries keep their verdict" "2" \
  "$(jq -sr '[.[]|select(.verdict=="👍")]|length' "$BLOG")"
assert_eq "👎 entries keep theirs" "1" \
  "$(jq -sr '[.[]|select(.verdict=="👎")]|length' "$BLOG")"
assert_eq "every backfilled record is flagged legacy" "3" \
  "$(jq -sr '[.[]|select(.legacy==true)]|length' "$BLOG")"
assert_eq "the date is parsed out" "2026-09-13" \
  "$(jq -sr '.[]|select(.name|test("マクドナルド"))|.run_date' "$BLOG")"
assert_eq "the region is parsed out" "埼玉東松山" \
  "$(jq -sr '.[]|select(.name|test("マクドナルド"))|.region' "$BLOG")"
assert_eq "the prose survives as a note" "全國速食連鎖" \
  "$(jq -sr '.[]|select(.name|test("マクドナルド"))|.note' "$BLOG")"
assert_eq "no field is invented to fill the gaps" "null" \
  "$(jq -sr '.[]|select(.name|test("マクドナルド"))|.rating' "$BLOG")"
assert_eq "bucket lines are not mistaken for evidence" "0" \
  "$(jq -sr '[.[]|select(.name|test("獨立店"))]|length' "$BLOG")"

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
