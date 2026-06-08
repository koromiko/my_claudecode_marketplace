# Session Locator SP1 (Indexer + Resolver Core) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a macOS-only, read-only, pull-based CLI that maps running Claude Code sessions to terminal panes by scanning process environments, exposing `list` and `resolve` over a stable JSON record schema.

**Architecture:** A single Python script (`locator.py`) split into *pure functions* (parse `ps`/`tmux`/`lsof` text, resolve session roles by process ancestry, assemble records) plus *thin impure wrappers* that shell out. Purity is for testability: the four tricky real-world cases become deterministic fixtures. No daemon, no hooks, no persisted state — every query re-scans live processes.

**Tech Stack:** Python 3 stdlib only (`argparse`, `glob`, `json`, `os`, `re`, `subprocess`, `unittest`). macOS `ps -E`, `tmux -L`, `lsof`.

**Spec:** `docs/superpowers/specs/2026-06-07-session-locator-sp1-design.md`

**Reference:** a working spike exists at `session-manager/scripts/locator.py`. This plan rebuilds it test-first into the hardened form; the engineer overwrites the spike.

---

## Conventions for this plan

- **Run tests with:** `python3 session-manager/tests/test_locator.py -v` (run from repo root). The test file inserts `../scripts` onto `sys.path` and calls `unittest.main()`.
- **Repo root:** `/Users/sthuang/Project/my_claudecode_marketplace`. All paths below are relative to it.
- **Branch:** work happens on the `session-locator` branch (already created).
- These UUIDs are reused across tests (define once, in Task 1):
  - `UUID_A = "83ae8ca6-0000-0000-0000-000000000001"` (interactive)
  - `UUID_B = "c392555a-0000-0000-0000-000000000002"` (child of A)
  - `UUID_C = "52e3b60e-0000-0000-0000-000000000003"` (one-session-two-panes)
  - `UUID_D = "0f2cf83f-0000-0000-0000-000000000004"` (second socket)

---

## Task 1: Process scanner — `parse_processes` + module skeleton

**Files:**
- Create/overwrite: `session-manager/scripts/locator.py`
- Create: `session-manager/tests/test_locator.py`

- [ ] **Step 1: Write the failing test**

Create `session-manager/tests/test_locator.py`:

```python
#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import locator  # noqa: E402

UUID_A = "83ae8ca6-0000-0000-0000-000000000001"
UUID_B = "c392555a-0000-0000-0000-000000000002"
UUID_C = "52e3b60e-0000-0000-0000-000000000003"
UUID_D = "0f2cf83f-0000-0000-0000-000000000004"

DEFAULT_SOCK = "/private/tmp/tmux-501/default,2611,7"


def pline(pid, ppid, tty, **env):
    """Build one `ps -E` output line: pid ppid tty <command + environ>."""
    env_str = " ".join(f"{k}={v}" for k, v in env.items())
    return f"{pid} {ppid} {tty} node /usr/bin/claude {env_str}"


class TestParseProcesses(unittest.TestCase):
    def test_extracts_markers_and_normalizes_tty(self):
        out = pline(
            2001, 1900, "??",
            CLAUDE_CODE_SESSION_ID=UUID_A,
            TMUX_PANE="%86",
            TMUX=DEFAULT_SOCK,
            ITERM_SESSION_ID="w0t6p0:GUID",
            TERM_SESSION_ID="w0t6p0:GUID",
            TERM_PROGRAM="tmux",
        )
        procs = locator.parse_processes(out)
        self.assertEqual(len(procs), 1)
        p = procs[0]
        self.assertEqual(p["pid"], 2001)
        self.assertEqual(p["ppid"], 1900)
        self.assertIsNone(p["tty"])  # "??" -> None
        self.assertEqual(p["session_id"], UUID_A)
        self.assertEqual(p["tmux_pane"], "%86")
        self.assertEqual(p["tmux_socket"], "default")  # basename of socket path

    def test_excludes_scanner_noise_without_real_uuid(self):
        # A grep/ps line whose command contains the literal regex text but no
        # real uuid must NOT be parsed as a session.
        noise = ("9999 8888 ttys999 grep -E "
                 "CLAUDE_CODE_SESSION_ID=[0-9a-fA-F]{8} TMUX_PANE=[^ ]+")
        real = pline(2001, 1900, "ttys016",
                     CLAUDE_CODE_SESSION_ID=UUID_A, TMUX_PANE="%86", TMUX=DEFAULT_SOCK)
        procs = locator.parse_processes(noise + "\n" + real)
        self.assertEqual([p["session_id"] for p in procs], [UUID_A])

    def test_excludes_self_pid(self):
        out = pline(4242, 1, "ttys016", CLAUDE_CODE_SESSION_ID=UUID_A)
        self.assertEqual(locator.parse_processes(out, self_pid=4242), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 session-manager/tests/test_locator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'locator'` or `AttributeError: module 'locator' has no attribute 'parse_processes'`.

