# SP2 — Fork-the-Active-Pane tmux Key-Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A tmux key-binding that forks the Claude Code session running in the *active* pane into a new split beside it.

**Architecture:** A new `fork-active-pane.sh` wrapper (the key-binding entrypoint) reads the active pane id from tmux, resolves the session in that pane via SP1's `locator.py resolve --pane`, and forks it through the existing `fork-iterm.sh` using two new flags (`--session-id`, `--target-pane`). `locator.py` gains a foreground tiebreak so `resolve --pane` returns a single record even when two interactive sessions share one pane.

**Tech Stack:** Python 3 stdlib (locator + unittest), Bash (fork scripts + shell tests), tmux.

**Spec:** `docs/superpowers/specs/2026-06-11-session-locator-sp2-design.md`

> **DO NOT modify SP1 contract files beyond what each task explicitly states.** The SP1 record schema (the 10 keys guarded by `test_record_has_exactly_the_schema_keys`) MUST NOT change. The tiebreak only *selects among* existing records; it never adds or removes record keys. If a test seems to require changing the schema, STOP and report BLOCKED.

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `session-manager/scripts/locator.py` | session↔pane indexer/resolver | **Modify**: add `parse_pgid_stat`, `foreground_pgids`, `pick_foreground_winner` (pure), `pane_foreground_ps` (impure), wire into `cmd_resolve` |
| `session-manager/tests/test_locator.py` | locator unit tests | **Modify**: add `TestForegroundTiebreak`, `TestResolveTiebreakWiring` |
| `session-manager/scripts/fork-iterm.sh` | fork a session into a new pane/tab | **Modify**: add `--session-id`, `--target-pane` flags + tmux guard + targeted split |
| `session-manager/tests/test-fork-verify.sh` | fork helper/flag tests | **Modify**: add flag-parsing + guard assertions |
| `session-manager/scripts/fork-active-pane.sh` | key-binding entrypoint | **Create** |
| `session-manager/tests/test-fork-active-pane.sh` | wrapper test | **Create** |
| `session-manager/CLAUDE.md` | plugin docs | **Modify**: document wrapper, key-binding, new flags |
| `session-manager/.claude-plugin/plugin.json` | manifest | **Modify**: version bump (via script) |

---

### Task 1: locator.py — foreground-tiebreak pure functions

Pure, injected-input functions that decide which of several interactive sessions sharing one tty holds the pane foreground. No CLI wiring yet.

**Files:**
- Modify: `session-manager/scripts/locator.py` (add functions after `match_selector`, before `list_tmux_sockets`)
- Test: `session-manager/tests/test_locator.py` (add a new test class)

- [ ] **Step 1: Write the failing tests**

Add this class to `session-manager/tests/test_locator.py` just before the `if __name__ == "__main__":` line:

```python
class TestForegroundTiebreak(unittest.TestCase):
    # `ps -t <tty> -o pid=,pgid=,stat=` rows. The "+" in stat marks a process in
    # the tty's FOREGROUND process group. A Claude leader is its own group leader
    # (pgid == leader_pid), so the foreground session's leader_pid appears as a
    # foreground pgid.
    PS_B_FOREGROUND = (
        "2001 2001 S\n"     # session A leader: running, background
        "2002 2002 S+\n"    # session B leader: foreground (+)
        "2050 2002 S+\n"    # a child of B, also foreground group
    )

    def test_parse_pgid_stat(self):
        rows = locator.parse_pgid_stat(self.PS_B_FOREGROUND)
        self.assertEqual(rows[0], (2001, 2001, "S"))
        self.assertEqual(rows[1], (2002, 2002, "S+"))
        self.assertEqual(len(rows), 3)

    def test_parse_pgid_stat_ignores_garbage(self):
        rows = locator.parse_pgid_stat("not a row\n\n1 2 R+\n")
        self.assertEqual(rows, [(1, 2, "R+")])

    def test_foreground_pgids(self):
        rows = locator.parse_pgid_stat(self.PS_B_FOREGROUND)
        self.assertEqual(locator.foreground_pgids(rows), {2002})

    def test_picks_the_foreground_session(self):
        hits = [
            {"session_id": UUID_A, "leader_pid": 2001, "tty": "ttys016"},
            {"session_id": UUID_B, "leader_pid": 2002, "tty": "ttys016"},
        ]
        winner = locator.pick_foreground_winner(hits, self.PS_B_FOREGROUND)
        self.assertIsNotNone(winner)
        self.assertEqual(winner["session_id"], UUID_B)

    def test_returns_none_when_no_hit_in_foreground(self):
        # Foreground pgid 9999 matches neither leader -> undeterminable -> None.
        hits = [
            {"session_id": UUID_A, "leader_pid": 2001, "tty": "ttys016"},
            {"session_id": UUID_B, "leader_pid": 2002, "tty": "ttys016"},
        ]
        self.assertIsNone(locator.pick_foreground_winner(hits, "9999 9999 S+\n"))

    def test_returns_none_when_two_hits_in_foreground(self):
        # Ambiguous: both leaders appear as foreground groups -> None (array fallback).
        hits = [
            {"session_id": UUID_A, "leader_pid": 2001, "tty": "ttys016"},
            {"session_id": UUID_B, "leader_pid": 2002, "tty": "ttys016"},
        ]
        ps = "2001 2001 S+\n2002 2002 S+\n"
        self.assertIsNone(locator.pick_foreground_winner(hits, ps))

    def test_returns_none_on_empty_ps(self):
        hits = [{"session_id": UUID_A, "leader_pid": 2001, "tty": "ttys016"}]
        self.assertIsNone(locator.pick_foreground_winner(hits, ""))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 session-manager/tests/test_locator.py -v 2>&1 | grep -i tiebreak`
