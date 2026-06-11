# Session Locator — SP2: Fork-the-Active-Pane tmux Key-Binding

**Date:** 2026-06-11
**Status:** Approved design (pre-implementation)
**Plugin:** `session-manager`
**Platform:** macOS only
**Builds on:** SP1 (`session-manager/scripts/locator.py`) + existing `fork-iterm.sh`

---

## Context: where this sits in the larger system

The session-locator system answers two questions about Claude Code sessions on the
local machine:

- **A. Mapping** — "what Claude session runs in pane X?" (SP1, done)
- **B. Focus** — "which pane is the user looking at right now?"

SP1 built the mapping (`locator.py`). The motivating consumer is a **fork hotkey**:
fork the Claude session in the pane the user is looking at, into a new split beside
it.

### The trigger decision that scopes SP2

The fork hotkey is triggered by a **tmux key-binding** (not a global macOS hotkey).
This is decisive: when a tmux key-binding fires, tmux runs the bound command in the
context of the active pane and substitutes `#{pane_id}` directly. **tmux answers
"which pane is focused" for free** — so SP2 needs *no* macOS frontmost-app → tab →
pane resolver.

That general OS-level focus resolver (global-hotkey support, iTerm/Apple-Terminal
focus adapters) is **explicitly deferred** to a later sub-project, to be built only if
a non-tmux consumer (status bar, overlay, global hotkey) ever needs it. It is out of
scope here.

So SP2 collapses to a small, well-bounded sub-project:

```
keypress in active pane
   │  tmux.conf:  bind F run-shell "…/fork-active-pane.sh #{pane_id}"
   ▼
fork-active-pane.sh  %N                 (NEW — the keybinding entrypoint)
   │  socket ← $TMUX basename;  addr = tmux:<socket>:%N
   ▼
locator.py resolve --pane tmux:<socket>:%N      (SP1, + new foreground tiebreak)
   │  → {"session_id": "…", …}          single record
   ▼
fork-iterm.sh --session-id <id> --target-pane %N   (existing script + 2 new flags)
   │  split-window -h -t %N → claude -r <id> --fork-session → verify → register
   ▼
managed id sm-xxxxxx ;  result surfaced to the user via `tmux display-message`
```

### Why the session is resolved from the pane id, not the environment

A tmux key-binding's `run-shell` command executes **detached from the active pane** —
it does *not* inherit that pane's Claude environment, so `CLAUDE_CODE_SESSION_ID` is
absent or wrong. The session therefore must be resolved **from the pane id**, which is
exactly what `locator.py resolve --pane` does. This is the concrete SP1 → SP2 join.

---

## SP2 scope

A tmux-native fork key-binding that:

1. takes the active pane id from tmux,
2. resolves the interactive Claude session in that pane via SP1's `locator.py`
   (breaking the rare two-sessions-in-one-pane tie — the SP1-deferred "focus" bit),
3. forks that session into a new horizontal split beside the focused pane, reusing
   the existing `fork-iterm.sh` spawn-and-verify path.

### Out of scope for SP2 (deferred)

- macOS frontmost-application focus detection / global hotkey — later SP.
- iTerm-tab and Apple-Terminal focus adapters — later SP.
- A slash-command entrypoint (`commands/fork-active-pane.md`) — **dropped by decision;
  key-binding only.** (Forking the *current* session from inside Claude is already
  served by the existing `/session-manager:fork` command.)
- Hook-backed registry / daemon / events — SP3 / SP4.

### Code-shape (verified against repo convention — ALIGNED)

Verified via `convention-checker` against `session-manager` precedent:

1. **New standalone script in `scripts/`** (`fork-active-pane.sh`) that shells out to
   `locator.py` then `fork-iterm.sh` — mirrors how `fork-iterm.sh` is a standalone
   feature script and how `commands/*.md` orchestrate scripts. ALIGNED.
2. **Two new flags on `fork-iterm.sh`** added to the existing `while/case` parser
   (lines 33-43), same shape as `--fork-dir` / `--relocate`. ALIGNED.
3. **Foreground tiebreak in `locator.py`** as a pure function called from
   `cmd_resolve` — the SP1 spec already assigned this step here
   (`2026-06-07-session-locator-sp1-design.md` lines 208-211). ALIGNED.

---

## Components

### 1. `locator.py` — foreground tiebreak (resolves the SP1-deferred ambiguity)

SP1 deliberately did not break the tie when two **interactive** sessions map to one
pane: `resolve --pane` returns a JSON **array** as the ambiguity signal. SP2 adds the
tiebreak so the common consumer gets a single record.