- [ ] **Step 3: Write minimal implementation**

Overwrite `session-manager/scripts/locator.py` with the module skeleton + `parse_processes`:

```python
#!/usr/bin/env python3
"""
locator.py — Claude Code session <-> terminal-pane indexer/resolver (SP1).

macOS-only, read-only, pull-based: every query re-scans live processes, so the
answer is always ground truth and never stale. No daemon, no hooks, no state.

Design: pure functions (parse_*, resolve_roles, build_sessions) take injected
command output for testability; thin wrappers (_run, *_index, cwd_of, gather_*)
are the only impure code. See docs/superpowers/specs/2026-06-07-session-locator-sp1-design.md
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys

# Strict marker formats so a scanner's own ps/grep command line never parses as
# a real record (it carries no real session uuid).
RE_SESSION = re.compile(
    r"CLAUDE_CODE_SESSION_ID=([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)
RE_TMUX_PANE = re.compile(r"\bTMUX_PANE=(%\d+)")
RE_TMUX = re.compile(r"\bTMUX=(\S+)")
RE_ITERM = re.compile(r"\bITERM_SESSION_ID=(\S+)")
RE_TERM_SESSION = re.compile(r"\bTERM_SESSION_ID=(\S+)")
RE_TERM_PROGRAM = re.compile(r"\bTERM_PROGRAM=(\S+)")


def parse_processes(ps_output, self_pid=None):
    """Parse `ps -E -ww -o pid=,ppid=,tty=,command=` output into claude records.

    Returns a list of dicts; only processes carrying a valid CLAUDE_CODE_SESSION_ID
    are included. self_pid (if given) is skipped (the scanner itself).
    """
    procs = []
    for line in ps_output.splitlines():
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        pid_s, ppid_s, tty, command = parts
        try:
            pid, ppid = int(pid_s), int(ppid_s)
        except ValueError:
            continue
        if self_pid is not None and pid == self_pid:
            continue
        m = RE_SESSION.search(command)
        if not m:
            continue
        tmux_env = RE_TMUX.search(command)
        socket = None
        if tmux_env:
            socket = os.path.basename(tmux_env.group(1).split(",")[0])
        pane = RE_TMUX_PANE.search(command)
        iterm = RE_ITERM.search(command)
        term_s = RE_TERM_SESSION.search(command)
        term_p = RE_TERM_PROGRAM.search(command)
        procs.append(
            {
                "pid": pid,
                "ppid": ppid,
                "tty": None if tty == "??" else tty.replace("/dev/", ""),
                "session_id": m.group(1),
                "tmux_pane": pane.group(1) if pane else None,
                "tmux_socket": socket,
                "iterm_session_id": iterm.group(1) if iterm else None,
                "term_session_id": term_s.group(1) if term_s else None,
                "term_program": term_p.group(1) if term_p else None,
            }
        )
    return procs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 session-manager/tests/test_locator.py -v`
Expected: PASS (3 tests in TestParseProcesses).

- [ ] **Step 5: Commit**

```bash
git add session-manager/scripts/locator.py session-manager/tests/test_locator.py
git commit -m "feat(session-manager): locator process scanner with marker parsing"
```