Expected: errors like `AttributeError: module 'locator' has no attribute 'parse_pgid_stat'`.

- [ ] **Step 3: Implement the pure functions**

In `session-manager/scripts/locator.py`, add these three functions immediately after the `match_selector` function (after its closing `return False`) and before `def list_tmux_sockets():`:

```python
def parse_pgid_stat(ps_output):
    """Parse `ps -t <tty> -o pid=,pgid=,stat=` into [(pid, pgid, stat), ...].

    Lines that don't start with two integers are skipped (best-effort).
    """
    rows = []
    for line in ps_output.splitlines():
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        try:
            pid, pgid = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        rows.append((pid, pgid, parts[2]))
    return rows


def foreground_pgids(ps_rows):
    """Process-group ids holding the tty foreground (ps stat contains '+')."""
    return {pgid for _pid, pgid, stat in ps_rows if "+" in stat}


def pick_foreground_winner(hits, ps_output):
    """Of several interactive sessions sharing one tty, return the one whose
    leader holds the pane's foreground process group; None if undeterminable.

    A Claude session's leader is its own process-group leader (pgid == leader_pid),
    so the foreground session is the hit whose leader_pid is a foreground pgid.
    Returns None when zero or more than one hit matches, so the caller falls back
    to the ambiguity array — correctness is never sacrificed to force an answer.
    """
    fg = foreground_pgids(parse_pgid_stat(ps_output))
    matches = [h for h in hits if h.get("leader_pid") in fg]
    return matches[0] if len(matches) == 1 else None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 session-manager/tests/test_locator.py -v`
Expected: all tests PASS, including the 7 new `TestForegroundTiebreak` tests. (The 19 SP1 tests still pass.)

- [ ] **Step 5: Commit**

```bash
git add session-manager/scripts/locator.py session-manager/tests/test_locator.py
git commit -m "feat(session-manager): locator foreground-tiebreak pure functions"
```

---

### Task 2: locator.py — wire the tiebreak into `cmd_resolve`

Add the impure `ps` wrapper and use the tiebreak in the resolve path so a pane with two interactive sessions returns a single record when the foreground is determinable.

**Files:**
- Modify: `session-manager/scripts/locator.py` (`cmd_resolve`, add `pane_foreground_ps`)
- Test: `session-manager/tests/test_locator.py` (wiring test)

- [ ] **Step 1: Write the failing wiring test**

Add this class to `session-manager/tests/test_locator.py` just before `if __name__ == "__main__":`:

