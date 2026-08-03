# Resume Ended Sessions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `tmux-cc-attach` so a plain run offers to resume recently-ended Claude sessions (via `claude -r`) alongside attaching live tmux sessions, fed by a SessionEnd-hook resume store.

**Architecture:** The SessionEnd hook writes a resume record `{session_id, cwd, ts_start, ts_end, reason}` to a dedicated `~/.claude/session-manager/resume/` store (the locator never reads/sweeps it), then deletes the live-registry file as before. `tmux-cc-attach` is vendored into the plugin, gains resume helpers behind a lib-only source guard, and — resume on by default — lists recent, still-resumable, not-currently-live ended sessions grouped by project, launching each with `tmux -CC new-session -c '<cwd>' "claude -r '<id>'"`.

**Tech Stack:** Bash + `jq`, AppleScript (`osascript`) for iTerm, tmux control mode (`-CC`), Python 3 (`locator.py`, consumed read-only).

## Global Constraints

- Base dir is `${CLAUDE_SM_HOME:-$HOME/.claude/session-manager}` — every path derives from it.
- Hooks MUST `exit 0` on every error path and missing `jq`; never block session start/shutdown.
- The SP3 locator contract is frozen: `sessions/<id>.json` keeps its exact `{session_id, claude_pid, cwd, ts}` shape and continues to be deleted on SessionEnd. Do NOT change `locator.py` or the `sessions/` layout.
- Resume records live ONLY in `resume/`; the locator sweep (`_sweep_dead_registry`) must never touch them.
- Atomic writes use the existing tmp-file + `mv -f` pattern from `record-session.sh`.
- `RESUME_MAX_AGE_DAYS` default is `14`.
- After implementation, bump the plugin version via `./scripts/bump-plugin.sh session-manager minor`.

---

### Task 1: SessionEnd hook writes a resume record

**Files:**
- Modify: `session-manager/hooks/remove-session.sh`
- Test: `session-manager/tests/test-record-session.sh`

**Interfaces:**
- Consumes: SessionEnd hook stdin JSON `{session_id, cwd?, reason?}`; the start record `sessions/<id>.json` `{cwd, ts}` written by `record-session.sh`.
- Produces: `resume/<id>.json` with exactly `{"session_id","cwd","ts_start","ts_end","reason"}` (cwd/reason JSON-string-escaped; ts_* bare numbers). `sessions/<id>.json` still deleted.

- [ ] **Step 1: Write the failing tests** — append to `session-manager/tests/test-record-session.sh` before the final pass/fail line:

```bash
# 7. SessionEnd writes a resume record merging start ts and end reason
RSID="99999999-8888-7777-6666-555555555555"
echo "{\"session_id\":\"$RSID\",\"cwd\":\"/tmp/proj\"}" | CLAUDE_PID=7777 bash "$REC"
START_TS=$(jq -r '.ts' "$TMP/sessions/$RSID.json")
echo "{\"session_id\":\"$RSID\",\"cwd\":\"/tmp/proj\",\"reason\":\"logout\"}" | bash "$RM"
RF="$TMP/resume/$RSID.json"
check "resume record written" "[ -f '$RF' ]"
check "resume has session_id" "grep -q '\"session_id\":\"$RSID\"' '$RF'"
check "resume has cwd" "grep -q '\"cwd\":\"/tmp/proj\"' '$RF'"
check "resume ts_start from start record" "[ \"\$(jq -r .ts_start '$RF')\" = \"$START_TS\" ]"
check "resume has ts_end" "[ \"\$(jq -r .ts_end '$RF')\" -ge \"$START_TS\" ]"
check "resume has reason" "grep -q '\"reason\":\"logout\"' '$RF'"
check "start record deleted" "[ ! -f '$TMP/sessions/$RSID.json' ]"

# 8. Fallback: no start record -> cwd/reason from input, ts_start==ts_end
RSID2="12121212-3434-5656-7878-909090909090"
echo "{\"session_id\":\"$RSID2\",\"cwd\":\"/tmp/fb\",\"reason\":\"other\"}" | bash "$RM"
RF2="$TMP/resume/$RSID2.json"
check "fallback resume written" "[ -f '$RF2' ]"
check "fallback cwd from input" "grep -q '\"cwd\":\"/tmp/fb\"' '$RF2'"
check "fallback ts_start==ts_end" "[ \"\$(jq -r .ts_start '$RF2')\" = \"\$(jq -r .ts_end '$RF2')\" ]"

# 9. No cwd anywhere -> no resume record, exit 0
RSID3="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
echo "{\"session_id\":\"$RSID3\"}" | bash "$RM"; rc=$?
check "no-cwd remove exits 0" "[ $rc -eq 0 ]"
check "no-cwd writes no resume" "[ ! -f '$TMP/resume/$RSID3.json' ]"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `bash session-manager/tests/test-record-session.sh`
Expected: FAIL on "resume record written" (remove-session.sh does not write resume yet).

- [ ] **Step 3: Rewrite `remove-session.sh`** to this:

```bash
#!/bin/bash
# SessionEnd hook (SP3 + resume): write a resume record, then delete this
# session's live-registry file. Never blocks the TUI.
set -u
input=$(cat)
command -v jq >/dev/null 2>&1 || exit 0
session_id=$(printf '%s' "$input" | jq -r '.session_id // ""')
[ -n "$session_id" ] || exit 0

