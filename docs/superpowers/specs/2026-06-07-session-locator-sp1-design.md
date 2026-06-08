# Session Locator — SP1: Indexer + Resolver Core

**Date:** 2026-06-07
**Status:** Approved design (pre-implementation)
**Plugin:** `session-manager`
**Platform:** macOS only

---

## Context: the larger system

The goal is a generalized system that lets any terminal, app, or script answer two
questions about Claude Code sessions on the local machine:

- **A. Mapping** — "what Claude session runs in pane X?" (objective; needs only process introspection)
- **B. Focus** — "which pane is the user looking at right now?" (subjective; needs a frontend adapter)

The motivating consumer is a fork hotkey: from a tmux key binding, fork the Claude
session in the *focused* pane. But the design generalizes so other consumers (status
bars, overlays, automation) can use the same substrate.

### Why the environment is the universal join

A single running Claude process simultaneously carries, in its environment:

- `CLAUDE_CODE_SESSION_ID` — the session
- `TMUX_PANE` + `TMUX` (socket) — the tmux pane it lives in
- `ITERM_SESSION_ID` / `TERM_SESSION_ID` — the host terminal session
- `TERM_PROGRAM` — the innermost frontend

So *Claude session ↔ pane ↔ host terminal* is fully recoverable from one process's
environ — no UI scraping required for the mapping. This was verified empirically on
the development machine (tmux-inside-iTerm).

### Decomposition into sub-projects

The full system decomposes by layer. Each sub-project gets its own spec → plan →
implementation cycle.

```
SP1 ── Indexer + resolver core   (Layer 1 pull)        ← THIS SPEC
        └─ foundation everything else joins against
        ├──────────────────────────────┐
        ▼                               ▼
SP2 ── Focus adapters            SP3 ── Hook-backed registry (push)
        (Layer 2)                        (enrich records at SessionStart/End)
        │
        ▼
   ★ FORK HOTKEY shippable (SP1 + SP2) ★
        │
        ▼
SP4 ── Daemon + watch/events     (Layer 3 push: Unix socket, focus stream)
        │
        ▼
SP5 ── Reactive consumers        (status bar / overlay example)
```

**Critical path to the fork hotkey: SP1 → SP2.** SP3 and SP4 are independent
enrichments. This document specifies **SP1 only**.

---

## SP1 scope

A macOS-only, **read-only, pull-based** tool that answers "which Claude session runs
in which pane" by scanning process environments **at query time**.

- **No daemon, no hooks, no persisted state.** Pure pull means the answer is always
  ground truth and never goes stale. (Hook-backed enrichment is SP3, explicitly out
  of scope here.)
- Produces the **record schema** every later sub-project joins against — the schema
  is the real deliverable; the CLI is its first consumer.
- A working spike exists at `session-manager/scripts/locator.py`; SP1 hardens it.

### Out of scope for SP1

- Focus detection ("which pane is focused") — SP2.
- Multiple clients attached to one tmux socket — a focus concern, SP2.
- Hook-backed registry / push events — SP3 / SP4.
- Linux / non-macOS — no OS-abstraction layer is built (may be added later if a real
  need appears).

### Code-shape (verified against repo convention — ALIGNED)

- Pure **Python 3, stdlib only** (`argparse`, `json`, `os`, `re`, `subprocess`).
- Single-file script at `session-manager/scripts/locator.py`.
- `add_subparsers` CLI emitting `json.dumps(..., indent=2)` to stdout; `sys.exit(1)`
  on no-match.
- Any future state file goes under `~/.claude/session-manager/` (mirrors
  `registry.json`); SP1 itself persists nothing.

Precedent: `claude-usage-analyzer/scripts/{generate_report,extract_sessions,analyze_sessions}.py`
(pure-Python stdlib argparse CLIs), and the existing `locator.py` spike.

---

## The record schema (the contract)

`list` emits an array of these. `resolve` emits a single object (the matching
`interactive` record) or, when ambiguous, the matching subset.

```json
{
  "session_id": "83ae8ca6-…",
  "role": "interactive",
  "parent_session_id": null,
  "pane": "tmux:default:%86",
  "host": "tmux",
  "tty": "ttys016",
  "cwd": "/Users/sthuang/Project/my_claudecode_marketplace",
  "leader_pid": 12345,
  "pane_live": true,
  "tmux": { "socket": "default", "session": "work", "window": "3", "active": true }
}
```

