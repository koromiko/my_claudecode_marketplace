# find-nearby 偏好學習機制 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 find-nearby 的偏好機制從「四個人工維護的等級桶」換成「append-only 目擊紀錄 + 每次執行現場推論」，讓偏好的適用範圍隨店種變化。

**Architecture:** 新增 `scripts/sightings`（bash，與既有 `maps`／`note-provenance` 同風格），每次執行把「展示過的每一家」連同結構化欄位、我們排的名次與使用者回饋，append 成一行 JSON 到 `~/.config/trip-notes/sightings.jsonl`。`preferences.md` 降為純人工檔，skill 不再寫入。Step 5 的 scoring agent 改讀目擊紀錄，被要求先分群、再列出帶計數的軸、最後才排序。

**Tech Stack:** bash 5 + jq（與既有 scripts 相同）；測試為 `tests/*.sh` 自撰 assert harness，無外部測試框架。

**Spec:** `docs/superpowers/specs/2026-09-16-find-nearby-preference-learning-design.md`

## Global Constraints

- 所有 script 用 `#!/usr/bin/env bash`，與 `skills/build-itinerary/scripts/maps`、`note-provenance` 一致。
- 退出碼慣例沿用既有 script：`64` = 用法錯誤，`65` = 內容違規，`78` = 設定缺失。
- 設定目錄一律取 `${TRIP_NOTES_CONFIG:-$HOME/.config/trip-notes}`，測試靠覆寫這個環境變數來隔離，**絕不寫入使用者真實的家目錄**。
- 記錄檔為 JSONL：一行一筆、append-only、永不重寫既有行。
- 缺的欄位寫 `null` 或整個省略，**不得補值、不得猜測**。
- 測試檔放 `trip-notes/tests/`，fixtures 放 `trip-notes/tests/fixtures/<主題>/`。
- 每個 task 結束時跑 `trip-notes/tests/test-skill-integrity.sh`，它必須保持全綠。

---

### Task 1: pool 檔自述它是哪個查詢產生的

`matched_queries` 是本設計最重要的新欄位，但目前 pool 檔（`maps nearby` / `maps search` 的輸出）只有 `fetched / from_cache / returned / shown / places`，**沒有記下產生它的查詢詞**。沒有這個，`matched_queries` 只能靠檔名猜或由呼叫端手動對應，兩者都會錯。先把 pool 檔變成自述的。

**Files:**
- Modify: `trip-notes/skills/build-itinerary/scripts/maps`（`nearby` 輸出區塊約 587-590 行、`search` 輸出區塊約 620-623 行）
- Test: `trip-notes/tests/test-maps.sh`

**Interfaces:**
- Consumes: 無（本 plan 的第一個 task）
- Produces: pool 檔新增兩個頂層欄位——`query`（字串或 `null`）與 `included_type`（字串或 `null`）。`search` 產生的檔 `query` 有值、`included_type` 為 `null`；`nearby` 產生的檔相反；`nearby` 未指定 type 時兩者皆 `null`。Task 2 的 `sightings append` 只認這兩個欄位。

- [ ] **Step 1: 寫失敗測試**

在 `trip-notes/tests/test-maps.sh` 裡新增一段。用該檔既有的 `run_maps` helper（它會設好 `TRIP_MAPS_STUB_DIR="$FIXTURES"`、拋棄式 cache 與假 API key，所以不會打到真的 Google）：

```bash
echo "== pool files say which query produced them =="
out=$(run_maps search --limit 5 "35.681,139.767" 1500 "クラフトビール" 2>/dev/null)
assert_eq "search stamps the query text" "クラフトビール" "$(jq -r '.query' <<<"$out")"
assert_eq "search leaves included_type null" "null" "$(jq -r '.included_type' <<<"$out")"

out=$(run_maps nearby --limit 5 "35.681,139.767" 500 restaurant 2>/dev/null)
assert_eq "nearby stamps the includedType" "restaurant" "$(jq -r '.included_type' <<<"$out")"
assert_eq "nearby leaves query null" "null" "$(jq -r '.query' <<<"$out")"

out=$(run_maps nearby --limit 5 "35.681,139.767" 500 2>/dev/null)
assert_eq "an untyped nearby stamps null, not an empty string" "null" "$(jq -r '.included_type' <<<"$out")"
```

`searchNearby.json` / `searchText.json` 已在 `tests/fixtures/` 裡，`run_maps` 會自動用到，不需另建 fixture。

- [ ] **Step 2: 跑測試確認它失敗**

Run: `trip-notes/tests/test-maps.sh 2>&1 | grep -A2 "pool files say"`
Expected: 四條 FAIL，訊息形如 `expected [クラフトビール] got [null]`

- [ ] **Step 3: 實作**

`nearby` 的輸出 jq（約 587 行）改為：

```bash
    check "$(post "${PLACES}/places:searchNearby" "$mask" "$body")" \
      | jq --argjson lim "$limit" --arg it "${3:-}" "$JQ_COMPACT$JQ_PLACE"'
      { returned: (.places // [] | length),
        shown: ([(.places // []) | length, $lim] | min),
        query: null,
        included_type: (if $it == "" then null else $it end),
        places: [ (.places // [])[] | place_row('"$amen_expr"') ]
                | .[0:$lim] }'
```

`search` 的輸出 jq（約 620 行）改為：

```bash
    check "$(post "${PLACES}/places:searchText" "$PLACES_MASK" "$body")" \
      | jq --argjson lim "$limit" --arg q "$*" "$JQ_COMPACT$JQ_PLACE"'
      { returned: (.places // [] | length),
        shown: ([(.places // []) | length, $lim] | min),
        query: (if $q == "" then null else $q end),
        included_type: null,
        places: [ (.places // [])[] | place_row({}) ]
                | .[0:$lim] }'
```

注意 `nearby` 區塊裡 `$3` 在 `lat`/`lng` 取值之後仍未被 `shift`，所以 `${3:-}` 仍是 includedType；`search` 區塊已 `shift 2`，`$*` 就是查詢文字。**兩處都不要另外加 `shift`。**

- [ ] **Step 4: 跑測試確認通過**

Run: `trip-notes/tests/test-maps.sh`
Expected: 全綠，且既有斷言數量不減（新增 4 條）

- [ ] **Step 5: Commit**

```bash
git -C /Users/neo/Projects/claude_local_marketplace add \
  trip-notes/skills/build-itinerary/scripts/maps trip-notes/tests/test-maps.sh
git -C /Users/neo/Projects/claude_local_marketplace commit -m "feat(trip-maps): stamp the query and includedType into pool output

matched_queries needs to know which of a run's queries returned a place.
The pool file was the only thing that knew, and it did not record it."
```

---

### Task 2: `sightings append` — 記錄寫入器

