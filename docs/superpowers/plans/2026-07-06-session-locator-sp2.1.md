# Session Locator SP2.1 — Resolution Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `locator.py` anchor every session's identity and pane to its real `claude` TUI process (found by walking up from tagged children), instead of to whichever tagged child process the env-scan finds — eliminating the MCP-as-leader bug and detached-child "ghost" pane attributions.

**Architecture:** Additive, backward-compatible. New pure functions (`build_process_table`, `RE_CLAUDE`, `nearest_claude_ancestor`, `tty_to_pane_index`, `session_placement`) take injected command output, matching the existing `parse_*/build_*` convention. `build_sessions` gains an optional `proc_table` param: when present (production, via `gather_sessions`) it uses claude-anchored placement; when absent (the existing 29 unit fixtures) it uses the current placement verbatim. `resolve_roles`, the 10-key record schema, and the `cmd_resolve` return contract are untouched.

**Tech Stack:** Python 3.8+ stdlib only; Bash. macOS. No new dependencies.

## Global Constraints

- Python 3.8+ **stdlib only** — no pip installs (matches SP1).
- Preserve the **10-key record schema** exactly: `session_id, role, parent_session_id, pane, host, tty, cwd, leader_pid, pane_live, tmux`. Guarded by `test_locator.py:172-180`.
- Preserve the **`resolve` return contract**: single JSON object (1 match) / JSON array (ambiguous) / `[]`+exit 1 (none). `cmd_resolve` and the SP2 foreground tiebreak (`pick_foreground_winner`) are **not modified**.
- **Keep all 29 existing `test_locator.py` tests green, unchanged.** New behavior is reached only when `proc_table` is supplied; the existing tests supply none.
- Follow the file convention: pure functions take injected `ps`/`tmux` text or parsed dicts; only `_run`/`*_index`/`cwd_of`/`gather_*` are impure. Name the TUI-matching regex like the existing `RE_*` constants.
- All paths relative to repo root `/Users/sthuang/Project/my_claudecode_marketplace`.
- Run the Python suite with: `python3 session-manager/tests/test_locator.py -v`. Run the fork wrapper suite with: `bash session-manager/tests/test-fork-active-pane.sh`.

---

### Task 1: `build_process_table` — full pid→{ppid,tty,command} map

**Files:**
- Modify: `session-manager/scripts/locator.py` (add function after `build_ppid_map`, ~line 98)
- Test: `session-manager/tests/test_locator.py` (add `TestBuildProcessTable` class)

**Interfaces:**
- Produces: `build_process_table(ps_output: str) -> dict[int, dict]` where each value is `{"ppid": int, "tty": str|None, "command": str}`. `tty` is normalized (`"??"`→`None`, `/dev/` stripped) exactly like `parse_processes`. Captures **every** process line (needed for ancestry to traverse non-claude hops), not just claude-tagged ones.

- [ ] **Step 1: Write the failing test**

Add to `session-manager/tests/test_locator.py` (after `TestBuildPpidMap`):

```python
class TestBuildProcessTable(unittest.TestCase):
    def test_captures_all_procs_with_tty_and_command(self):
        out = "\n".join([
            "79481 79313 ttys008 claude",
            "79770 79492 ttys008 node /npx/abc/.bin/context7-mcp",
            "94268 94266 ?? node /npx/def/.bin/some-mcp",
            "1900 1800 ttys016 -zsh",
            "garbage line",                       # non-numeric pid -> skipped
        ])
        t = locator.build_process_table(out)
        self.assertEqual(t[79481], {"ppid": 79313, "tty": "ttys008", "command": "claude"})
        self.assertEqual(t[79770]["command"], "node /npx/abc/.bin/context7-mcp")
        self.assertIsNone(t[94268]["tty"])        # "??" -> None
        self.assertEqual(t[1900]["ppid"], 1800)   # non-claude proc present for ancestry
        self.assertNotIn("garbage", t)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 session-manager/tests/test_locator.py TestBuildProcessTable -v`
