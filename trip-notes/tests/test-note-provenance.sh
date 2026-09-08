#!/bin/bash
# note-provenance: does the note only state facts the data supports?
#
# The failure this guards is not hypothetical. A real run shipped a 結論表 with
# eight invented Google Maps cids and six invented "Google 無資料" hours cells,
# written by the orchestrator itself for rows it never looked up. Every existing
# check passed: the links were well-formed, the lint gate is a grep over shape,
# and the browser verifier is told not to open map links at all.

set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CHECK="$SCRIPT_DIR/../skills/build-itinerary/scripts/note-provenance"
F="$SCRIPT_DIR/fixtures/provenance"

PASSED=0; FAILED=0; FAIL_DETAILS=()
assert_pass() { PASSED=$((PASSED+1)); printf "  PASS  %s\n" "$1"; }
assert_fail() { FAILED=$((FAILED+1)); FAIL_DETAILS+=("$1 :: $2"); printf "  FAIL  %s\n        %s\n" "$1" "$2"; }
assert_eq() { if [[ "$2" == "$3" ]]; then assert_pass "$1"; else assert_fail "$1" "expected [$2] got [$3]"; fi; }
assert_has() { if grep -qF "$2" <<<"$3"; then assert_pass "$1"; else assert_fail "$1" "missing [$2] in: $3"; fi; }

echo "== the script exists and is executable =="
if [[ -x "$CHECK" ]]; then assert_pass "note-provenance is executable"; else assert_fail "note-provenance is executable" "not found or not +x at $CHECK"; fi

echo "== a note that only states what the data supports passes =="
out=$("$CHECK" "$F/clean.md" "$F/data.json" 2>&1); rc=$?
assert_eq "clean note exits 0" "0" "$rc"
assert_has "clean note says so" "clean" "$out"

echo "== an invented map link is caught =="
out=$("$CHECK" "$F/fabricated-cid.md" "$F/data.json" 2>&1); rc=$?
assert_eq "fabricated cid exits 65" "65" "$rc"
assert_has "fabricated cid is named" "cid=999" "$out"
assert_has "the offending row's venue is named" "ガンマ珈琲" "$out"
# The point of the check is that a *well-formed, plausible* link still fails.
assert_eq "a real cid on the same page is not flagged" "0" \
  "$(grep -c 'cid=111' <<<"$out")"

echo "== a false 'no data' claim is caught =="
# 喫茶アルファ has hours in data.json; the note says Google has none.
out=$("$CHECK" "$F/false-nodata.md" "$F/data.json" 2>&1); rc=$?
assert_eq "false 無資料 claim exits 65" "65" "$rc"
assert_has "false 無資料 claim names the venue" "喫茶アルファ" "$out"

echo "== a TRUE 'no data' claim is not a violation =="
# ベータ食堂's hours really are null, and clean.md writes 「Google 無資料」 for it.
# If this ever fails, the check has started punishing honesty, which is worse
# than the bug it was written for.
out=$("$CHECK" "$F/clean.md" "$F/data.json" 2>&1)
assert_eq "an honest 無資料 row is left alone" "0" "$(grep -c 'ベータ食堂' <<<"$out")"

echo "== usage errors are distinguishable from violations =="
assert_eq "missing arguments exit 64" "64" "$("$CHECK" "$F/clean.md" >/dev/null 2>&1; echo $?)"
assert_eq "a missing note exits 64" "64" "$("$CHECK" "$F/nope.md" "$F/data.json" >/dev/null 2>&1; echo $?)"
assert_eq "a missing data file exits 64" "64" "$("$CHECK" "$F/clean.md" "$F/nope.json" >/dev/null 2>&1; echo $?)"

echo
if [[ $FAILED -gt 0 ]]; then
  printf -- "-- %d passed, %d failed --\n" "$PASSED" "$FAILED"
  for d in "${FAIL_DETAILS[@]}"; do printf "   %s\n" "$d"; done
  exit 1
fi
printf -- "-- %d passed, 0 failed --\n" "$PASSED"