**Files:**
- Create: `trip-notes/skills/find-nearby/scripts/sightings`
- Create: `trip-notes/tests/test-sightings.sh`
- Create: `trip-notes/tests/fixtures/sightings/run.json`
- Create: `trip-notes/tests/fixtures/sightings/top14.json`
- Create: `trip-notes/tests/fixtures/sightings/shown.json`
- Create: `trip-notes/tests/fixtures/sightings/pool-a.json`
- Create: `trip-notes/tests/fixtures/sightings/pool-b.json`

**Interfaces:**
- Consumes: Task 1 的 `query` / `included_type` 欄位
- Produces: 可執行檔 `sightings`，子命令
  `sightings append --log <path> --run <run.json> --top14 <top14.json> --shown <shown.json> [--pool <pool.json>]...`
  每筆 shown 記錄 append 一行 JSON。輸出一行摘要到 stdout：
  `sightings: appended N record(s) to <path> (P 👍 / Q 👎 / R unmarked)`
  Task 3 的 `backfill`、Task 4 的 `stats` 共用同一支 script 的參數解析與 `LOG_DEFAULT`。

- [ ] **Step 1: 建立 fixtures**

```bash
cd /Users/neo/Projects/claude_local_marketplace/trip-notes/tests/fixtures
mkdir -p sightings
cat > sightings/run.json <<'EOF'
{"run_id":"2026-09-16-kokura-craftbeer","run_date":"2026-09-16",
 "target_date":"2026-09-19","region":"福岡県北九州市小倉北区","origin":"小倉駅",
 "request":"北九州市小倉精釀啤酒或清酒，車站走路可到 (20分鐘)，日期 9/19",
 "queries":["クラフトビール","角打ち"],"mode":"WALK","max_min":20}
EOF
cat > sightings/top14.json <<'EOF'
{"origin":"小倉駅","mode":"WALK","max_min":20,"pool_fetched":"2026-09-15T16:03:19Z",
 "places":[
  {"place_id":"P_NAKA","name":"角打ちなかむらえん","type":"酒店","travel_min":7,
   "rating":4.7,"reviews":61,"status":"OPERATIONAL","pool_hits":2,
   "hours":{"closed":[],"hours":["月曜日: 15時00分～21時00分","火曜日: 15時00分～21時00分",
     "水曜日: 15時00分～21時00分","木曜日: 15時00分～21時00分","金曜日: 15時00分～21時00分",
     "土曜日: 13時00分～21時00分","日曜日: 13時00分～20時00分"]}},
  {"place_id":"P_HAKU","name":"飛来haku","type":"バー","travel_min":5,
   "rating":4.9,"reviews":16,"status":"OPERATIONAL","pool_hits":1,
   "hours":{"closed":[],"hours":"19時00分～0時00分"}},
  {"place_id":"P_BUMBLE","name":"Bar Bumblebees","type":"軽食店","travel_min":4,
   "rating":4.8,"reviews":6,"status":"OPERATIONAL","pool_hits":1,"hours":null},
  {"place_id":"P_TIGER","name":"小倉タイガー","type":"バー","travel_min":10,
   "rating":4.6,"reviews":18,"status":"OPERATIONAL","pool_hits":1,
   "hours":{"closed":["日"],"hours":["月曜日: 17時00分～23時00分","火曜日: 17時00分～23時00分",
     "水曜日: 17時00分～23時00分","木曜日: 17時00分～23時00分","金曜日: 17時00分～2時00分",
     "土曜日: 17時00分～2時00分","日曜日: 定休日"]}}]}
EOF
cat > sightings/shown.json <<'EOF'
[{"place_id":"P_NAKA","rank_shown":1,"tier":"首選","verdict":"👍",
  "research":{"independent":true,"chain":false,"in_mall":false,"own_production":false,
              "price_band":"¥1,100/飲み比べ","seating":"立ち飲み+テーブル",
              "has_website":true,"instagram_state":"age_restricted",
              "official_info_conflict":false}},
 {"place_id":"P_HAKU","rank_shown":2,"tier":"首選","verdict":null},
 {"place_id":"P_BUMBLE","rank_shown":3,"tier":"其他候選","verdict":"👎"},
 {"place_id":"P_TIGER","rank_shown":4,"tier":"其他候選","verdict":null}]
EOF
cat > sightings/pool-a.json <<'EOF'
{"returned":2,"shown":2,"fetched":"2026-09-15T16:03:19Z","from_cache":false,
 "query":"クラフトビール","included_type":null,
 "places":[{"place_id":"P_NAKA"},{"place_id":"P_TIGER"}]}
EOF
cat > sightings/pool-b.json <<'EOF'
{"returned":2,"shown":2,"fetched":"2026-09-15T16:03:20Z","from_cache":false,
 "query":"角打ち","included_type":null,
 "places":[{"place_id":"P_NAKA"},{"place_id":"P_HAKU"}]}
EOF
```

- [ ] **Step 2: 寫失敗測試**

```bash
cat > /Users/neo/Projects/claude_local_marketplace/trip-notes/tests/test-sightings.sh <<'EOF'
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
EOF
chmod +x /Users/neo/Projects/claude_local_marketplace/trip-notes/tests/test-sightings.sh
```

- [ ] **Step 3: 跑測試確認它失敗**

Run: `trip-notes/tests/test-sightings.sh`
Expected: 第一條就 FAIL — `sightings is executable :: not found or not +x`

- [ ] **Step 4: 實作 `sightings append`**