```python
class TestResolveTiebreakWiring(unittest.TestCase):
    """cmd_resolve must collapse a two-interactive-session pane to the foreground
    one, and keep returning the array when the foreground is undeterminable."""

    def setUp(self):
        self._gather = locator.gather_sessions
        self._ps = locator.pane_foreground_ps
        self.two = [
            {"session_id": UUID_A, "role": "interactive", "pane": "tmux:default:%86",
             "host": "tmux", "tty": "ttys016", "leader_pid": 2001},
            {"session_id": UUID_B, "role": "interactive", "pane": "tmux:default:%86",
             "host": "tmux", "tty": "ttys016", "leader_pid": 2002},
        ]
        locator.gather_sessions = lambda: self.two

    def tearDown(self):
        locator.gather_sessions = self._gather
        locator.pane_foreground_ps = self._ps

    def _resolve_pane(self):
        import contextlib
        import io
        ns = locator.argparse.Namespace(pane="tmux:default:%86", tty=None, session=None)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            locator.cmd_resolve(ns)
        return json.loads(buf.getvalue())

    def test_breaks_tie_via_foreground(self):
        locator.pane_foreground_ps = lambda tty: "2001 2001 S\n2002 2002 S+\n"
        out = self._resolve_pane()
        self.assertIsInstance(out, dict)
        self.assertEqual(out["session_id"], UUID_B)

    def test_returns_array_when_undeterminable(self):
        locator.pane_foreground_ps = lambda tty: ""   # no foreground signal
        out = self._resolve_pane()
        self.assertIsInstance(out, list)
        self.assertEqual({r["session_id"] for r in out}, {UUID_A, UUID_B})
```

Note: `test_locator.py` already imports `json` indirectly? It does not — add `import json` to the top of the file if absent (the SP1 file imports only `os`, `sys`, `unittest`). Add `import json` after `import os`.

- [ ] **Step 2: Run to verify failure**

Run: `python3 session-manager/tests/test_locator.py -v 2>&1 | grep -iE 'tie|wiring'`
Expected: failures — `cmd_resolve` does not yet break the tie (returns the array in both cases), and `pane_foreground_ps` does not exist (`AttributeError` in `tearDown`/`setUp` reference). 

- [ ] **Step 3: Implement the impure wrapper and wire `cmd_resolve`**

In `session-manager/scripts/locator.py`, add this function immediately after `cwd_of` (after its `return None`) and before `def build_sessions(`:

```python
def pane_foreground_ps(tty):
    """Best-effort `ps -t <tty> -o pid=,pgid=,stat=` output ('' on failure)."""
    if not tty:
        return ""
    return _run(["ps", "-t", tty, "-o", "pid=,pgid=,stat="])
```

Then replace the body of `cmd_resolve` with the tiebreak-aware version:

```python
def cmd_resolve(args):
    sessions = gather_sessions()
    hits = [s for s in sessions if match_selector(s, args)]
    if not hits:
        print(json.dumps([], indent=2))
        sys.exit(1)
    if len(hits) > 1:
        winner = pick_foreground_winner(hits, pane_foreground_ps(hits[0].get("tty")))
        if winner is not None:
            hits = [winner]
    print(json.dumps(hits[0] if len(hits) == 1 else hits, indent=2))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 session-manager/tests/test_locator.py -v`