base="${CLAUDE_SM_HOME:-$HOME/.claude/session-manager}"
start_file="$base/sessions/$session_id.json"

cwd=""; ts_start=""
if [ -f "$start_file" ]; then
    cwd=$(jq -r '.cwd // ""' "$start_file" 2>/dev/null)
    ts_start=$(jq -r '.ts // ""' "$start_file" 2>/dev/null)
fi
[ -n "$cwd" ] || cwd=$(printf '%s' "$input" | jq -r '.cwd // ""')
reason=$(printf '%s' "$input" | jq -r '.reason // ""')
ts_end=$(date +%s)
case "$ts_start" in ''|*[!0-9]*) ts_start="$ts_end" ;; esac

# Write the resume record only when we know the owning cwd (claude -r needs it).
if [ -n "$cwd" ]; then
    rdir="$base/resume"
    mkdir -p "$rdir" 2>/dev/null
    cwd_json=$(printf '%s' "$cwd" | jq -R .)
    reason_json=$(printf '%s' "$reason" | jq -R .)
    tmp=$(mktemp "$rdir/.tmp.XXXXXX" 2>/dev/null) && {
        printf '{"session_id":"%s","cwd":%s,"ts_start":%s,"ts_end":%s,"reason":%s}\n' \
            "$session_id" "$cwd_json" "$ts_start" "$ts_end" "$reason_json" > "$tmp"
        mv -f "$tmp" "$rdir/$session_id.json" 2>/dev/null || rm -f "$tmp"
    }
fi

rm -f "$start_file" 2>/dev/null
exit 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `bash session-manager/tests/test-record-session.sh`
Expected: `ALL PASS`.

- [ ] **Step 5: Commit**

```bash
git add session-manager/hooks/remove-session.sh session-manager/tests/test-record-session.sh
git commit -m "feat(session-manager): SessionEnd hook records resume keys"
```

---

### Task 2: Vendor tmux-cc-attach + add resume helpers behind a lib guard

**Files:**
- Create: `session-manager/scripts/tmux-cc-attach` (copy of `~/.local/bin/tmux-cc-attach`, then edited)
- Create: `session-manager/tests/test-tmux-cc-attach.sh`

**Interfaces:**
- Consumes: existing `escape_shell_single` (already in the script).
- Produces (sourceable when `TMUX_CC_LIB_ONLY=1`): `resume_dir`, `transcript_root`, `resume_within_age ts_end now days`, `resume_is_resumable id root`, `resume_attach_command cwd id`, `read_resume_records` (emits `id|cwd|ts_end|reason` per record).

- [ ] **Step 1: Copy the current global script into the repo**

Run:
```bash
cp ~/.local/bin/tmux-cc-attach session-manager/scripts/tmux-cc-attach
chmod +x session-manager/scripts/tmux-cc-attach
```