Expected: FAIL with `AttributeError: module 'locator' has no attribute 'build_process_table'`

- [ ] **Step 3: Write minimal implementation**

Add to `session-manager/scripts/locator.py` after `build_ppid_map` (after ~line 97):

```python
def build_process_table(ps_output):
    """pid -> {ppid, tty, command} for ALL processes in the ps output.

    Superset of build_ppid_map: ancestry walks, claude-TUI identification, and
    the TUI's tty are all read from this one table. tty normalized like
    parse_processes ("??" -> None, /dev/ stripped).
    """
    table = {}
    for line in ps_output.splitlines():
        parts = line.split(None, 3)
        if len(parts) < 2:
            continue
        try:
            pid, ppid = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        tty = parts[2] if len(parts) >= 3 else "??"
        command = parts[3] if len(parts) >= 4 else ""
        table[pid] = {
            "ppid": ppid,
            "tty": None if tty == "??" else tty.replace("/dev/", ""),
            "command": command,
        }
    return table
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 session-manager/tests/test_locator.py TestBuildProcessTable -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add session-manager/scripts/locator.py session-manager/tests/test_locator.py
git commit -m "feat(locator): build_process_table — full pid->{ppid,tty,command} map"
```

---

### Task 2: `RE_CLAUDE` + `nearest_claude_ancestor` — find the claude TUI

**Files:**
- Modify: `session-manager/scripts/locator.py` (add `RE_CLAUDE` near the other `RE_*` constants ~line 31; add `nearest_claude_ancestor` after `build_process_table`)
- Test: `session-manager/tests/test_locator.py` (add `TestNearestClaudeAncestor` class)

**Interfaces:**
- Consumes: the `proc_table` shape from Task 1.
- Produces:
  - `RE_CLAUDE` — compiled regex matching the `claude` TUI program token in a command string.
  - `nearest_claude_ancestor(pid: int, proc_table: dict) -> int | None` — inclusive upward walk (checks `pid` itself, then ancestors); returns the first pid whose `command` matches `RE_CLAUDE`, or `None` if none found / chain breaks / cycle.

- [ ] **Step 1: Write the failing test**

Add to `session-manager/tests/test_locator.py`:

```python
class TestNearestClaudeAncestor(unittest.TestCase):
    TABLE = {
        79481: {"ppid": 79313, "tty": "ttys008", "command": "claude"},
        79492: {"ppid": 79481, "tty": "ttys008", "command": "node /npx/x/.bin/wrap"},
        79770: {"ppid": 79492, "tty": "ttys008", "command": "node /npx/x/.bin/context7-mcp"},
        79313: {"ppid": 1, "tty": "ttys008", "command": "-zsh"},
        94268: {"ppid": 94266, "tty": None, "command": "node /npx/y/.bin/some-mcp"},
    }

    def test_re_claude_matches_tui_not_mcp(self):
        self.assertTrue(locator.RE_CLAUDE.search("claude"))
        self.assertTrue(locator.RE_CLAUDE.search("claude -r abc --fork-session"))
        self.assertTrue(locator.RE_CLAUDE.search("/usr/local/bin/claude -r"))
        self.assertFalse(locator.RE_CLAUDE.search("node /npx/x/.bin/context7-mcp"))
        self.assertFalse(locator.RE_CLAUDE.search("node /Users/me/.claude/plugins/foo-mcp"))

    def test_walks_up_from_mcp_child_to_claude_tui(self):
        self.assertEqual(locator.nearest_claude_ancestor(79770, self.TABLE), 79481)

    def test_returns_self_when_pid_is_claude(self):
        self.assertEqual(locator.nearest_claude_ancestor(79481, self.TABLE), 79481)

    def test_returns_none_when_chain_breaks_before_claude(self):
        # 94268's parent 94266 is gone from the table -> orphan -> None
        self.assertIsNone(locator.nearest_claude_ancestor(94268, self.TABLE))

    def test_returns_none_on_cycle(self):
        cyc = {1: {"ppid": 2, "tty": None, "command": "a"},
               2: {"ppid": 1, "tty": None, "command": "b"}}
        self.assertIsNone(locator.nearest_claude_ancestor(1, cyc))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 session-manager/tests/test_locator.py TestNearestClaudeAncestor -v`
