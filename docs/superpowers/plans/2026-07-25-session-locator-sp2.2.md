# Session Locator SP2.2 — `CLAUDE_PID`-anchored placement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Place a Claude session on its pane via the TUI named by the `CLAUDE_PID` env value (validated live), so sessions with no on-tty tagged member (no live stdio MCP server) resolve correctly instead of returning `pane=None`.

**Architecture:** `parse_processes` gains a `claude_pid` field. `session_placement` anchors the TUI to that pid (validated as a live `claude` in `proc_table`), falling back to the existing `nearest_claude_ancestor` ppid-walk when absent, and derives the pane from the TUI's live tty — dropping SP2.1's on-tty-member requirement. Stale-straggler rejection for the rare reused-TUI case moves to `cmd_resolve`, whose foreground tiebreak is extended to break a same-pgid tie by on-tty-member presence.

**Tech Stack:** Python 3.8+ stdlib only; `unittest`. macOS `ps`/`tmux`. No new dependencies.

## Global Constraints

- macOS-only, read-only, pure functions (`parse_*`, `build_*`, `session_placement`, `resolve_collision`) take injected data; only `_run`/`*_index`/`cwd_of`/`_scan_and_build` are impure. (from spec)
- The session record has **exactly** these 10 keys: `session_id`, `role`, `parent_session_id`, `pane`, `host`, `tty`, `cwd`, `leader_pid`, `pane_live`, `tmux`. (unchanged contract)
- `resolve` prints a single JSON object for one match, a JSON array for several, and `[]` + exit 1 for none. (unchanged contract)
- No `RE_CLAUDE` change (version-path binary match is out of scope / separate follow-up). (from spec)
- Python 3.8+ stdlib only; no pip installs.
- Run the full suite after every task: `python3 session-manager/tests/test_locator.py -v` — all pass.

---

### Task 1: Capture `claude_pid` in `parse_processes`

**Files:**
- Modify: `session-manager/scripts/locator.py` (add `RE_CLAUDE_PID` near `locator.py:27`; add `claude_pid` to the dict in `parse_processes` `locator.py:69-81`)
- Test: `session-manager/tests/test_locator.py` (new test in `TestParseProcesses`)

**Interfaces:**
- Produces: each dict from `parse_processes` gains key `"claude_pid"` → `int` when the member's env carries `CLAUDE_PID=<n>`, else `None`.

- [ ] **Step 1: Write the failing test**

Add to `TestParseProcesses` in `session-manager/tests/test_locator.py`:

```python
    def test_extracts_claude_pid(self):
        with_pid = pline(2001, 1900, "ttys016",
                         CLAUDE_CODE_SESSION_ID=UUID_A, CLAUDE_PID="17141")
        without = pline(2002, 1900, "ttys016", CLAUDE_CODE_SESSION_ID=UUID_B)
        procs = locator.parse_processes(with_pid + "\n" + without)
        by_sid = {p["session_id"]: p for p in procs}
        self.assertEqual(by_sid[UUID_A]["claude_pid"], 17141)
        self.assertIsNone(by_sid[UUID_B]["claude_pid"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 session-manager/tests/test_locator.py TestParseProcesses.test_extracts_claude_pid -v`
Expected: FAIL with `KeyError: 'claude_pid'`.

- [ ] **Step 3: Add the regex constant**

In `session-manager/scripts/locator.py`, immediately after `RE_TMUX_PANE = re.compile(r"\bTMUX_PANE=(%\d+)")` (line 27), add:

```python
RE_CLAUDE_PID = re.compile(r"\bCLAUDE_PID=(\d+)")
```

- [ ] **Step 4: Capture the field in `parse_processes`**

In `parse_processes`, after the line `term_p = RE_TERM_PROGRAM.search(command)` (around line 66), add:

```python
        claude_pid_m = RE_CLAUDE_PID.search(command)
```

Then in the `procs.append({...})` dict (lines 69-81), add this entry (e.g. after the `"session_id"` line):