---

## Task 2: Global pid→ppid map — `build_ppid_map`

**Files:**
- Modify: `session-manager/scripts/locator.py`
- Test: `session-manager/tests/test_locator.py`

- [ ] **Step 1: Write the failing test**

Append this class to `session-manager/tests/test_locator.py` (before the `if __name__` block):

```python
class TestBuildPpidMap(unittest.TestCase):
    def test_maps_all_processes_not_just_claude(self):
        out = "\n".join([
            "1900 1800 ttys016 -zsh",                 # plain shell, no session
            pline(2001, 1900, "??", CLAUDE_CODE_SESSION_ID=UUID_A),
            "garbage line",                             # ignored
        ])
        m = locator.build_ppid_map(out)
        self.assertEqual(m[1900], 1800)   # non-claude proc present (ancestry needs it)
        self.assertEqual(m[2001], 1900)
        self.assertNotIn("garbage", m)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 session-manager/tests/test_locator.py -v`
Expected: FAIL — `AttributeError: module 'locator' has no attribute 'build_ppid_map'`.

- [ ] **Step 3: Write minimal implementation**

Add to `locator.py` after `parse_processes`:

```python
def build_ppid_map(ps_output):
    """pid -> ppid for ALL processes in the ps output (not just claude-tagged).

    Ancestry walks must traverse non-claude processes (shells, node wrappers), so
    this covers every line, unlike parse_processes.
    """
    m = {}
    for line in ps_output.splitlines():
        parts = line.split(None, 2)
        if len(parts) < 2:
            continue
        try:
            pid, ppid = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        m[pid] = ppid
    return m
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 session-manager/tests/test_locator.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add session-manager/scripts/locator.py session-manager/tests/test_locator.py
git commit -m "feat(session-manager): locator global pid-ppid map for ancestry walks"
```

---

## Task 3: tmux pane index — socket-qualified parsing

**Files:**
- Modify: `session-manager/scripts/locator.py`
- Test: `session-manager/tests/test_locator.py`

- [ ] **Step 1: Write the failing test**

Append to `session-manager/tests/test_locator.py`:

```python
class TestParseTmuxPanes(unittest.TestCase):
    SAMPLE = "%86\t/dev/ttys016\t1900\twork\t3\t1\n%0\t/dev/ttys020\t1700\tmisc\t0\t0"

    def test_parses_and_keys_by_socket_and_pane(self):
        idx = locator.parse_tmux_panes("default", self.SAMPLE)
        self.assertEqual(
            idx[("default", "%86")],
            {"tty": "ttys016", "pane_pid": 1900, "tmux_session": "work",
             "tmux_window": "3", "active": True},
        )
        self.assertFalse(idx[("default", "%0")]["active"])

    def test_same_pane_id_on_two_sockets_is_distinct(self):
        # The multi-socket fix: %0 on two sockets must not collide.
        a = locator.parse_tmux_panes("default", "%0\t/dev/ttys020\t1\ts\t0\t1")
        b = locator.parse_tmux_panes("sm_e2e", "%0\t/dev/ttys099\t2\ts\t0\t1")
        merged = {**a, **b}
        self.assertEqual(merged[("default", "%0")]["tty"], "ttys020")
        self.assertEqual(merged[("sm_e2e", "%0")]["tty"], "ttys099")
        self.assertEqual(len(merged), 2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 session-manager/tests/test_locator.py -v`
Expected: FAIL — `AttributeError: module 'locator' has no attribute 'parse_tmux_panes'`.

- [ ] **Step 3: Write minimal implementation**

Add to `locator.py`:

```python
TMUX_FMT = (
    "#{pane_id}\t#{pane_tty}\t#{pane_pid}\t#{session_name}\t"
    "#{window_index}\t#{pane_active}"
)


def parse_tmux_panes(socket_name, list_panes_output):
    """Parse `tmux list-panes -a -F TMUX_FMT` output, keyed by (socket, pane_id)."""
    panes = {}
    for line in list_panes_output.splitlines():
        cols = line.split("\t")
        if len(cols) != 6:
            continue
        pane_id, tty, pane_pid, sess, win, active = cols
        try:
            pane_pid_int = int(pane_pid)
        except ValueError:
            pane_pid_int = None
        panes[(socket_name, pane_id)] = {
            "tty": tty.replace("/dev/", ""),
            "pane_pid": pane_pid_int,
            "tmux_session": sess,
            "tmux_window": win,
            "active": active == "1",
        }
    return panes
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 session-manager/tests/test_locator.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add session-manager/scripts/locator.py session-manager/tests/test_locator.py
git commit -m "feat(session-manager): locator socket-qualified tmux pane parsing"
```

---

## Task 4: Role resolution by process ancestry — `resolve_roles`

This is the core correctness logic: which session in a pane is `interactive` vs a `child`.

**Files:**
- Modify: `session-manager/scripts/locator.py`
- Test: `session-manager/tests/test_locator.py`

- [ ] **Step 1: Write the failing test**

Append to `session-manager/tests/test_locator.py`:

```python
class TestResolveRoles(unittest.TestCase):
    def test_child_session_demoted_to_child_of_interactive(self):
        # Case (b): two sessions in one pane. B (pid 2002) is spawned by A (pid 2001).
        procs = [
            {"pid": 2001, "ppid": 1900, "session_id": UUID_A, "tmux_pane": "%86"},
            {"pid": 2002, "ppid": 2001, "session_id": UUID_B, "tmux_pane": "%86"},
        ]
        ppid_map = {2001: 1900, 2002: 2001, 1900: 1800}
        roles = locator.resolve_roles(procs, ppid_map)
        self.assertEqual(roles[UUID_A]["role"], "interactive")
        self.assertIsNone(roles[UUID_A]["parent_session_id"])
        self.assertEqual(roles[UUID_A]["leader_pid"], 2001)
        self.assertEqual(roles[UUID_B]["role"], "child")
        self.assertEqual(roles[UUID_B]["parent_session_id"], UUID_A)
        self.assertEqual(roles[UUID_B]["leader_pid"], 2002)

    def test_one_session_two_panes_leader_is_topmost(self):
        # Case (a): session A appears in procs tagged %5 (leader) and %6 (re-parented
        # child member of the SAME session). Leader is the topmost member.
        procs = [
            {"pid": 1001, "ppid": 900, "session_id": UUID_C, "tmux_pane": "%5"},
            {"pid": 1002, "ppid": 1001, "session_id": UUID_C, "tmux_pane": "%6"},
        ]
        ppid_map = {1001: 900, 1002: 1001, 900: 800}
        roles = locator.resolve_roles(procs, ppid_map)
        self.assertEqual(roles[UUID_C]["leader_pid"], 1001)  # the %5 one
        self.assertEqual(roles[UUID_C]["role"], "interactive")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 session-manager/tests/test_locator.py -v`
Expected: FAIL — `AttributeError: module 'locator' has no attribute 'resolve_roles'`.

- [ ] **Step 3: Write minimal implementation**

Add to `locator.py`:

```python
def resolve_roles(procs, ppid_map):
    """Assign each session a role (interactive|child) and its leader pid.

    Leader of a session = its topmost process (whose parent is not in the same
    session group). A session is `child` if its leader's ancestry reaches another
    claude session before the top; otherwise `interactive`.
    """
    by_session = {}
    for p in procs:
        by_session.setdefault(p["session_id"], []).append(p)
    session_of_pid = {p["pid"]: p["session_id"] for p in procs}

    roles = {}
    for sid, members in by_session.items():
        pids = {p["pid"] for p in members}
        leaders = [p for p in members if p["ppid"] not in pids]
        leader = min(leaders or members, key=lambda p: p["pid"])

        parent_session = None
        cur = leader["ppid"]
        seen = set()
        while cur and cur not in seen:
            seen.add(cur)
            anc_sid = session_of_pid.get(cur)
            if anc_sid and anc_sid != sid:
                parent_session = anc_sid
                break
            cur = ppid_map.get(cur)

        roles[sid] = {
            "leader_pid": leader["pid"],
            "role": "child" if parent_session else "interactive",
            "parent_session_id": parent_session,
        }
    return roles
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 session-manager/tests/test_locator.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add session-manager/scripts/locator.py session-manager/tests/test_locator.py
git commit -m "feat(session-manager): locator role resolution by process ancestry"
```