Expected: FAIL (`RE_CLAUDE` / `nearest_claude_ancestor` not defined)

- [ ] **Step 3: Write minimal implementation**

Add `RE_CLAUDE` next to the other `RE_*` constants in `locator.py` (after `RE_TERM_PROGRAM`, ~line 31):

```python
# The claude TUI's own command (e.g. "claude", "claude -r", "/path/claude -r").
# Matches the claude program token; deliberately does NOT match node MCP-server
# children ("node .../xxx-mcp") or a ".claude" directory inside another path.
RE_CLAUDE = re.compile(r"(?:^|/)claude(?:\s|$)")
```

Add `nearest_claude_ancestor` after `build_process_table`:

```python
def nearest_claude_ancestor(pid, proc_table):
    """Nearest process at or above `pid` whose command is the claude TUI, else None.

    The claude TUI does not carry CLAUDE_CODE_SESSION_ID in its own start-time
    env (only its children do), so a session's tagged procs are its children; walk
    up to find the real TUI. Bounded by a seen-set against ppid cycles.
    """
    cur = pid
    seen = set()
    while cur is not None and cur not in seen:
        seen.add(cur)
        info = proc_table.get(cur)
        if info is None:
            return None
        if RE_CLAUDE.search(info["command"]):
            return cur
        cur = info["ppid"]
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 session-manager/tests/test_locator.py TestNearestClaudeAncestor -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add session-manager/scripts/locator.py session-manager/tests/test_locator.py
git commit -m "feat(locator): RE_CLAUDE + nearest_claude_ancestor (find the real claude TUI)"
```

---

### Task 3: `tty_to_pane_index` — invert the tmux pane index

**Files:**
- Modify: `session-manager/scripts/locator.py` (add after `parse_tmux_panes`, ~line 125)
- Test: `session-manager/tests/test_locator.py` (add `TestTtyToPaneIndex` class)

**Interfaces:**
- Consumes: the `tmux_index` shape from `parse_tmux_panes` — `{(socket, pane_id): {"tty", "pane_pid", "tmux_session", "tmux_window", "active"}}`.
- Produces: `tty_to_pane_index(tmux_index: dict) -> dict[str, tuple[str, str]]` mapping `tty -> (socket, pane_id)`. Entries with falsy tty are skipped. If two panes somehow share a tty, last-writer-wins (not expected in practice).

- [ ] **Step 1: Write the failing test**

Add to `session-manager/tests/test_locator.py`:

```python
class TestTtyToPaneIndex(unittest.TestCase):
    def test_inverts_index_by_tty(self):
        idx = {
            ("default", "%126"): {"tty": "ttys008", "pane_pid": 1, "tmux_session": "11",
                                  "tmux_window": "1", "active": True},
            ("default", "%127"): {"tty": "ttys009", "pane_pid": 2, "tmux_session": "11",
                                  "tmux_window": "1", "active": False},
        }
        inv = locator.tty_to_pane_index(idx)
        self.assertEqual(inv["ttys008"], ("default", "%126"))
        self.assertEqual(inv["ttys009"], ("default", "%127"))

    def test_skips_falsy_tty(self):
        idx = {("default", "%5"): {"tty": "", "pane_pid": 1, "tmux_session": "s",
                                   "tmux_window": "0", "active": True}}
        self.assertEqual(locator.tty_to_pane_index(idx), {})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 session-manager/tests/test_locator.py TestTtyToPaneIndex -v`
Expected: FAIL (`tty_to_pane_index` not defined)

- [ ] **Step 3: Write minimal implementation**

Add after `parse_tmux_panes` in `locator.py`:

```python
def tty_to_pane_index(tmux_index):
    """Invert {(socket, pane_id): {tty,...}} to {tty: (socket, pane_id)}.

    Used to place a session on the pane whose tty its claude TUI actually holds,
    rather than trusting a (possibly stale) TMUX_PANE env on a detached child.
    """
    inv = {}
    for (socket, pane_id), info in tmux_index.items():
        tty = info.get("tty")
        if tty:
            inv[tty] = (socket, pane_id)
    return inv
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 session-manager/tests/test_locator.py TestTtyToPaneIndex -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add session-manager/scripts/locator.py session-manager/tests/test_locator.py
git commit -m "feat(locator): tty_to_pane_index — invert pane index by tty"
```

---

### Task 4: claude-anchored placement in `build_sessions`

**Files:**
- Modify: `session-manager/scripts/locator.py` — add `session_placement`; add optional `proc_table=None` param to `build_sessions`; wire `build_process_table` into `gather_sessions`.
- Test: `session-manager/tests/test_locator.py` (add `TestClaudeAnchoredPlacement` class)

**Interfaces:**
- Consumes: `nearest_claude_ancestor` (Task 2), `tty_to_pane_index` output (Task 3), `proc_table` (Task 1), and the existing `procs`/`tmux_index` shapes.
- Produces:
  - `session_placement(members: list, rep: dict, proc_table: dict, tmux_index: dict, tty_pane_idx: dict) -> dict` with keys `leader_pid, pane, host, tty, pane_live, tmux`. Finds the session's claude TUI (via `nearest_claude_ancestor` over `members`, preferring a candidate that has a tty), places it on the pane whose tty the TUI holds; falls back to iTerm/Apple-Terminal env markers on `rep`; orphan (no TUI) → `pane=None, host=None, pane_live=False`.
  - `build_sessions(procs, ppid_map, tmux_index, cwd_fn=cwd_of, proc_table=None)` — when `proc_table` is falsy, behaves exactly as before (existing tests); when provided, uses `session_placement`. Record still has exactly the 10 schema keys.

- [ ] **Step 1: Write the failing test**

Add to `session-manager/tests/test_locator.py`:

```python
UUID_9C = "9ccee61d-0000-0000-0000-00000000009c"
UUID_C3 = "c392555a-0000-0000-0000-0000000000c3"

class TestClaudeAnchoredPlacement(unittest.TestCase):
    def _proc(self, pid, ppid, sid, pane, tty=None, iterm=None, term=None):
        return {"pid": pid, "ppid": ppid, "session_id": sid, "tmux_pane": pane,
                "tmux_socket": "default" if pane else None, "tty": tty,
                "iterm_session_id": iterm, "term_session_id": term}

    TMUX_INDEX = {("default", "%126"): {
        "tty": "ttys008", "pane_pid": 79313, "tmux_session": "11",
        "tmux_window": "1", "active": True}}

    def test_leader_upgrades_from_mcp_child_to_claude_tui(self):
        # Only tagged proc is an MCP child; its claude TUI is pid 79481.
        procs = [self._proc(79770, 79492, UUID_9C, "%126", tty="ttys008")]
        table = {
            79770: {"ppid": 79492, "tty": "ttys008", "command": "node /npx/.bin/context7-mcp"},
            79492: {"ppid": 79481, "tty": "ttys008", "command": "node /npx/.bin/wrap"},
            79481: {"ppid": 79313, "tty": "ttys008", "command": "claude"},
            79313: {"ppid": 1, "tty": "ttys008", "command": "-zsh"},
        }
        out = locator.build_sessions(procs, {}, self.TMUX_INDEX,
                                     cwd_fn=lambda pid: None, proc_table=table)
        r = out[0]
        self.assertEqual(r["leader_pid"], 79481)          # the claude TUI, not the MCP child
        self.assertEqual(r["pane"], "tmux:default:%126")  # from the TUI's tty
        self.assertEqual(r["tty"], "ttys008")
        self.assertTrue(r["pane_live"])

    def test_detached_child_does_not_ghost_onto_a_pane(self):
        # c392555a's only tagged proc is detached (tty None) with a STALE TMUX_PANE
        # of %126, and its parent is gone -> no claude ancestor -> must NOT map to %126.
        # 9ccee61d legitimately occupies %126.
        procs = [
            self._proc(79770, 79492, UUID_9C, "%126", tty="ttys008"),
            self._proc(94268, 94266, UUID_C3, "%126", tty=None),
        ]
        table = {
            79770: {"ppid": 79492, "tty": "ttys008", "command": "node /npx/.bin/context7-mcp"},
            79492: {"ppid": 79481, "tty": "ttys008", "command": "node /npx/.bin/wrap"},
            79481: {"ppid": 79313, "tty": "ttys008", "command": "claude"},
            94268: {"ppid": 94266, "tty": None, "command": "node /npx/.bin/some-mcp"},
            # 94266 (parent) is gone from the table -> orphan chain
        }
        out = locator.build_sessions(procs, {}, self.TMUX_INDEX,
                                     cwd_fn=lambda pid: None, proc_table=table)
        by_sid = {r["session_id"]: r for r in out}
        self.assertEqual(by_sid[UUID_9C]["pane"], "tmux:default:%126")
        self.assertIsNone(by_sid[UUID_C3]["pane"])         # ghost eliminated
        self.assertFalse(by_sid[UUID_C3]["pane_live"])
        self.assertEqual(by_sid[UUID_C3]["leader_pid"], 94268)  # structural fallback

    def test_claude_tui_on_non_tmux_tty_uses_iterm_env(self):
        # TUI found but its tty maps to no tmux pane -> iTerm host via rep's env marker.
        procs = [self._proc(3100, 3050, UUID_A, None, tty="ttys030",
                            iterm="w0t6p0:GUID")]
        table = {
            3100: {"ppid": 3090, "tty": "ttys030", "command": "node /npx/.bin/context7-mcp"},
            3090: {"ppid": 3000, "tty": "ttys030", "command": "claude"},
        }
        out = locator.build_sessions(procs, {}, {},  # no tmux panes
                                     cwd_fn=lambda pid: None, proc_table=table)
        r = out[0]
        self.assertEqual(r["leader_pid"], 3090)
        self.assertEqual(r["pane"], "iterm:w0t6p0:GUID")
        self.assertEqual(r["host"], "iterm")

    def test_schema_unchanged_with_proc_table(self):
        procs = [self._proc(79770, 79492, UUID_9C, "%126", tty="ttys008")]
        table = {79770: {"ppid": 79481, "tty": "ttys008", "command": "node x-mcp"},
                 79481: {"ppid": 1, "tty": "ttys008", "command": "claude"}}
        out = locator.build_sessions(procs, {}, self.TMUX_INDEX,
                                     cwd_fn=lambda pid: None, proc_table=table)
        self.assertEqual(
            set(out[0].keys()),
            {"session_id", "role", "parent_session_id", "pane", "host", "tty",
             "cwd", "leader_pid", "pane_live", "tmux"},
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 session-manager/tests/test_locator.py TestClaudeAnchoredPlacement -v`
Expected: FAIL (`build_sessions() got an unexpected keyword argument 'proc_table'`)

- [ ] **Step 3: Write minimal implementation**

In `locator.py`, add `session_placement` immediately before `build_sessions`:

```python
def session_placement(members, rep, proc_table, tmux_index, tty_pane_idx):
    """Place a session on the pane its real claude TUI holds (claude-anchored).

    members: this session's tagged procs (parse_processes output).
    rep: the structural leader proc (resolve_roles' leader_pid), used only for
         iTerm/Apple-Terminal env-marker fallback.
    Returns {leader_pid, pane, host, tty, pane_live, tmux}.
    """
    # Find the session's claude TUI: walk up from each tagged member; prefer a
    # candidate that has a tty (a live TUI on a terminal).
    tui = None
    for m in members:
        cand = nearest_claude_ancestor(m["pid"], proc_table)
        if cand is None:
            continue
        if proc_table.get(cand, {}).get("tty"):
            tui = cand
            break
        tui = tui or cand

    if tui is None:
        # Orphaned stragglers (detached children whose TUI has exited): do NOT
        # trust their stale TMUX_PANE env. Structural leader, no live pane.
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

Then modify `build_sessions`. Change the signature and, inside the per-session loop, branch on `proc_table`. Replace the existing function (`locator.py:191-244`) with:

```python
def build_sessions(procs, ppid_map, tmux_index, cwd_fn=cwd_of, proc_table=None):
    """Assemble one record per session (see spec for schema).

    When proc_table is provided, placement is claude-anchored (the pane comes
    from the session's real claude TUI, not from a tagged child's env). When
    absent, the legacy env-based placement is used (SP1 behavior / unit fixtures).
    """
    roles = resolve_roles(procs, ppid_map)
    by_pid = {p["pid"]: p for p in procs}
    members_by_sid = {}
    for p in procs:
        members_by_sid.setdefault(p["session_id"], []).append(p)
    tty_pane_idx = tty_to_pane_index(tmux_index) if proc_table else {}

    sessions = []
    for sid, role in roles.items():
        rep = by_pid[role["leader_pid"]]
        if proc_table:
            place = session_placement(members_by_sid[sid], rep, proc_table,
                                      tmux_index, tty_pane_idx)
        else:
            place = _legacy_placement(rep, tmux_index)
        sessions.append(
            {
                "session_id": sid,
                "role": role["role"],
                "parent_session_id": role["parent_session_id"],
                "pane": place["pane"],
                "host": place["host"],
                "tty": place["tty"],
                "cwd": cwd_fn(place["leader_pid"]),
                "leader_pid": place["leader_pid"],
                "pane_live": place["pane_live"],
                "tmux": place["tmux"],
            }
        )
    sessions.sort(key=lambda s: (s["pane"] or "~", s["session_id"]))
    return sessions


def _legacy_placement(rep, tmux_index):
    """SP1 env-based placement (used when no proc_table is supplied)."""
    pane = host = tty = tmux_meta = None
    pane_live = True
    if rep.get("tmux_pane") and rep.get("tmux_socket"):
        socket = rep["tmux_socket"]
        pane = f"tmux:{socket}:{rep['tmux_pane']}"
        host = "tmux"
        pinfo = tmux_index.get((socket, rep["tmux_pane"]))
        if pinfo:
            tty = pinfo["tty"]
            tmux_meta = {"socket": socket, "session": pinfo["tmux_session"],
                         "window": pinfo["tmux_window"], "active": pinfo["active"]}
        else:
            tty = rep.get("tty")
            pane_live = False
    elif rep.get("iterm_session_id"):
        pane = f"iterm:{rep['iterm_session_id']}"
        host = "iterm"
        tty = rep.get("tty")
    elif rep.get("term_session_id"):
        pane = f"term:{rep['term_session_id']}"
        host = "apple-terminal"
        tty = rep.get("tty")
    else:
        tty = rep.get("tty")
    return {"leader_pid": rep["pid"], "pane": pane, "host": host, "tty": tty,
            "pane_live": pane_live, "tmux": tmux_meta}
```

Finally, wire `proc_table` into the impure `gather_sessions` (`locator.py:334-340`):

```python
def gather_sessions():
    """Live scan -> assembled session records (the impure top-level)."""
    ps_output = _run(["ps", "-E", "-ww", "-o", "pid=,ppid=,tty=,command=", "-ax"])
    procs = parse_processes(ps_output, self_pid=os.getpid())
    ppid_map = build_ppid_map(ps_output)
    proc_table = build_process_table(ps_output)
    tmux_index = tmux_pane_index()
    return build_sessions(procs, ppid_map, tmux_index, proc_table=proc_table)
