# Session Locator — SP2.2: `CLAUDE_PID`-anchored placement (place MCP-less sessions)

**Builds on:** merged SP1 (`locator.py`), SP2 (`fork-active-pane.sh`, foreground tiebreak), SP2.1 (claude-anchored placement + liveness anchor, commit `7361efc`).

**Goal:** Resolve a session to its pane even when it has **no live tagged member on the TUI's tty** — the common case once a session's stdio MCP servers exit or were never present. Anchor placement to the TUI named directly by the `CLAUDE_PID` env value, and move stale-straggler rejection from placement to the resolve tiebreak, where the full set of colliding sessions is available to compare.

## Motivation — the liveness anchor is too strict

SP2.1's `session_placement` (`locator.py:255`) proves a session occupies a pane only through **a tagged member whose own tty equals the TUI's tty** (`locator.py:262-282`). A session's tagged members are its stdio MCP servers and Bash-tool shells. Only stdio MCP servers inherit the TUI's controlling tty; Bash-tool shells run **detached** (`tty=??`). So a session has an on-tty member **iff a stdio MCP server is alive**. When none is (never configured, exited, or disconnected mid-session), every tagged member is detached and the session gets `pane=None` — unplaceable, un-forkable.

Verified live (37 sessions, throwaway prototype, no code changes): **2** genuinely interactive `claude` TUIs on real tmux panes were wrongly dropped to `pane=None` by this rule — including the session whose fork hotkey exposed the bug (`c392555a` → TUI `17141` on `ttys034` = pane `%393`). The other 16 `pane=None` sessions are legitimately paneless (dead TUIs, subagents, IDE sessions).

The root fact: the claude TUI does **not** carry `CLAUDE_CODE_SESSION_ID` in its own start-time env (only its children do), but every tagged child **does** carry `CLAUDE_PID=<the TUI's pid>` (verified present on all tagged procs on the test machine). That is a direct, reliable name for the TUI — independent of whether any member shares its tty.

## Scope

In scope:
1. Capture `CLAUDE_PID` as a new `parse_processes` field.
2. Anchor a session's TUI to the process `CLAUDE_PID` names (validated as a live `claude`), deriving the pane from that TUI's **live** tty. Remove the on-tty-member *requirement* from placement.
3. Move stale-straggler rejection into the existing `cmd_resolve` foreground tiebreak, extended to break a same-TUI (same-pgid) tie by on-tty-member presence before returning the ambiguity array.

Out of scope (unchanged): the 10-key record schema; the `resolve` single/array/`[]`+exit-1 contract; SP3–SP5; non-macOS. **Explicitly deferred (separate follow-up):** broadening `RE_CLAUDE` to match a TUI whose command is the version-numbered binary path (`…/claude/versions/2.1.198 …`) instead of `claude`. On the test machine that shape only occurs for agent-team subagents (children, not fork targets); it is a pre-existing gap SP2.2 neither fixes nor worsens.

## Design

### 1. Capture `CLAUDE_PID` (aligned with the `RE_*` field-capture idiom)

Add a module constant `RE_CLAUDE_PID = re.compile(r"\bCLAUDE_PID=(\d+)")` beside the existing `RE_TMUX_PANE` / `RE_ITERM` (`locator.py:27-31`), `.search(command)` it inside `parse_processes`, and pack a `claude_pid` key (`int` or `None`) into each member dict (`locator.py:69-81`) — the same shape as every other optional env signal. (Convention review: this part is ALIGNED.)

### 2. Placement anchors on the named TUI, via a live tty (pure)

In `session_placement`, replace the on-tty-member loop with:

- **Name the TUI candidate:** the `claude_pid` shared by the session's members, accepted only if that pid is present in `proc_table` **and** its command matches `RE_CLAUDE` (a live claude). When `claude_pid` is absent or fails validation (older claude), fall back to today's `nearest_claude_ancestor` ppid-walk (`locator.py:130`) to name the candidate.
- **Derive the pane from the TUI's own tty**, read from `proc_table` (live `ps` at scan time — **not** a member's start-time `TMUX_PANE` env), via `tty_to_pane_index` exactly as today (`locator.py:284-292`). iTerm / Apple-Terminal env-marker fallback on `rep` is unchanged.
- If the named TUI is not a live claude on a tty that maps to a pane → `pane=None` (orphan), as today.

Placement stays a **pure** function over injected `ps`/tmux data; no OS calls are added to `build_sessions`. It may now yield the **same pane for two sessions** (the residual reuse case below) — that is a legitimate candidacy signal, resolved one layer up.

