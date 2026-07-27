# Session Locator — SP3: hook-backed registry (discover idle childless sessions)

**Builds on:** merged SP1 (`locator.py` pull scan), SP2 (foreground tiebreak), SP2.1 (claude-anchored placement + liveness anchor), SP2.2 (`CLAUDE_PID`-anchored placement), SP2.3 (`CLAUDE_PID`-carriage resolve tiebreak, commit `016e033`).

**Fills the roadmap's reserved SP3 slot** (`docs/superpowers/session-locator-roadmap.md:75-81` — "Hook-backed registry … SessionStart/SessionEnd"), broadening its sketched purpose from *enrichment* to *discovery*.

**Goal:** Resolve a session to its pane even when it has **no live tagged process at all** — no MCP server, no in-flight Bash-tool shell. The pull scan discovers a session only through its tagged children; an idle session between turns (or one whose MCP servers have exited) has none, so it is invisible and the fork hotkey resolves `NONE`. A hook records each session's `{session_id → claude_pid}` at start; the locator falls back to that registry, liveness-validated, when the pull scan places nothing.

## Motivation — the pull scan is blind to a childless session

The claude TUI does not carry `CLAUDE_CODE_SESSION_ID` in its own environment; only its children do. `parse_processes` therefore discovers a session only via a tagged child (stdio MCP server or a Bash-tool shell). An idle interactive session with no MCP server and no tool in flight has **zero** tagged processes, so `build_sessions` produces no record for it and `resolve --pane` returns `[]`.

Verified live: this session (`c392555a`, TUI pid `40116`, `claude --resume c392555a…` on `%393`) has an actively-growing transcript but, between tool calls, **no** process carries its id — its MCP servers had disconnected. Pressing the fork hotkey on the idle pane logged `[fork] forked %393 -> ` (empty) — `fork-active-pane.sh` hit its `SESSION_ID=NONE` exit-0 path. The fork appears to "succeed" (rc 0) but does nothing.

Discovery signals that do **not** work, and why:
- **TUI argv (`--resume <id>`)** — covers resumed sessions only; a fresh `claude` carries no id in argv.
- **TUI open file descriptors** — the TUI does not hold its transcript open (`lsof -p <tui>` shows no `.jsonl`); it appends and closes per write.
- **cwd → latest transcript** — ambiguous: many panes run `claude` in the same repo, so cwd cannot say which transcript belongs to which pane.

The only child-independent, unambiguous source is a record written **from inside the session** (where the id and the TUI pid are both known) at a lifecycle event — a hook.

## Scope

In scope:
1. `SessionStart` hook: stamp `~/.claude/session-manager/sessions/<session_id>.json` = `{session_id, claude_pid, cwd, ts}`.
2. `SessionEnd` hook: delete that file (clean-exit cleanup).
3. `locator.py`: a pure `merge_registry_sessions(...)` that synthesizes records for registry entries not discovered by the pull scan, placed claude-anchored on `claude_pid` and validated for liveness; called from `_scan_and_build` after `build_sessions`. Sweep entries whose `claude_pid` is dead.
4. Roadmap doc update: mark SP3 specced; record the per-session-file decision + rationale.

