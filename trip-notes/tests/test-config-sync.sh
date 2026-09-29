#!/bin/bash
# Tests for trip-notes/skills/find-nearby/scripts/config-sync.
#
# Every case runs against TRIP_NOTES_SYNC_STUB_DIR — a plain directory standing
# in for the R2 bucket — so no test needs credentials or network.
#
# Exit code: 0 — all assertions pass; 1 — one or more failures.

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SYNC="$SCRIPT_DIR/../skills/find-nearby/scripts/config-sync"

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

# fresh — new empty local config dir and bucket; sets LOCAL and BUCKET.
fresh() {
  LOCAL=$(mktemp -d)
  BUCKET=$(mktemp -d)
}
sync_() {  # <pull|push>
  TRIP_NOTES_CONFIG="$LOCAL" TRIP_NOTES_SYNC_STUB_DIR="$BUCKET" "$SYNC" "$1" 2>/dev/null
}
mtime() { stat -f %m "$1" 2>/dev/null || stat -c %Y "$1"; }

# pull into an empty local dir brings both files down
fresh
echo '# prefs' > "$BUCKET/preferences.md"
printf '%s\n' '{"n":1}' '{"n":2}' > "$BUCKET/sightings.jsonl"
sync_ pull
assert_eq "pull exits 0" "0" "$?"
assert_eq "pull brings preferences.md down" "# prefs" "$(cat "$LOCAL/preferences.md")"
assert_eq "pull brings sightings.jsonl down" "2" "$(wc -l < "$LOCAL/sightings.jsonl" | tr -d ' ')"

# records appended on both sides since the last sync all survive, once each
fresh
printf '%s\n' '{"n":1}' '{"n":2}' '{"n":"local"}' > "$LOCAL/sightings.jsonl"
printf '%s\n' '{"n":1}' '{"n":2}' '{"n":"cloud"}' > "$BUCKET/sightings.jsonl"
sync_ push
expected=$(printf '%s\n' '{"n":1}' '{"n":2}' '{"n":"local"}' '{"n":"cloud"}')
assert_eq "sightings merge is a line union, local order first" "$expected" "$(cat "$LOCAL/sightings.jsonl")"
assert_eq "push uploads the merged log" "$expected" "$(cat "$BUCKET/sightings.jsonl")"

# an idle sync does not rewrite the log (mtime unchanged)
touch -t 202601010000 "$LOCAL/sightings.jsonl"
before=$(mtime "$LOCAL/sightings.jsonl")
sync_ pull
assert_eq "idle pull leaves the log's mtime alone" "$before" "$(mtime "$LOCAL/sightings.jsonl")"

# preferences.md: the newer copy wins, in both directions
fresh
echo old > "$LOCAL/preferences.md";  touch -t 202601010000 "$LOCAL/preferences.md"
echo new > "$BUCKET/preferences.md"; touch -t 202602010000 "$BUCKET/preferences.md"
sync_ pull
assert_eq "a newer bucket preferences.md replaces the local one" "new" "$(cat "$LOCAL/preferences.md")"
fresh
echo edited > "$LOCAL/preferences.md"; touch -t 202603010000 "$LOCAL/preferences.md"
echo stale > "$BUCKET/preferences.md"; touch -t 202601010000 "$BUCKET/preferences.md"
sync_ push
assert_eq "an older bucket copy does not overwrite a local edit" "edited" "$(cat "$LOCAL/preferences.md")"
assert_eq "push uploads the newer local preferences.md" "edited" "$(cat "$BUCKET/preferences.md")"

# the API key never leaves the machine
fresh
echo 'export GOOGLE_MAPS_API_KEY=secret' > "$LOCAL/maps.env"
echo '{"n":1}' > "$LOCAL/sightings.jsonl"
sync_ push
if [[ -e "$BUCKET/maps.env" ]]; then assert_fail "maps.env is never uploaded" "found in bucket"
else assert_pass "maps.env is never uploaded"; fi

# no backend at all is an error, not a silent skip
fresh
TRIP_NOTES_CONFIG="$LOCAL" TRIP_NOTES_RCLONE_REMOTE=none PATH=/usr/bin:/bin "$SYNC" pull >/dev/null 2>&1
assert_eq "no backend exits 1" "1" "$?"

# usage
"$SYNC" >/dev/null 2>&1
assert_eq "no argument exits 1" "1" "$?"

echo
echo "-- $PASSED passed, $FAILED failed --"
if [[ ${#FAIL_DETAILS[@]} -gt 0 ]]; then printf '%s\n' "${FAIL_DETAILS[@]}"; fi
[[ $FAILED -eq 0 ]]
