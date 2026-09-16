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

echo "== the preference file is human-authored only =="
PE="$FN/templates/preferences-example.md"
if grep -qF "skill 不會寫這個檔" "$PE"; then assert_pass "skeleton says the skill never writes it"
else assert_fail "skeleton says the skill never writes it" "missing"; fi
for h in 反感 強偏好 弱偏好 未定 證據紀錄; do
  if grep -q "^## $h" "$PE"; then
    assert_fail "the bucket section '$h' is gone from the skeleton" "still present"
  else assert_pass "the bucket section '$h' is gone from the skeleton"; fi
done

echo "== SKILL.md wires up the sightings log =="
if [[ -x "$FN/scripts/sightings" ]]; then assert_pass "sightings script ships with the skill"
else assert_fail "sightings script ships with the skill" "not found or not +x"; fi
for phrase in "sightings append" "sightings stats" "<SIGHTINGS_PATH>"; do
  if grep -qF "$phrase" "$FN/SKILL.md"; then assert_pass "SKILL.md references: $phrase"
  else assert_fail "SKILL.md references: $phrase" "missing"; fi
done

echo "== Step 11 no longer keeps books =="
for gone in "升到" "每區上限 8 條" "最後更新："; do
  if grep -qF "$gone" "$FN/SKILL.md"; then
    assert_fail "the old bookkeeping rule '$gone' is gone from SKILL.md" "still present"
  else assert_pass "the old bookkeeping rule '$gone' is gone from SKILL.md"; fi
done

echo "== brief placeholders are all fillable =="

assert_eq "score brief placeholders" "<CONDITIONS> <N> <POOL_PATH> <REVIEWS_PATH> <SIGHTINGS_PATH>" \
  "$(grep -o '<[A-Z_]*>' "$FN/templates/score-candidates-brief.md" | sort -u | tr '\n' ' ' | sed 's/ $//')"
assert_eq "research brief placeholders" \
  "<ADDRESS> <FETCHED> <HOURS> <MAPS_URL> <NAME> <QUESTIONS> <STATUS> <TRAVEL_MIN>" \
  "$(grep -o '<[A-Z_]*>' "$FN/templates/research-venue-brief.md" | sort -u | tr '\n' ' ' | sed 's/ $//')"

echo "== the scoring brief mandates segment-then-axes-then-rank =="
SB="$FN/templates/score-candidates-brief.md"
for phrase in "先分群" "每條軸都要附計數" "沒有計數的軸不得使用"; do
  if grep -qF "$phrase" "$SB"; then assert_pass "score brief states: $phrase"
  else assert_fail "score brief states: $phrase" "missing"; fi
done

echo "== the removal bar survives the rewrite =="
for phrase in "少於 5 筆" "≥ 2 次不同執行" "任何一群都沒有帶同一特徵的 👍" "矛盾證據永久禁止刷掉"; do
  if grep -qF "$phrase" "$SB"; then assert_pass "score brief keeps the removal bar: $phrase"
  else assert_fail "score brief keeps the removal bar: $phrase" "missing"; fi
done

echo "== inference may never silently remove =="
if grep -qF "若這條推錯了，告訴我" "$SB"; then
  assert_pass "score brief mandates the correctable removal line"
else assert_fail "score brief mandates the correctable removal line" "missing"; fi

echo "== a preference match may never rest on review text alone =="
for phrase in "絕不能只靠評論" "是降級加待確認問題，不是刷掉"; do
  if grep -qF "$phrase" "$SB"; then assert_pass "score brief bans review-only preference rejection: $phrase"
  else assert_fail "score brief bans review-only preference rejection: $phrase" "missing"; fi
done

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

echo "== 評論印象 is carried end to end, and always with its disclaimer =="

# Reviews now reach the note as a labelled impression, which is a deliberate,
# narrow exception to "a review never reaches the note". The exception only
# holds while the label travels WITH it: the disclaimer 「（N 則評論，未驗證）」
# is what keeps an impression from reading as a confirmed fact. So every place
# that produces or renders an impression must also carry the disclaimer, and
# the two bans that make the exception safe — no verbatim/reworded review text,
# nothing a structured field already answers — must stay stated in the brief.

