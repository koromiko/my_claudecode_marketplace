# Session Locator — SP2.1: Resolution Hardening (anchor sessions to the real claude TUI)

**Builds on:** merged SP1 (`session-manager/scripts/locator.py`) + SP2 (`fork-active-pane.sh`, foreground tiebreak).

**Goal:** Make `locator.py` resolve a pane to the *correct* interactive session by anchoring every session's identity to its real `claude` TUI process, instead of to whichever tagged child process the env-scan happens to find.

## Motivation — one root cause, two symptoms

Live debugging of the fork hotkey exposed two failures that share a single root cause.

The locator identifies sessions and their panes purely from `CLAUDE_CODE_SESSION_ID` in process **start-time environments** (`ps -E`). But:

- The `claude` TUI generates its session id **at runtime** and exports it only to the processes it spawns. So `ps -E` shows the id on a session's **MCP children / subagents, never on the `claude` TUI itself**.
- **Detached** children (`tty=??`) still carry a `TMUX_PANE=%N` value inherited from their environment, which need not reflect where the TUI actually runs.

Observed live (two sessions, same machine):

```
c392555a (real conv):  94268, 94270   tty=??       child   TMUX_PANE=%126
9ccee61d (fresh):      79770, 79802   tty=ttys008  child   TMUX_PANE=%126
real claude TUI 79481  ttys008  (= 9ccee61d)
```

- **Symptom 1 (MCP-as-leader):** `resolve --pane %126` reported `leader_pid 79770`, a `context7-mcp` process — the leader was an MCP child, not the `claude` TUI.
- **Symptom 2 (ghost attribution):** `c392555a`'s only tagged procs are detached (`tty=??`) yet carry `TMUX_PANE=%126`, so the locator attributed `c392555a` to `%126` even though its TUI runs elsewhere. That produced a spurious second interactive session on `%126`, which the SP2 foreground tiebreak then had to (and did) choose against.

Both stem from **trusting arbitrary tagged child processes instead of the pane's real `claude` TUI**.

## Scope

In scope:

1. **Leader = nearest `claude` ancestor** of a session's tagged processes.
2. **Pane derived from the leader TUI's own tty** (→ tmux pane), not from any process's `TMUX_PANE` env; env-based host detection kept only as the non-tmux fallback.
3. **Friendlier message** in `fork-active-pane.sh` for the no-transcript case.

Out of scope (unchanged): the 10-key record schema; the `resolve` return contract (single object / array / `[]`+exit 1); the SP2 foreground tiebreak mechanism (kept as a safety net); SP3–SP5; non-macOS.

## Design

### 1. Leader = nearest `claude` ancestor

A session's tagged procs are its MCP children / subagents; the TUI itself is not tagged. From any tagged proc, walk **up** the ppid chain — the existing idiom in `resolve_roles` (`locator.py:146-155`) — to the nearest ancestor whose command is the `claude` TUI. That ancestor is the session's leader.

- Reuses the existing **upward** ancestry walk; no new downward `pane_pid` traversal (per the convention review, which flagged a downward rewrite as fighting the unified pipeline and creating a competing leader definition).
- One leader definition for all hosts.
- **Fallback:** if no `claude` ancestor is found (orphaned stragglers whose TUI has exited), keep today's structural leader (min-pid tagged proc whose ppid is outside the session). Such a session will not falsely claim a live pane (see §2).

### 2. Pane from the TUI's tty, not child env

Derive a session's pane from its **leader TUI's tty → tmux pane**, by inverting the existing `tmux_index` (`(socket,pane_id) → {tty,…}`) into a `tty → (socket, pane_id)` map.

