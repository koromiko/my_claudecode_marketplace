# Session Locator — SP2.3: reject the `--resume` phantom session in the resolve tiebreak

**Builds on:** merged SP2.2 (`CLAUDE_PID`-anchored placement + `resolve_collision` foreground/on-tty tiebreak, commit `833ef1e`).

**Goal:** When one `claude` TUI resolves to two colliding session ids on a pane — its real active session and a throwaway pre-resume id — `resolve --pane`/`--tty` must return the real one. SP2.2's tiebreak returns the phantom.

## Motivation — the `--resume` flow inverts the on-tty polarity

A TUI started with `claude --resume <id>` generates a fresh session id at init, spawns its stdio MCP servers under that id, then switches its active session to `<id>` (the resume target). The MCP servers keep the throwaway pre-resume id; every later tool child (Bash-tool shells) carries the active id. So **one TUI emits two session ids**, and both anchor to the same TUI pid.

Observed live (pane `%393`, TUI pid `2076` = `claude --resume c392555a…`):

| session | tagged members | carries `CLAUDE_PID=2076` | on TUI's tty | transcript |
|---|---|---|---|---|
| `c392555a` (active) | detached Bash-tool shells | **yes** | no (all `tty=??`) | yes (live) |
| `edf6ab2b` (pre-resume phantom) | context7 + playwright MCP servers | **no** | yes (`ttys034`) | none |

`resolve_collision` runs foreground pgid (both share the TUI's pgid → tie), then on-tty-member presence → the phantom `edf6ab2b` has the on-tty MCP members and wins. Wrong: `edf6ab2b` has no transcript, so the fork fails (`no transcript found for session edf6ab2b…`).

SP2.2's tiebreak assumed the live occupant is the one **with** on-tty MCP members and the straggler is detached-only (the `/clear`-reuse case). The `--resume` flow is the opposite polarity: the **phantom** holds the on-tty MCP servers, and the **active** session is MCP-less on-tty. On-tty presence alone therefore selects the phantom.

## The discriminator

A member carrying `CLAUDE_PID=<tui>` is a first-class witness that TUI `<tui>`'s session is that member's session id. The active session's tool shells carry it; the pre-resume phantom's MCP servers reach the TUI only by ancestor-walk (no `CLAUDE_PID`). This signal is **complementary** to on-tty presence, not a replacement:

- `--resume` collision: only the active session has a `CLAUDE_PID`-carrying member → separates them; on-tty alone does not.
- `/clear`-reuse collision (SP2.2's target): **both** old and new sessions' shells carry `CLAUDE_PID=<tui>` → this signal ties → on-tty presence still separates the live occupant from the detached straggler.

So the fix is a new tiebreak tier ordered **between** foreground pgid and on-tty presence.

## Scope

In scope:
1. New pure helper `claude_pid_anchored_sids(hits, procs)` in `locator.py`, mirroring `on_tty_member_sids`.
2. Insert it as tier 2 in `resolve_collision` (foreground → **CLAUDE_PID carriage** → on-tty → ambiguity).

Out of scope (unchanged): placement (`session_placement`) — the phantom may still appear co-located in `list`, exactly as SP2.2 §4 already documents for stragglers; only `resolve` (which feeds the fork) must be correct. The 10-key record schema; the `resolve` single/array/`[]`+exit-1 contract; the SP2.2 deferrals (`RE_CLAUDE` version-path binaries); SP3–SP5; non-macOS.

## Design

### 1. `claude_pid_anchored_sids(hits, procs)` (pure)

```python
def claude_pid_anchored_sids(hits, procs):
    leader_of = {h["session_id"]: h.get("leader_pid") for h in hits}
    return {p["session_id"] for p in procs
            if p.get("claude_pid") is not None
            and p["claude_pid"] == leader_of.get(p["session_id"])}
```

Returns the session ids among `hits` that have at least one member directly carrying `CLAUDE_PID` equal to that session's resolved TUI (`leader_pid`). For `CLAUDE_PID`-anchored placements `leader_pid == claude_pid` by construction (`session_placement` sets `leader_pid = tui`, and `tui` is the validated `claude_pid`); ancestor-only sessions never match. Pure over injected `hits`/`procs`.

### 2. Tier insertion in `resolve_collision`

```python
def resolve_collision(hits, tty, procs, ps_output):
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

Behavior across cases:
- **`--resume` phantom:** tier 1 ties (shared pgid); tier 2 `by_anchor = [active]` → returns the active session. ✓ (the SP2.3 fix)
- **`/clear`-reuse:** tier 1 ties; tier 2 `by_anchor` has both → not length 1 → tier 3 on-tty returns the live occupant. ✓ (SP2.2 preserved)
- **old-claude (no `CLAUDE_PID`):** tier 2 `anchored` empty → `by_anchor` length 0 → falls through to tier 3 exactly as today. ✓ (no regression)
- **genuine ambiguity:** neither tier separates → original `hits` (array + exit 1). ✓

## Convention alignment

`claude_pid_anchored_sids` is a direct sibling of `on_tty_member_sids` (same file, merged in SP2.2 `833ef1e`): a pure `set`-returning selector over `procs`, consumed by `resolve_collision`. The tier insertion extends the existing multi-tier structure in place. Same-file precedent; ALIGNED.

## Testing

Extend `session-manager/tests/test_locator.py` (injected fixtures, no live processes). All existing tests stay green.

- **`--resume` phantom** — two hits share `leader_pid` (the TUI); one session has a member with `claude_pid == leader_pid`, the other's members carry `claude_pid=None` but resolve to the same TUI by ancestry. Assert `resolve_collision` returns the `CLAUDE_PID`-carrier (single), and (integration) `resolve --pane` returns it as a single object. Regression guard for the `c392555a`/`edf6ab2b` shape.
- **`/clear`-reuse regression** — both hits carry `claude_pid == leader_pid`; only one has a live on-tty member. Assert tier 2 ties and tier 3 returns the on-tty occupant (SP2.2 behavior unchanged).
- **old-claude** — no member carries `claude_pid`; one has an on-tty member. Assert the on-tty tier still resolves it (tier 2 is inert).
- **genuine ambiguity** — neither `CLAUDE_PID` carriage nor on-tty presence separates the hits. Assert the ambiguity array.
- **helper unit tests** — `claude_pid_anchored_sids` returns the right set for: carrier present, `claude_pid` mismatching `leader_pid`, `claude_pid=None`, empty inputs.
- The exact-10-keys schema assertion remains the guardrail.
