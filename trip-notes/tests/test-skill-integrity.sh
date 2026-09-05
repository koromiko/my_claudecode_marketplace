#!/bin/bash
# Cross-reference checks over the trip-notes skills' markdown.
#
# These catch the failure mode a prose skill actually has: a brief that
# references a template that isn't there, a shared template that moved, a
# placeholder the orchestrator never fills, or an includedType that the API
# rejects. None of that shows up until a user runs the skill.

set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS="$SCRIPT_DIR/../skills"

PASSED=0; FAILED=0; FAIL_DETAILS=()
assert_pass() { PASSED=$((PASSED+1)); printf "  PASS  %s\n" "$1"; }
assert_fail() { FAILED=$((FAILED+1)); FAIL_DETAILS+=("$1 :: $2"); printf "  FAIL  %s\n        %s\n" "$1" "$2"; }
assert_eq() { if [[ "$2" == "$3" ]]; then assert_pass "$1"; else assert_fail "$1" "expected [$2] got [$3]"; fi; }

echo "== find-nearby structure =="

FN="$SKILLS/find-nearby"
for f in SKILL.md templates/score-candidates-brief.md templates/research-venue-brief.md \
         templates/preferences-example.md references/api-facts.md; do
  if [[ -f "$FN/$f" ]]; then assert_pass "exists: $f"; else assert_fail "exists: $f" "not found"; fi
done

echo "== cross-references resolve =="

# Collect every markdown path SKILL.md actually references: a bare
# "templates/foo.md" / "references/foo.md" (this skill's own assets, no
# directory prefix), or a "../<dir>/templates/foo.md" borrowed-template
# reference. Both forms resolve relative to the skill directory ($FN).
# The filename class allows digits and dots so it also matches something
# like "verify-facts-brief.md" and any future "v2.md"-style name.
missing=""
while read -r p; do
  [[ -z "$p" ]] && continue
  [[ -f "$FN/$p" ]] || missing="$missing $p"
done < <(grep -oE '(\.\./[a-zA-Z0-9_-]+/)?(templates|references)/[a-zA-Z0-9._-]+\.md' "$FN/SKILL.md" | sort -u)
assert_eq "every template/reference path in SKILL.md resolves" "" "$missing"

echo "== preference file headings are the contract =="

PE="$FN/templates/preferences-example.md"
assert_eq "preference skeleton has all five sections" "5" \
  "$(grep -cE '^## (反感|強偏好|弱偏好|未定|證據紀錄)$' "$PE")"
assert_eq "preference skeleton has both evidence subsections" "2" \
  "$(grep -cE '^### (👍 想去|👎 不要)$' "$PE")"
for h in 反感 強偏好 弱偏好 未定; do
  if grep -q "$h" "$FN/SKILL.md"; then assert_pass "SKILL.md references section: $h"
  else assert_fail "SKILL.md references section: $h" "not mentioned"; fi
done

echo "== brief placeholders are all fillable =="

assert_eq "score brief placeholders" "<CONDITIONS> <N> <POOL_PATH> <REVIEWS_PATH>" \
  "$(grep -o '<[A-Z_]*>' "$FN/templates/score-candidates-brief.md" | sort -u | tr '\n' ' ' | sed 's/ $//')"
assert_eq "research brief placeholders" \
  "<ADDRESS> <FETCHED> <HOURS> <MAPS_URL> <NAME> <QUESTIONS> <STATUS> <TRAVEL_MIN>" \
  "$(grep -o '<[A-Z_]*>' "$FN/templates/research-venue-brief.md" | sort -u | tr '\n' ' ' | sed 's/ $//')"

echo "== the hard-won verification rules survive in the shared briefs =="

VB="$SKILLS/build-itinerary/templates/verify-brief.md"
if grep -q 'domcontentloaded' "$VB"; then assert_pass "verify-brief mandates domcontentloaded"
else assert_fail "verify-brief mandates domcontentloaded" "flag missing"; fi
if grep -q 'networkidle' "$VB"; then assert_pass "verify-brief still bans networkidle by name"
else assert_fail "verify-brief still bans networkidle by name" "ban text missing"; fi

echo "== includedType strings referenced in SKILL.md are all listed in api-facts.md =="