- Only when the leader's tty matches no tmux pane do we fall back to env markers on the leader (`ITERM_SESSION_ID` / `TERM_SESSION_ID` for iTerm / Apple Terminal hosts, whose TUI start-env legitimately carries them). A process's `TMUX_PANE` env is **no longer** used for tmux attribution.
- This eliminates the ghost: `c392555a`'s detached children stop attributing it to `%126`; it maps to wherever its TUI's tty is, and `%126` resolves to only `9ccee61d`.
- A session whose leader is not a live TUI on a real tty gets `pane = None` / `pane_live = False` rather than a ghost pane.

### 3. New / changed pure functions (convention-aligned)

All take injected command output or already-parsed dicts, matching `parse_processes` / `build_ppid_map` / `parse_tmux_panes`.

- `build_process_table(ps_output)` → `pid → {ppid, tty, command}` for **all** processes (superset of `build_ppid_map`; ancestry + TUI identification + TUI tty all read from one table).
- `RE_CLAUDE` — module constant mirroring the existing `RE_*`, matching the `claude` program token in the command field (e.g. `(?:^|/)claude(?:\s|$)`), distinct from the `node …-mcp` children.
- `nearest_claude_ancestor(start_pid, table)` → pid of the nearest ancestor process whose command matches `RE_CLAUDE`, else `None`. Pure upward walk (bounded by a seen-set, like `resolve_roles`).
- `tty_to_pane_index(tmux_index)` → `tty → (socket, pane_id)`. Pure inversion.
- `resolve_roles` (or a thin new step it calls) sets `leader_pid` to the claude-ancestor leader; role/`parent_session_id` classification is unchanged. `build_sessions` uses `tty_to_pane_index` for pane/host/tmux-meta derivation from the leader's tty, with the env fallback above.

The impure `gather_sessions` wires `build_process_table` in alongside the existing scans. The record still has exactly the 10 keys; `cmd_resolve` is untouched.

### 4. Tiebreak & contract

With panes anchored to real TUIs, "two interactive sessions on one pane" essentially cannot occur (a tty has one foreground TUI), so the SP2 foreground tiebreak (`pick_foreground_winner`) becomes a rarely-hit safety net. It is **kept**, not removed, so `resolve`'s single/array/`[]`+exit-1 contract is unchanged and consumers need no update.

### 5. `fork-active-pane.sh` message (defect 3)

When the fork fails specifically because the resolved session has no transcript, surface `No saved conversation in this pane yet — nothing to fork.` on the tmux status line / stderr, instead of the raw `Error: no transcript found for session <id>…`. Detect by matching the fork script's existing `no transcript found` error text; all other failures keep their current message.

## Testing

Extend `session-manager/tests/test_locator.py` (injected fixtures, no live processes):

- **MCP-as-leader fixture** — a session whose only tagged procs are `node …-mcp` children under a `claude` ancestor; assert `leader_pid` resolves to the `claude` ancestor, not the MCP child.
- **Ghost fixture** — the observed `c392555a` shape: tagged procs with `tty=??` and `TMUX_PANE=%126`, whose `claude` TUI is on a different tty/pane; assert the session maps to the TUI's pane and does **not** appear as an occupant of `%126`.
- **Orphaned-straggler fixture** — tagged procs with no `claude` ancestor; assert graceful fallback (structural leader, `pane_live = False`, no ghost pane).
- **`tty_to_pane_index` / `nearest_claude_ancestor`** unit fixtures.
- All 29 existing tests stay green; the exact-10-keys assertion (`test_locator.py:172-180`) is the guardrail.

For `fork-active-pane.sh`: extend `tests/test-fork-active-pane.sh` with a shimmed fork that emits the `no transcript found` text; assert the friendly message.

## Convention note

Convention review verdict: **DIVERGENT (minor)** — the new pure functions align with `parse_*/build_*`; identifying the TUI by program name is a new *signal kind* but the same regex-on-command idiom (name it like the existing `RE_*`). The two flagged architecture risks (moving per-host branching earlier; a competing leader definition) are avoided by reusing the upward ancestry walk and keeping one leader definition, as specified in §1–§2.