```python
                "claude_pid": int(claude_pid_m.group(1)) if claude_pid_m else None,
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 session-manager/tests/test_locator.py -v`
Expected: PASS, including the new `test_extracts_claude_pid`; all pre-existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add session-manager/scripts/locator.py session-manager/tests/test_locator.py
git commit -m "feat(locator): capture CLAUDE_PID field in parse_processes (SP2.2)"
```

---

### Task 2: Anchor `session_placement` on `CLAUDE_PID`

**Files:**
- Modify: `session-manager/scripts/locator.py` (`session_placement`, `locator.py:255-302`)
- Test: `session-manager/tests/test_locator.py` (`TestClaudeAnchoredPlacement`: update `_proc` helper; add new tests; re-express the stale-straggler test)

**Interfaces:**
- Consumes: `members[i]["claude_pid"]` (Task 1), `proc_table`, `tmux_index`, `tty_pane_idx`.
- Produces: `session_placement(...)` returns the same `{leader_pid, pane, host, tty, pane_live, tmux}` dict. It no longer requires an on-tty member; it may now return the **same pane for two sessions** (resolved in Task 3).

- [ ] **Step 1: Extend the `_proc` test helper to carry `claude_pid`**

In `TestClaudeAnchoredPlacement` (`session-manager/tests/test_locator.py:439`), replace the `_proc` method with:

```python
    def _proc(self, pid, ppid, sid, pane, tty=None, iterm=None, term=None,
              claude_pid=None):
        return {"pid": pid, "ppid": ppid, "session_id": sid, "tmux_pane": pane,
                "tmux_socket": "default" if pane else None, "tty": tty,
                "iterm_session_id": iterm, "term_session_id": term,
                "claude_pid": claude_pid}
```

- [ ] **Step 2: Write the failing tests (the fix + the re-expressed collision)**

In `TestClaudeAnchoredPlacement`, add these two tests, and **replace** `test_stale_straggler_shares_tui_but_not_pane` (`locator.py` test at line 503) with the re-expressed collision test below:

```python
    def test_mcp_less_detached_session_placed_via_claude_pid(self):
        # SP2.2 fix: the session's only member is DETACHED (tty None), no on-tty
        # member, but CLAUDE_PID names the live claude TUI 79313 on ttys008.
        procs = [self._proc(2740, 1, UUID_9C, None, tty=None, claude_pid=79313)]
        table = {79313: {"ppid": 14528, "tty": "ttys008", "command": "claude"}}
        out = locator.build_sessions(procs, {}, self.TMUX_INDEX,
                                     cwd_fn=lambda pid: None, proc_table=table)
        r = out[0]
        self.assertEqual(r["leader_pid"], 79313)
        self.assertEqual(r["pane"], "tmux:default:%126")   # from the TUI's tty
        self.assertTrue(r["pane_live"])

    def test_claude_pid_naming_dead_pid_orphans(self):
        # CLAUDE_PID names a pid absent from proc_table and no claude ancestor is
        # reachable -> orphan (pane=None), never a ghost.
        procs = [self._proc(2740, 1, UUID_9C, None, tty=None, claude_pid=99999)]
        table = {2740: {"ppid": 1, "tty": None, "command": "zsh -c tool"}}
        out = locator.build_sessions(procs, {}, self.TMUX_INDEX,
                                     cwd_fn=lambda pid: None, proc_table=table)
        r = out[0]
        self.assertIsNone(r["pane"])
        self.assertFalse(r["pane_live"])
        self.assertEqual(r["leader_pid"], 2740)            # structural fallback

    def test_reuse_straggler_collides_at_placement(self):
        # SP2.2: both sessions name the same live TUI 4973 (one via an on-tty MCP
        # child, one via a detached child), so BOTH are placed on %126 at the
        # placement layer. Disambiguation is the resolve layer's job (Task 3).
        procs = [
            self._proc(5054, 4997, UUID_OWNER, "%126", tty="ttys008"),
            self._proc(81310, 81300, UUID_STALE, "%126", tty=None),
        ]
        table = {
            5054: {"ppid": 4997, "tty": "ttys008", "command": "node /npx/.bin/context7-mcp"},
            4997: {"ppid": 4973, "tty": "ttys008", "command": "node /npx/.bin/wrap"},
            4973: {"ppid": 79313, "tty": "ttys008", "command": "claude -r"},
            81310: {"ppid": 81300, "tty": None, "command": "node /npx/.bin/some-mcp"},
            81300: {"ppid": 4973, "tty": None, "command": "zsh -c tool"},
        }
        out = locator.build_sessions(procs, {}, self.TMUX_INDEX,
                                     cwd_fn=lambda pid: None, proc_table=table)
        by_sid = {r["session_id"]: r for r in out}
        self.assertEqual(by_sid[UUID_OWNER]["pane"], "tmux:default:%126")
        self.assertEqual(by_sid[UUID_STALE]["pane"], "tmux:default:%126")  # co-located now
        self.assertEqual(by_sid[UUID_OWNER]["leader_pid"], 4973)
        self.assertEqual(by_sid[UUID_STALE]["leader_pid"], 4973)