- [ ] **Step 2: Add resume config + helpers** — in `session-manager/scripts/tmux-cc-attach`, immediately after the `readonly PREF_TABS=2` line, add:

```bash
readonly RESUME_MAX_AGE_DAYS_DEFAULT=14
RESUME_MAX_AGE_DAYS="${RESUME_MAX_AGE_DAYS:-$RESUME_MAX_AGE_DAYS_DEFAULT}"
SM_HOME="${CLAUDE_SM_HOME:-$HOME/.claude/session-manager}"
PROJECTS_DIR="${CLAUDE_PROJECTS_DIR:-$HOME/.claude/projects}"
```

- [ ] **Step 3: Add the resume helper functions** — after the `escape_shell_single` function definition, add:

```bash
# --- resume store ------------------------------------------------------------

resume_dir()      { printf '%s\n' "$SM_HOME/resume"; }
transcript_root() { printf '%s\n' "$PROJECTS_DIR"; }

# 0 if ts_end is within max_age_days of now.
resume_within_age() {
    local te="$1" now="$2" days="$3"
    case "$te" in ''|*[!0-9]*) return 1 ;; esac
    [ "$te" -ge "$(( now - days * 86400 ))" ]
}

# 0 if a transcript exists for this session id under the transcript root.
resume_is_resumable() {
    local id="$1" root="$2"
    compgen -G "$root/*/$id.jsonl" >/dev/null 2>&1
}

# The command that recreates + attaches a session in a fresh tmux -CC session.
resume_attach_command() {
    local ec ei
    ec=$(escape_shell_single "$1")
    ei=$(escape_shell_single "$2")
    printf "tmux -CC new-session -c '%s' \"claude -r '%s'\"" "$ec" "$ei"
}

# Emit one line per resume record: id|cwd|ts_end|reason
read_resume_records() {
    local d f
    d=$(resume_dir)
    for f in "$d"/*.json; do
        [ -e "$f" ] || continue
        jq -r '[.session_id, .cwd, (.ts_end|tostring), (.reason // "")] | join("|")' \
            "$f" 2>/dev/null
    done
}
```

- [ ] **Step 4: Add the lib-only guard** — immediately BEFORE the `# --- argument parsing` comment block (the `while [ $# -gt 0 ]` loop), add:

```bash
# When sourced by tests, stop here with all helpers defined.
if [ -n "${TMUX_CC_LIB_ONLY:-}" ]; then
    return 0 2>/dev/null || exit 0
fi
```

- [ ] **Step 5: Write the helper unit tests** — create `session-manager/tests/test-tmux-cc-attach.sh`:

```bash
#!/bin/bash
# Unit tests for tmux-cc-attach resume helpers (sourced lib-only).
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/../scripts/tmux-cc-attach"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export CLAUDE_SM_HOME="$TMP"
export CLAUDE_PROJECTS_DIR="$TMP/projects"
fails=0
check() { if eval "$2"; then echo "ok - $1"; else echo "FAIL - $1"; fails=$((fails+1)); fi; }

TMUX_CC_LIB_ONLY=1 . "$SCRIPT"

NOW=1785000000
check "within age true"  "resume_within_age $((NOW-86400)) $NOW 14"
check "within age false" "! resume_within_age $((NOW-15*86400)) $NOW 14"
check "within age junk"  "! resume_within_age '' $NOW 14"

mkdir -p "$CLAUDE_PROJECTS_DIR/-tmp-proj"
touch "$CLAUDE_PROJECTS_DIR/-tmp-proj/abc123.jsonl"
check "resumable true"  "resume_is_resumable abc123 \"\$(transcript_root)\""
check "resumable false" "! resume_is_resumable nope \"\$(transcript_root)\""

cmd=$(resume_attach_command "/tmp/my proj" "id'x")
check "attach cmd cwd"  "printf '%s' \"\$cmd\" | grep -q \"new-session -c '/tmp/my proj'\""
check "attach cmd id"   "printf '%s' \"\$cmd\" | grep -q \"claude -r 'id'\\\\\\\\''x'\""

mkdir -p "$(resume_dir)"
printf '{"session_id":"s1","cwd":"/tmp/a","ts_start":1,"ts_end":100,"reason":"logout"}\n' > "$(resume_dir)/s1.json"
line=$(read_resume_records)
check "read record joined" "[ \"\$line\" = 's1|/tmp/a|100|logout' ]"

[ "$fails" -eq 0 ] && { echo "ALL PASS"; exit 0; } || { echo "$fails FAILED"; exit 1; }
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `bash session-manager/tests/test-tmux-cc-attach.sh`
Expected: `ALL PASS`.

- [ ] **Step 7: Commit**

```bash
git add session-manager/scripts/tmux-cc-attach session-manager/tests/test-tmux-cc-attach.sh
git commit -m "feat(session-manager): vendor tmux-cc-attach, add resume helpers + lib guard"
```

---

### Task 3: Gather resume entries into the report + dry-run behind flags

**Files:**
- Modify: `session-manager/scripts/tmux-cc-attach`
- Test: `session-manager/tests/test-tmux-cc-attach.sh`

**Interfaces:**
- Consumes: helpers from Task 2; `project_of_dir` (existing).
- Produces: resume gathering controlled by `RESUME=1` (default), `--no-resume` (RESUME=0), `--resume-only` (RESUME=1, live off), `--since <days>`. `-n` dry-run prints `tmux -CC new-session ...` lines for each surviving resume entry. Live session ids for dedup come from `live_session_ids` (locator, best-effort empty).

- [ ] **Step 1: Write the failing dry-run test** — append to `session-manager/tests/test-tmux-cc-attach.sh` before the final pass/fail line:

```bash
# Integration: --resume-only -n prints a resume command for a fresh, resumable record.
NOW2=$(date +%s)
rm -f "$(resume_dir)"/*.json
mkdir -p "$CLAUDE_PROJECTS_DIR/-tmp-live"
touch "$CLAUDE_PROJECTS_DIR/-tmp-live/livesid.jsonl"
printf '{"session_id":"livesid","cwd":"/tmp/live","ts_start":1,"ts_end":%s,"reason":"logout"}\n' "$NOW2" \
    > "$(resume_dir)/livesid.json"
# A stale (old) record and a no-transcript record must be dropped.
printf '{"session_id":"oldsid","cwd":"/tmp/old","ts_start":1,"ts_end":1,"reason":"other"}\n' \
    > "$(resume_dir)/oldsid.json"
printf '{"session_id":"ghostsid","cwd":"/tmp/ghost","ts_start":1,"ts_end":%s,"reason":"other"}\n' "$NOW2" \
    > "$(resume_dir)/ghostsid.json"
out=$(TMUX_CC_LOCATOR=/nonexistent bash "$SCRIPT" --resume-only -n 2>/dev/null)
check "dry-run shows resumable" "printf '%s' \"\$out\" | grep -q \"claude -r 'livesid'\""
check "dry-run drops stale age" "! printf '%s' \"\$out\" | grep -q oldsid"
check "dry-run drops no-transcript" "! printf '%s' \"\$out\" | grep -q ghostsid"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash session-manager/tests/test-tmux-cc-attach.sh`
Expected: FAIL — `--resume-only` is an unknown option / no resume output yet.

- [ ] **Step 3: Add `live_session_ids` helper** — after `read_resume_records`, add:

```bash
LOCATOR="${TMUX_CC_LOCATOR:-$(cd "$(dirname "$0")" && pwd)/locator.py}"

# session_ids currently live per the locator (best-effort; empty on any failure).
live_session_ids() {
    command -v python3 >/dev/null 2>&1 || return 0
    [ -f "$LOCATOR" ] || return 0
    python3 "$LOCATOR" list 2>/dev/null | jq -r '.[].session_id' 2>/dev/null
}
```

- [ ] **Step 4: Add flag defaults + parse the new flags** — near the other option defaults (`GROUP=1`), add `RESUME=1` and `RESUME_ONLY=0`. Then in the argument-parsing `case`, add these arms before the `*)` catch-all:

```bash
        --no-resume)    RESUME=0; shift ;;
        --resume-only)  RESUME_ONLY=1; RESUME=1; shift ;;
        --since)        [ $# -ge 2 ] || die "--since needs days"; RESUME_MAX_AGE_DAYS="$2"; shift 2 ;;
```

- [ ] **Step 5: Skip the tmux-server preflight in resume-only mode** — replace the line `tmux list-sessions >/dev/null 2>&1 || die "no tmux server running"` with:

```bash
if [ "$RESUME_ONLY" -eq 0 ]; then
    tmux list-sessions >/dev/null 2>&1 || die "no tmux server running"
fi
```

- [ ] **Step 6: Guard the live-session gathering** — wrap the existing live-session build block (the `PANE_DATA=$(tmux list-panes ...)` sweep through the `SESSION_IDS` population loop, up to and including its closing `done < <(tmux list-sessions ...)`) so it only runs when live is on. Immediately before `PANE_DATA=$(tmux list-panes ...)` add:

```bash
if [ "$RESUME_ONLY" -eq 0 ]; then
```

and immediately after the `done < <(tmux list-sessions ... )` that populates `SESSION_IDS`, add:

```bash
fi
```

- [ ] **Step 7: Gather resume entries** — immediately after that closing `fi`, add:

```bash
# --- resume work list --------------------------------------------------------

RESUME_IDS=()
RESUME_CWDS=()
RESUME_PROJECT=()
RESUME_REASON=()

if [ "$RESUME" -eq 1 ]; then
    now=$(date +%s)
    live_ids=$(live_session_ids)
    troot=$(transcript_root)
    while IFS='|' read -r rid rcwd rts rreason; do
        [ -n "$rid" ] || continue
        resume_within_age "$rts" "$now" "$RESUME_MAX_AGE_DAYS" || { rm -f "$(resume_dir)/$rid.json" 2>/dev/null; continue; }
        resume_is_resumable "$rid" "$troot" || { rm -f "$(resume_dir)/$rid.json" 2>/dev/null; continue; }
        printf '%s\n' "$live_ids" | grep -qx "$rid" && continue
        proj=$(project_of_dir "$rcwd")
        if [ ${#PROJECT_GLOBS[@]} -gt 0 ] && ! matches_any "$proj" "${PROJECT_GLOBS[@]}"; then
            continue
        fi
        RESUME_IDS+=("$rid")
        RESUME_CWDS+=("$rcwd")
        RESUME_PROJECT+=("$proj")
        RESUME_REASON+=("$rreason")
    done < <(read_resume_records)
fi
```

- [ ] **Step 8: Fix the empty-work-list guard** — replace the existing block:

```bash
if [ ${#SESSION_IDS[@]} -eq 0 ]; then
    echo "Nothing to attach (no sessions matched)."
    exit 0
fi
```

with:

```bash
if [ ${#SESSION_IDS[@]} -eq 0 ] && [ ${#RESUME_IDS[@]} -eq 0 ]; then
    echo "Nothing to attach or resume (no sessions matched)."
    exit 0
fi
```

- [ ] **Step 9: Add a resume section to the dry-run output** — in the `if [ "$DRY_RUN" -eq 1 ]; then` block, after the loop that prints attach commands and before its `exit 0`, add:

```bash
    for i in "${!RESUME_IDS[@]}"; do
        printf '  %s\n' \
            "$(resume_attach_command "${RESUME_CWDS[i]}" "${RESUME_IDS[i]}")   # resume ${RESUME_IDS[i]} @ ${RESUME_PROJECT[i]}"
    done
```

- [ ] **Step 10: Run tests to verify they pass**

Run: `bash session-manager/tests/test-tmux-cc-attach.sh`
Expected: `ALL PASS`.

- [ ] **Step 11: Commit**

```bash
git add session-manager/scripts/tmux-cc-attach session-manager/tests/test-tmux-cc-attach.sh
git commit -m "feat(session-manager): gather resumable ended sessions in tmux-cc-attach dry-run"
```

---

### Task 4: Launch resume entries in the live report + attach loop; install symlink

**Files:**
- Modify: `session-manager/scripts/tmux-cc-attach`

**Interfaces:**
- Consumes: `RESUME_IDS/RESUME_CWDS/RESUME_PROJECT/RESUME_REASON`, `resume_attach_command`, existing `create_group_window` / `add_gateway_tab`.
- Produces: resume entries printed in the human report and launched (grouped by project) alongside live attaches; `~/.local/bin/tmux-cc-attach` symlinked to the repo copy.

- [ ] **Step 1: Show resume entries in the human report** — in the report section that loops `PROJECT_GROUPS`, after the inner loop that prints live sessions for a group, add a second inner loop printing resume entries whose `RESUME_PROJECT[i]` equals the group. Because resume projects may introduce groups with no live session, first extend group discovery: where `PROJECT_GROUPS` is built from `SESSION_GROUP`, also fold in resume projects. Replace the `PROJECT_GROUPS` build loop:

```bash
PROJECT_GROUPS=()
for group in "${SESSION_GROUP[@]}"; do
    contains_exact "$group" ${PROJECT_GROUPS[@]+"${PROJECT_GROUPS[@]}"} \
        || PROJECT_GROUPS+=("$group")
done
```

with:

```bash
PROJECT_GROUPS=()
for group in ${SESSION_GROUP[@]+"${SESSION_GROUP[@]}"}; do
    contains_exact "$group" ${PROJECT_GROUPS[@]+"${PROJECT_GROUPS[@]}"} \
        || PROJECT_GROUPS+=("$group")
done
for group in ${RESUME_PROJECT[@]+"${RESUME_PROJECT[@]}"}; do
    contains_exact "$group" ${PROJECT_GROUPS[@]+"${PROJECT_GROUPS[@]}"} \
        || PROJECT_GROUPS+=("$group")
done
```

Then in the per-group report loop, after the live-session inner loop, add:

```bash
    for i in ${RESUME_IDS[@]+"${!RESUME_IDS[@]}"}; do
        [ "${RESUME_PROJECT[i]}" = "$group" ] || continue
        printf '      %-12s (%s)  [resume: %s]\n' \
            "${RESUME_IDS[i]:0:8}" "${RESUME_IDS[i]}" "${RESUME_REASON[i]:-ended}"
    done
```

- [ ] **Step 2: Launch resume entries in the attach loop** — in the final attach loop over `PROJECT_GROUPS`, after the inner loop that attaches live sessions for the group, add a resume inner loop that reuses the same window/tab creation:

```bash
        for i in ${RESUME_IDS[@]+"${!RESUME_IDS[@]}"}; do
            [ "${RESUME_PROJECT[i]}" = "$group" ] || continue
            name="${RESUME_IDS[i]:0:8}"
            cmd=$(resume_attach_command "${RESUME_CWDS[i]}" "${RESUME_IDS[i]}")
            if [ -z "$window_id" ]; then
                window_id=$(create_group_window "$cmd")
                if [ -z "$window_id" ]; then
                    warn "failed to create iTerm window for group $group"
                    FAILED+=("$name"); failed_count=$((failed_count + 1)); continue
                fi
                printf '  %-12s -> new window %s   %s [resume]\n' "$name" "$window_id" "$group"
            else
                if [ "$(add_gateway_tab "$window_id" "$cmd")" != "ok" ]; then
                    warn "failed to open resume tab for $name"
                    FAILED+=("$name"); failed_count=$((failed_count + 1)); continue
                fi
                printf '  %-12s -> tab in window %s [resume]\n' "$name" "$window_id"
            fi
            attached_count=$((attached_count + 1))
            sleep "$DELAY"
        done
```

- [ ] **Step 3: Update the summary banner** — replace the report banner line beginning `printf 'Attaching %d session(s)...` so it accounts for resume entries. Change the leading count computation to add `${#RESUME_IDS[@]}` and adjust the wording:

```bash
printf 'Attaching/resuming %d session(s) into %d iTerm window(s), ~%d tabs total:\n\n' \
    "$(( ${#SESSION_IDS[@]} + ${#RESUME_IDS[@]} ))" "${#PROJECT_GROUPS[@]}" "$total_tabs"
```

and in the `total_tabs` computation loop that precedes it, after the `SESSION_IDS` loop add:

```bash
total_tabs=$(( total_tabs + ${#RESUME_IDS[@]} ))
```

- [ ] **Step 4: Verify dry-run still passes with both paths**

Run: `bash session-manager/tests/test-tmux-cc-attach.sh`
Expected: `ALL PASS`.

- [ ] **Step 5: Manual smoke test (documented, not automated)**

Run: `session-manager/scripts/tmux-cc-attach -n` on a machine with tmux + iTerm and at least one resume record. Confirm live sessions and resume entries both appear grouped by project, and resume lines show `tmux -CC new-session -c ... 'claude -r ...'`. (Real attach/resume opens iTerm windows — verify one resume actually reloads the session.)

- [ ] **Step 6: Install the symlink**

Run:
```bash
ln -sf "$(cd session-manager/scripts && pwd)/tmux-cc-attach" ~/.local/bin/tmux-cc-attach
ls -l ~/.local/bin/tmux-cc-attach
```

- [ ] **Step 7: Commit**

```bash
git add session-manager/scripts/tmux-cc-attach
git commit -m "feat(session-manager): resume ended sessions in tmux-cc-attach (on by default)"
```

---

### Task 5: Documentation + version bump

**Files:**
- Modify: `session-manager/CLAUDE.md`
- Modify: `session-manager/README.md`
- Modify: `session-manager/.claude-plugin/plugin.json` (via bump script)
- Modify: `.claude-plugin/marketplace.json` (via bump script / sync)

- [ ] **Step 1: Document the resume path in `session-manager/CLAUDE.md`** — add a subsection under the registry docs describing: the `resume/` store shape `{session_id, cwd, ts_start, ts_end, reason}`, that it is written by the SessionEnd hook and NOT touched by the locator sweep, and the `tmux-cc-attach` flags (`--no-resume`, `--resume-only`, `--since`, `RESUME_MAX_AGE_DAYS`). State that resume is on by default and launches `tmux -CC new-session -c '<cwd>' "claude -r '<id>'"`.

- [ ] **Step 2: Document `tmux-cc-attach` in `session-manager/README.md`** — add a short section: what the vendored `scripts/tmux-cc-attach` does, the symlink to `~/.local/bin`, and the resume-on-by-default behavior with its flags. Note the store fills only from when the extended hook shipped.

- [ ] **Step 3: Run the full plugin test suite**

Run:
```bash
bash session-manager/tests/test-record-session.sh
bash session-manager/tests/test-tmux-cc-attach.sh
python3 session-manager/tests/test_locator.py -v
```
Expected: all pass (locator unaffected — resume lives in a separate store).

- [ ] **Step 4: Bump the plugin version + clear cache**

Run: `./scripts/bump-plugin.sh session-manager minor`

- [ ] **Step 5: Commit**

```bash
git add session-manager/CLAUDE.md session-manager/README.md session-manager/.claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "docs(session-manager): document resume-ended-sessions; bump version"
```

---

## Self-Review Notes

- **Spec coverage:** SessionEnd resume record (Task 1) ✓; separate store never swept (Task 1 writes `resume/`, locator untouched) ✓; read-time hygiene — age/transcript/live-dedup (Task 3 Step 7) ✓; vendored script + lib guard (Task 2) ✓; flags incl. default-on + `--no-resume`/`--resume-only`/`--since` (Task 3) ✓; project grouping via `project_of_dir` (Task 3 Step 7) ✓; fresh `tmux -CC new-session` launch (Tasks 2–4) ✓; tests for hook + helpers + dry-run (Tasks 1–4) ✓; docs + version bump (Task 5) ✓; symlink migration (Task 4 Step 6) ✓.
- **Placeholder scan:** every code step carries concrete code; no TBD/TODO. The only unverified value is the SessionEnd `reason` string set, recorded verbatim and never branched on — consistent with the spec's non-goal.
- **Type/name consistency:** helper names (`resume_dir`, `transcript_root`, `resume_within_age`, `resume_is_resumable`, `resume_attach_command`, `read_resume_records`, `live_session_ids`) and array names (`RESUME_IDS/RESUME_CWDS/RESUME_PROJECT/RESUME_REASON`) are used identically across Tasks 2–5.