---

## Task 5: Record assembly — `build_sessions`

**Files:**
- Modify: `session-manager/scripts/locator.py`
- Test: `session-manager/tests/test_locator.py`

- [ ] **Step 1: Write the failing test**

Append to `session-manager/tests/test_locator.py`:

```python
class TestBuildSessions(unittest.TestCase):
    def _full_proc(self, pid, ppid, sid, pane, socket="default", tty=None,
                   iterm=None, term=None):
        return {"pid": pid, "ppid": ppid, "session_id": sid, "tmux_pane": pane,
                "tmux_socket": socket if pane else None, "tty": tty,
                "iterm_session_id": iterm, "term_session_id": term}

    def test_tmux_record_enriched_and_pane_live(self):
        procs = [self._full_proc(2001, 1900, UUID_A, "%86")]
        ppid_map = {2001: 1900, 1900: 1800}
        tmux_index = {("default", "%86"): {
            "tty": "ttys016", "pane_pid": 1900, "tmux_session": "work",
            "tmux_window": "3", "active": True}}
        out = locator.build_sessions(procs, ppid_map, tmux_index,
                                     cwd_fn=lambda pid: "/tmp/x")
        self.assertEqual(len(out), 1)
        r = out[0]
        self.assertEqual(r["pane"], "tmux:default:%86")
        self.assertEqual(r["host"], "tmux")
        self.assertEqual(r["tty"], "ttys016")       # authoritative from tmux
        self.assertEqual(r["cwd"], "/tmp/x")
        self.assertTrue(r["pane_live"])
        self.assertEqual(r["tmux"]["session"], "work")
        self.assertEqual(r["role"], "interactive")

    def test_detached_straggler_flagged_not_live(self):
        procs = [self._full_proc(2001, 1900, UUID_A, "%99", tty="ttys016")]
        out = locator.build_sessions(procs, {2001: 1900}, {},  # empty index
                                     cwd_fn=lambda pid: None)
        r = out[0]
        self.assertEqual(r["pane"], "tmux:default:%99")
        self.assertFalse(r["pane_live"])     # pane not in index
        self.assertEqual(r["tty"], "ttys016")  # falls back to process tty

    def test_iterm_host_when_no_tmux(self):
        procs = [self._full_proc(3001, 2900, UUID_A, None, tty="ttys030",
                                 iterm="w0t6p0:GUID")]
        out = locator.build_sessions(procs, {3001: 2900}, {},
                                     cwd_fn=lambda pid: "/tmp/y")
        r = out[0]
        self.assertEqual(r["pane"], "iterm:w0t6p0:GUID")
        self.assertEqual(r["host"], "iterm")
        self.assertTrue(r["pane_live"])  # non-tmux -> always live (leader alive)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 session-manager/tests/test_locator.py -v`
Expected: FAIL — `AttributeError: module 'locator' has no attribute 'build_sessions'`.

- [ ] **Step 3: Write minimal implementation**

Add to `locator.py`:

```python
def _run(cmd):
    """Run a command, return stdout str or '' on any failure. Never raises."""
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=10, check=False
        ).stdout
    except Exception:
        return ""


def cwd_of(pid):
    """Working directory of pid via lsof (robust against spaces). None on failure."""
    out = _run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"])
    for line in out.splitlines():
        if line.startswith("n"):
            return line[1:]
    return None


def build_sessions(procs, ppid_map, tmux_index, cwd_fn=cwd_of):
    """Assemble one record per session (see spec for schema)."""
    roles = resolve_roles(procs, ppid_map)
    by_pid = {p["pid"]: p for p in procs}

    sessions = []
    for sid, role in roles.items():
        rep = by_pid[role["leader_pid"]]
        pane = host = tty = tmux_meta = None
        pane_live = True

        if rep.get("tmux_pane") and rep.get("tmux_socket"):
            socket = rep["tmux_socket"]
            pane = f"tmux:{socket}:{rep['tmux_pane']}"
            host = "tmux"
            pinfo = tmux_index.get((socket, rep["tmux_pane"]))
            if pinfo:
                tty = pinfo["tty"]
                tmux_meta = {
                    "socket": socket,
                    "session": pinfo["tmux_session"],
                    "window": pinfo["tmux_window"],
                    "active": pinfo["active"],
                }
            else:
                tty = rep.get("tty")
                pane_live = False  # detached straggler: pane gone
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

        sessions.append(
            {
                "session_id": sid,
                "role": role["role"],
                "parent_session_id": role["parent_session_id"],
                "pane": pane,
                "host": host,
                "tty": tty,
                "cwd": cwd_fn(role["leader_pid"]),
                "leader_pid": role["leader_pid"],
                "pane_live": pane_live,
                "tmux": tmux_meta,
            }
        )
    sessions.sort(key=lambda s: (s["pane"] or "~", s["session_id"]))
    return sessions
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 session-manager/tests/test_locator.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add session-manager/scripts/locator.py session-manager/tests/test_locator.py
git commit -m "feat(session-manager): locator record assembly with tty/cwd/pane_live"
```

---

## Task 6: CLI — `list` and `resolve` selectors + gather wrappers

**Files:**
- Modify: `session-manager/scripts/locator.py`
- Test: `session-manager/tests/test_locator.py`

- [ ] **Step 1: Write the failing test**

Append to `session-manager/tests/test_locator.py`:

```python
class TestSelector(unittest.TestCase):
    SESSIONS = [
        {"session_id": UUID_A, "role": "interactive", "pane": "tmux:default:%86",
         "host": "tmux", "tty": "ttys016"},
        {"session_id": UUID_B, "role": "child", "pane": "tmux:default:%86",
         "host": "tmux", "tty": "ttys016"},
        {"session_id": UUID_D, "role": "interactive", "pane": "iterm:w0t6p0:GUID",
         "host": "iterm", "tty": "ttys030"},
    ]

    def _filter(self, **kw):
        ns = locator.argparse.Namespace(pane=None, tty=None, session=None)
        for k, v in kw.items():
            setattr(ns, k, v)
        return [s for s in self.SESSIONS if locator.match_selector(s, ns)]

    def test_pane_full_address_returns_interactive_only(self):
        hits = self._filter(pane="tmux:default:%86")
        self.assertEqual([h["session_id"] for h in hits], [UUID_A])

    def test_pane_bare_id_matches_across_sockets_interactive_only(self):
        hits = self._filter(pane="%86")
        self.assertEqual([h["session_id"] for h in hits], [UUID_A])

    def test_tty_returns_interactive_only(self):
        hits = self._filter(tty="/dev/ttys016")  # accepts /dev/ prefix too
        self.assertEqual([h["session_id"] for h in hits], [UUID_A])

    def test_session_selector_returns_child_too(self):
        hits = self._filter(session=UUID_B)  # addresses a specific session, role-agnostic
        self.assertEqual([h["session_id"] for h in hits], [UUID_B])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 session-manager/tests/test_locator.py -v`
Expected: FAIL — `AttributeError: module 'locator' has no attribute 'match_selector'`.

- [ ] **Step 3: Write minimal implementation**

Add to `locator.py`:

```python
def match_selector(s, args):
    """True if session record s matches the resolve selector in args.

    --session is role-agnostic (addresses a specific session). --pane / --tty
    return only the interactive session for that pane.
    """
    if args.session:
        return s["session_id"] == args.session
    if args.tty:
        want = args.tty.replace("/dev/", "")
        return s["tty"] == want and s["role"] == "interactive"
    if args.pane:
        if s["role"] != "interactive":
            return False
        p = args.pane
        if p.startswith(("tmux:", "iterm:", "term:")):
            return s["pane"] == p
        if p.startswith("%"):  # bare pane id: match across all sockets
            return s["host"] == "tmux" and bool(s["pane"]) and s["pane"].endswith(
                ":" + p
            )
        return False
    return False


def list_tmux_sockets():
    """All tmux socket basenames for this user (plus the one from $TMUX)."""
    sockets = set()
    for path in glob.glob(f"/private/tmp/tmux-{os.getuid()}/*"):
        sockets.add(os.path.basename(path))
    env_tmux = os.environ.get("TMUX")
    if env_tmux:
        sockets.add(os.path.basename(env_tmux.split(",")[0]))
    return sorted(sockets)


def tmux_pane_index():
    """(socket, pane_id) -> pane meta across ALL tmux sockets. {} if none."""
    index = {}
    for socket in list_tmux_sockets():
        out = _run(["tmux", "-L", socket, "list-panes", "-a", "-F", TMUX_FMT])
        index.update(parse_tmux_panes(socket, out))
    return index


def gather_sessions():
    """Live scan -> assembled session records (the impure top-level)."""
    ps_output = _run(["ps", "-E", "-ww", "-o", "pid=,ppid=,tty=,command=", "-ax"])
    procs = parse_processes(ps_output, self_pid=os.getpid())
    ppid_map = build_ppid_map(ps_output)
    tmux_index = tmux_pane_index()
    return build_sessions(procs, ppid_map, tmux_index)


def cmd_list(_args):
    print(json.dumps(gather_sessions(), indent=2))


def cmd_resolve(args):
    sessions = gather_sessions()
    hits = [s for s in sessions if match_selector(s, args)]
    if not hits:
        print(json.dumps([], indent=2))
        sys.exit(1)
    print(json.dumps(hits[0] if len(hits) == 1 else hits, indent=2))


def main():
    ap = argparse.ArgumentParser(description="Claude Code session locator.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list all live Claude sessions with pane/tty/cwd")
    rp = sub.add_parser("resolve", help="resolve a session by pane / tty / session id")
    g = rp.add_mutually_exclusive_group(required=True)
    g.add_argument("--pane", help="tmux:<socket>:%%N | %%N | iterm:<guid> | term:<guid>")
    g.add_argument("--tty", help="e.g. /dev/ttys016 or ttys016")
    g.add_argument("--session", help="Claude session id (uuid)")

    args = ap.parse_args()
    if args.cmd == "list":
        cmd_list(args)
    elif args.cmd == "resolve":
        cmd_resolve(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 session-manager/tests/test_locator.py -v`
Expected: PASS (all classes).

- [ ] **Step 5: Live smoke test**

Run: `python3 session-manager/scripts/locator.py list`
Expected: a JSON array of the real sessions on the machine, each with a
socket-qualified `pane`, a `role`, and a `cwd`. Then resolve this very pane:

Run: `python3 session-manager/scripts/locator.py resolve --tty "$(tmux display-message -p '#{pane_tty}' 2>/dev/null || tty)"`
Expected: a single JSON object with `"role": "interactive"` whose `cwd` is the
current project directory. Exit code 0.

- [ ] **Step 6: Commit**

```bash
git add session-manager/scripts/locator.py session-manager/tests/test_locator.py
git commit -m "feat(session-manager): locator CLI list/resolve with multi-socket gather"
```

---

## Task 7: Docs + version bump

**Files:**
- Modify: `session-manager/CLAUDE.md`
- Modify (via script): `session-manager/.claude-plugin/plugin.json`

- [ ] **Step 1: Document the locator in `session-manager/CLAUDE.md`**

Add a new subsection under "Key Components" (after the `session-manager.sh` table).
Insert this exact markdown:

```markdown
### locator.py (session <-> pane indexer/resolver)

Read-only, pull-based tool (macOS) that maps running Claude Code sessions to
terminal panes by scanning process environments. No daemon, no state — every
query re-scans, so results are never stale. Foundation for focus adapters /
daemon / hooks (SP2-SP5); other tools consume its JSON contract.

CLI:
- `locator.py list` — JSON array, one record per live Claude session.
- `locator.py resolve --pane tmux:<socket>:%N | %N | iterm:<guid>` — the
  interactive session in that pane.
- `locator.py resolve --tty <tty>` — the interactive session on that tty.
- `locator.py resolve --session <uuid>` — that specific session (role-agnostic).

Record schema (the contract): `session_id`, `role` (interactive|child),
`parent_session_id`, `pane` (socket-qualified), `host`, `tty`, `cwd`,
`leader_pid`, `pane_live`, `tmux`. `resolve --pane/--tty` return only the
`interactive` record; `list` shows children too.

Design rationale: a running Claude process carries CLAUDE_CODE_SESSION_ID plus
its host pane id (TMUX_PANE / ITERM_SESSION_ID) in one environment, so the
session<->pane mapping is recoverable without UI scraping. Roles are resolved by
process ancestry (a session whose leader descends from another claude session is
a child). Pane ids are socket-qualified because they are not unique across tmux
servers. See docs/superpowers/specs/2026-06-07-session-locator-sp1-design.md.

Tests: `python3 session-manager/tests/test_locator.py -v`.
```

- [ ] **Step 2: Run the full test suite once more**

Run: `python3 session-manager/tests/test_locator.py -v`
Expected: PASS (all tests).

- [ ] **Step 3: Bump plugin version + clear cache**

Run: `./scripts/bump-plugin.sh session-manager minor`
Expected: `session-manager` `version` in `.claude-plugin/plugin.json` bumped (minor); cache cleared.

- [ ] **Step 4: Commit**

```bash
git add session-manager/CLAUDE.md session-manager/.claude-plugin/plugin.json
git commit -m "docs(session-manager): document locator tool and bump version"
```

---

## Self-Review

**Spec coverage** (each spec section → task):
- Record schema → Task 5 (assembly) + Task 1 (markers). All 10 fields produced. ✓
- `scan_processes` → Task 1. ✓
- `build_ppid_map` → Task 2. ✓
- `tmux_pane_index` (multi-socket) → Task 3 (parse) + Task 6 (enumeration). ✓
- `resolve_roles` ancestry (interactive vs child) → Task 4. ✓
- `build_sessions` (tty enrich, cwd, pane_live) → Task 5. ✓
- CLI `list` + `resolve` selector semantics (--pane/--tty interactive-only; --session role-agnostic) → Task 6. ✓
- Error handling (best-effort `_run`, never raises) → Task 5 (`_run`). ✓
- Four test fixtures: (a) one-session-two-panes → Task 4; (b) two-sessions-one-pane → Task 4; (c) same pane id two sockets → Task 3; (d) scanner self-noise → Task 1. ✓
- Deliverables: hardened locator.py (Tasks 1-6), test_locator.py (Tasks 1-6), CLAUDE.md (Task 7), version bump (Task 7). ✓
- Acceptance criteria: `list`/`resolve` verified live in Task 6 Step 5; fixtures in Tasks 1-6; no-crash via `_run`. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code; every run step shows expected output. ✓

**Type/name consistency:** `parse_processes`, `build_ppid_map`, `parse_tmux_panes`, `resolve_roles`, `build_sessions`, `match_selector`, `gather_sessions`, `tmux_pane_index`, `list_tmux_sockets`, `cwd_of`, `_run`, `TMUX_FMT` — names used in tests match definitions. Record keys (`session_id`, `role`, `parent_session_id`, `pane`, `host`, `tty`, `cwd`, `leader_pid`, `pane_live`, `tmux`) consistent between Task 5 implementation and Task 6 selector/tests. `resolve_roles` return keys (`leader_pid`, `role`, `parent_session_id`) consistent between Task 4 and Task 5 consumption. ✓

Note: Task 6's test references `locator.argparse.Namespace` — `argparse` is imported in `locator.py` (Task 1), so it is reachable as `locator.argparse`. ✓