```bash
cat > /Users/neo/Projects/claude_local_marketplace/trip-notes/skills/find-nearby/scripts/sightings <<'EOF'
#!/usr/bin/env bash
# sightings — the find-nearby preference memory.
#
# One line per SHOWN candidate per run. Not per marked candidate: the signal
# that matters most is the gap between the rank we showed and the choice the
# user made, and that only exists if the unmarked ones are written down too.
#
# Nothing here infers anything. It records what happened; the scoring agent
# does the reasoning, every run, from these lines.
set -euo pipefail

CONFIG_DIR="${TRIP_NOTES_CONFIG:-$HOME/.config/trip-notes}"
LOG_DEFAULT="$CONFIG_DIR/sightings.jsonl"

die64() { echo "error: $*" >&2; exit 64; }
die65() { echo "violation: $*" >&2; exit 65; }

usage() {
  cat >&2 <<'USAGE'
usage:
  sightings append --run <run.json> --top14 <top14.json> --shown <shown.json>
                   [--pool <pool.json>]... [--log <path>]
  sightings backfill --from <preferences.md> [--log <path>]
  sightings stats [--log <path>]

Records live at ${TRIP_NOTES_CONFIG:-$HOME/.config/trip-notes}/sightings.jsonl
USAGE
  exit 64
}

# 月曜日..日曜日 for date's %u (1=Monday .. 7=Sunday)
weekday_jp() {
  case "$1" in
    1) echo 月曜日 ;; 2) echo 火曜日 ;; 3) echo 水曜日 ;; 4) echo 木曜日 ;;
    5) echo 金曜日 ;; 6) echo 土曜日 ;; 7) echo 日曜日 ;;
    *) echo "" ;;
  esac
}
# short form used by the `closed` array (月火水木金土日)
weekday_short() {
  case "$1" in
    1) echo 月 ;; 2) echo 火 ;; 3) echo 水 ;; 4) echo 木 ;;
    5) echo 金 ;; 6) echo 土 ;; 7) echo 日 ;; *) echo "" ;;
  esac
}

cmd="${1:-}"; [[ -n "$cmd" ]] || usage; shift

case "$cmd" in
  append)
    log="$LOG_DEFAULT"; run=""; top14=""; shown=""; pools=()
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --log)   log="${2:?--log needs a path}"; shift 2 ;;
        --run)   run="${2:?--run needs a file}"; shift 2 ;;
        --top14) top14="${2:?--top14 needs a file}"; shift 2 ;;
        --shown) shown="${2:?--shown needs a file}"; shift 2 ;;
        --pool)  pools+=("${2:?--pool needs a file}"); shift 2 ;;
        *) die64 "unknown flag '$1'" ;;
      esac
    done
    for f in "$run" "$top14" "$shown"; do
      [[ -n "$f" ]] || usage
      [[ -f "$f" ]] || die64 "no such file: $f"
    done
    for p in "${pools[@]:-}"; do
      [[ -z "$p" || -f "$p" ]] || die64 "no such pool file: $p"
    done

    target_date=$(jq -r '.target_date // empty' "$run")
    if [[ -n "$target_date" ]]; then
      u=$(date -j -f "%Y-%m-%d" "$target_date" +%u 2>/dev/null || echo "")
    else
      u=""
    fi
    wd_long=$(weekday_jp "${u:-0}")
    wd_short=$(weekday_short "${u:-0}")

    # place_id -> [queries], built from the pools' own self-description.
    if [[ ${#pools[@]} -gt 0 ]]; then
      mq=$(jq -s '
        [ .[]
          | (.query // .included_type) as $q
          | select($q != null)
          | .places[]? | {place_id, q: $q} ]
        | group_by(.place_id)
        | map({key: .[0].place_id, value: [.[].q] | unique})
        | from_entries' "${pools[@]}")
    else
      mq='{}'
    fi

    mkdir -p "$(dirname "$log")"

    lines=$(jq -c -n \
      --slurpfile run_arr "$run" \
      --slurpfile top_arr "$top14" \
      --slurpfile shown_arr "$shown" \
      --argjson mq "$mq" \
      --arg wd "$wd_long" --arg wds "$wd_short" '
      def hm: capture("(?<h>[0-9]+)時(?<m>[0-9]+)分") | ((.h|tonumber)*60 + (.m|tonumber));
      def fmt: "\(((./60)|floor)|tostring|if length==1 then "0"+. else . end):\((.%60)|tostring|if length==1 then "0"+. else . end)";

      # Returns {open_from, close_at, hours_span_h, closed_on_target, hours_missing}
      def derive(h; wd; wds):
        if h == null or (h|type) != "object" then
          {open_from:null, close_at:null, hours_span_h:null,
           closed_on_target:null, hours_missing:true}
        else
          ( if (h.hours|type) == "array" then
              ( [ h.hours[] | select(startswith(wd + ":")) ] | first // null )
            elif (h.hours|type) == "string" then h.hours
            else null end ) as $line
          | ( (h.closed // []) | index(wds) != null ) as $closed_listed
          | if $line == null then
              {open_from:null, close_at:null, hours_span_h:null,
               closed_on_target:$closed_listed, hours_missing:true}
            elif ($line | test("定休日")) then
              {open_from:null, close_at:null, hours_span_h:null,
               closed_on_target:true, hours_missing:false}
            else
              ( [ $line | scan("[0-9]+時[0-9]+分") ] ) as $parts
              | if ($parts|length) < 2 then
                  {open_from:null, close_at:null, hours_span_h:null,
                   closed_on_target:$closed_listed, hours_missing:true}
                else
                  ($parts[0]|hm) as $o | ($parts[1]|hm) as $c
                  | (if $c <= $o then $c + 1440 else $c end) as $c2
                  | {open_from: ($o|fmt), close_at: ($c|fmt),
                     hours_span_h: ((($c2 - $o)/60)|floor),
                     closed_on_target: $closed_listed, hours_missing:false}
                end
            end
        end;

      $run_arr[0] as $run
      | ($top_arr[0].places | map({key:.place_id, value:.}) | from_entries) as $by_id
      | $shown_arr[0][]
      | . as $s
      | ($by_id[$s.place_id] // null) as $p
      | if $p == null then
          ("MISSING:" + $s.place_id) | halt_error(65)
        else . end
      | derive($p.hours; $wd; $wds) as $h
      | {
          run_id: $run.run_id, run_date: $run.run_date, target_date: $run.target_date,
          region: $run.region, origin: $run.origin, request: $run.request,
          queries: $run.queries, mode: $run.mode, max_min: $run.max_min,

          place_id: $p.place_id, name: $p.name, type: $p.type,
          pool_hits: ($p.pool_hits // null),
          matched_queries: ($mq[$p.place_id] // []),
          travel_min: ($p.travel_min // null),
          rating: ($p.rating // null), reviews: ($p.reviews // null),
          status: ($p.status // "UNKNOWN"),
          open_from: $h.open_from, close_at: $h.close_at,
          hours_span_h: $h.hours_span_h,
          closed_on_target: $h.closed_on_target,
          hours_missing: $h.hours_missing,
          closed_days: (($p.hours.closed) // []),
          # Google has no "不定休" field. It only ever arrives from Step 7
          # verification, so it rides in on the shown record's research block
          # and is null for everything else — never inferred from an empty
          # closed_days, which means "no closure data", not "closes never".
          irregular_closure: ($s.research.irregular_closure // null),
          amenities: ($p.amenities // {}),

          rank_shown: $s.rank_shown, tier: $s.tier,
          verdict: ($s.verdict // null),
          research: ($s.research // null)
        }') || die65 "a shown place_id is not present in top14.json"

    printf '%s\n' "$lines" >> "$log"

    n=$(printf '%s\n' "$lines" | wc -l | tr -d ' ')
    up=$(printf '%s\n' "$lines" | jq -s '[.[]|select(.verdict=="👍")]|length')
    down=$(printf '%s\n' "$lines" | jq -s '[.[]|select(.verdict=="👎")]|length')
    none=$(printf '%s\n' "$lines" | jq -s '[.[]|select(.verdict==null)]|length')
    echo "sightings: appended $n record(s) to $log ($up 👍 / $down 👎 / $none unmarked)"
    ;;

  backfill|stats)
    echo "error: '$cmd' is not implemented yet" >&2; exit 64 ;;

  *) usage ;;
esac
EOF
chmod +x /Users/neo/Projects/claude_local_marketplace/trip-notes/skills/find-nearby/scripts/sightings
```