AF="$FN/references/api-facts.md"
missing=""
while read -r t; do
  [[ -z "$t" ]] && continue
  grep -q "$t" "$AF" || missing="$missing $t"
done < <(grep -oE '`[a-z_]+_restaurant`|`(restaurant|cafe|bakery|home_goods_store|gift_shop|clothing_store|book_store|drugstore|supermarket|convenience_store|tourist_attraction|historical_landmark|park|garden|national_park|dog_park|hiking_area|botanical_garden)`' "$FN/SKILL.md" \
     | tr -d '`' | sort -u)
assert_eq "every includedType SKILL.md cites appears in api-facts.md" "" "$missing"

echo "== SKILL.md's --fields list matches the script's allowlist =="

# SKILL.md used to advertise ten layer-2 field names while `scripts/maps` accepted
# six. Asking for one of the other four exits 64 and aborts Step 2 — a user typing
# 「有供早餐的咖啡廳」 got an error, not a result. Nothing compared the two lists,
# so the drift was invisible. Pin them to each other.
MAPS_SCRIPT="$SKILLS/build-itinerary/scripts/maps"
script_fields=$(grep -o 'AMENITY_ALLOWED="[^"]*"' "$MAPS_SCRIPT" \
  | head -1 | sed 's/AMENITY_ALLOWED="//; s/"$//' | tr ' ' '\n' | sort | tr '\n' ' ')
# The prose list is the run of backticked names on the "Validated layer-2 field
# names" line, up to the sentence that closes it.
skill_fields=$(grep '^Validated layer-2 field names' "$FN/SKILL.md" \
  | sed 's/\*\*These six.*//' | grep -o '`[a-zA-Z]*`' | tr -d '`' | sort -u | tr '\n' ' ')
assert_eq "SKILL.md advertises exactly the --fields names the script accepts" \
  "$script_fields" "$skill_fields"

echo "== three-state rule covers status, not only amenities =="

# A bare `grep -q UNKNOWN` passed on ANY mention of the token, including prose
# saying the opposite. These two assertions guard a Critical — a filter on
# `status != "OPERATIONAL"` silently culls every venue Google holds no status for
# — so they pin the CLAIM, not the word.
if grep -q '`UNKNOWN` is not a closure' "$FN/SKILL.md" \
   && grep -q '`UNKNOWN` survives' "$FN/SKILL.md"; then
  assert_pass "SKILL.md states UNKNOWN is not a closure and survives"
else
  assert_fail "SKILL.md states UNKNOWN is not a closure and survives" \
    "the claim itself is missing (a bare mention of the token is not enough)"
fi
if grep -q 'Reject only the two explicit closure values' "$FN/SKILL.md"; then
  assert_pass "SKILL.md names the only two values that may reject"
else
  assert_fail "SKILL.md names the only two values that may reject" "rule text missing"
fi

if grep -q '`UNKNOWN` is its no-data value' "$FN/templates/score-candidates-brief.md" \
   && grep -q '`OPERATIONAL` and `UNKNOWN` both survive' "$FN/templates/score-candidates-brief.md"; then
  assert_pass "score-candidates-brief states UNKNOWN is no-data and survives"
else
  assert_fail "score-candidates-brief states UNKNOWN is no-data and survives" \
    "the claim itself is missing (a bare mention of the token is not enough)"
fi

echo "== the preference skeleton carries every maintenance rule the skill relies on =="

# This file is copied VERBATIM into the user's real ~/.config/trip-notes/preferences.md,
# so its rule comment is the version that persists on disk. SKILL.md declares it
# authoritative for preference maintenance; a rule missing here is a rule the user's
# own file will never carry.
# Match the RULE, not the 「最後更新：」 field itself — the field is present in the
# skeleton either way, so a bare token grep would pass with the rule missing.
if grep -q '必須同時更新檔案開頭的「最後更新：」' "$PE"; then
  assert_pass "preference skeleton's rules include updating 最後更新"
else assert_fail "preference skeleton's rules include updating 最後更新" "rule missing from the comment"; fi

echo
echo "-- $PASSED passed, $FAILED failed --"
if [[ ${#FAIL_DETAILS[@]} -gt 0 ]]; then printf '%s\n' "${FAIL_DETAILS[@]}"; fi
[[ $FAILED -eq 0 ]]