```

- [ ] **Step 3: Run the new tests to verify they fail**

Run: `python3 session-manager/tests/test_locator.py TestClaudeAnchoredPlacement -v`
Expected: `test_mcp_less_detached_session_placed_via_claude_pid` FAILs (current code requires an on-tty member → `pane` is `None`); `test_reuse_straggler_collides_at_placement` FAILs (current code returns `None` for `UUID_STALE`).

- [ ] **Step 4: Rewrite `session_placement`**

In `session-manager/scripts/locator.py`, replace the entire body of `session_placement` (lines 255-302) with:

```python
def session_placement(members, rep, proc_table, tmux_index, tty_pane_idx):
    """Place a session on the pane its real claude TUI holds (claude-anchored, SP2.2).

    The TUI is named directly by the CLAUDE_PID a tagged member carries in its env
    (validated as a live claude in proc_table). This works even when every member
    is detached (tty None) — unlike SP2.1, which required an on-tty member and so
    dropped sessions with no live stdio MCP server. Falls back to the ppid-walk
    (nearest_claude_ancestor) when CLAUDE_PID is absent/invalid (older claude).

    Stale-straggler rejection for a REUSED TUI (a previous session's detached
    members still name the current live TUI pid) is deliberately NOT done here:
    the live occupant and the stale one name the same pid, so both are placed and
    the tie is broken one layer up, in cmd_resolve (see spec 2026-07-25 and
    resolve_collision). The pane is always derived from the TUI's own live tty,
    never from a member's start-time TMUX_PANE env, so a straggler never ghosts
    onto a pane its TUI does not occupy.

    members: this session's tagged procs (parse_processes output).
    rep: the structural leader proc (resolve_roles' leader_pid), used only for
         iTerm/Apple-Terminal env-marker fallback.
    Returns {leader_pid, pane, host, tty, pane_live, tmux}.
    """
    tui = None
    for m in members:
        cp = m.get("claude_pid")
        if cp and cp in proc_table and RE_CLAUDE.search(proc_table[cp]["command"]):
            tui = cp
            break
    if tui is None:
        for m in members:
            cand = nearest_claude_ancestor(m["pid"], proc_table)
            if cand is not None:
                tui = cand
                break

    if tui is None:
        # No live claude TUI reachable (orphaned stragglers whose TUI has exited).
        return {"leader_pid": rep["pid"], "pane": None, "host": None,
                "tty": rep.get("tty"), "pane_live": False, "tmux": None}

    tui_tty = proc_table[tui].get("tty")
    if tui_tty and tui_tty in tty_pane_idx:
        socket, pane_id = tty_pane_idx[tui_tty]
        pinfo = tmux_index.get((socket, pane_id))
        tmux_meta = ({"socket": socket, "session": pinfo["tmux_session"],
                      "window": pinfo["tmux_window"], "active": pinfo["active"]}
                     if pinfo else None)
        return {"leader_pid": tui, "pane": f"tmux:{socket}:{pane_id}", "host": "tmux",
                "tty": tui_tty, "pane_live": True, "tmux": tmux_meta}
    if rep.get("iterm_session_id"):
        return {"leader_pid": tui, "pane": f"iterm:{rep['iterm_session_id']}",
                "host": "iterm", "tty": tui_tty or rep.get("tty"),
                "pane_live": True, "tmux": None}
    if rep.get("term_session_id"):
        return {"leader_pid": tui, "pane": f"term:{rep['term_session_id']}",
                "host": "apple-terminal", "tty": tui_tty or rep.get("tty"),
                "pane_live": True, "tmux": None}
    return {"leader_pid": tui, "pane": None, "host": None,
            "tty": tui_tty or rep.get("tty"), "pane_live": True, "tmux": None}