Out of scope (unchanged): the 10-key record schema; the `resolve` single/array/`[]`+exit-1 contract; the SP2.x process-scan discovery (registry is a **fallback**, never overrides a live-discovered session); non-macOS; session titles / cross-restart parent chains (the roadmap's original enrichment idea — deferred, not needed for the fork). No change to `fork-active-pane.sh` / `fork-iterm.sh`; they consume `resolve` unchanged.

## Design

### 1. Registry storage — per-session files (divergence, recorded)

`~/.claude/session-manager/sessions/<session_id>.json`, one file per live session, each written **only** by that session's own hook. Each file: `{"session_id": "<uuid>", "claude_pid": <int>, "cwd": "<path>", "ts": <epoch>}`.

The existing session-manager state (`registry.json`, `fork-snapshots.list`) uses a single shared file with **non-atomic** read-modify-write and no locking. SP3 introduces genuinely concurrent independent writers (every session's own `SessionStart` fires on its own schedule); following the shared-file precedent literally would import a data-loss race. Per-session files remove the race by construction and match the ambient single-writer-per-file convention `fork-iterm.sh` already depends on (`~/.claude/projects/*/<session_id>.jsonl`). The roadmap's "mirrors `registry.json`" sketch predates this concurrency consideration and is updated by this spec.

### 2. `SessionStart` hook — `hooks/record-session.sh`

Reads the hook stdin JSON (`session_id`, `cwd`) and the environment. Determines `claude_pid`:
- `$CLAUDE_PID` when set (the TUI pid, carried by every child); else
- a bounded ppid-walk from `$PPID` to the nearest ancestor whose command is the `claude` TUI (same idea as `nearest_claude_ancestor`), so the hook does not depend on `CLAUDE_PID` being present.

Writes the JSON to a temp file in the same dir and `mv`s it into place (atomic replace). `mkdir -p` the `sessions/` dir first. Never fails the session: any error exits 0 (a hook that errors must not block the TUI). Fires for `startup`, `resume`, `clear`, `compact` — all re-stamp the same file (idempotent).

`session_id` from stdin is the active/transcript id (the id the fork must resume) — confirmed: tool children carry that id, and for `--resume` it equals the resume target (`c392555a`), not the pre-resume phantom.

### 3. `SessionEnd` hook — `hooks/remove-session.sh`

Reads `session_id` from stdin, deletes `~/.claude/session-manager/sessions/<session_id>.json` if present. Exits 0 regardless. This is the clean-exit path; pid-liveness pruning (below) is the backstop for crashes / kills where `SessionEnd` never fires.

### 4. `hooks/hooks.json`

Mirrors `default-tools/hooks/hooks.json`: `{ "hooks": { "SessionStart": [{ "hooks": [{ "type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/hooks/record-session.sh", "timeout": 5000 }] }], "SessionEnd": [{ "hooks": [{ "type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/hooks/remove-session.sh", "timeout": 5000 }] }] } }`. Auto-discovered; no `hooks` key added to `plugin.json`.

### 5. `locator.py` — `merge_registry_sessions` (pure) + `_scan_and_build` wiring

```
def merge_registry_sessions(sessions, entries, proc_table, tmux_index, tty_pane_idx):
    known = {s["session_id"] for s in sessions}
    out = list(sessions)
    for e in entries:
        sid, cpid = e.get("session_id"), e.get("claude_pid")
        if not sid or sid in known:                      # live discovery wins
            continue
        if not cpid or cpid not in proc_table:            # dead / unknown TUI
            continue
        if not RE_CLAUDE.search(proc_table[cpid]["command"]):
            continue
        member = {"pid": cpid, "claude_pid": cpid, "tty": None,
                  "iterm_session_id": None, "term_session_id": None}
        placement = session_placement([member], member, proc_table, tmux_index, tty_pane_idx)
        out.append({"session_id": sid, "role": "interactive",
                    "parent_session_id": None, "cwd": e.get("cwd"),
                    **{k: placement[k] for k in
                       ("pane","host","tty","leader_pid","pane_live","tmux")}})
        known.add(sid)
    return out
```

- Placement reuses `session_placement` claude-anchored on `claude_pid` (its first branch: a member whose `claude_pid` is a live `claude`) — so a registry session lands on the TUI's live tty→pane exactly like a pull-discovered one. Record has the **same 10 keys**.
- `_scan_and_build` reads the registry dir (impure, alongside its `ps`/`tmux` reads), passes parsed entries to the pure merge, and sweeps files whose `claude_pid` is absent from `proc_table` or not a `claude` (opportunistic cleanup, like the `fork-snapshots` sweep). The registry read is the only new impure surface; the merge is pure and unit-tested with injected entries.

Because a registry session is only added when **no** live session already has that id, the SP2.x pull scan stays ground truth and the `resolve` tiebreaks (`resolve_collision`) are unaffected — a registry session appears only where the scan found nothing, so it never creates a new collision.

## Convention alignment

Convention-checker verdict: hooks.json shape ALIGNED (`default-tools/hooks/hooks.json`); pure-merge-from-`_scan_and_build` ALIGNED (`locator.py` `_scan_and_build`/`build_sessions`/`session_placement`, test seam at `test_locator.py`); per-session-file storage DIVERGENT (minor) vs the roadmap's "mirrors `registry.json`" sketch — surfaced to and approved by the user, roadmap updated, justified by the concurrent-writer race the shared-file precedent would import.

## Testing

Extend `session-manager/tests/test_locator.py` (injected fixtures) and add `session-manager/tests/test-record-session.sh` (hook scripts).

`merge_registry_sessions` (pure):
- **live pid → placed** — entry `{sid, claude_pid=P}` where `P` is a `claude` in `proc_table` on a tty that maps to a pane; assert a 10-key interactive record placed on that pane.
- **dead pid → skipped** — `claude_pid` absent from `proc_table`; assert not added.
- **non-claude pid → skipped** — `claude_pid` in `proc_table` but command isn't `claude`; assert not added.
- **dup with live → live wins** — `sid` already in `sessions`; assert the registry entry is ignored (no duplicate, live record unchanged).
- **empty entries / empty sessions** — identity / no-op.
- exact-10-keys schema assertion holds for a registry-synthesized record.

Hook scripts (`test-record-session.sh`, tmpdir-scoped via an env override for the registry dir):
- `record-session.sh` with stdin `{session_id, cwd}` + `CLAUDE_PID` set → file written with the four fields; a second run re-stamps idempotently; write is atomic (temp + `mv`).
- `CLAUDE_PID` unset → ppid-walk still records a `claude_pid` (or exits 0 writing nothing rather than erroring).
- `remove-session.sh` deletes the file; deleting a nonexistent file still exits 0.

## Verification (post-implementation, live)

After install + restarting a `claude` in a pane and letting it go idle (no tool running): `locator.py resolve --pane <that-pane>` returns the session as a single object (previously `[]`), and the fork hotkey creates a pane instead of "nothing to fork." Environment-dependent (needs a restarted session so the hook has fired) — informational, not a unit gate.