**Why this is ghost-free for the normal case:** the pane comes from the *live* TUI process's own tty, never from a possibly-stale `TMUX_PANE` env. A detached straggler whose real TUI has exited names a dead pid → not in `proc_table` → orphan. A straggler whose TUI is alive elsewhere is placed on *that* TUI's pane (correct), not on a pane it merely remembers.

### 3. Stale-straggler rejection moves to the resolve tiebreak

There is an inherent reason placement alone cannot both (a) place MCP-less single sessions and (b) keep a stale straggler off a **reused** TUI's pane: the discriminator is the *same* signal (on-tty membership) pointing opposite ways. So the reuse case — one `claude` TUI process reused across sessions (`/clear`, in-process re-resume), where a previous session's detached members still name the current live TUI pid — is resolved where the full set of colliding sessions is visible: `cmd_resolve`.

- Keep `pick_foreground_winner` (`locator.py:423`) as the primary tiebreak (live foreground pgid via `ps -t <tty>`).
- **Extend it:** when the foreground pgid does not separate the hits (they share the reused TUI's pgid), prefer the session that has a **live on-tty tagged member** (SP2.1's exact signal, checked live at scan time). This preserves `7361efc`'s guarantee: the real occupant (with on-tty MCP members) wins over the stale straggler (detached-only).
- Only when neither pgid nor on-tty presence separates them → return the ambiguity array (fail-safe; `fork-active-pane.sh` shows "Multiple Claude sessions — can't disambiguate"). This is strictly better than today's common-case hard failure.

No recency / pid-ordering heuristic is introduced (pid order is not a liveness signal). No new resolution layer is created; the one ambiguity-resolution layer remains `cmd_resolve`.

### 4. Behavioral change to record: honest and documented

Because rejection moves to the resolve layer, in the rare reuse case `locator.py list` may now show a **stale straggler co-located** on a pane (as a candidate), where SP2.1 showed it as `pane=None`. `resolve --pane` — the only consumer that must be correct (it feeds the fork) — still returns the single live occupant. The 10-key schema and the `resolve` contract are unchanged.

## Convention alignment

A convention-checker pass on the *initial* shape returned **DIVERGENT (significant)** for two reasons, both addressed here:
- *Anchoring on `CLAUDE_PID` with no live check* would reintroduce the `7361efc` ghost. → Fixed: the anchor is validated live (`proc_table` + `RE_CLAUDE`), the pane comes from the live TUI's tty, and reuse collisions are rejected by a live signal in the tiebreak.
- *A recency ("newest member wins") rule inside placement* is an unprecedented resolution layer and not a liveness signal. → Dropped entirely; resolution stays in `cmd_resolve` and the discriminator is on-tty presence, SP2.1's already-established live signal.

The `CLAUDE_PID` field-capture itself is a straightforward instance of the existing `RE_*`/`parse_processes` idiom.

## Testing

Extend `session-manager/tests/test_locator.py` (injected fixtures, no live processes). All existing tests stay green except the SP2.1 placement-level straggler assertion, which is **re-expressed** at the resolve/tiebreak level (per §3–§4).

- **MCP-less detached-only session** — members all `tty=??` carrying `CLAUDE_PID=<live claude pid>`; the TUI is a live `claude` on a tty that maps to a pane. Assert the session is placed on that pane (the SP2.2 fix; regression guard for `c392555a`-shaped input).
- **Orphaned straggler** — `CLAUDE_PID` names a dead pid (absent from `proc_table`). Assert `pane=None`.
- **`CLAUDE_PID` absent** — no `CLAUDE_PID` on any member; assert the `nearest_claude_ancestor` fallback reproduces SP2.1 placement.
- **Reuse collision at the resolve layer** — two sessions name the same live TUI pid; one has a live on-tty member, the other is detached-only. Assert `cmd_resolve` returns the on-tty session as a single object (not the ambiguity array), and that both may appear in `list`.
- **Genuine ambiguity** — two sessions share one TUI pid, neither separable by pgid or on-tty presence. Assert the ambiguity array + exit 1.
- The exact-10-keys assertion (`test_locator.py`) remains the schema guardrail.

## Verification evidence (prototype, pre-implementation)

A standalone prototype of §2–§3 run against the 37 live sessions on the dev machine: **2** sessions recovered a correct pane (incl. `c392555a` → `%393`), **0** sessions lost a pane, **0** panes claimed by more than one session (no ghosts, no collisions in the current population). The foreground-liveness variant produced identical results, confirming it costs nothing here and serves purely as the collision safety.