- [ ] **Step 5: 跑測試確認通過**

Run: `trip-notes/tests/test-sightings.sh`
Expected: 全綠。若 `halt_error(65)` 的退出碼不是 65（jq 的 `halt_error` 預設用 5），改成在 jq 外面先做存在性檢查：

```bash
    missing=$(jq -r --slurpfile t "$top14" '
      ($t[0].places | map(.place_id)) as $ids
      | .[] | select(.place_id as $p | $ids | index($p) | not) | .place_id' "$shown")
    [[ -z "$missing" ]] || die65 "shown place_id not in top14: $missing"
```

並把 jq 主體裡的 `halt_error` 分支移除。**以測試的實際結果為準，不要假設 jq 版本行為。**

- [ ] **Step 6: Commit**

```bash
git -C /Users/neo/Projects/claude_local_marketplace add \
  trip-notes/skills/find-nearby/scripts/sightings \
  trip-notes/tests/test-sightings.sh trip-notes/tests/fixtures/sightings
git -C /Users/neo/Projects/claude_local_marketplace commit -m "feat(find-nearby): record one sighting per shown candidate

Unmarked candidates are recorded too. Their rank_shown next to a null
verdict is the only place the log says where our ranking was wrong."
```

---

### Task 3: `sightings backfill` — 把現有 16 筆證據紀錄搬進來

**Files:**
- Modify: `trip-notes/skills/find-nearby/scripts/sightings`（`backfill` 分支）
- Modify: `trip-notes/tests/test-sightings.sh`
- Create: `trip-notes/tests/fixtures/sightings/legacy-preferences.md`

**Interfaces:**
- Consumes: Task 2 的 `sightings` 參數解析與 `LOG_DEFAULT`
- Produces: `sightings backfill --from <preferences.md> [--log <path>]`，
  對「證據紀錄」底下 `### 👍 想去` / `### 👎 不要` 的每一條 `- <date> · <region> · <name> — <note>`
  寫一筆稀疏記錄，含 `legacy:true`、`run_date`、`region`、`name`、`verdict`、`note`；
  **其餘欄位一律省略，不得補值。** 輸出 `sightings: backfilled N legacy record(s)`。

- [ ] **Step 1: 建立 fixture**

```bash
cat > /Users/neo/Projects/claude_local_marketplace/trip-notes/tests/fixtures/sightings/legacy-preferences.md <<'EOF'
# 個人偵店偏好

最後更新：2026-09-16（第 5 次回饋）

## 強偏好
- 獨立店／獨棟路面店，而非連鎖品牌（4/4，2026-09-06 自由が丘）

## 證據紀錄

### 👍 想去
- 2026-09-06 · 東京自由が丘 · ONIBUS COFFEE 自由が丘店 — 自家烘焙、轉角路面店、有露台座位
- 2026-09-16 · 福岡県北九州市小倉北区魚町 · Good Beer TAP TAP — 獨立單店、6 tap 國產精釀為主

### 👎 不要
- 2026-09-13 · 埼玉東松山 · マクドナルド 東松山インター店 — 全國速食連鎖

<!-- 註：以上皆為「意向回饋」。 -->
EOF
```

- [ ] **Step 2: 寫失敗測試**

在 `test-sightings.sh` 的 `== usage errors` 區段**之前**插入：

```bash
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
```

最後一條是關鍵：`## 強偏好` 裡的條目也是 `- ` 開頭，**必須只讀「證據紀錄」以下的兩個小節**。

- [ ] **Step 3: 跑測試確認它失敗**

Run: `trip-notes/tests/test-sightings.sh 2>&1 | grep -A3 "backfill converts"`
Expected: `backfill exits 0 :: expected [0] got [64]`

- [ ] **Step 4: 實作**

把 `backfill|stats)` 那個分支拆開，`backfill` 改為：

```bash
  backfill)
    log="$LOG_DEFAULT"; from=""
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --log)  log="${2:?--log needs a path}"; shift 2 ;;
        --from) from="${2:?--from needs a file}"; shift 2 ;;
        *) die64 "unknown flag '$1'" ;;
      esac
    done
    [[ -n "$from" ]] || usage
    [[ -f "$from" ]] || die64 "no such file: $from"
    mkdir -p "$(dirname "$log")"

    # Only the 證據紀錄 section. The bucket sections use the same "- " bullet
    # and would otherwise be read as venues.
    section=$(awk '/^## 證據紀錄/{s=1; next} /^## /{if(s) exit} s' "$from")

    lines=$(printf '%s\n' "$section" | awk '
      /^### 👍/ { v="👍"; next }
      /^### 👎/ { v="👎"; next }
      /^- / && v != "" { print v "\t" substr($0, 3) }
    ' | jq -R -c '
      split("\t") as $f
      | $f[1]
      | capture("^(?<d>[0-9]{4}-[0-9]{2}-[0-9]{2}) · (?<r>[^·]+) · (?<rest>.*)$")
      | (.rest | split(" — ")) as $nn
      | {legacy: true,
         run_date: .d,
         region: (.r | sub(" +$"; "")),
         name: ($nn[0] | sub(" +$"; "")),
         note: (if ($nn|length) > 1 then ($nn[1:] | join(" — ")) else null end),
         verdict: $f[0],
         rating: null, reviews: null, travel_min: null,
         matched_queries: [], rank_shown: null, tier: null, research: null}')

    if [[ -z "$lines" ]]; then
      echo "sightings: backfilled 0 legacy record(s) — no 證據紀錄 entries found in $from"
      exit 0
    fi
    printf '%s\n' "$lines" >> "$log"
    echo "sightings: backfilled $(printf '%s\n' "$lines" | wc -l | tr -d ' ') legacy record(s) to $log"
    ;;

  stats)
    echo "error: 'stats' is not implemented yet" >&2; exit 64 ;;
```

- [ ] **Step 5: 跑測試確認通過**

Run: `trip-notes/tests/test-sightings.sh`
Expected: 全綠

- [ ] **Step 6: 真的跑一次 backfill（一次性）**

```bash
trip-notes/skills/find-nearby/scripts/sightings backfill \
  --from ~/.config/trip-notes/preferences.md
jq -s 'length' ~/.config/trip-notes/sightings.jsonl
```
Expected: 16

**不要修改 `~/.config/trip-notes/preferences.md`。** 它是使用者的檔案，backfill 只讀不寫。

- [ ] **Step 7: Commit**

```bash
git -C /Users/neo/Projects/claude_local_marketplace add \
  trip-notes/skills/find-nearby/scripts/sightings \
  trip-notes/tests/test-sightings.sh trip-notes/tests/fixtures/sightings
git -C /Users/neo/Projects/claude_local_marketplace commit -m "feat(find-nearby): backfill the legacy evidence log into sightings

Sparse records with legacy:true. The fields the old prose never captured
stay absent rather than being reconstructed."
```