```

- [ ] **Step 5: Run the full suite**

Run: `python3 session-manager/tests/test_locator.py -v`
Expected: PASS. The two new tests pass; `test_reuse_straggler_collides_at_placement` passes; `test_detached_child_does_not_ghost_onto_a_pane`, `test_leader_upgrades_from_mcp_child_to_claude_tui`, `test_claude_tui_on_non_tmux_tty_uses_iterm_env`, and `test_schema_unchanged_with_proc_table` still pass (they use the `nearest_claude_ancestor` fallback path, unchanged).

- [ ] **Step 6: Commit**

```bash
git add session-manager/scripts/locator.py session-manager/tests/test_locator.py
git commit -m "feat(locator): CLAUDE_PID-anchored placement, drop on-tty requirement (SP2.2)"
```

---

### Task 3: Resolve-layer disambiguation (`on_tty_member_sids`, `resolve_collision`, `_scan_and_build`)

**Files:**
- Modify: `session-manager/scripts/locator.py` (add `on_tty_member_sids` and `resolve_collision` after `pick_foreground_winner` `locator.py:439`; add `_scan_and_build`, rewrite `gather_sessions` `locator.py:462-469` and `cmd_resolve` `locator.py:476-488`)
- Test: `session-manager/tests/test_locator.py` (new `TestOnTtyMemberSids`, `TestResolveCollision`; update `TestResolveTiebreakWiring` to patch `_scan_and_build`)

**Interfaces:**
- Consumes: `parse_processes` procs (Task 1, with `tty`), session records (Task 2), `pick_foreground_winner(hits, ps_output)` (existing).
- Produces:
  - `on_tty_member_sids(procs, tty) -> set[str]` — session ids with a member whose `tty` equals `tty`.
  - `resolve_collision(hits, tty, procs, ps_output) -> list` — length-1 list when narrowed to one, else the original hits.
  - `_scan_and_build() -> (sessions: list, procs: list)` — the impure scan used by both `gather_sessions` and `cmd_resolve`.

- [ ] **Step 1: Write the failing pure-function tests**

Add these two classes to `session-manager/tests/test_locator.py` (after `TestResolveTiebreakWiring`):

```python
class TestOnTtyMemberSids(unittest.TestCase):
    def test_selects_sessions_with_member_on_tty(self):
        procs = [
            {"session_id": UUID_OWNER, "pid": 5054, "tty": "ttys008"},
            {"session_id": UUID_STALE, "pid": 81310, "tty": None},
        ]
        self.assertEqual(locator.on_tty_member_sids(procs, "ttys008"), {UUID_OWNER})

    def test_empty_tty_returns_empty(self):
        procs = [{"session_id": UUID_A, "pid": 1, "tty": "ttys1"}]
        self.assertEqual(locator.on_tty_member_sids(procs, None), set())


class TestResolveCollision(unittest.TestCase):
    def _hit(self, sid, leader):
        return {"session_id": sid, "role": "interactive", "pane": "tmux:default:%126",
                "host": "tmux", "tty": "ttys008", "leader_pid": leader}

    def test_reuse_collision_prefers_on_tty_session(self):
        # Both hits share the reused TUI 4973 -> foreground pgid ties -> the
        # on-tty member breaks it in favor of the live owner.
        hits = [self._hit(UUID_OWNER, 4973), self._hit(UUID_STALE, 4973)]
        procs = [{"session_id": UUID_OWNER, "pid": 5054, "tty": "ttys008"},
                 {"session_id": UUID_STALE, "pid": 81310, "tty": None}]
        ps = "4973 4973 S+\n5054 4973 S+\n"
        out = locator.resolve_collision(hits, "ttys008", procs, ps)
        self.assertEqual([h["session_id"] for h in out], [UUID_OWNER])

    def test_genuine_ambiguity_returns_both(self):
        hits = [self._hit(UUID_OWNER, 4973), self._hit(UUID_STALE, 4973)]
        procs = [{"session_id": UUID_OWNER, "pid": 5054, "tty": "ttys008"},
                 {"session_id": UUID_STALE, "pid": 81310, "tty": "ttys008"}]
        ps = "4973 4973 S+\n"
        out = locator.resolve_collision(hits, "ttys008", procs, ps)
        self.assertEqual({h["session_id"] for h in out}, {UUID_OWNER, UUID_STALE})

    def test_foreground_wins_for_distinct_leaders(self):
        hits = [self._hit(UUID_A, 2001), self._hit(UUID_B, 2002)]
        ps = "2001 2001 S\n2002 2002 S+\n"
        out = locator.resolve_collision(hits, "ttys016", [], ps)
        self.assertEqual([h["session_id"] for h in out], [UUID_B])
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 session-manager/tests/test_locator.py TestResolveCollision TestOnTtyMemberSids -v`
Expected: FAIL with `AttributeError: module 'locator' has no attribute 'on_tty_member_sids'`.

- [ ] **Step 3: Add the two pure functions**

In `session-manager/scripts/locator.py`, immediately after `pick_foreground_winner` (ends at line 439), add:

```python
def on_tty_member_sids(procs, tty):
    """Session ids with a tagged member whose own tty is `tty` (live on-tty presence).

    Used by resolve_collision to separate a reused TUI's live occupant (which has an
    on-tty member) from a stale straggler (detached-only) when both name the same TUI
    pid and thus share a foreground pgid.
    """
    if not tty:
        return set()
    return {p["session_id"] for p in procs if p.get("tty") == tty}


