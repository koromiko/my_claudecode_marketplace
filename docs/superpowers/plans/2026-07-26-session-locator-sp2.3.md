# Session Locator SP2.3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `resolve --pane`/`--tty` return the real active session (not the throwaway pre-resume phantom) when one `claude --resume` TUI produces two colliding session ids on a pane.

**Architecture:** Add a pure helper `claude_pid_anchored_sids` (sibling of `on_tty_member_sids`) that selects the colliding sessions whose members directly carry `CLAUDE_PID == leader_pid`, then insert it as a new middle tier in `resolve_collision`, ordered between the foreground-pgid tier and the on-tty-presence tier. No placement change.

**Tech Stack:** Python 3 stdlib, `unittest`. All logic pure over injected `ps`/proc fixtures.

## Global Constraints

- Python 3.8+ stdlib only; no external deps.
- Do NOT modify `session_placement`, `parse_processes`, the 10-key record schema, or the `resolve` single/array/`[]`+exit-1 contract. This is a `resolve_collision`-only change plus one new helper.
- `claude_pid_anchored_sids` and `resolve_collision` must stay pure (operate only on injected `hits`/`procs`/`ps_output`; no OS calls).
- Preserve every existing test in `session-manager/tests/test_locator.py` green.
- Tier order in `resolve_collision` must be exactly: foreground pgid → CLAUDE_PID carriage → on-tty presence → ambiguity array.

---

### Task 1: `claude_pid_anchored_sids` helper

**Files:**
- Modify: `session-manager/scripts/locator.py` (add function immediately after `on_tty_member_sids`, ~line 466)
- Test: `session-manager/tests/test_locator.py` (add `TestClaudePidAnchoredSids` after `TestOnTtyMemberSids`, ~line 404)

**Interfaces:**
- Consumes: nothing new.
- Produces: `claude_pid_anchored_sids(hits, procs) -> set[str]` — the session ids among `hits` that have at least one member in `procs` whose `claude_pid` equals that session's `leader_pid`.

- [ ] **Step 1: Write the failing tests**

Add to `session-manager/tests/test_locator.py` after the `TestOnTtyMemberSids` class:

```python
class TestClaudePidAnchoredSids(unittest.TestCase):
    def _hit(self, sid, leader):
        return {"session_id": sid, "leader_pid": leader}

    def test_selects_session_whose_member_carries_claude_pid_of_its_tui(self):
        hits = [self._hit(UUID_OWNER, 2076), self._hit(UUID_STALE, 2076)]
        procs = [
            {"session_id": UUID_OWNER, "pid": 3100, "claude_pid": 2076},
            {"session_id": UUID_STALE, "pid": 2900, "claude_pid": None},
        ]
        self.assertEqual(
            locator.claude_pid_anchored_sids(hits, procs), {UUID_OWNER})

    def test_ignores_member_whose_claude_pid_mismatches_leader(self):
        hits = [self._hit(UUID_OWNER, 2076)]
        procs = [{"session_id": UUID_OWNER, "pid": 3100, "claude_pid": 9999}]
        self.assertEqual(locator.claude_pid_anchored_sids(hits, procs), set())

    def test_none_claude_pid_never_matches(self):
        hits = [self._hit(UUID_OWNER, 2076)]
        procs = [{"session_id": UUID_OWNER, "pid": 3100, "claude_pid": None}]
        self.assertEqual(locator.claude_pid_anchored_sids(hits, procs), set())

    def test_both_carriers_returns_both(self):
        hits = [self._hit(UUID_OWNER, 4973), self._hit(UUID_STALE, 4973)]
        procs = [
            {"session_id": UUID_OWNER, "pid": 5054, "claude_pid": 4973},
            {"session_id": UUID_STALE, "pid": 5090, "claude_pid": 4973},
        ]
        self.assertEqual(
            locator.claude_pid_anchored_sids(hits, procs),
            {UUID_OWNER, UUID_STALE})

    def test_empty_inputs(self):
        self.assertEqual(locator.claude_pid_anchored_sids([], []), set())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest session-manager.tests.test_locator.TestClaudePidAnchoredSids -v`
(from repo root; if the dotted path fails, `cd session-manager && python3 -m unittest tests.test_locator.TestClaudePidAnchoredSids -v`)
Expected: FAIL with `AttributeError: module 'locator' has no attribute 'claude_pid_anchored_sids'`.

- [ ] **Step 3: Write minimal implementation**

Add to `session-manager/scripts/locator.py` immediately after `on_tty_member_sids` (after line 465):

```python
def claude_pid_anchored_sids(hits, procs):
    """Session ids among `hits` with a member directly carrying CLAUDE_PID == that
    session's TUI (leader_pid) — a first-class TUI-ownership witness, distinct from
    ancestor-only reachability. Separates a `claude --resume` active session (whose
    tool shells carry CLAUDE_PID) from the throwaway pre-resume id (whose MCP servers
    carry none) when both anchor to the same TUI pid. Ties (both carry it) for the
    reused-TUI case, where the on-tty tier decides instead.
    """
    leader_of = {h["session_id"]: h.get("leader_pid") for h in hits}
    return {p["session_id"] for p in procs
            if p.get("claude_pid") is not None
            and p["claude_pid"] == leader_of.get(p["session_id"])}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest session-manager.tests.test_locator.TestClaudePidAnchoredSids -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add session-manager/scripts/locator.py session-manager/tests/test_locator.py
git commit -m "feat(locator): claude_pid_anchored_sids helper (SP2.3)"
```

---

### Task 2: Insert CLAUDE_PID-carriage tier into `resolve_collision`