| Field | Type | Meaning |
|-------|------|---------|
| `session_id` | string (uuid) | Claude Code session id (from `CLAUDE_CODE_SESSION_ID`). |
| `role` | `"interactive"` \| `"child"` | Interactive = the session the user drives; child = a session spawned by another (subagent / headless `claude`). |
| `parent_session_id` | string \| null | Set when `role` is `child`; the interactive session that spawned it. |
| `pane` | string \| null | **Socket-qualified** address: `tmux:<socket>:%N`, `iterm:<guid>`, or `term:<guid>`. Null if no host pane resolvable. |
| `host` | `"tmux"`\|`"iterm"`\|`"apple-terminal"`\|null | Innermost host frontend. |
| `tty` | string \| null | Bare form (`ttys016`). Authoritative from tmux pane when host is tmux; process tty is unreliable (`??`) for detached node leaders. |
| `cwd` | string \| null | Working directory of the leader process (via `lsof -d cwd`). |
| `leader_pid` | int | Pid of the session's leader (topmost) process. |
| `pane_live` | bool | For tmux hosts: whether `(socket, pane)` still exists in the tmux index (false = detached straggler). For non-tmux hosts (iterm / apple-terminal) and detached sessions with no host: true iff the leader process is alive — which it always is by construction (it was just scanned), so non-tmux records are always `pane_live: true`. |
| `tmux` | object \| null | tmux metadata when host is tmux. |

### Schema decisions

1. **Flat records, not nested.** Children are their own records carrying
   `parent_session_id`, rather than being nested inside the interactive record. This
   keeps every record uniform and lets consumers filter by `role` trivially.
2. **Socket-qualified pane address.** The spike proved pane ids like `%86` are *not*
   unique across tmux sockets (`default`, `sm_e2e`, `sm_tty` all coexist). The pane
   address must include the socket basename to be a stable, globally-unique key.
3. **`resolve --pane X` returns only the `interactive` record.** `list` shows
   everything (interactive + children). This matches the agreed semantics: the
   default answer to "what session is in this pane" is the one the user is driving.

### `resolve` selector semantics

- **`--pane <addr>`** → the single `interactive` record for that pane (or both
  records if the rare two-interactive-roots ambiguity occurs; see edge cases).
- **`--tty <tty>`** → same as `--pane`, addressed by tty: the `interactive` record
  for the pane on that tty.
- **`--session <id>`** → the one record with that exact `session_id`, whether its
  `role` is `interactive` or `child` (this selector addresses a specific session, so
  it does not filter by role).

In all cases `resolve` exits non-zero if there is no match.

---

## Components

All within the single `locator.py`. Parsing/resolution are **pure functions** that
accept injected command output (for testability); only thin wrappers call `ps` /
`tmux` / `lsof`.

- **`parse_processes()`** — parse `ps -E -ww -o pid=,ppid=,tty=,command=`, extract
  format-validated markers (session uuid, `TMUX_PANE`, `TMUX` socket,
  `ITERM_SESSION_ID`, `TERM_SESSION_ID`, `TERM_PROGRAM`). Builds the per-process raw
  records. Strict marker regexes reject the scanner's own `ps`/`grep` command lines.
- **`build_ppid_map()`** — global `pid → ppid` map from the same `ps` output (covers
  *all* processes, not just claude-tagged ones, so ancestry walks don't dead-end).
- **`tmux_pane_index()`** — enumerate **all** tmux sockets (glob
  `/private/tmp/tmux-<uid>/*` plus the socket from `$TMUX`), run `list-panes -a` per
  socket, build `(socket, pane_id) → {tty, pane_pid, session, window, active}`. This
  is the multi-socket fix.
- **`resolve_roles()`** — the ancestry algorithm (below). Pure function over the raw
  records + ppid map.
- **`build_sessions()`** — assemble final records: attach authoritative tmux tty,
  resolve cwd via `lsof`, compute `pane_live`.
- **CLI dispatch** — `list`, `resolve --pane/--tty/--session`.

---

## Resolution algorithm

The spike exposed four realities a naive version gets wrong; the algorithm handles
each:

1. **Scan** → claude-tagged processes (format-validated) + global `pid → ppid` map.
2. **Group by `session_id`.** Each group's **leader** = its topmost process (the
   group member whose parent is not itself in the group).