---

### Task 4: `sightings stats` — 摘要與壞行容忍

orchestrator 需要一行摘要（記錄數、分群概況）才能決定是否進中性模式，而**不能把整個 log 讀進自己的 context**——這與 SKILL.md「never cat an `--out` file」是同一條規則。壞掉的行必須跳過並回報，絕不中止。

**Files:**
- Modify: `trip-notes/skills/find-nearby/scripts/sightings`（`stats` 分支）
- Modify: `trip-notes/tests/test-sightings.sh`

**Interfaces:**
- Consumes: Task 2、Task 3 寫出的記錄
- Produces: `sightings stats [--log <path>] [--types <t1,t2>] [--queries <q1,q2>]`
  輸出三行：總數與回饋分佈、相關群大小（給了 `--types`/`--queries` 時）、壞行數。
  log 不存在時退出碼 0 並輸出 `sightings: no log at <path> (neutral mode)`。

- [ ] **Step 1: 寫失敗測試**

在 `== usage errors` 之前插入：

```bash
echo "== stats summarises without dumping records =="
out=$("$SIGHTINGS" stats --log "$LOG" 2>&1); rc=$?
assert_eq "stats exits 0" "0" "$rc"
assert_has "stats reports the total" "8 record(s)" "$out"
assert_eq "stats never prints a whole record" "0" "$(grep -c 'place_id' <<<"$out")"

echo "== stats sizes the relevant segment =="
out=$("$SIGHTINGS" stats --log "$LOG" --queries "角打ち" 2>&1)
assert_has "the segment is counted" "segment: 4 record(s)" "$out"

echo "== a missing log is neutral mode, not an error =="
out=$("$SIGHTINGS" stats --log "$TMP/nope.jsonl" 2>&1); rc=$?
assert_eq "a missing log exits 0" "0" "$rc"
assert_has "and says so plainly" "neutral mode" "$out"

echo "== a malformed line is skipped and reported, never fatal =="
cp "$LOG" "$TMP/dirty.jsonl"; echo '{"broken": ' >> "$TMP/dirty.jsonl"
out=$("$SIGHTINGS" stats --log "$TMP/dirty.jsonl" 2>&1); rc=$?
assert_eq "a malformed line does not abort" "0" "$rc"
assert_has "the skipped line is reported" "1 unreadable line" "$out"
assert_has "the readable ones still count" "8 record(s)" "$out"
```

- [ ] **Step 2: 跑測試確認它失敗**

Run: `trip-notes/tests/test-sightings.sh 2>&1 | grep -A3 "stats summarises"`
Expected: `stats exits 0 :: expected [0] got [64]`

- [ ] **Step 3: 實作**

把 `stats)` 分支換成：

```bash
  stats)
    log="$LOG_DEFAULT"; types=""; queries=""
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --log)     log="${2:?--log needs a path}"; shift 2 ;;
        --types)   types="${2:?--types needs a list}"; shift 2 ;;
        --queries) queries="${2:?--queries needs a list}"; shift 2 ;;
        *) die64 "unknown flag '$1'" ;;
      esac
    done
    if [[ ! -f "$log" ]]; then
      echo "sightings: no log at $log (neutral mode)"; exit 0
    fi

    total_lines=$(wc -l < "$log" | tr -d ' ')
    good=$(jq -c . "$log" 2>/dev/null | wc -l | tr -d ' ')
    bad=$(( total_lines - good ))

    jq -s -r --arg t "$types" --arg q "$queries" '
      ($t | split(",") | map(select(. != ""))) as $types
      | ($q | split(",") | map(select(. != ""))) as $queries
      | length as $n
      | ([.[] | select(.verdict=="👍")] | length) as $up
      | ([.[] | select(.verdict=="👎")] | length) as $down
      | ([.[] | select(.verdict==null)] | length) as $none
      | "sightings: \($n) record(s) — \($up) 👍 / \($down) 👎 / \($none) unmarked",
        ( if ($types|length) + ($queries|length) > 0 then
            ([ .[]
               | select( ((.type // "") as $ty | $types | index($ty) != null)
                         or ((.matched_queries // []) as $m
                             | ($queries | map(. as $x | $m | index($x) != null) | any)) )
             ] | length) as $seg
            | "segment: \($seg) record(s)"
            + (if $seg < 5 then "  ⚠ 少於 5 筆，推論薄弱且無刷掉權" else "" end)
          else empty end )' \
      <(jq -c . "$log" 2>/dev/null)

    [[ "$bad" -gt 0 ]] && echo "note: $bad unreadable line(s) skipped"
    exit 0
    ;;
```

- [ ] **Step 4: 跑測試確認通過**

Run: `trip-notes/tests/test-sightings.sh`
Expected: 全綠

若 `bad` 大於 0 時因 `set -e` 導致 `[[ ]]` 回傳非零而提前結束，把該行改成
`if [[ "$bad" -gt 0 ]]; then echo "note: $bad unreadable line(s) skipped"; fi`。

- [ ] **Step 5: Commit**

```bash
git -C /Users/neo/Projects/claude_local_marketplace add \
  trip-notes/skills/find-nearby/scripts/sightings trip-notes/tests/test-sightings.sh
git -C /Users/neo/Projects/claude_local_marketplace commit -m "feat(find-nearby): sightings stats, with a segment size and a weak-evidence warning

A malformed line is skipped and counted, never fatal — a corrupted memory
must not be able to stop a run."
```

---

### Task 5: 改寫 scoring brief 的契約

**Files:**
- Modify: `trip-notes/skills/find-nearby/templates/score-candidates-brief.md`
- Modify: `trip-notes/tests/test-skill-integrity.sh`

**Interfaces:**
- Consumes: Task 2–4 的記錄格式與 `sightings stats` 的 segment 概念
- Produces: brief 的 placeholder 集合變成
  `<CONDITIONS> <N> <POOL_PATH> <REVIEWS_PATH> <SIGHTINGS_PATH>`（Task 6 的 SKILL.md 依此填值）；
  輸出多一個 `### 分群與軸` 區段，`### 排序依據` 必須含計數。

- [ ] **Step 1: 寫失敗測試**

在 `test-skill-integrity.sh` 的 `== brief placeholders are all fillable ==` 區段，把 score brief 那條斷言改成新集合，並在其後新增：

