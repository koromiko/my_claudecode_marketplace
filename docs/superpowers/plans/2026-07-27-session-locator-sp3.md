# Session Locator SP3 (hook-backed registry) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the locator resolve an idle session that has no live tagged child process, by having a hook record each session's `{session_id, claude_pid, cwd, ts}` and the locator fall back to that registry (liveness-validated) when the pull scan places nothing.

**Architecture:** A `SessionStart` hook writes a per-session JSON file under `~/.claude/session-manager/sessions/`; a `SessionEnd` hook deletes it. `locator.py` gains a pure `merge_registry_sessions` (adds records for registry entries the pull scan missed, placed claude-anchored on `claude_pid`) and a pure `dead_registry_sids` (which stale files to sweep), both wired into the one impure `_scan_and_build`.

**Tech Stack:** Python 3 stdlib (`unittest`), Bash + `jq`.

## Global Constraints

- Python 3.8+ stdlib only; no external Python deps.
- Hook scripts must ALWAYS `exit 0` — a hook must never block or fail the TUI. If `jq` is absent or any field is missing, exit 0 doing nothing.
- Record schema stays EXACTLY 10 keys: `session_id, role, parent_session_id, pane, host, tty, cwd, leader_pid, pane_live, tmux`.
- Registry is a FALLBACK only: `merge_registry_sessions` never overrides a live-discovered session (dedup by `session_id`; live wins).
- Registry storage: per-session files at `${CLAUDE_SM_HOME:-$HOME/.claude/session-manager}/sessions/<session_id>.json`; writes are atomic (temp file + `mv` in the same dir). The locator reads the same dir (honor `CLAUDE_SM_HOME`).
- Do NOT change `session_placement`, `parse_processes`, `build_sessions`, or `resolve_collision` semantics. SP3 only ADDS functions + wiring.
- Hooks are auto-discovered from `session-manager/hooks/hooks.json`; do NOT add a `hooks` key to `plugin.json`. Mirror `default-tools/hooks/hooks.json` shape.

---

### Task 1: locator registry discovery (pure merge + sweep + wiring)

**Files:**
- Modify: `session-manager/scripts/locator.py` (add `SESSIONS_DIR` const near other module constants ~line 36; add `merge_registry_sessions` + `dead_registry_sids` after `build_sessions` ~line 360; add `_read_registry_entries` + `_sweep_dead_registry` and wire into `_scan_and_build` ~line 525)
- Test: `session-manager/tests/test_locator.py` (add `TestMergeRegistrySessions` and `TestDeadRegistrySids` after `TestClaudeAnchoredPlacement`)

**Interfaces:**
- Consumes: existing `session_placement(members, rep, proc_table, tmux_index, tty_pane_idx)`, `tty_to_pane_index(tmux_index)`, `RE_CLAUDE`.
- Produces:
  - `merge_registry_sessions(sessions, entries, proc_table, tmux_index, tty_pane_idx) -> list` — `sessions` augmented with a 10-key interactive record for each entry whose `session_id` is not already present and whose `claude_pid` is a live `claude` in `proc_table`; result sorted like `build_sessions`.
  - `dead_registry_sids(entries, proc_table) -> set[str]` — `session_id`s whose `claude_pid` is absent from `proc_table` or not a `claude`.
  - `SESSIONS_DIR` — module constant, the registry dir path.

- [ ] **Step 1: Write the failing tests**

Add to `session-manager/tests/test_locator.py` after the `TestClaudeAnchoredPlacement` class:

```python
class TestMergeRegistrySessions(unittest.TestCase):
    TMUX_INDEX = {("default", "%126"): {
        "tty": "ttys008", "pane_pid": 79313, "tmux_session": "11",
        "tmux_window": "1", "active": True}}
    TABLE = {40116: {"ppid": 14528, "tty": "ttys008", "command": "claude --resume x"},
             99: {"ppid": 1, "tty": "ttys008", "command": "-zsh"}}

    def _idx(self):
        return locator.tty_to_pane_index(self.TMUX_INDEX)

    def test_live_pid_synthesizes_placed_record(self):
        entries = [{"session_id": UUID_C3, "claude_pid": 40116, "cwd": "/x", "ts": 1}]
        out = locator.merge_registry_sessions([], entries, self.TABLE,
                                              self.TMUX_INDEX, self._idx())
        self.assertEqual(len(out), 1)
        rec = out[0]
        self.assertEqual(rec["session_id"], UUID_C3)
        self.assertEqual(rec["role"], "interactive")
        self.assertEqual(rec["pane"], "tmux:default:%126")
        self.assertEqual(rec["leader_pid"], 40116)
        self.assertEqual(rec["cwd"], "/x")
        self.assertTrue(rec["pane_live"])

    def test_dead_pid_skipped(self):
        entries = [{"session_id": UUID_C3, "claude_pid": 55555, "cwd": "/x", "ts": 1}]
        out = locator.merge_registry_sessions([], entries, self.TABLE,
                                              self.TMUX_INDEX, self._idx())
        self.assertEqual(out, [])

    def test_non_claude_pid_skipped(self):
        entries = [{"session_id": UUID_C3, "claude_pid": 99, "cwd": "/x", "ts": 1}]
        out = locator.merge_registry_sessions([], entries, self.TABLE,
                                              self.TMUX_INDEX, self._idx())
        self.assertEqual(out, [])

    def test_live_discovered_session_wins(self):
        existing = [{"session_id": UUID_C3, "role": "interactive", "pane": "tmux:default:%126",
                     "leader_pid": 40116, "parent_session_id": None, "host": "tmux",
                     "tty": "ttys008", "cwd": "/live", "pane_live": True, "tmux": None}]
        entries = [{"session_id": UUID_C3, "claude_pid": 40116, "cwd": "/stale", "ts": 1}]
        out = locator.merge_registry_sessions(existing, entries, self.TABLE,
                                              self.TMUX_INDEX, self._idx())
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["cwd"], "/live")  # live record untouched

    def test_empty_inputs(self):
        self.assertEqual(locator.merge_registry_sessions([], [], {}, {}, {}), [])

    def test_synthesized_record_has_exactly_schema_keys(self):
        entries = [{"session_id": UUID_C3, "claude_pid": 40116, "cwd": "/x", "ts": 1}]
        out = locator.merge_registry_sessions([], entries, self.TABLE,
                                              self.TMUX_INDEX, self._idx())
        self.assertEqual(set(out[0].keys()), {
            "session_id", "role", "parent_session_id", "pane", "host", "tty",
            "cwd", "leader_pid", "pane_live", "tmux"})


class TestDeadRegistrySids(unittest.TestCase):
    TABLE = {40116: {"ppid": 1, "tty": "ttys008", "command": "claude --resume x"},
             99: {"ppid": 1, "tty": "ttys008", "command": "-zsh"}}

    def test_flags_dead_and_non_claude_only(self):
        entries = [
            {"session_id": UUID_C3, "claude_pid": 40116},   # live claude -> keep
            {"session_id": UUID_9C, "claude_pid": 55555},   # dead pid -> dead
            {"session_id": UUID_OWNER, "claude_pid": 99},    # non-claude -> dead
            {"session_id": UUID_STALE, "claude_pid": None},  # no pid -> dead
        ]
        self.assertEqual(locator.dead_registry_sids(entries, self.TABLE),
                         {UUID_9C, UUID_OWNER, UUID_STALE})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd session-manager && python3 -m unittest tests.test_locator.TestMergeRegistrySessions tests.test_locator.TestDeadRegistrySids -v`
Expected: FAIL with `AttributeError: module 'locator' has no attribute 'merge_registry_sessions'`.

- [ ] **Step 3: Add the module constant**

In `session-manager/scripts/locator.py`, after the `RE_CLAUDE = ...` line (~line 36), add:

```python
SESSIONS_DIR = os.path.join(
    os.environ.get("CLAUDE_SM_HOME", os.path.expanduser("~/.claude/session-manager")),
    "sessions",
)
```

- [ ] **Step 4: Add the two pure functions**

In `session-manager/scripts/locator.py`, immediately after `build_sessions` (after its `return sessions` / before `_legacy_placement`, ~line 358), add:

```python
def merge_registry_sessions(sessions, entries, proc_table, tmux_index, tty_pane_idx):
    """Add records for registry entries the pull scan didn't discover (idle sessions
    with no live tagged child). Placed claude-anchored on claude_pid; a registry entry
    is used only when its session_id is not already present (live discovery wins) and
    its claude_pid is a live claude TUI. Pure; result sorted like build_sessions."""
    known = {s["session_id"] for s in sessions}
    out = list(sessions)
    for e in entries:
        sid = e.get("session_id")
        cpid = e.get("claude_pid")
        if not sid or sid in known:
            continue
        if not cpid or cpid not in proc_table:
            continue
        if not RE_CLAUDE.search(proc_table[cpid]["command"]):
            continue
        member = {"pid": cpid, "claude_pid": cpid, "tty": None,
                  "iterm_session_id": None, "term_session_id": None}
        place = session_placement([member], member, proc_table, tmux_index, tty_pane_idx)
        out.append({
            "session_id": sid,
            "role": "interactive",
            "parent_session_id": None,
            "pane": place["pane"],
            "host": place["host"],
            "tty": place["tty"],
            "cwd": e.get("cwd"),
            "leader_pid": place["leader_pid"],
            "pane_live": place["pane_live"],
            "tmux": place["tmux"],
        })
        known.add(sid)
    out.sort(key=lambda s: (s["pane"] or "~", s["session_id"]))
    return out


def dead_registry_sids(entries, proc_table):
    """session_ids whose recorded claude_pid is no longer a live claude TUI — safe to
    delete from the registry. Pure."""
    dead = set()
    for e in entries:
        sid = e.get("session_id")
        cpid = e.get("claude_pid")
        if not sid:
            continue
        if not cpid or cpid not in proc_table or not RE_CLAUDE.search(proc_table[cpid]["command"]):
            dead.add(sid)
    return dead
```

- [ ] **Step 5: Run the pure-function tests to verify they pass**

Run: `cd session-manager && python3 -m unittest tests.test_locator.TestMergeRegistrySessions tests.test_locator.TestDeadRegistrySids -v`
Expected: PASS (7 tests).

- [ ] **Step 6: Add the impure IO helpers and wire into `_scan_and_build`**

In `session-manager/scripts/locator.py`, add these helpers just above `_scan_and_build` (~line 525):

```python
def _read_registry_entries():
    """Load registry entries from the per-session files (impure). Skips malformed."""
    entries = []
    for path in glob.glob(os.path.join(SESSIONS_DIR, "*.json")):
        try:
            with open(path) as f:
                entries.append(json.load(f))
        except (OSError, ValueError):
            continue
    return entries


def _sweep_dead_registry(entries, proc_table):
    """Delete registry files whose claude_pid is dead (impure, best-effort)."""
    for sid in dead_registry_sids(entries, proc_table):
        try:
            os.remove(os.path.join(SESSIONS_DIR, f"{sid}.json"))
        except OSError:
            pass
```

Then change `_scan_and_build` so its tail reads (keep the existing `ps`/`tmux`/`build_sessions` lines above unchanged):

```python
    sessions = build_sessions(procs, ppid_map, tmux_index, proc_table=proc_table)
    entries = _read_registry_entries()
    tty_pane_idx = tty_to_pane_index(tmux_index)
    sessions = merge_registry_sessions(sessions, entries, proc_table, tmux_index, tty_pane_idx)
    _sweep_dead_registry(entries, proc_table)
    return sessions, procs
```

- [ ] **Step 7: Run the full locator suite**

Run: `cd session-manager && python3 -m unittest tests.test_locator -v`
Expected: PASS (all existing tests + 7 new). No regressions (registry dir is normally absent in the test env, so `_read_registry_entries` returns `[]` and merge is a no-op for existing tests).

- [ ] **Step 8: Commit**

```bash
git add session-manager/scripts/locator.py session-manager/tests/test_locator.py
git commit -m "feat(locator): hook-backed registry fallback for idle childless sessions (SP3)"
```

---

### Task 2: SessionStart / SessionEnd hooks

**Files:**
- Create: `session-manager/hooks/hooks.json`
- Create: `session-manager/hooks/record-session.sh`
- Create: `session-manager/hooks/remove-session.sh`
- Test: `session-manager/tests/test-record-session.sh`

**Interfaces:**
- Consumes: nothing from Task 1 (decoupled by the on-disk format).
- Produces: `${CLAUDE_SM_HOME:-$HOME/.claude/session-manager}/sessions/<session_id>.json` = `{"session_id","claude_pid","cwd","ts"}`, which Task 1's `_read_registry_entries` consumes.

- [ ] **Step 1: Write the failing test**

Create `session-manager/tests/test-record-session.sh`:

```bash
#!/bin/bash
# Tests for the SP3 SessionStart/SessionEnd hook scripts.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REC="$HERE/../hooks/record-session.sh"
RM="$HERE/../hooks/remove-session.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export CLAUDE_SM_HOME="$TMP"
fails=0
check() { if eval "$2"; then echo "ok - $1"; else echo "FAIL - $1"; fails=$((fails+1)); fi; }

SID="11111111-2222-3333-4444-555555555555"
F="$TMP/sessions/$SID.json"

# 1. record with CLAUDE_PID set writes the four fields
echo "{\"session_id\":\"$SID\",\"cwd\":\"/tmp/x\"}" | CLAUDE_PID=4242 bash "$REC"
check "record writes file" "[ -f '$F' ]"
check "has session_id" "grep -q '\"session_id\":\"$SID\"' '$F'"
check "has claude_pid" "grep -q '\"claude_pid\":4242' '$F'"
check "has cwd" "grep -q '\"cwd\":\"/tmp/x\"' '$F'"
check "has ts" "grep -q '\"ts\":[0-9]' '$F'"

# 2. re-record is idempotent (still one valid file, new pid)
echo "{\"session_id\":\"$SID\",\"cwd\":\"/tmp/x\"}" | CLAUDE_PID=4243 bash "$REC"
check "re-record updates pid" "grep -q '\"claude_pid\":4243' '$F'"

# 3. missing session_id -> no file, exit 0
echo '{"cwd":"/tmp/x"}' | CLAUDE_PID=4242 bash "$REC"; rc=$?
check "missing sid exits 0" "[ $rc -eq 0 ]"

# 4. remove deletes the file
echo "{\"session_id\":\"$SID\"}" | bash "$RM"
check "remove deletes file" "[ ! -f '$F' ]"

# 5. remove of nonexistent file still exits 0
echo "{\"session_id\":\"$SID\"}" | bash "$RM"; rc=$?
check "remove nonexistent exits 0" "[ $rc -eq 0 ]"

# 6. no CLAUDE_PID -> ppid-walk best-effort; must still exit 0 (may or may not write)
echo "{\"session_id\":\"$SID\",\"cwd\":\"/tmp/x\"}" | env -u CLAUDE_PID bash "$REC"; rc=$?
check "no CLAUDE_PID exits 0" "[ $rc -eq 0 ]"

[ "$fails" -eq 0 ] && { echo "ALL PASS"; exit 0; } || { echo "$fails FAILED"; exit 1; }
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `bash session-manager/tests/test-record-session.sh`
Expected: FAIL — the hook scripts don't exist yet (`record-session.sh: No such file`).

- [ ] **Step 3: Create `record-session.sh`**

Create `session-manager/hooks/record-session.sh`:

```bash
#!/bin/bash
# SessionStart hook (SP3): record {session_id, claude_pid, cwd, ts} so the locator can
# resolve an idle session that has no live tagged child process. Never blocks the TUI.
set -u
input=$(cat)
command -v jq >/dev/null 2>&1 || exit 0

session_id=$(printf '%s' "$input" | jq -r '.session_id // ""')
cwd=$(printf '%s' "$input" | jq -r '.cwd // ""')
[ -n "$session_id" ] || exit 0

# TUI pid: prefer CLAUDE_PID; else walk the ppid chain to the claude process.
claude_pid="${CLAUDE_PID:-}"
if [ -z "$claude_pid" ]; then
    pid="${PPID:-1}"
    i=0
    while [ "$i" -lt 20 ]; do
        case "$pid" in ''|*[!0-9]*) break ;; esac
        [ "$pid" -gt 1 ] || break
        comm=$(ps -o comm= -p "$pid" 2>/dev/null)
        case "$comm" in *claude*) claude_pid="$pid"; break ;; esac
        pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
        i=$((i + 1))
    done
fi
case "$claude_pid" in ''|*[!0-9]*) exit 0 ;; esac

dir="${CLAUDE_SM_HOME:-$HOME/.claude/session-manager}/sessions"
mkdir -p "$dir" 2>/dev/null || exit 0
ts=$(date +%s)
cwd_json=$(printf '%s' "$cwd" | jq -R .)
tmp=$(mktemp "$dir/.tmp.XXXXXX" 2>/dev/null) || exit 0
printf '{"session_id":"%s","claude_pid":%s,"cwd":%s,"ts":%s}\n' \
    "$session_id" "$claude_pid" "$cwd_json" "$ts" > "$tmp"