def resolve_collision(hits, tty, procs, ps_output):
    """Narrow >1 interactive hits sharing one tty to a single winner if possible.

    1) foreground pgid (pick_foreground_winner);
    2) if that signal ties (e.g. a reused TUI shared as leader_pid by both), prefer
       the hit whose session has a live on-tty member.
    Returns a list: length 1 when resolved, else the original hits (ambiguity array).
    """
    winner = pick_foreground_winner(hits, ps_output)
    if winner is not None:
        return [winner]
    on_tty = on_tty_member_sids(procs, tty)
    narrowed = [h for h in hits if h["session_id"] in on_tty]
    return narrowed if len(narrowed) == 1 else list(hits)
```

- [ ] **Step 4: Run to verify they pass**

Run: `python3 session-manager/tests/test_locator.py TestResolveCollision TestOnTtyMemberSids -v`
Expected: PASS.

- [ ] **Step 5: Refactor the scan + wire the tiebreak into `cmd_resolve`**

In `session-manager/scripts/locator.py`, replace `gather_sessions` (lines 462-469) with:

```python
def _scan_and_build():
    """Live scan -> (session records, tagged procs). The impure top-level shared
    by cmd_list (records only) and cmd_resolve (also needs procs for the tiebreak)."""
    ps_output = _run(["ps", "-E", "-ww", "-o", "pid=,ppid=,tty=,command=", "-ax"])
    procs = parse_processes(ps_output, self_pid=os.getpid())
    ppid_map = build_ppid_map(ps_output)
    proc_table = build_process_table(ps_output)
    tmux_index = tmux_pane_index()
    sessions = build_sessions(procs, ppid_map, tmux_index, proc_table=proc_table)
    return sessions, procs


def gather_sessions():
    """Assembled session records (the impure top-level)."""
    return _scan_and_build()[0]
```

Then replace `cmd_resolve` (lines 476-488) with:

```python
def cmd_resolve(args):
    sessions, procs = _scan_and_build()
    hits = [s for s in sessions if match_selector(s, args)]
    if not hits:
        print(json.dumps([], indent=2))
        sys.exit(1)
    if len(hits) > 1:
        # Multiple hits only arise from a --pane/--tty selector, so they all share
        # one tty; hits[0]'s tty is the pane's tty.
        tty = hits[0].get("tty")
        hits = resolve_collision(hits, tty, procs, pane_foreground_ps(tty))
    print(json.dumps(hits[0] if len(hits) == 1 else hits, indent=2))
```

- [ ] **Step 6: Update `TestResolveTiebreakWiring` to patch `_scan_and_build`**

In `session-manager/tests/test_locator.py`, in `TestResolveTiebreakWiring`, replace `setUp` and `tearDown` with:

```python
    def setUp(self):
        self._scan = locator._scan_and_build
        self._ps = locator.pane_foreground_ps
        self.two = [
            {"session_id": UUID_A, "role": "interactive", "pane": "tmux:default:%86",
             "host": "tmux", "tty": "ttys016", "leader_pid": 2001},
            {"session_id": UUID_B, "role": "interactive", "pane": "tmux:default:%86",
             "host": "tmux", "tty": "ttys016", "leader_pid": 2002},
        ]
        # No live procs -> the on-tty discriminator finds nothing, so behavior is
        # governed purely by the foreground signal (as before this refactor).
        locator._scan_and_build = lambda: (self.two, [])

    def tearDown(self):
        locator._scan_and_build = self._scan
        locator.pane_foreground_ps = self._ps