```bash
echo "== the scoring brief mandates segment-then-axes-then-rank =="
SB="$FN/templates/score-candidates-brief.md"
for phrase in "先分群" "每條軸都要附計數" "沒有計數的軸不得使用"; do
  if grep -qF "$phrase" "$SB"; then assert_pass "score brief states: $phrase"
  else assert_fail "score brief states: $phrase" "missing"; fi
done

echo "== the removal bar survives the rewrite =="
for phrase in "少於 5 筆" "≥ 2 次不同執行" "任何一群都沒有"; do
  if grep -qF "$phrase" "$SB"; then assert_pass "score brief keeps the removal bar: $phrase"
  else assert_fail "score brief keeps the removal bar: $phrase" "missing"; fi
done

echo "== inference may never silently remove =="
if grep -qF "若這條推錯了，告訴我" "$SB"; then
  assert_pass "score brief mandates the correctable removal line"
else assert_fail "score brief mandates the correctable removal line" "missing"; fi
```

- [ ] **Step 2: 跑測試確認它失敗**

Run: `trip-notes/tests/test-skill-integrity.sh 2>&1 | grep -B1 -A3 FAIL | head -30`
Expected: 上述新斷言全部 FAIL

- [ ] **Step 3: 改寫 brief**

把 `score-candidates-brief.md` 的「Inputs」段中 `Preferences:` 那一條換成：

```markdown
- 目擊紀錄: `<SIGHTINGS_PATH>` — append-only JSONL，一行一筆，每筆是「某次執行展示過的
  某一家店」。含 `type` / `matched_queries` / `rating` / `reviews` / `open_from` /
  `hours_span_h` / `travel_min` / `pool_hits` / `rank_shown` / `tier` / `verdict`，
  首選層另有 `research`。`verdict` 為 `null` 代表展示過但使用者沒標記——那是弱負面
  訊號，配上 `rank_shown` 才看得出「我們排第 1 的他沒選」。`legacy: true` 的記錄是從
  舊偏好檔搬來的，欄位稀疏，只有 `name` / `run_date` / `region` / `verdict` / `note`。
- 使用者親口說的話: `~/.config/trip-notes/preferences.md`（若存在）。**權威高於任何
  你從目擊紀錄推論出來的東西。** 它是純人工檔，你不得寫入。
```

把原本的「Neutral mode」段改成：

```markdown
## 三步，順序不得顛倒

1. **先分群。** 用 `type` 重疊**或** `matched_queries` 重疊，從目擊紀錄裡切出與本次
   相關的那群。先寫出這群有幾筆、包含哪些店。`legacy` 記錄沒有 `type` 也沒有
   `matched_queries`，只能靠 `name` 與 `note` 判斷，判不出來就不要硬塞進群裡。
2. **在群內找軸。** 每條軸都要附計數，例如
   「`hours_span_h ≥ 8` 的 5 家裡 3 家 👍；`< 4` 的 4 家 0 家 👍」。
   **沒有計數的軸不得使用。** 也要主動找出歷史上「排得高卻沒被選」與「排得低卻被選」
   的案例，說明本次如何避免重蹈。
3. **才排序。**

若相關群少於 5 筆，或目擊紀錄檔不存在：寫明
「此店種僅 N 筆目擊，推論薄弱」，改以條件符合度與 `rating` 排序，並且**沒有刷掉權**。

## 刷掉權

只有這四種情形可以讓候選從筆記裡消失：

1. `status` 是 `CLOSED_PERMANENTLY` 或 `CLOSED_TEMPORARILY`
2. 某個 amenity 欄位對使用者要求的條件明確為 `false`
3. 使用者在 `preferences.md` 裡親口說的話明確適用
4. 從目擊紀錄推論出的特徵，且**同時**滿足：
   - 相關群**不是**少於 5 筆
   - 該群內 **≥ 2 筆 👎** 共有該特徵
   - 這些 👎 來自 **≥ 2 次不同執行**（同一次執行裡注意到的兩項特徵只算 1 次）
   - **任何一群都沒有**帶同一特徵的 👍（矛盾證據永久禁止刷掉）

第 4 種每刷掉一個，「已篩掉」那行必須寫成：
`<店名> — 本次推論「<特徵>」（證據：N 筆 👎 / M 筆 👍）。若這條推錯了，告訴我。`

一個從未出現的候選，使用者永遠沒機會說「這條錯了」——所以刷掉必須留下可被糾正的痕跡。
```

在「Output」段的 `### 排序結果` **之前**插入：

```markdown
### 分群與軸
先寫：相關群有幾筆、由哪些店組成、怎麼判定相關（`type` 還是 `matched_queries`）。
再寫：你找到的每條軸與它的計數。沒有計數的軸不要寫。
若少於 5 筆，這一段就只寫「此店種僅 N 筆目擊，推論薄弱」與你改用的排序依據。
```

並把 `### 排序依據` 的說明改成：

```markdown
### 排序依據
寫：相關群的大小、你實際用了哪幾條軸與各自計數、`preferences.md` 裡有沒有使用者親口
說的話被套用，以及有沒有哪條軸因為資料不存在而無法套用。**每條軸都要帶計數**——這是
使用者唯一能看出推論在兩次執行之間漂移的地方。
```

**刪除**整個「## Neutral mode」舊段與所有提及「強偏好／弱偏好／未定／反感」四個桶的文字。

- [ ] **Step 4: 跑測試確認通過**

Run: `trip-notes/tests/test-skill-integrity.sh`
Expected: 全綠

- [ ] **Step 5: Commit**

```bash
git -C /Users/neo/Projects/claude_local_marketplace add \
  trip-notes/skills/find-nearby/templates/score-candidates-brief.md \
  trip-notes/tests/test-skill-integrity.sh
git -C /Users/neo/Projects/claude_local_marketplace commit -m "feat(find-nearby): scoring agent segments, derives axes with counts, then ranks

The removal bar is unchanged — two 👎 from two different runs, and any
contradicting 👍 disqualifies the trait forever. It is computed from the
log now instead of maintained by hand."
```

---

### Task 6: SKILL.md 改線 + preferences 模板降為人工檔

**Files:**
- Modify: `trip-notes/skills/find-nearby/SKILL.md`（Step 0.5、pipeline 圖、Step 5、Step 11、Guardrails）
- Modify: `trip-notes/skills/find-nearby/templates/preferences-example.md`
- Modify: `trip-notes/tests/test-skill-integrity.sh`

**Interfaces:**
- Consumes: Task 2–5 的全部產出
- Produces: SKILL.md 引用 `scripts/sightings` 與 `<SIGHTINGS_PATH>`；Step 11 只 append 不算帳。

- [ ] **Step 1: 寫失敗測試**

`test-skill-integrity.sh` 裡的
`== preference file headings are the contract ==` 整段刪掉（那份契約不再存在），
換成：

```bash
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
```

- [ ] **Step 2: 跑測試確認它失敗**

Run: `trip-notes/tests/test-skill-integrity.sh`
Expected: 新斷言 FAIL

- [ ] **Step 3: 改寫 `preferences-example.md`**

整檔換成：