Expected: all tests PASS (SP1 19 + Task 1's 7 + these 2).

- [ ] **Step 5: Live sanity check (confirms the real `ps` format matches the parser)**

Run: `python3 session-manager/scripts/locator.py resolve --pane %86`
Expected: a single JSON **object** (this machine runs one interactive session in `%86`), with a `session_id`. Then run the raw probe to eyeball the real `ps` columns the parser will see:
Run: `ps -t "$(python3 session-manager/scripts/locator.py resolve --pane %86 | python3 -c 'import json,sys;print(json.load(sys.stdin)["tty"])')" -o pid=,pgid=,stat=`
Expected: rows of `<pid> <pgid> <stat>` where the active foreground process carries a `+` (e.g. `S+`). This confirms `parse_pgid_stat`'s 3-column assumption holds against live output. If the format differs materially (e.g. no `+` ever appears, or node never shows on the tty), STOP and report BLOCKED with the actual output — the spec flagged this as the one unverified mechanism.

- [ ] **Step 6: Commit**

```bash
git add session-manager/scripts/locator.py session-manager/tests/test_locator.py
git commit -m "feat(session-manager): break resolve --pane tie via pane foreground"
```

---

### Task 3: fork-iterm.sh — `--session-id` flag

Let a caller supply the session explicitly, overriding env/symlink detection. Needed because the key-binding wrapper resolves the session from the pane, not the environment.

**Files:**
- Modify: `session-manager/scripts/fork-iterm.sh` (arg defaults, parser, session resolution)
- Test: `session-manager/tests/test-fork-verify.sh`

- [ ] **Step 1: Write the failing test**

In `session-manager/tests/test-fork-verify.sh`, add the following just before the final `echo "----"` line. It sources the script in lib-only mode with the new flag and asserts the captured option variable:

```bash
# --- new SP2 flags: --session-id is captured into SESSION_ID_OPT ---
(
  FORK_LIB_ONLY=1 source "$SCRIPT_DIR/../scripts/fork-iterm.sh" --session-id "feed-beef"
  [ "$SESSION_ID_OPT" = "feed-beef" ]
) && r=yes || r=no
ok "$r" "yes" "--session-id is parsed into SESSION_ID_OPT"
```

- [ ] **Step 2: Run to verify failure**

Run: `bash session-manager/tests/test-fork-verify.sh 2>&1 | grep session-id`
Expected: `FAIL: --session-id is parsed into SESSION_ID_OPT` (the flag is unknown, so the parser hits the `-*) echo "unknown option"` arm and the subshell exits non-zero).

- [ ] **Step 3: Implement the flag**

In `session-manager/scripts/fork-iterm.sh`:

(a) Add the default near the other option defaults (the block that currently reads `CURRENT_DIR=""` … `QUIET=0`). Add one line:

```bash
SESSION_ID_OPT=""
```

(b) Add a case arm inside the `while [ $# -gt 0 ]; do case "$1" in` block, alongside `--fork-dir`:

```bash
        --session-id) SESSION_ID_OPT="$2"; shift 2 ;;
```

(c) Replace the session-resolution block. The current block reads:

```bash
SESSION_ID="${CLAUDE_CODE_SESSION_ID:-}"
if [ -z "$SESSION_ID" ]; then
    SESSION_ID=$(detect_session_id "$CURRENT_DIR")
    if [[ "$SESSION_ID" == Error:* ]]; then
        echo "$SESSION_ID" >&2
        exit 1
    fi
fi
```

Replace it with (explicit `--session-id` wins over everything):

```bash
if [ -n "$SESSION_ID_OPT" ]; then
    SESSION_ID="$SESSION_ID_OPT"
else
    SESSION_ID="${CLAUDE_CODE_SESSION_ID:-}"
    if [ -z "$SESSION_ID" ]; then
        SESSION_ID=$(detect_session_id "$CURRENT_DIR")
        if [[ "$SESSION_ID" == Error:* ]]; then
            echo "$SESSION_ID" >&2
            exit 1
        fi
    fi
fi
```

(d) Update the usage comment at the top of the file (the `# Usage:` block) to include `[--session-id <id>]`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `bash session-manager/tests/test-fork-verify.sh`
Expected: ends with `PASS=N FAIL=0` (N = prior count + 1), including the `--session-id` line.

- [ ] **Step 5: Commit**

```bash
git add session-manager/scripts/fork-iterm.sh session-manager/tests/test-fork-verify.sh
git commit -m "feat(session-manager): fork-iterm.sh --session-id (explicit session)"
```

---

### Task 4: fork-iterm.sh — `--target-pane` flag, tmux guard, targeted split

Make the fork land beside a specific pane, and reject the flag outside tmux.

**Files:**
- Modify: `session-manager/scripts/fork-iterm.sh` (default, parser, early guard, tmux split)
- Test: `session-manager/tests/test-fork-verify.sh`

- [ ] **Step 1: Write the failing tests**

In `session-manager/tests/test-fork-verify.sh`, add just before the final `echo "----"`:

```bash
# --- --target-pane is captured into TARGET_PANE ---
# Dummy TMUX so the "target-pane requires tmux" early guard (added in this task)
# does not exit during lib-only sourcing on hosts where $TMUX is unset (e.g. CI).
(
  TMUX="dummy,1,1" FORK_LIB_ONLY=1 source "$SCRIPT_DIR/../scripts/fork-iterm.sh" --target-pane "%7"
  [ "$TARGET_PANE" = "%7" ]
) && r=yes || r=no
ok "$r" "yes" "--target-pane is parsed into TARGET_PANE"

# --- --target-pane outside tmux is rejected with exit 2 (full-script run) ---
# Run the real script (NOT lib-only) with TMUX unset; the early guard must fire
# before any session resolution.
env -u TMUX bash "$SCRIPT_DIR/../scripts/fork-iterm.sh" --session-id x --target-pane "%7" >/dev/null 2>&1
ok "$?" "2" "--target-pane errors (exit 2) when not inside tmux"
```

- [ ] **Step 2: Run to verify failure**

Run: `bash session-manager/tests/test-fork-verify.sh 2>&1 | grep target-pane`
Expected: both `--target-pane` lines FAIL (unknown flag; and the no-tmux run does not exit 2 yet).

- [ ] **Step 3: Implement the flag, guard, and targeted split**

In `session-manager/scripts/fork-iterm.sh`:

(a) Add the default beside `SESSION_ID_OPT=""`:

```bash
TARGET_PANE=""
```

(b) Add a case arm beside `--session-id`:

```bash
        --target-pane) TARGET_PANE="$2"; shift 2 ;;
```

(c) Add the early guard immediately after the line `CURRENT_DIR="${CURRENT_DIR:-$(pwd)}"` (so it runs for both full-script and lib-only loads, and before session resolution):

```bash
# --target-pane only makes sense for the tmux split path.
if [ -n "$TARGET_PANE" ] && [ -z "${TMUX:-}" ]; then
    echo "Error: --target-pane is only valid inside tmux." >&2
    exit 2
fi
```

(d) Make the tmux split target the pane. The current line in the `if [ -n "$TMUX" ]` branch reads:

```bash
    pane_id=$(tmux split-window -h -P -F '#{pane_id}' -c "$FORK_DIR" "$DEFAULT_SHELL")
```

Replace it with a conditional that adds `-t "$TARGET_PANE"` only when set:

```bash
    if [ -n "$TARGET_PANE" ]; then
        pane_id=$(tmux split-window -h -t "$TARGET_PANE" -P -F '#{pane_id}' -c "$FORK_DIR" "$DEFAULT_SHELL")
    else
        pane_id=$(tmux split-window -h -P -F '#{pane_id}' -c "$FORK_DIR" "$DEFAULT_SHELL")
    fi
```

(e) Update the top-of-file `# Usage:` comment to include `[--target-pane <pane>]`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `bash session-manager/tests/test-fork-verify.sh`
Expected: ends with `PASS=N FAIL=0`, including both `--target-pane` lines.

- [ ] **Step 5: Commit**

```bash
git add session-manager/scripts/fork-iterm.sh session-manager/tests/test-fork-verify.sh
git commit -m "feat(session-manager): fork-iterm.sh --target-pane + tmux guard"
```

---

### Task 5: fork-active-pane.sh — the key-binding entrypoint

The wrapper that ties pane → session → fork. Standalone script mirroring `fork-iterm.sh`'s contract, with a shimmable locator/fork for testing.

**Files:**
- Create: `session-manager/scripts/fork-active-pane.sh`
- Create: `session-manager/tests/test-fork-active-pane.sh`

- [ ] **Step 1: Write the script**

Create `session-manager/scripts/fork-active-pane.sh` with this content:

```bash
#!/bin/bash
# fork-active-pane.sh — tmux key-binding entrypoint: fork the Claude Code session
# running in a given pane into a new split beside it.
#
# Usage (from ~/.tmux.conf):
#   bind-key F run-shell "/abs/path/to/fork-active-pane.sh '#{pane_id}'"
#
# Why resolve from the PANE, not the environment: a tmux `run-shell` command runs
# detached from the active pane and does NOT inherit its CLAUDE_CODE_SESSION_ID,
# so the session must be looked up from the pane id via locator.py (SP1).
#
# Tests may override the resolver/forker via FAP_LOCATOR / FAP_FORK env vars.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCATOR="${FAP_LOCATOR:-$SCRIPT_DIR/locator.py}"
FORK="${FAP_FORK:-$SCRIPT_DIR/fork-iterm.sh}"

# A key-binding has no stdout the user sees; route status to the tmux status line.
notify() { tmux display-message "$1" 2>/dev/null || true; }

PANE_ID="${1:-}"
if [ -z "$PANE_ID" ]; then
    echo "Error: no pane id. Usage: fork-active-pane.sh '#{pane_id}'" >&2
    exit 2
fi

if [ -z "${TMUX:-}" ]; then
    echo "Error: fork-active-pane.sh must run inside tmux (\$TMUX unset)." >&2
    exit 2
fi

# Socket basename from $TMUX (e.g. /private/tmp/tmux-501/default,2611,7 -> default).
SOCKET="$(basename "${TMUX%%,*}")"
ADDR="tmux:${SOCKET}:${PANE_ID}"

# Resolve the interactive session in that pane (SP1).
RESOLVE_OUT="$(python3 "$LOCATOR" resolve --pane "$ADDR" 2>/dev/null)"
RESOLVE_RC=$?

# Classify the three SP1 return shapes: object -> session_id ; array -> AMBIGUOUS ;
# [] / parse failure -> NONE.
SESSION_ID="$(printf '%s' "$RESOLVE_OUT" | python3 - <<'PY'
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    print("NONE"); sys.exit()
if isinstance(data, list):
    print("AMBIGUOUS" if data else "NONE")
elif isinstance(data, dict) and data.get("session_id"):
    print(data["session_id"])
else:
    print("NONE")
PY
)"

if [ "$RESOLVE_RC" -ne 0 ] || [ "$SESSION_ID" = "NONE" ]; then
    notify "No Claude session in this pane to fork."
    exit 0
fi
if [ "$SESSION_ID" = "AMBIGUOUS" ]; then
    notify "Multiple Claude sessions in this pane — can't disambiguate."
    exit 1
fi

# Fork that session into a split beside the focused pane (reuse fork-iterm.sh).
ERRF="$(mktemp -t fork-active-pane.XXXXXX)"
MANAGED_ID="$("$FORK" --session-id "$SESSION_ID" --target-pane "$PANE_ID" --quiet 2>"$ERRF")"
FORK_RC=$?

if [ "$FORK_RC" -eq 0 ] && [ -n "$MANAGED_ID" ]; then
    notify "Forked → $MANAGED_ID"
    echo "$MANAGED_ID"
    rm -f "$ERRF"
    exit 0
else
    notify "Fork failed: $(head -1 "$ERRF" 2>/dev/null)"
    cat "$ERRF" >&2 2>/dev/null || true
    rm -f "$ERRF"
    exit 1
fi
```

- [ ] **Step 2: Make it executable**

Run: `chmod +x session-manager/scripts/fork-active-pane.sh`
Expected: no output; `test -x session-manager/scripts/fork-active-pane.sh && echo OK` prints `OK`.

- [ ] **Step 3: Write the test (it will fail until the script exists — it now does, so it should pass; write it and confirm)**

Create `session-manager/tests/test-fork-active-pane.sh`:

```bash
#!/bin/bash
# Tests for fork-active-pane.sh using shimmed locator/fork (FAP_LOCATOR/FAP_FORK).
# Run: bash session-manager/tests/test-fork-active-pane.sh
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER="$SCRIPT_DIR/../scripts/fork-active-pane.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

pass=0; fail=0
ok() { if [ "$1" = "$2" ]; then echo "PASS: $3"; pass=$((pass+1)); else echo "FAIL: $3 (want='$2' got='$1')"; fail=$((fail+1)); fi; }

# A fake locator: prints whatever JSON / exit code the test puts in control files,
# and records the args it was called with.
FAKE_LOC="$TMP/locator.py"
cat > "$FAKE_LOC" <<'PY'
import os, sys
argf = os.environ.get("LOC_ARGS_OUT")
if argf:
    open(argf, "w").write(" ".join(sys.argv[1:]))
sys.stdout.write(os.environ.get("LOC_OUT", "[]"))
sys.exit(int(os.environ.get("LOC_RC", "0")))
PY

# A fake fork: echoes a managed id (or fails) and records its args.
FAKE_FORK="$TMP/fork.sh"
cat > "$FAKE_FORK" <<'SH'
#!/bin/bash
argf="${FORK_ARGS_OUT:-}"
[ -n "$argf" ] && echo "$@" > "$argf"
if [ "${FORK_RC:-0}" -ne 0 ]; then echo "boom" >&2; exit "${FORK_RC}"; fi
echo "${FORK_ID:-sm-test01}"
SH
chmod +x "$FAKE_FORK"

run() { FAP_LOCATOR="$FAKE_LOC" FAP_FORK="$FAKE_FORK" bash "$WRAPPER" "$@"; }

# Case 1: single object -> forks, prints managed id, exit 0.
out=$(TMUX="/private/tmp/tmux-501/default,1,1" LOC_OUT='{"session_id":"abc-123","tty":"ttys9"}' LOC_RC=0 \
      FORK_ID="sm-aaa111" run "%5"); rc=$?
ok "$rc" "0" "single object: exit 0"
ok "$out" "sm-aaa111" "single object: prints managed id"

# Case 1b: the wrapper builds the right pane address and fork args.
LARGS="$TMP/largs"; FARGS="$TMP/fargs"
TMUX="/private/tmp/tmux-501/default,1,1" LOC_OUT='{"session_id":"abc-123","tty":"ttys9"}' LOC_RC=0 \
  LOC_ARGS_OUT="$LARGS" FORK_ARGS_OUT="$FARGS" run "%5" >/dev/null 2>&1
ok "$(cat "$LARGS")" "resolve --pane tmux:default:%5" "builds socket-qualified pane address"
ok "$(cat "$FARGS")" "--session-id abc-123 --target-pane %5 --quiet" "passes session id + target pane to fork"

# Case 2: empty array / rc 1 -> 'no session', exit 0, no managed id.
out=$(TMUX="/private/tmp/tmux-501/default,1,1" LOC_OUT='[]' LOC_RC=1 run "%5"); rc=$?
ok "$rc" "0" "no session: exit 0"
ok "$out" "" "no session: no managed id on stdout"

# Case 3: array of two -> ambiguous, exit 1.
out=$(TMUX="/private/tmp/tmux-501/default,1,1" \
      LOC_OUT='[{"session_id":"a"},{"session_id":"b"}]' LOC_RC=0 run "%5"); rc=$?
ok "$rc" "1" "ambiguous array: exit 1"

# Case 4: no $TMUX -> exit 2.
env -u TMUX bash "$WRAPPER" "%5" >/dev/null 2>&1
ok "$?" "2" "no \$TMUX: exit 2"

# Case 5: missing pane arg -> exit 2.
TMUX="/private/tmp/tmux-501/default,1,1" bash "$WRAPPER" >/dev/null 2>&1
ok "$?" "2" "missing pane arg: exit 2"

# Case 6: fork fails -> exit 1.
out=$(TMUX="/private/tmp/tmux-501/default,1,1" LOC_OUT='{"session_id":"abc","tty":"t"}' LOC_RC=0 \
      FORK_RC=1 run "%5"); rc=$?
ok "$rc" "1" "fork failure: exit 1"

echo "----"
echo "PASS=$pass FAIL=$fail"
[ "$fail" -eq 0 ]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `bash session-manager/tests/test-fork-active-pane.sh`
Expected: ends with `PASS=10 FAIL=0`.

- [ ] **Step 5: Commit**

```bash
git add session-manager/scripts/fork-active-pane.sh session-manager/tests/test-fork-active-pane.sh
git commit -m "feat(session-manager): fork-active-pane.sh key-binding entrypoint"
```

---

### Task 6: docs — CLAUDE.md + key-binding snippet

Document the wrapper, the key-binding, and the new flags so a user can wire the hotkey.

**Files:**
- Modify: `session-manager/CLAUDE.md`

- [ ] **Step 1: Add the documentation section**

In `session-manager/CLAUDE.md`, immediately after the `### locator.py (session ↔ pane indexer/resolver)` subsection (before `### Registry System`), insert:

````markdown
### fork-active-pane.sh (fork the focused pane — tmux key-binding)

The fork hotkey: press a tmux key on any pane and the Claude session running in
*that* pane is forked into a new split beside it. It is the SP2 layer over the
SP1 locator.

How it works (`scripts/fork-active-pane.sh '<pane-id>'`):

1. A tmux `run-shell` key-binding passes the active pane's `#{pane_id}`. (The
   command runs detached, so it cannot read the pane's `CLAUDE_CODE_SESSION_ID`
   from the environment — it must resolve from the pane id.)