mv -f "$tmp" "$dir/$session_id.json" 2>/dev/null || rm -f "$tmp"
exit 0
```

Make it executable: `chmod +x session-manager/hooks/record-session.sh`

- [ ] **Step 4: Create `remove-session.sh`**

Create `session-manager/hooks/remove-session.sh`:

```bash
#!/bin/bash
# SessionEnd hook (SP3): delete this session's registry file. Never blocks the TUI.
set -u
input=$(cat)
command -v jq >/dev/null 2>&1 || exit 0
session_id=$(printf '%s' "$input" | jq -r '.session_id // ""')
[ -n "$session_id" ] || exit 0
dir="${CLAUDE_SM_HOME:-$HOME/.claude/session-manager}/sessions"
rm -f "$dir/$session_id.json" 2>/dev/null
exit 0
```

Make it executable: `chmod +x session-manager/hooks/remove-session.sh`

- [ ] **Step 5: Create `hooks.json`**

Create `session-manager/hooks/hooks.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/hooks/record-session.sh",
            "timeout": 5000
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/hooks/remove-session.sh",
            "timeout": 5000
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 6: Run the hook test + validate JSON**

Run: `bash session-manager/tests/test-record-session.sh && jq . session-manager/hooks/hooks.json >/dev/null && echo "hooks.json valid"`
Expected: `ALL PASS` then `hooks.json valid`.

- [ ] **Step 7: Commit**

```bash
git add session-manager/hooks/ session-manager/tests/test-record-session.sh
git commit -m "feat(session-manager): SessionStart/SessionEnd hooks record session→TUI registry (SP3)"
```

---

### Task 3: Docs + version bump

**Files:**
- Modify: `session-manager/CLAUDE.md` (document the hook-backed registry under the locator section)
- Modify: `session-manager/.claude-plugin/plugin.json` (version bump, via the repo script)

**Interfaces:** none (documentation + manifest only).

- [ ] **Step 1: Document the registry in CLAUDE.md**

In `session-manager/CLAUDE.md`, in the `locator.py` section, immediately after the paragraph that begins "Resolution is **claude-anchored**", add this paragraph:

```markdown
When a session is **idle with no live tagged child** (no stdio MCP server, no in-flight
Bash-tool shell), the pull scan cannot see it — the TUI itself carries no
`CLAUDE_CODE_SESSION_ID`. A **hook-backed registry** (SP3) closes this gap: a
`SessionStart` hook writes `~/.claude/session-manager/sessions/<session_id>.json`
(`{session_id, claude_pid, cwd, ts}`) and a `SessionEnd` hook deletes it. When the pull
scan places no session for a pane, `merge_registry_sessions` synthesizes the record from
the registry, placed claude-anchored on the recorded `claude_pid` — but only if that pid
is still a live `claude` (dead entries are ignored and swept). Live-scan discovery always
wins over the registry (dedup by `session_id`), so SP1's pull remains ground truth. See
`docs/superpowers/specs/2026-07-27-session-locator-sp3-hook-backed-registry-design.md`.
```

- [ ] **Step 2: Bump the plugin version + clear cache**

Run: `./scripts/bump-plugin.sh session-manager minor`
(SP3 is a feature → minor bump. This also clears the plugin cache.)

- [ ] **Step 3: Verify the manifest bumped**

Run: `jq -r .version session-manager/.claude-plugin/plugin.json`
Expected: a version higher than the pre-bump value (minor increment).

- [ ] **Step 4: Commit**

```bash
git add session-manager/CLAUDE.md session-manager/.claude-plugin/plugin.json
git commit -m "docs(session-manager): document hook-backed registry; bump version (SP3)"
```

---

## Notes for the executor

- `UUID_9C`, `UUID_C3`, `UUID_OWNER`, `UUID_STALE` are module-level fixtures already defined at `test_locator.py:548-551` — reuse them.
- The test env normally has no `~/.claude/session-manager/sessions/` dir, so `_read_registry_entries()` returns `[]` and Task 1's merge is a no-op for every existing test — that's the regression guard, not a gap.
- The hooks require `jq` (already used by `default-tools` hooks). Both scripts exit 0 if `jq` is missing.
- Live verification after all tasks + `chmod +x` (env-dependent, informational): restart a `claude` in a pane, let it idle, then `python3 session-manager/scripts/locator.py resolve --pane <pane>` should return that session as a single object where it previously returned `[]`.
```