```markdown
# 個人偵店偏好

<!--
這個檔案完全屬於你。**skill 不會寫這個檔**，只會讀。

寫在這裡的東西是「你親口說的話」，權威高於 skill 從目擊紀錄推論出來的任何結論。
格式隨你——條列、散文、中英日夾雜都可以。skill 不解析區塊標題。

適合寫在這裡的：
- 硬條件（「我不去全席吸菸的店」）
- 你已經確定、不想每次重新被推論的結論
- 你希望 skill 知道的背景（同行者、行動限制、預算上限）

skill 自己的記憶在 `sightings.jsonl`，那是機器讀的；這個檔是給你寫的。
-->
```

- [ ] **Step 4: 改寫 SKILL.md**

把 `## Step 0.5 — The preference file` 整節換成：

```markdown
## Step 0.5 — 記憶

兩個來源，權威分明：

- `~/.config/trip-notes/preferences.md` — **使用者親口說的話**，純人工檔。
  存在就整份交給 Step 5 的 agent，當作最高權威。**skill 永遠不寫這個檔。**
- `~/.config/trip-notes/sightings.jsonl` — 目擊紀錄，skill 唯一會寫的記憶。

先跑一行拿摘要，**不要把 log 讀進自己的 context**：

```bash
scripts/sightings stats --queries "<本次查詢詞，逗號分隔>"
```

它會回報總筆數、相關群大小，以及群小於 5 筆時的警告。log 不存在 → 中性模式，
一行告知使用者，流程照跑。
```

pipeline 圖中 `0.5` 那行改為：

```
0.5  sightings stats（拿摘要，不讀內容）；log 不存在 → 中性模式，一行告知
```

`11` 那行改為：

```
11   回饋階段 → sightings append（展示過的每一家）→ 一行回報
```

Step 5 的派工段，把填 `<POOL_PATH>` 那句改為同時填
`<SIGHTINGS_PATH>`（`~/.config/trip-notes/sightings.jsonl`），
並把「Record for 驗證狀態」那段之後補上：

```markdown
agent 會回一個 `### 分群與軸` 區段。把它的內容帶進筆記的「排序依據」——**每條軸都要
帶計數**。相關群少於 5 筆時，agent 必須宣告推論薄弱且不得行使刷掉權；若它在薄弱的
情況下仍刷掉了候選，退回重做。
```

`## Step 11 — The feedback round` 整節換成：

```markdown
## Step 11 — 回饋階段

用 `AskUserQuestion` 問兩題（都 `multiSelect: true`）：「哪幾家你會想去？」
「哪幾家一看就不要？」兩面都問，因為負面訊號不需要使用者真的去過就成立。

這是**意向回饋，不是體驗回饋**——使用者當下還沒去過。

然後只做一件事：把**展示過的每一家**寫進目擊紀錄。先寫一個 shown 檔：

```bash
cat > <scratch>/shown.json <<'JSON'
[{"place_id":"...","rank_shown":1,"tier":"首選","verdict":"👍","research":{...}},
 {"place_id":"...","rank_shown":2,"tier":"首選","verdict":null}]
JSON
cat > <scratch>/run.json <<'JSON'
{"run_id":"<日期>-<地點>-<主題>","run_date":"<今天>","target_date":"<目標日>",
 "region":"...","origin":"...","request":"<使用者原話，逐字>",
 "queries":["..."],"mode":"WALK","max_min":20}
JSON
scripts/sightings append --run <scratch>/run.json --top14 <scratch>/top14.json \
  --shown <scratch>/shown.json --pool <scratch>/pool-*.json
```

`verdict` 只有三種值：`"👍"`、`"👎"`、`null`。**沒被標記的一律寫 `null`，不要省略
那一筆**——它配上 `rank_shown` 才說得出「我們排第 1 的使用者沒選」，而那是這份記憶
裡最有價值的一句話。`research` 只有首選層有，其餘省略。

使用者略過不答是合法結果：`verdict` 全部寫 `null`，記錄照寫。

回報一行：「已記錄 10 筆目擊（3 👍 / 1 👎 / 6 未標記）」。

**不再有升級運算、條目上限、合併與汰換。** 那些帳本身就是錯誤來源。
```

Guardrails 段裡關於 `## 強偏好` / `## 反感` 的那兩條刪除，換成：

```markdown
- 推論出來的偏好可以刷掉候選，但門檻與交代方式由 `score-candidates-brief.md` 規定，
  且每一次刷掉都必須在筆記裡留下可被糾正的那一行。使用者親口說的話權威更高。
```

- [ ] **Step 5: 跑測試確認通過**

Run: `trip-notes/tests/test-skill-integrity.sh && trip-notes/tests/test-sightings.sh && trip-notes/tests/test-maps.sh && trip-notes/tests/test-note-provenance.sh`
Expected: 四支全綠

- [ ] **Step 6: Commit**

```bash
git -C /Users/neo/Projects/claude_local_marketplace add \
  trip-notes/skills/find-nearby/SKILL.md \
  trip-notes/skills/find-nearby/templates/preferences-example.md \
  trip-notes/tests/test-skill-integrity.sh
git -C /Users/neo/Projects/claude_local_marketplace commit -m "feat(find-nearby): wire the sightings log through the pipeline

preferences.md becomes human-authored only. 'Hand edits must survive' stops
being a discipline the skill has to remember and becomes a property: the
skill no longer writes that file at all."
```

---

### Task 7: 小倉回歸案例

這個設計是被一次具體的失敗推動的，回歸測試要鎖住那次失敗。2026-09-16 小倉那次執行：
「自家製造・自家調達」從咖啡廳與麵店學來，套到日本酒與精釀啤酒上，把最命中的兩家排在
第 1、第 2，使用者一家都沒選。

**Files:**
- Create: `trip-notes/tests/fixtures/sightings/kokura-replay.jsonl`
- Modify: `trip-notes/tests/test-sightings.sh`

**Interfaces:**
- Consumes: Task 2–6 全部
- Produces: 一份可重放的目擊紀錄，與針對它的結構性斷言。

- [ ] **Step 1: 產生 fixture**