2. The socket basename comes from `$TMUX`; the script builds the SP1 address
   `tmux:<socket>:<pane-id>` and calls `locator.py resolve --pane`.
3. The resolved `session_id` is forked via
   `fork-iterm.sh --session-id <id> --target-pane <pane-id> --quiet`, which splits
   beside the focused pane and verifies launch (existing behavior).
4. The outcome is shown on the tmux status line via `tmux display-message`
   (a key-binding has no user-visible stdout): the managed id on success, or
   "No Claude session in this pane" / "can't disambiguate" / "Fork failed".

Install the key-binding in `~/.tmux.conf` (adjust the path to your checkout):

```tmux
# Prefix + F: fork the Claude session in the focused pane into a split beside it.
bind-key F run-shell "$HOME/Project/my_claudecode_marketplace/session-manager/scripts/fork-active-pane.sh '#{pane_id}'"
```

Then reload: `tmux source-file ~/.tmux.conf`.

Related `fork-iterm.sh` flags added for this path:
- `--session-id <id>` — fork an explicitly-supplied session, bypassing
  environment/symlink detection (the wrapper supplies the pane's resolved id).
- `--target-pane <pane>` — split beside a specific pane (`split-window -h -t`).
  Valid only inside tmux; supplying it elsewhere errors with exit 2.

Tests: `bash session-manager/tests/test-fork-active-pane.sh`.
````

Then update the `### locator.py` subsection's "Resolve return contract" paragraph: change the sentence that says SP1 does not break the two-interactive tie. Find the text:

```
that tie; choosing the foreground session is focus work, deferred to SP2.
Consumers must handle the array case (test for a list / `len > 1`).
```

Replace with:

```
that tie at the SP1 layer; SP2 added a foreground tiebreak in `cmd_resolve`, so
`resolve --pane`/`--tty` now return a single object whenever the pane foreground
is determinable, and the array only when two interactive sessions are genuinely
indistinguishable. Consumers must still handle the array case (test for a list /
`len > 1`).
```

- [ ] **Step 2: Verify the markdown has no broken code fences**

Run: `python3 -c "import sys; t=open('session-manager/CLAUDE.md').read(); print('triple-backticks:', t.count('\`\`\`'))"`
Expected: an even number of triple-backtick fences (balanced).

- [ ] **Step 3: Commit**

```bash
git add session-manager/CLAUDE.md
git commit -m "docs(session-manager): document fork-active-pane.sh + key-binding"
```

---

### Task 7: version bump (minor)

**Files:**
- Modify: `session-manager/.claude-plugin/plugin.json` (via script)

- [ ] **Step 1: Run the bump script**

Run: `./scripts/bump-plugin.sh session-manager minor`
Expected: bumps the `version` in `session-manager/.claude-plugin/plugin.json` (from `2.6.0` to `2.7.0`) and clears the plugin cache. Confirm with:
Run: `python3 -c "import json;print(json.load(open('session-manager/.claude-plugin/plugin.json'))['version'])"`
Expected: `2.7.0`.

- [ ] **Step 2: Run the full test suite one last time**

Run: `python3 session-manager/tests/test_locator.py -v && bash session-manager/tests/test-fork-verify.sh && bash session-manager/tests/test-fork-active-pane.sh`
Expected: all three suites pass — locator `OK`, and both shell suites end `FAIL=0`.

- [ ] **Step 3: Commit**

```bash
git add session-manager/.claude-plugin/plugin.json
git commit -m "chore(session-manager): bump to 2.7.0 for SP2 fork-active-pane"
```

---

## Notes for the implementer

- **Stay on a branch, not `main`.** If not already on an SP2 branch, create one before Task 1.
- **DO NOT change the SP1 record schema.** The tiebreak selects among existing records; it must not add/remove keys. The guard test `test_record_has_exactly_the_schema_keys` must keep passing untouched.
- **The Task 2 live spike (Step 5) is the one place reality may diverge from the plan.** If `ps -t <tty>` never shows a `+` foreground process or the columns differ, report BLOCKED with the real output rather than forcing the parser to fit.
- **`--quiet` matters in the wrapper** — without it, `fork-iterm.sh` prints progress to stderr; the wrapper captures stdout for the managed id, so progress on stderr is harmless but `--quiet` keeps the forked transcript clean.
- Frequent commits per task; each task leaves the suite green.