SB="$FN/templates/score-candidates-brief.md"
BI="$SKILLS/build-itinerary/SKILL.md"

for f in "$SB" "$FN/SKILL.md" "$BI"; do
  n=$(basename "$(dirname "$f")")/$(basename "$f")
  if grep -q '評論印象' "$f"; then assert_pass "評論印象 is defined in $n"
  else assert_fail "評論印象 is defined in $n" "not mentioned"; fi
  # The disclaimer template, with N as the literal placeholder for the count.
  if grep -q '（N 則評論，未驗證）' "$f"; then
    assert_pass "the 未驗證 disclaimer template appears in $n"
  else assert_fail "the 未驗證 disclaimer template appears in $n" "disclaimer missing"; fi
done

# The scoring agent is the only producer; these are the constraints that keep
# its output publishable and non-factual.
if grep -q '不得寫結構化欄位能回答的事' "$SB"; then
  assert_pass "score brief bans restating what a structured field answers"
else assert_fail "score brief bans restating what a structured field answers" "ban missing"; fi
if grep -q '評論不足，未做摘要' "$SB"; then
  assert_pass "score brief gives a no-data phrasing instead of inviting invention"
else assert_fail "score brief gives a no-data phrasing instead of inviting invention" "phrase missing"; fi
if grep -qE '逐字|verbatim' "$SB"; then
  assert_pass "score brief still bans verbatim review text"
else assert_fail "score brief still bans verbatim review text" "ban missing"; fi

# The impression is an output section of the brief, not a remark buried in prose.
if grep -q '^### 評論印象' "$SB"; then
  assert_pass "評論印象 is its own output section of the score brief"
else assert_fail "評論印象 is its own output section of the score brief" "heading missing"; fi

# find-nearby renders it in two places with different length budgets; the 其他候選
# table gains a column, and a candidate whose reviews were never read must be
# visibly distinguishable there rather than silently blank.
if grep -q '評論印象（未驗證）' "$FN/SKILL.md"; then
  assert_pass "the 其他候選 table header carries the disclaimer inline"
else assert_fail "the 其他候選 table header carries the disclaimer inline" "column header missing"; fi

# Every impression must also land in the existing 「僅來自評論推測、未經確認」
# list — that list is what Step 9 and the reader use to tell impression from
# verified fact. Without this the note would carry unverified claims that the
# 驗證狀態 section implicitly denies exist.
if grep -q '僅來自評論推測、未經確認' "$FN/SKILL.md"; then
  assert_pass "find-nearby still routes impressions into 驗證狀態"
else assert_fail "find-nearby still routes impressions into 驗證狀態" "list missing"; fi


echo "== the provenance gate exists and both skills point at it =="

PROV="$SKILLS/build-itinerary/scripts/note-provenance"
if [[ -x "$PROV" ]]; then assert_pass "note-provenance exists and is executable"
else assert_fail "note-provenance exists and is executable" "not found or not +x"; fi

# The gate is worthless if a SKILL.md forgets to run it, so both must name it.
for sk in build-itinerary find-nearby; do
  if grep -q 'note-provenance' "$SKILLS/$sk/SKILL.md"; then
    assert_pass "$sk/SKILL.md invokes note-provenance"
  else
    assert_fail "$sk/SKILL.md invokes note-provenance" "no mention of the provenance gate"
  fi
done

# find-nearby borrows it across skills, so its path must actually resolve from there.
while read -r rel; do
  [[ -z "$rel" ]] && continue
  if [[ -x "$SKILLS/find-nearby/$rel" ]]; then assert_pass "find-nearby's path to $rel resolves"
  else assert_fail "find-nearby's path to $rel resolves" "not executable at $SKILLS/find-nearby/$rel"; fi
done < <(grep -oE '\.\./[a-zA-Z0-9_-]+/scripts/[a-zA-Z0-9._-]+' "$SKILLS/find-nearby/SKILL.md" | sort -u)

echo
echo "-- $PASSED passed, $FAILED failed --"
if [[ ${#FAIL_DETAILS[@]} -gt 0 ]]; then printf '%s\n' "${FAIL_DETAILS[@]}"; fi
[[ $FAILED -eq 0 ]]