```

- [ ] **Step 4: Run the new test, then the full suite**

Run: `python3 session-manager/tests/test_locator.py TestClaudeAnchoredPlacement -v`
Expected: PASS (4 tests)

Run: `python3 session-manager/tests/test_locator.py -v`
Expected: PASS — all prior 29 tests still green (they pass no `proc_table` → `_legacy_placement`), plus the new classes from Tasks 1-4.

- [ ] **Step 5: Commit**

```bash
git add session-manager/scripts/locator.py session-manager/tests/test_locator.py
git commit -m "feat(locator): claude-anchored placement — pane from the TUI's tty, not child env"
```

---

### Task 5: `fork-active-pane.sh` friendly no-transcript message

**Files:**
- Modify: `session-manager/scripts/fork-active-pane.sh` (the fork-failure branch, ~lines 76-86)
- Test: `session-manager/tests/test-fork-active-pane.sh` (add one case)

**Interfaces:**
- Consumes: the existing shimmed-fork test harness (`FAP_FORK`, `FORK_RC`) in `test-fork-active-pane.sh`.
- Produces: no interface change; on a fork failure whose stderr contains `no transcript found`, the tmux status-line message becomes `No saved conversation in this pane yet — nothing to fork.`; all other failures keep `Fork failed: <first line>`. Exit code stays 1.

- [ ] **Step 1: Write the failing test**

The existing fake fork emits `boom` on failure. Add a way to emit custom stderr and a new case. In `session-manager/tests/test-fork-active-pane.sh`, replace the fake-fork heredoc (lines 28-34) with one that honors an optional `FORK_ERR`:

```bash
FAKE_FORK="$TMP/fork.sh"
cat > "$FAKE_FORK" <<'SH'
#!/bin/bash
argf="${FORK_ARGS_OUT:-}"
[ -n "$argf" ] && echo "$@" > "$argf"
if [ "${FORK_RC:-0}" -ne 0 ]; then echo "${FORK_ERR:-boom}" >&2; exit "${FORK_RC}"; fi
echo "${FORK_ID-sm-test01}"
SH
chmod +x "$FAKE_FORK"
```

Then add, before the `echo "----"` summary (after Case 7, ~line 78):

```bash
# Case 8: fork fails with a "no transcript" error -> friendly status message, exit 1.
err=$(TMUX="/private/tmp/tmux-501/default,1,1" LOC_OUT='{"session_id":"abc","tty":"t"}' LOC_RC=0 \
      FORK_RC=1 FORK_ERR="Error: no transcript found for session abc in any project." \
      run "%5" 2>&1); rc=$?
ok "$rc" "1" "no-transcript: exit 1"
case "$err" in
  *"No saved conversation in this pane yet"*) ok "yes" "yes" "no-transcript: friendly message shown" ;;
  *) ok "no" "yes" "no-transcript: friendly message shown" ;;
esac
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash session-manager/tests/test-fork-active-pane.sh`
Expected: FAIL — the `no-transcript: friendly message shown` assertion fails (current code prints `Fork failed: Error: no transcript found…`). `PASS`/`FAIL` counter shows 1 failure.

- [ ] **Step 3: Write minimal implementation**

In `session-manager/scripts/fork-active-pane.sh`, replace the failure branch (currently ~lines 81-86):

```bash
else
    notify "Fork failed: $(head -1 "$ERRF" 2>/dev/null)"
    cat "$ERRF" >&2 2>/dev/null || true
    rm -f "$ERRF"
    exit 1
fi
```

with:

```bash
else
    if grep -q "no transcript found" "$ERRF" 2>/dev/null; then
        notify "No saved conversation in this pane yet — nothing to fork."
    else
        notify "Fork failed: $(head -1 "$ERRF" 2>/dev/null)"
    fi
    cat "$ERRF" >&2 2>/dev/null || true
    rm -f "$ERRF"
    exit 1