```bash
cd /Users/neo/Projects/claude_local_marketplace/trip-notes/tests/fixtures/sightings
cat > kokura-replay.jsonl <<'EOF'
{"run_id":"2026-09-06-jiyugaoka","run_date":"2026-09-06","region":"東京自由が丘","name":"ONIBUS COFFEE 自由が丘店","type":"カフェ","matched_queries":["自家焙煎"],"verdict":"👍","rank_shown":3,"tier":"首選","research":{"own_production":true,"independent":true}}
{"run_id":"2026-09-13-hiki","run_date":"2026-09-13","region":"埼玉比企郡","name":"手打うどん 大井戸","type":"うどん","matched_queries":["手打ち"],"verdict":"👍","rank_shown":2,"tier":"首選","research":{"own_production":true,"independent":true}}
{"run_id":"2026-09-16-kokura-craftbeer","run_date":"2026-09-16","target_date":"2026-09-19","region":"福岡県北九州市小倉北区","name":"飛来haku","type":"バー","matched_queries":["日本酒"],"open_from":"19:00","hours_span_h":5,"rating":4.9,"reviews":16,"verdict":null,"rank_shown":1,"tier":"首選","research":{"own_production":true,"independent":true}}
{"run_id":"2026-09-16-kokura-craftbeer","run_date":"2026-09-16","target_date":"2026-09-19","region":"福岡県北九州市小倉北区","name":"林田酒店","type":"酒店","matched_queries":["日本酒","角打ち"],"open_from":"10:00","hours_span_h":8,"rating":4.5,"reviews":83,"verdict":null,"rank_shown":2,"tier":"首選","research":{"own_production":true,"independent":true}}
{"run_id":"2026-09-16-kokura-craftbeer","run_date":"2026-09-16","target_date":"2026-09-19","region":"福岡県北九州市小倉北区","name":"酒の中村園 魚町店","type":"酒店","matched_queries":["クラフトビール","日本酒","角打ち"],"open_from":"13:00","hours_span_h":8,"rating":4.7,"reviews":61,"verdict":"👍","rank_shown":3,"tier":"首選","research":{"own_production":false,"independent":true}}
{"run_id":"2026-09-16-kokura-craftbeer","run_date":"2026-09-16","target_date":"2026-09-19","region":"福岡県北九州市小倉北区","name":"Good Beer TAP TAP","type":"バー","matched_queries":["クラフトビール","ビアバー"],"open_from":"13:00","hours_span_h":9,"rating":4.6,"reviews":48,"verdict":"👍","rank_shown":4,"tier":"首選","research":{"own_production":false,"independent":true}}
{"run_id":"2026-09-16-kokura-craftbeer","run_date":"2026-09-16","target_date":"2026-09-19","region":"福岡県北九州市小倉北区","name":"MELKED 小倉駅ナカ店","type":"酒店","matched_queries":["日本酒","角打ち"],"open_from":"09:00","hours_span_h":12,"rating":4.4,"reviews":40,"verdict":"👍","rank_shown":8,"tier":"其他候選","research":{"own_production":false,"independent":false,"in_mall":true}}
{"run_id":"2026-09-16-kokura-craftbeer","run_date":"2026-09-16","target_date":"2026-09-19","region":"福岡県北九州市小倉北区","name":"Bar Bumblebees","type":"軽食店","matched_queries":["ビアバー"],"open_from":null,"hours_span_h":null,"hours_missing":true,"rating":4.8,"reviews":6,"verdict":"👎","rank_shown":9,"tier":"其他候選"}
EOF
```

- [ ] **Step 2: 寫失敗測試**

在 `test-sightings.sh` 的 `== usage errors` 之前插入：

```bash
echo "== the Kokura regression case is queryable from the log alone =="
K="$F/kokura-replay.jsonl"

# The axis the old buckets fired on. Inside the sake/beer segment it has NO
# support: both 👍-less venues had it, and none of the three picks did.
seg='[.[] | select((.matched_queries // []) | any(. == "日本酒" or . == "クラフトビール" or . == "角打ち" or . == "ビアバー"))]'
assert_eq "the segment is six venues" "6" "$(jq -s "$seg | length" "$K")"
assert_eq "own_production has zero 👍 inside the segment" "0" \
  "$(jq -s "$seg | [.[] | select(.research.own_production == true and .verdict == \"👍\")] | length" "$K")"
assert_eq "and it is exactly the two the user skipped" "2" \
  "$(jq -s "$seg | [.[] | select(.research.own_production == true and .verdict == null)] | length" "$K")"

# The axis the user actually picked on, which the old model had no field for.
assert_eq "all three picks open at or before 13:00" "3" \
  "$(jq -s "$seg | [.[] | select(.verdict == \"👍\" and .open_from != null and .open_from <= \"13:00\")] | length" "$K")"
assert_eq "no pick opens later than that" "0" \
  "$(jq -s "$seg | [.[] | select(.verdict == \"👍\" and .open_from != null and .open_from > \"13:00\")] | length" "$K")"

# The inversion: the log must be able to say where our ranking was wrong.
assert_eq "our #1 was not picked" "null" \
  "$(jq -sr '.[] | select(.rank_shown == 1 and .run_id == "2026-09-16-kokura-craftbeer") | .verdict' "$K")"
assert_eq "a venue we ranked 8th was" "👍" \
  "$(jq -sr '.[] | select(.rank_shown == 8 and .run_id == "2026-09-16-kokura-craftbeer") | .verdict' "$K")"

# The contradiction rule's raw material: in_mall has a 👍, so it may never remove.
assert_eq "in_mall has a 👍 and can therefore never earn removal power" "1" \
  "$(jq -s '[.[] | select(.research.in_mall == true and .verdict == "👍")] | length' "$K")"

echo "== cross-segment traits do not leak =="
assert_eq "own_production's 👍 all come from outside the drinks segment" "2" \
  "$(jq -s '[.[] | select(.research.own_production == true and .verdict == "👍")] | length' "$K")"
```

- [ ] **Step 3: 跑測試確認它失敗**

Run: `trip-notes/tests/test-sightings.sh 2>&1 | grep -A6 "Kokura regression"`
Expected: 因 fixture 尚未建立而 FAIL（若先做了 Step 1 則會直接通過——**那就把 Step 1 的檔案暫時移走再跑一次**，確認測試真的會抓）

- [ ] **Step 4: 確認通過**

Run: `trip-notes/tests/test-sightings.sh`
Expected: 全綠

- [ ] **Step 5: 人工重放檢查（記錄結果，不自動化）**

真實派一次 Step 5 的 scoring agent，餵 `kokura-replay.jsonl` 與當時的 14 家候選，
確認它的 `### 分群與軸` 區段：

1. 明確寫出酒類群的筆數；
2. **沒有**把 `own_production` 當成本次的正向軸；
3. 每條軸都帶計數。

三項有任何一項不成立，回頭改 `score-candidates-brief.md` 的措辭，不要改 fixture。
把結果寫進 commit message。

- [ ] **Step 6: Commit**

```bash
git -C /Users/neo/Projects/claude_local_marketplace add \
  trip-notes/tests/fixtures/sightings/kokura-replay.jsonl \
  trip-notes/tests/test-sightings.sh
git -C /Users/neo/Projects/claude_local_marketplace commit -m "test(find-nearby): lock in the Kokura case that motivated the redesign

own_production had two 👍 in the log and zero inside the drinks segment. The
old flat model could not see that distinction; these assertions fail if the
record shape ever stops being able to."
```

---

## 延後項目（不在本 plan 內）

**B — 店種側寫卡快取。** 把 `sightings.jsonl` 蒸餾成 `profile-<kind>.md`，每次只讀
相關那張卡。目前 16 筆目擊，屬 YAGNI。觸發條件：`sightings stats` 回報的總筆數大到
scoring agent 讀不完整個 log 時。屆時另開 spec。