```

(Leave `_resolve_pane`, `test_breaks_tie_via_foreground`, and `test_returns_array_when_undeterminable` unchanged — they now exercise the refactored `cmd_resolve`.)

- [ ] **Step 7: Run the full suite**

Run: `python3 session-manager/tests/test_locator.py -v`
Expected: PASS — all tests, including the updated `TestResolveTiebreakWiring` (foreground still breaks the tie; empty foreground still returns the array) and the new collision tests.

- [ ] **Step 8: Commit**

```bash
git add session-manager/scripts/locator.py session-manager/tests/test_locator.py
git commit -m "feat(locator): resolve-layer collision break via on-tty member (SP2.2)"
```

---

### Task 4: Docs + version bump

**Files:**
- Modify: `session-manager/CLAUDE.md` (locator.py section — describe CLAUDE_PID anchoring + resolve-layer disambiguation)
- Modify: `session-manager/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` (version bump, lockstep) — via the bump script

**Interfaces:** none (docs/metadata only).

- [ ] **Step 1: Update the locator description in `session-manager/CLAUDE.md`**

In the `### locator.py` section, update the "claude-anchored" paragraph to state that the TUI is identified by the `CLAUDE_PID` env value a tagged child carries (validated as a live `claude`), falling back to the ppid-walk when absent; the pane comes from that TUI's live tty; and that when a reused TUI is named by both a live session and a stale straggler, they collide at the placement layer and `resolve --pane` breaks the tie via foreground pgid then on-tty-member presence (so `list` may show a stale straggler co-located, but `resolve` returns the live occupant). Keep it to a few sentences, matching the surrounding style. Do not edit the fork-snapshot or fork-verification sections.

- [ ] **Step 2: Bump the plugin version (patch) and clear cache**

Run: `./scripts/bump-plugin.sh session-manager patch`
Expected: `session-manager/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` version fields bump in lockstep; cache cleared.

- [ ] **Step 3: Run the full suite once more**

Run: `python3 session-manager/tests/test_locator.py -v`
Expected: PASS (unchanged by docs/version edits).

- [ ] **Step 4: Commit**

```bash
git add session-manager/CLAUDE.md session-manager/.claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "docs(session-manager): SP2.2 CLAUDE_PID anchoring; bump version"
```

---

## Self-Review

**Spec coverage:**
- Spec §1 (capture `CLAUDE_PID`) → Task 1. ✅
- Spec §2 (anchor via `CLAUDE_PID`, pane from live tty, ppid-walk fallback, drop on-tty requirement, pure placement) → Task 2. ✅
- Spec §3 (rejection moves to `cmd_resolve`; foreground tiebreak extended by on-tty presence; no recency; single resolution layer) → Task 3 (`resolve_collision`, `on_tty_member_sids`). ✅
- Spec §4 (behavioral change: `list` may co-locate a straggler; `resolve` still correct; 10-key schema unchanged) → Task 2 `test_reuse_straggler_collides_at_placement` + Task 3 `TestResolveCollision`; schema guarded by the untouched `test_schema_unchanged_with_proc_table`. ✅
- Spec "out of scope" (`RE_CLAUDE` version-path) → Global Constraints note; no task touches `RE_CLAUDE`. ✅
- Spec testing fixtures (MCP-less detached; orphaned straggler; CLAUDE_PID absent fallback; reuse collision at resolve; genuine ambiguity) → Tasks 2 and 3. ✅

**Placeholder scan:** none — every code step shows complete code and exact commands.

**Type consistency:** `claude_pid` (int|None) produced in Task 1, read via `.get("claude_pid")` in Task 2 and set in the `_proc` helper; `on_tty_member_sids(procs, tty)` and `resolve_collision(hits, tty, procs, ps_output)` defined in Task 3 and called with matching arguments in `cmd_resolve`; `_scan_and_build()` returns `(sessions, procs)` consumed as such by `gather_sessions` and `cmd_resolve`. Record keys unchanged (10-key guardrail).