**Files:**
- Modify: `session-manager/scripts/locator.py:468-481` (`resolve_collision`)
- Test: `session-manager/tests/test_locator.py` (extend `TestResolveCollision`, ~line 406)

**Interfaces:**
- Consumes: `claude_pid_anchored_sids(hits, procs)` from Task 1; existing `pick_foreground_winner`, `on_tty_member_sids`.
- Produces: unchanged signature `resolve_collision(hits, tty, procs, ps_output) -> list`.

- [ ] **Step 1: Write the failing tests**

Add to the `TestResolveCollision` class in `session-manager/tests/test_locator.py`:

```python
    def test_resume_phantom_prefers_claude_pid_carrier(self):
        # One TUI (2076) -> two sids: active carries CLAUDE_PID=2076 on a detached
        # shell; the pre-resume phantom's MCP server is on-tty but carries no
        # CLAUDE_PID. Foreground pgid ties; the CLAUDE_PID tier must pick the active.
        hits = [self._hit(UUID_OWNER, 2076), self._hit(UUID_STALE, 2076)]
        procs = [
            {"session_id": UUID_OWNER, "pid": 3100, "tty": None, "claude_pid": 2076},
            {"session_id": UUID_STALE, "pid": 2900, "tty": "ttys008", "claude_pid": None},
        ]
        ps = "2076 2076 S+\n2900 2076 S+\n"
        out = locator.resolve_collision(hits, "ttys008", procs, ps)
        self.assertEqual([h["session_id"] for h in out], [UUID_OWNER])

    def test_reuse_collision_still_uses_on_tty_when_both_carry_claude_pid(self):
        # /clear-reuse: both sids carry CLAUDE_PID=4973 -> tier 2 ties -> on-tty
        # presence (tier 3) still picks the live owner. SP2.2 behavior preserved.
        hits = [self._hit(UUID_OWNER, 4973), self._hit(UUID_STALE, 4973)]
        procs = [
            {"session_id": UUID_OWNER, "pid": 5054, "tty": "ttys008", "claude_pid": 4973},
            {"session_id": UUID_STALE, "pid": 81310, "tty": None, "claude_pid": 4973},
        ]
        ps = "4973 4973 S+\n5054 4973 S+\n"
        out = locator.resolve_collision(hits, "ttys008", procs, ps)
        self.assertEqual([h["session_id"] for h in out], [UUID_OWNER])
```

- [ ] **Step 2: Run tests to verify the new one fails**

Run: `python3 -m unittest session-manager.tests.test_locator.TestResolveCollision -v`
Expected: `test_resume_phantom_prefers_claude_pid_carrier` FAILS — current code falls straight to the on-tty tier and returns `UUID_STALE` (the phantom). `test_reuse_collision_still_uses_on_tty_when_both_carry_claude_pid` PASSES already (on-tty tier).

- [ ] **Step 3: Write minimal implementation**

Replace `resolve_collision` (`session-manager/scripts/locator.py:468-481`) with:

```python
def resolve_collision(hits, tty, procs, ps_output):
    """Narrow >1 interactive hits sharing one tty to a single winner if possible.

    1) foreground pgid (pick_foreground_winner);
    2) if that ties, prefer the hit whose session has a member directly carrying
       CLAUDE_PID == its leader_pid (a `claude --resume` active session vs the
       throwaway pre-resume id, whose MCP members carry no CLAUDE_PID);
    3) if that still ties (a reused TUI where both sids carry CLAUDE_PID), prefer
       the hit whose session has a live on-tty member.
    Returns a list: length 1 when resolved, else the original hits (ambiguity array).
    """
    winner = pick_foreground_winner(hits, ps_output)
    if winner is not None:
        return [winner]
    anchored = claude_pid_anchored_sids(hits, procs)
    by_anchor = [h for h in hits if h["session_id"] in anchored]
    if len(by_anchor) == 1:
        return by_anchor
    on_tty = on_tty_member_sids(procs, tty)
    narrowed = [h for h in hits if h["session_id"] in on_tty]
    return narrowed if len(narrowed) == 1 else list(hits)
```

- [ ] **Step 4: Run the full test file to verify all pass**

Run: `python3 -m unittest session-manager.tests.test_locator -v`
Expected: PASS (all existing tests + the 2 new ones). Confirm `test_reuse_collision_prefers_on_tty_session`, `test_genuine_ambiguity_returns_both`, and `test_foreground_wins_for_distinct_leaders` remain green (tier 2 is inert when no member carries a matching `claude_pid`).

- [ ] **Step 5: Commit**

```bash
git add session-manager/scripts/locator.py session-manager/tests/test_locator.py
git commit -m "feat(locator): CLAUDE_PID-carriage tiebreak tier, reject --resume phantom (SP2.3)"
```

---

## Notes for the executor

- The `_hit` helper already exists on `TestResolveCollision` (returns a dict with `session_id`, `role`, `pane`, `host`, `tty`, `leader_pid`). Task 1's `TestClaudePidAnchoredSids` defines its own minimal `_hit` (only `session_id` + `leader_pid` are read by the helper).
- `UUID_OWNER`, `UUID_STALE`, `UUID_A`, `UUID_B` are module-level fixtures already defined at the top of the test file — reuse them, don't invent new ones.
- After both tasks, the live regression check is: `python3 session-manager/scripts/locator.py resolve --pane %393` should return the session id with a transcript (a single JSON object), not the phantom. This is environment-dependent (only reproduces while a `--resume` TUI with lingering pre-resume MCP servers is alive) — treat a mismatch here as informational, not a unit-test failure.
```