fi
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bash session-manager/tests/test-fork-active-pane.sh`
Expected: PASS — `PASS=13 FAIL=0` (the prior 11 + the 2 new assertions).

- [ ] **Step 5: Commit**

```bash
git add session-manager/scripts/fork-active-pane.sh session-manager/tests/test-fork-active-pane.sh
git commit -m "feat(session-manager): friendly no-transcript message in fork-active-pane.sh"
```

---

### Task 6: Docs, version bump, and live verification

**Files:**
- Modify: `session-manager/CLAUDE.md` (locator.py section — note claude-anchored resolution)
- Modify: `docs/superpowers/session-locator-roadmap.md` (add SP2.1 row / mark done)
- Modify: `session-manager/.claude-plugin/plugin.json` (version bump via script)

- [ ] **Step 1: Update `session-manager/CLAUDE.md`**

In the `### locator.py` section, add a sentence after the "How it works" paragraph:

```markdown
Resolution is **claude-anchored**: a session's pane and `leader_pid` come from its
real `claude` TUI process (found by walking up from a tagged child via
`nearest_claude_ancestor`), and the pane is derived from that TUI's tty — not from
a `TMUX_PANE` env value on a possibly-detached child. This prevents MCP-server
children from being reported as the leader and prevents detached stragglers from
"ghosting" a session onto a pane its TUI does not occupy (SP2.1).
```

- [ ] **Step 2: Update the roadmap index**

In `docs/superpowers/session-locator-roadmap.md`, add a row to the status table under SP2:

```markdown
| SP2.1 | Locator resolution hardening (claude-anchored) | ✅ Done, merged | `specs/2026-07-06-session-locator-sp2.1-locator-hardening-design.md` | `plans/2026-07-06-session-locator-sp2.1.md` |
```

- [ ] **Step 3: Run both full suites**

Run: `python3 session-manager/tests/test_locator.py -v`
Expected: PASS (29 original + new classes; 0 failures)

Run: `bash session-manager/tests/test-fork-active-pane.sh`
Expected: `PASS=13 FAIL=0`

- [ ] **Step 4: Live smoke check (macOS, real sessions)**

Run: `python3 session-manager/scripts/locator.py list`
Expected: interactive records now report `leader_pid` pointing at `claude` processes (verify one against `ps -p <leader_pid> -o command=` showing `claude…`, not `node …-mcp`). No session should appear on a pane whose live TUI belongs to a different session.

Run (pick a pane with a known single conversation): `python3 session-manager/scripts/locator.py resolve --pane tmux:default:%<N>`
Expected: single object whose `session_id` is that pane's real conversation and whose `leader_pid` is a `claude` process.

- [ ] **Step 5: Version bump + commit**

```bash
./scripts/bump-plugin.sh session-manager patch
git add session-manager/CLAUDE.md docs/superpowers/session-locator-roadmap.md \
        session-manager/.claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "docs(session-manager): SP2.1 claude-anchored resolution; bump version"
```

---

## Self-Review

**Spec coverage:**
- §1 Leader = nearest claude ancestor → Task 2 (`nearest_claude_ancestor`) + Task 4 (`session_placement` upgrades leader). Fallback for orphans → Task 4 (`tui is None` branch, structural leader). ✓
- §2 Pane from TUI tty, not child env → Task 3 (`tty_to_pane_index`) + Task 4 (`session_placement` tmux branch; orphan → pane None). ✓
- §3 New pure functions → Tasks 1-3 + `session_placement` (Task 4). ✓
- §4 Tiebreak & contract preserved → `cmd_resolve`/`pick_foreground_winner` untouched; verified by unchanged `TestForegroundTiebreak`/`TestResolveTiebreakWiring` in Task 4 Step 4 full-suite run. ✓
- §3 defect (friendly message) → Task 5. ✓
- §5 Testing (MCP-as-leader, ghost, orphan, unit fixtures; keep 29 green) → Tasks 1-4 test classes + Task 4 Step 4. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step shows complete code. ✓

**Type consistency:** `proc_table` value shape `{ppid, tty, command}` is identical across Tasks 1, 2, 4. `session_placement` returns the exact 6 keys `build_sessions` consumes. `tty_to_pane_index` returns `tty -> (socket, pane_id)`, consumed as `socket, pane_id = tty_pane_idx[tty]` in `session_placement`. `RE_CLAUDE` / `nearest_claude_ancestor` names consistent across Tasks 2 and 4. ✓
