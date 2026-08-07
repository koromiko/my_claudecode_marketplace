# Resume filter + per-project toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exclude autonomous (teammate/agent) sessions from `tmux-cc-attach`'s resume list, and replace the all-or-nothing `Proceed? [y/N]` with a per-project-group toggle.

**Architecture:** Two independent, additive changes to the single vendored script `session-manager/scripts/tmux-cc-attach`. Both slot into existing structures: the autonomous filter is one new pure helper plus one line in the read-time hygiene loop; the toggle is one new pure parser plus a replacement of the confirmation prompt and a one-line gate on the attach loop. All new helpers live above the `TMUX_CC_LIB_ONLY` guard so they are unit-testable by sourcing.

**Tech Stack:** Bash (stock macOS `/bin/bash` 3.2.57 compatible), `jq`, `grep`, existing test harness `tests/test-tmux-cc-attach.sh`.

## Global Constraints

- Target shell is stock macOS `/bin/bash` 3.2.57. Never bare-expand a possibly-empty array under `set -u`: use `${arr[@]+"${arr[@]}"}` for values, `"${!arr[@]}"` for indices, `${#arr[@]}` for count.
- Autonomous detection marker: a transcript record `"type":"agent-setting"`. Match literally.
- Autonomous entries are **skipped from the list, never unlinked** — age-prune handles file cleanup.
- The autonomous filter is **unconditional** (no flag) and applies **only to resume-store entries**, never to live tmux sessions.
- `-y`/`--yes` must preserve the non-interactive contract (skip the prompt, take all groups). `-n`/`--dry-run` must not prompt.
- Read-time only: no change to `hooks/remove-session.sh`.
- Finish by bumping the plugin `2.9.0` → `2.10.0` (minor) via `./scripts/bump-plugin.sh session-manager minor`.

---

### Task 1: Autonomous-session filter (read-time)

**Files:**
- Modify: `session-manager/scripts/tmux-cc-attach` (add helper after `resume_is_resumable`, ~line 214; add one filter line in the resume-build loop, ~line 369)
- Test: `session-manager/tests/test-tmux-cc-attach.sh`

**Interfaces:**
- Consumes: `transcript_root` (existing), the resume-build loop's `$rid` / `$troot` locals (existing).
- Produces: `resume_is_autonomous <id> <root>` → exit 0 if the session's transcript is an autonomous teammate/agent session, else 1.

- [ ] **Step 1: Write the failing unit tests**

Add after the existing `resume_is_resumable` checks (after line 24) in `tests/test-tmux-cc-attach.sh`:

```bash
# resume_is_autonomous: a transcript carrying an agent-setting record is
# autonomous; a plain human transcript is not; a missing transcript is not.
mkdir -p "$CLAUDE_PROJECTS_DIR/-tmp-auto"
printf '{"type":"agent-setting"}\n{"type":"user"}\n' > "$CLAUDE_PROJECTS_DIR/-tmp-auto/autosid.jsonl"
printf '{"type":"user"}\n{"type":"assistant"}\n'     > "$CLAUDE_PROJECTS_DIR/-tmp-auto/humansid.jsonl"
check "autonomous true"    "resume_is_autonomous autosid \"\$(transcript_root)\""
check "autonomous false"   "! resume_is_autonomous humansid \"\$(transcript_root)\""
check "autonomous missing" "! resume_is_autonomous nope \"\$(transcript_root)\""
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `bash session-manager/tests/test-tmux-cc-attach.sh`
Expected: FAIL — `resume_is_autonomous: command not found` on the three new checks.

- [ ] **Step 3: Add the helper**

Insert immediately after the `resume_is_resumable` function (after its closing `}` at ~line 214) in `scripts/tmux-cc-attach`:

```bash
# 0 if the session's transcript marks it as an autonomous teammate/agent
# session (carries a "type":"agent-setting" record); human sessions have none.
resume_is_autonomous() {
    local id="$1" root="$2" f
    for f in "$root"/*/"$id".jsonl; do
        [ -e "$f" ] || continue
        grep -q '"type":"agent-setting"' "$f" && return 0
    done
    return 1
}
```

- [ ] **Step 4: Run the unit tests to verify they pass**

Run: `bash session-manager/tests/test-tmux-cc-attach.sh`
Expected: the three `autonomous …` checks PASS.

- [ ] **Step 5: Write the failing integration test**

In the `--resume-only -n` fixture block, add an autonomous fixture **before** the `out=$(…)` line (before line 47). Insert after the `ghostsid` record block (after line 46):

```bash
# An autonomous (teammate/agent) session must be excluded from the list.
mkdir -p "$CLAUDE_PROJECTS_DIR/-tmp-auto2"
printf '{"type":"agent-setting"}\n' > "$CLAUDE_PROJECTS_DIR/-tmp-auto2/autosid2.jsonl"
printf '{"session_id":"autosid2","cwd":"/tmp/auto2","ts_start":1,"ts_end":%s,"reason":"other"}\n' "$NOW2" \
    > "$(resume_dir)/autosid2.json"
```

Then add this assertion after the existing `dry-run drops no-transcript` check (after line 50):

```bash
check "dry-run drops autonomous" "! printf '%s' \"\$out\" | grep -q autosid2"
```

- [ ] **Step 6: Run to verify the integration test fails**

Run: `bash session-manager/tests/test-tmux-cc-attach.sh`
Expected: FAIL — `dry-run drops autonomous` fails because `autosid2` is still listed (filter not wired into the loop yet).

- [ ] **Step 7: Wire the filter into the resume-build loop**

In `scripts/tmux-cc-attach`, in the resume-build loop, add the autonomous check between the transcript-exists check (line 369) and the live-dedup check (line 370). Insert this line immediately after the `resume_is_resumable … continue; }` line:

```bash
        resume_is_autonomous "$rid" "$troot" && continue
```

The resulting order is: `resume_within_age` → `resume_is_resumable` → `resume_is_autonomous` → live-dedup → project-glob. No `rm -f`: autonomous entries are skipped, not pruned.

- [ ] **Step 8: Run the full suite to verify it passes**

Run: `bash session-manager/tests/test-tmux-cc-attach.sh`
Expected: `ALL PASS`.

- [ ] **Step 9: Verify bash 3.2 compatibility**

Run: `/bin/bash session-manager/tests/test-tmux-cc-attach.sh; echo rc=$?`
Expected: `ALL PASS`, `rc=0`.

- [ ] **Step 10: Commit**

```bash
git add session-manager/scripts/tmux-cc-attach session-manager/tests/test-tmux-cc-attach.sh
git commit -m "feat(session-manager): filter autonomous sessions from resume list

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Per-project-group toggle

**Files:**
- Modify: `session-manager/scripts/tmux-cc-attach` (add `parse_group_selection` above the lib-only guard; number the report group headers; replace the `Proceed? [y/N]` block; gate the attach loop)
- Test: `session-manager/tests/test-tmux-cc-attach.sh`

**Interfaces:**
- Consumes: `PROJECT_GROUPS` array (existing), `contains_exact` (existing), `DRY_RUN` / `ASSUME_YES` (existing).
- Produces: `parse_group_selection <reply> <count>` → prints selected 1-based indices (one per line); empty reply prints all `1..count`; returns 2 for none (`n`/`none`); returns 1 on any bad token. `SELECTED_GROUPS` array consumed by the attach loop.

- [ ] **Step 1: Write the failing unit tests**

Add before the final pass/fail summary (before line 64) in `tests/test-tmux-cc-attach.sh`:

```bash
# parse_group_selection: empty=all, subset, comma form, none(rc2), bad(rc1)
check "sel empty = all" "[ \"\$(parse_group_selection '' 3 | tr '\n' ' ')\" = '1 2 3 ' ]"
check "sel subset"      "[ \"\$(parse_group_selection '1 3' 3 | tr '\n' ' ')\" = '1 3 ' ]"
check "sel comma"       "[ \"\$(parse_group_selection '2,3' 3 | tr '\n' ' ')\" = '2 3 ' ]"
parse_group_selection 'n' 3 >/dev/null; check "sel none rc2" "[ $? -eq 2 ]"
parse_group_selection '5' 3 >/dev/null; check "sel oob rc1"  "[ $? -eq 1 ]"
parse_group_selection 'x' 3 >/dev/null; check "sel nonnum rc1" "[ $? -eq 1 ]"
```

- [ ] **Step 2: Run to verify they fail**

Run: `bash session-manager/tests/test-tmux-cc-attach.sh`
Expected: FAIL — `parse_group_selection: command not found`.

- [ ] **Step 3: Add the parser**

Insert in `scripts/tmux-cc-attach` just before the `TMUX_CC_LIB_ONLY` guard (before line 284, after `add_gateway_tab`):

```bash
# --- group selection ---------------------------------------------------------

# Parse a group-selection reply against a group count.
#   empty reply         -> print 1..count (all), return 0
#   n / none            -> return 2 (abort)
#   space/comma numbers -> print those indices, return 0
#   any bad token / oob -> return 1 (caller re-prompts)
parse_group_selection() {
    local reply="$1" count="$2" tok i out=()
    reply="${reply//,/ }"
    reply="$(printf '%s' "$reply" | tr -s ' ')"
    case "$reply" in
        ''|' ') for ((i = 1; i <= count; i++)); do printf '%s\n' "$i"; done; return 0 ;;
        n|N|none|NONE) return 2 ;;
    esac
    for tok in $reply; do
        case "$tok" in ''|*[!0-9]*) return 1 ;; esac
        { [ "$tok" -ge 1 ] && [ "$tok" -le "$count" ]; } || return 1
        out+=("$tok")
    done
    printf '%s\n' ${out[@]+"${out[@]}"}
    return 0
}
```

- [ ] **Step 4: Run to verify the parser tests pass**

Run: `bash session-manager/tests/test-tmux-cc-attach.sh`
Expected: the six `sel …` checks PASS.

- [ ] **Step 5: Number the report group headers**

In `scripts/tmux-cc-attach`, replace the report group loop header (lines 419-420):

```bash
for group in "${PROJECT_GROUPS[@]}"; do
    printf '  %s\n' "$group"
```

with a numbered header:

```bash
gi=0
for group in "${PROJECT_GROUPS[@]}"; do
    gi=$((gi + 1))
    printf '  [%d] %s\n' "$gi" "$group"
```

- [ ] **Step 6: Replace the confirmation prompt with the toggle**

Replace the entire `Proceed? [y/N]` block (lines 453-460):

```bash
if [ "$ASSUME_YES" -eq 0 ]; then
    printf 'Proceed? [y/N] '
    read -r reply
    case "$reply" in
        y|Y|yes|YES) ;;
        *) echo "Aborted."; exit 0 ;;
    esac
fi
```

with the per-group selection:

```bash
SELECTED_GROUPS=()
if [ "$ASSUME_YES" -eq 1 ]; then
    SELECTED_GROUPS=(${PROJECT_GROUPS[@]+"${PROJECT_GROUPS[@]}"})
else
    while :; do
        printf "Select projects [Enter=all, e.g. '1 3', 'n'=none]: "
        read -r reply || { echo "Aborted."; exit 0; }
        sel=$(parse_group_selection "$reply" "${#PROJECT_GROUPS[@]}"); rc=$?
        [ "$rc" -eq 2 ] && { echo "Aborted."; exit 0; }
        if [ "$rc" -eq 0 ]; then
            for idx in $sel; do
                SELECTED_GROUPS+=("${PROJECT_GROUPS[idx-1]}")
            done
            break
        fi
        printf '  Invalid selection; enter numbers 1-%d, Enter for all, or n.\n' "${#PROJECT_GROUPS[@]}"
    done
fi
```

- [ ] **Step 7: Gate the attach loop on the selection**

In `scripts/tmux-cc-attach`, at the top of the attach loop (line 473):

```bash
for group in "${PROJECT_GROUPS[@]}"; do
    window_id=""
```

add the gate as the first statement inside the loop:

```bash
for group in "${PROJECT_GROUPS[@]}"; do
    contains_exact "$group" ${SELECTED_GROUPS[@]+"${SELECTED_GROUPS[@]}"} || continue
    window_id=""
```

- [ ] **Step 8: Add the dry-run-no-prompt assertion**

The dry-run path (line 436) exits before the prompt. Add, right after the existing `dry-run drops autonomous` check (Task 1, Step 5), a guard that `-n` never emits the prompt:

```bash
check "dry-run has no selection prompt" "! printf '%s' \"\$out\" | grep -q 'Select projects'"
```

- [ ] **Step 9: Run the full suite**

Run: `bash session-manager/tests/test-tmux-cc-attach.sh`
Expected: `ALL PASS`.

- [ ] **Step 10: Verify bash 3.2 compatibility (headline path + dry-run)**

Run: `/bin/bash session-manager/tests/test-tmux-cc-attach.sh; echo rc=$?`
Expected: `ALL PASS`, `rc=0`.

- [ ] **Step 11: Manual interactive smoke (documented, not automated)**

Live iTerm attach cannot be exercised headlessly (osascript window creation). Record in the commit body that the `-y` and interactive-select attach paths need a manual smoke test on a live machine. No code change.

- [ ] **Step 12: Commit**

```bash
git add session-manager/scripts/tmux-cc-attach session-manager/tests/test-tmux-cc-attach.sh
git commit -m "feat(session-manager): per-project-group toggle for attach/resume

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Docs + version bump

**Files:**
- Modify: `session-manager/CLAUDE.md` (resume-hygiene paragraph + toggle note under the `tmux-cc-attach` section)
- Modify: `session-manager/README.md` (if it documents `tmux-cc-attach` flags/behavior — check first)
- Modify: `session-manager/.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` (via bump script)

**Interfaces:**
- Consumes: the behavior implemented in Tasks 1-2.
- Produces: docs describing the autonomous-skip hygiene step and the toggle; plugin at version `2.10.0`.

- [ ] **Step 1: Update `session-manager/CLAUDE.md`**

In the `tmux-cc-attach` section, extend the "Read-time hygiene" paragraph so it lists the autonomous-skip step, and add a short toggle description. Replace the sentence beginning "Read-time hygiene runs on every listing:" with:

```markdown
Read-time hygiene runs on every listing: entries past the age window,
entries whose transcript (`~/.claude/projects/*/<session_id>.jsonl`) is gone,
entries whose transcript is an autonomous teammate/agent session (carries a
`"type":"agent-setting"` record), and entries whose `session_id` is currently
live (per `locator.py list`) are omitted from the list. Autonomous entries are
skipped, not deleted; they age out via the window prune. Under `-n` (dry-run)
the omission still happens, but the stale/no-transcript record files are not
deleted.

Selection is per project group. After the report (each group numbered
`[1]`, `[2]`, …), the prompt `Select projects [Enter=all, e.g. '1 3',
'n'=none]` toggles whole groups: a deselected group skips both its live-attach
and resume entries. `-y` skips the prompt and takes all groups; `-n` previews
all groups without prompting.
```

- [ ] **Step 2: Check and update `session-manager/README.md`**

Run: `grep -n "resume\|Proceed\|--resume\|tmux-cc-attach" session-manager/README.md`
If the README documents the resume hygiene list or the confirmation prompt, mirror the two changes from Step 1 (add autonomous-skip to the hygiene list; describe the per-group toggle). If it does not mention them, no change.

- [ ] **Step 3: Bump the plugin version + clear cache**

Run: `./scripts/bump-plugin.sh session-manager minor`
Expected: `session-manager/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` both move `2.9.0` → `2.10.0`; cache cleared.

- [ ] **Step 4: Verify the version bump**

Run: `jq -r .version session-manager/.claude-plugin/plugin.json; jq -r '.plugins[] | select(.name=="session-manager") | .version' .claude-plugin/marketplace.json`
Expected: both print `2.10.0`.

- [ ] **Step 5: Run the full session-manager test suite**

Run:
```bash
bash session-manager/tests/test-tmux-cc-attach.sh && \
bash session-manager/tests/test-record-session.sh && \
python3 session-manager/tests/test_locator.py -v 2>&1 | tail -1
```
Expected: `ALL PASS` for both bash suites; `OK` for the locator suite.

- [ ] **Step 6: Commit**

```bash
git add session-manager/CLAUDE.md session-manager/README.md session-manager/.claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "docs(session-manager): resume autonomous-skip + toggle; bump 2.10.0

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Autonomous detection (`agent-setting`) → Task 1 Step 3 (helper), Step 1/5 (tests).
- Read-time filter order (after transcript-exists, before live-dedup; skip not unlink) → Task 1 Step 7.
- Filter unconditional, resume-only, no hook change → Global Constraints + Task 1 (no hook file touched).
- Numbered report + toggle prompt (Enter=all, `n`=none, numbers) → Task 2 Steps 5-6.
- Whole-group unit, attach-loop gate → Task 2 Step 7.
- `-y` all / `-n` no-prompt → Task 2 Step 6 (`ASSUME_YES` branch), Step 8 (dry-run assertion).
- `parse_group_selection` pure/testable → Task 2 Steps 1,3.
- Tests (helper unit, parser unit, integration excludes autonomous) → Task 1 Steps 1,5; Task 2 Step 1.
- Docs + 2.10.0 bump → Task 3.

**Placeholder scan:** none — every code step has literal content.

**Type consistency:** `resume_is_autonomous <id> <root>` used identically in helper and loop; `parse_group_selection <reply> <count>` and `SELECTED_GROUPS` used consistently across Steps 3/6/7; `contains_exact` signature matches existing usage.