- **New pure function** `pick_foreground_winner(hits, ps_output)`:
  - Inputs: the matched interactive `hits` (≥ 2, all sharing one pane → one `tty`) and
    raw `ps -t <tty> -o pid=,pgid=,stat=` output (injected for testability).
  - **Intent:** select the `hit` whose session is the one currently in the pane's
    foreground; return `None` when the foreground cannot be determined so the caller
    falls back to the array.
  - **Approach (to be confirmed by an implementation spike — NOT yet verified):** the
    pane's foreground process group is the one whose `ps` stat carries the `+` flag;
    the winner is the `hit` whose `leader_pid` maps to that foreground process group
    (via its `pgid`). **Subtlety the spike must resolve:** SP1 found the node leader
    often detaches from the tty (`tty=??`), so the leader pid may not appear directly
    in `ps -t <tty>` output. The implementer must verify, against two genuinely
    co-resident interactive sessions, that the foreground session's process group *is*
    distinguishable on the tty (e.g. via the leader's child or its `pgid`), and adjust
    the exact `ps` columns / comparison accordingly before settling the contract. If no
    reliable signal exists, the function returns `None` (array fallback) — correctness
    is never sacrificed to force a single answer.
- **Wiring in `cmd_resolve`:** after `match_selector` produces `hits`, replace the
  bare `hits[0] if len(hits) == 1 else hits` with:
  - 1 hit → that record (unchanged);
  - > 1 hit → `pick_foreground_winner(...)` if it returns a winner, else the array
    (existing safety-net contract preserved).
- A thin impure helper (e.g. `pane_foreground_ps(tty)`) wraps the `ps` call via the
  existing best-effort `_run()`; `pick_foreground_winner` itself stays pure.

This is the one genuine "focus" decision in SP2. The hotkey works **without** it in
the normal case (one session per pane); the tiebreak hardens the rare case and makes
`resolve --pane` reliably single-valued for *all* current and future consumers.

### 2. `fork-iterm.sh` — two new flags

Added to the `while/case` arg parser (`fork-iterm.sh:33-43`), same shape as existing
flags:

- **`--session-id <id>`** — fork an explicitly-supplied session, bypassing the
  `CLAUDE_CODE_SESSION_ID` / `detect_session_id` acquisition. A third acquisition path
  that overrides auto-detection, mirroring how `--fork-dir` overrides the
  auto-resolved cwd. All downstream logic (owner-file discovery, owner-cwd, resumability
  pre-flight, spawn, verify, register) already keys off `SESSION_ID`, so this is a
  minimal, additive change.
- **`--target-pane <pane_id>`** — make the tmux split land beside a specific pane:
  conditionalize the split at `fork-iterm.sh:483` as
  `tmux split-window -h -t "$TARGET_PANE" …` when `TARGET_PANE` is non-empty; otherwise
  unchanged (splits the active pane). **`--target-pane` is meaningful only in the tmux
  branch** — supplying it when the script falls through to the iTerm branch is an
  explicit error (`exit 2`), since the hotkey path is always inside tmux.

### 3. `fork-active-pane.sh` — the key-binding entrypoint (NEW)

Standalone bash script in `session-manager/scripts/`, mirroring `fork-iterm.sh`'s
contract: success-path chatter via a `progress()` helper to stderr, errors to stderr,
managed id (or nothing) to stdout, and additionally surfacing the outcome to the user
via `tmux display-message` (a key-binding has no stdout TTY the user sees).

Flow:

1. **Arg:** `%N` — the pane id, passed by the key-binding as `#{pane_id}`.
2. **Refuse outside tmux:** if `$TMUX` is unset → error (`exit 2`). This is a tmux-only
   entrypoint.
3. **Socket:** `socket = basename(first comma-field of $TMUX)`; build the
   SP1 address `tmux:<socket>:%N`.
4. **Resolve:** `locator.py resolve --pane tmux:<socket>:%N`. Parse stdout with a
   stdlib `python3 -c` / `json` one-liner.
   - exit 1 / `[]` → no Claude session here → `tmux display-message "No Claude session
     in this pane to fork."`, exit 0 (nothing to do, not an error).
   - JSON **array** (ambiguous after tiebreak) → `tmux display-message "Multiple Claude
     sessions in this pane — can't disambiguate."`, exit 1.
   - JSON **object** → extract `session_id`.
5. **Fork:** `fork-iterm.sh --session-id <id> --target-pane %N --quiet`. On success the
   managed id is captured and shown via `tmux display-message "Forked → <managed id>"`.
   On failure, surface fork-iterm.sh's error via `tmux display-message`.

The script locates its sibling scripts relative to its own path (`$(dirname "$0")`),
so it works regardless of cwd.

### 4. tmux key-binding + docs (no slash command)

- A documented `bind-key` snippet for `~/.tmux.conf`, e.g.:

  ```tmux
  # Fork the Claude session in the focused pane into a new split beside it.
  bind-key F run-shell "$HOME/Project/my_claudecode_marketplace/session-manager/scripts/fork-active-pane.sh '#{pane_id}'"
  ```

  (Documented with a note that the path is install-specific; the snippet shows how to
  point it at the plugin's `scripts/` directory.)
- A `session-manager/CLAUDE.md` section documenting `fork-active-pane.sh`, the
  key-binding, the SP1 → SP2 data flow, and the `--session-id` / `--target-pane` flags.

---

## Data contract between components

- **Wrapper → locator:** `resolve --pane tmux:<socket>:%N`. Wrapper MUST handle all
  three SP1 return shapes (single object / array / `[]`+exit 1).
- **Wrapper → fork-iterm.sh:** `--session-id <uuid>` (required), `--target-pane <%N>`
  (the focused pane), `--quiet`. The fork script owns directory resolution (Approach A
  — forks from the session's own recorded cwd) and launch verification unchanged.
- **locator `resolve --pane` post-SP2:** returns a single object whenever the
  foreground is determinable (the normal case and the tiebroken case); returns an array
  only when two interactive sessions are genuinely indistinguishable. `[]` + exit 1
  when no interactive session matches.

---

## Error handling

All user-facing outcomes in the key-binding path are surfaced via `tmux
display-message` (status-line toast), because a `run-shell` command's stdout/stderr is
not shown to the user.

| Condition | Detection | Behavior |
|-----------|-----------|----------|
| Not in tmux | `$TMUX` unset | stderr error, `exit 2` |
| No Claude session in pane | locator exit 1 / `[]` | toast "No Claude session in this pane to fork.", `exit 0` |
| Ambiguous (array) | locator returns JSON list | toast "Multiple Claude sessions … can't disambiguate.", `exit 1` |
| Fork failed | `fork-iterm.sh` non-zero | toast with the failure; pane left for inspection (existing behavior) |
| Success | managed id captured | toast "Forked → sm-xxxxxx" |

`locator.py`'s internal `ps`/`tmux`/`lsof` calls remain best-effort (never raise), per
SP1. The new `ps -t <tty>` foreground probe uses the same `_run()` wrapper; an
inconclusive probe degrades to the array fallback, never a crash.

---

## Testing

- **locator foreground tiebreak** (`tests/test_locator.py`, extends SP1 suite):
  - Two interactive sessions sharing one tty + injected `ps` output where one leader's
    process group carries the `+` (foreground) flag → `pick_foreground_winner` returns
    that single record.
  - Same, but neither/both in the foreground group → returns `None` → `cmd_resolve`
    falls back to the array.
  - Pure function, injected `ps` text — matches the SP1 fixture-injection style.
- **fork-iterm.sh flags** (`tests/test-fork-verify.sh`, `FORK_LIB_ONLY=1` source):
  - `--session-id <id>` sets `SESSION_ID` and skips detection.
  - `--target-pane <%N>` composes `split-window -h -t <%N>` (assert the constructed
    command / a stubbed `tmux`).
  - `--target-pane` in the iTerm branch errors (`exit 2`).
- **`fork-active-pane.sh` wrapper** (new test, `locator.py` + `fork-iterm.sh` shimmed
  on `PATH` or via dirname override):
  - builds the correct `tmux:<socket>:%N` address from a given `$TMUX` + pane arg;
  - routes each of the three locator return shapes to the right branch (fork / "no
    session" toast / "ambiguous" toast);
  - refuses to run with `$TMUX` unset.

---

## Deliverables

1. `session-manager/scripts/fork-active-pane.sh` (new) — the key-binding entrypoint.
2. `session-manager/scripts/locator.py` — foreground tiebreak (`pick_foreground_winner`
   + `cmd_resolve` wiring).
3. `session-manager/scripts/fork-iterm.sh` — `--session-id` and `--target-pane` flags.
4. `session-manager/tests/test_locator.py` — tiebreak fixtures.
5. `session-manager/tests/test-fork-verify.sh` — flag-parsing / split-targeting tests.
6. `session-manager/tests/` — a wrapper test for `fork-active-pane.sh`.
7. `session-manager/CLAUDE.md` — docs for the wrapper, the key-binding snippet, and the
   new flags.
8. Plugin version bump via `./scripts/bump-plugin.sh session-manager minor`.

---

## Acceptance criteria

- Pressing the bound key on a pane running an interactive Claude session forks that
  session into a new horizontal split beside it, and a `tmux display-message` toast
  reports the managed id.
- Pressing it on a pane with no Claude session shows the "no session" toast and does
  nothing else.
- `locator.py resolve --pane` returns a single object for a pane running two
  interactive sessions when their foreground is distinguishable; returns the array only
  when genuinely indistinguishable.
- `fork-iterm.sh --session-id <id> --target-pane <%N>` forks the specified session into
  a split beside the specified pane.
- `--target-pane` supplied to the iTerm branch errors rather than silently ignoring.
- All new and existing tests pass (`python3 session-manager/tests/test_locator.py -v`;
  `bash session-manager/tests/test-fork-verify.sh`; the wrapper test).
- No external-command failure causes a crash; degraded data surfaces as `null` / array
  fallback (SP1 contract preserved).