3. **Assign role by ancestry.** For each leader, walk `ppid` upward and find the
   *nearest claude-tagged ancestor whose `session_id` differs*:
   - **none found** → `role: interactive` (the parent chain reaches a plain shell /
     the pane);
   - **found** → `role: child`, `parent_session_id` = that ancestor's session.

   *(This is how a headless/subagent session sharing a pane gets correctly demoted to
   a child of the interactive session — the `c392555a`-under-`%86` case.)*
4. **Pane identity = `(socket, pane_id)`.** The socket comes from the leader's `TMUX=`
   env (first comma-field). tty is enriched from `tmux_pane_index` (authoritative);
   the process tty is ignored for tmux hosts because node detaches (`tty=??`).
5. **`pane_live`** = whether `(socket, pane)` still exists in the tmux index. Detached
   stragglers are reported with `pane_live: false`, never silently mapped onto a dead
   pane.

### Known edge cases & dispositions

- **Session appears under multiple panes** (inherited env in a re-parented child):
  resolved by the ancestry rule — only the leader's own pane counts; the leader has
  exactly one `(socket, pane)`.
- **Two independent interactive roots in one pane** (rare; sequential sessions): if
  ancestry yields two interactive candidates for one pane, prefer the one whose
  leader matches the pane's live foreground (tty / `pane_pid` descendant); if still
  ambiguous, return both and flag it (consumer decides). Documented, not silently
  collapsed.
- **No tmux server / tmux not installed:** tmux fields null; fall back to process tty
  and `ITERM_SESSION_ID` / `TERM_SESSION_ID`.

---

## Error handling

Every external call (`ps`, `tmux`, `lsof`) is **best-effort and never raises** — a
failure or timeout yields `null` fields, not a crash. This is deliberate: the tool is
a read-only introspector and partial data is more useful than an exception.
`resolve` exits non-zero only when there is no matching session.

> Note: `ps` / `tmux` / `lsof` here are local read-only introspection commands, not
> the "critical internal tools" (MCP/CLI sources of truth) covered by the stop-and-ask
> rule. Best-effort degradation is the correct behavior for them.

---

## Testing

- **Pure-function design for testability.** `parse_processes`, `resolve_roles`,
  `tmux_pane_index` parsing, and `build_sessions` accept injected command output
  (raw `ps`/`tmux`/`lsof` text) rather than shelling out themselves. The thin shell
  wrappers are the only impure code.
- **Fixtures from the four spike-discovered cases:**
  1. one session id appearing across two panes (inherited env);
  2. two session ids in one pane (interactive + child);
  3. the same pane id (`%86`) on two different sockets;
  4. scanner self-noise (a `grep`/`ps` line containing literal `TMUX_PANE=` text).
- Each fixture asserts the resolved records (role assignment, pane address,
  tty enrichment, `pane_live`).
- **Location/style:** `session-manager/tests/`, mirroring the existing
  `test-fork-verify.sh` approach (a runnable test script), adapted for Python (e.g.
  a `test_locator.py` using stdlib `unittest`, invoked from the same tests dir).

---

## Deliverables

1. Hardened `session-manager/scripts/locator.py` implementing the schema, components,
   and algorithm above.
2. `session-manager/tests/test_locator.py` with the four fixture cases.
3. `session-manager/CLAUDE.md` updated to document the locator tool, its CLI, and the
   record schema (the contract SP2–SP5 depend on).
4. Plugin version bump via `./scripts/bump-plugin.sh session-manager minor`.

---

## Acceptance criteria

- `locator.py list` returns one record per live Claude session, each correctly
  role-tagged and mapped to a socket-qualified pane (verified against the live
  machine state).
- `locator.py resolve --pane tmux:<socket>:%N` returns the single interactive record
  for that pane.
- `locator.py resolve --tty <tty>` and `--session <id>` resolve correctly.
- All four fixture tests pass.
- No external-command failure causes a crash; degraded data surfaces as `null`.
