# Session Locator — Roadmap & Resume Index

> **Living document.** Records where the session-locator project stands so a fresh
> Claude Code session can resume without re-reading the whole history. Update the
> status table whenever a sub-project lands.

**Last updated:** 2026-06-12 (SP2 merged to `main`).

## What this project is

A read-only system that answers **"which Claude Code session runs in which terminal
pane?"** — and, building on that, **"fork the session in the pane I'm looking at."**
It decomposes by layer; each sub-project (SP) has its own spec → plan → implementation
cycle.

```
SP1 ── Indexer + resolver core   (Layer 1 pull)        ✅ DONE
        └─ foundation everything else joins against
        ├──────────────────────────────┐
        ▼                               ▼
SP2 ── Focus adapters            SP3 ── Hook-backed registry (push)
        (Layer 2)                        (enrich records at SessionStart/End)
        │
        ▼
   ★ FORK HOTKEY shippable (SP1 + SP2) ★   ✅ SHIPPED
        │
        ▼
SP4 ── Daemon + watch/events     (Layer 3 push: Unix socket, focus stream)
        │
        ▼
SP5 ── Reactive consumers        (status bar / overlay example)
```

**Critical path to the fork hotkey: SP1 → SP2** (both done). SP3 and SP4 are
independent enrichments; SP5 consumes them.

## Status

| SP  | Title | Status | Spec | Plan |
|-----|-------|--------|------|------|
| SP1 | Indexer + resolver core (`locator.py`) | ✅ Done, merged | `specs/2026-06-07-session-locator-sp1-design.md` | `plans/2026-06-08-session-locator-sp1.md` |
| SP2 | Focus adapters → fork-the-active-pane tmux key-binding | ✅ Done, merged to `main` | `specs/2026-06-11-session-locator-sp2-design.md` | `plans/2026-06-12-session-locator-sp2.md` |
| SP2.1 | Locator resolution hardening (claude-anchored) | ✅ Done, merged | `specs/2026-07-06-session-locator-sp2.1-locator-hardening-design.md` | `plans/2026-07-06-session-locator-sp2.1.md` |
| SP3 | Hook-backed registry (push: enrich records at SessionStart/End) | ⬜ Not started | — | — |
| SP4 | Daemon + watch/events (Unix socket, focus stream) | ⬜ Not started | — | — |
| SP5 | Reactive consumers (status bar / overlay example) | ⬜ Not started | — | — |

## What shipped (SP1 + SP2)

- **`session-manager/scripts/locator.py`** — read-only, macOS, pull-based. Scans
  process environments; never stale. CLI: `list`, `resolve --pane|--tty|--session`.
- **`session-manager/scripts/fork-active-pane.sh`** — tmux key-binding entrypoint.
  Resolves the focused pane's session via the locator, then forks it through the
  verified `fork-iterm.sh` path into a split beside the pane.
- **`session-manager/scripts/fork-iterm.sh`** — gained `--session-id <id>` (fork an
  explicit session) and `--target-pane <pane>` (split beside a specific pane).
- **Fork hotkey installed:** `prefix + F` in `~/.tmux.conf`.
- Plugin version: `session-manager` 2.7.x. Tests: 52 passing across
  `tests/test_locator.py`, `tests/test-fork-verify.sh`, `tests/test-fork-active-pane.sh`.

## Contracts a resuming session must not break

- **Record schema (10 keys):** `session_id`, `role` (interactive|child),
  `parent_session_id`, `pane` (socket-qualified), `host`, `tty`, `cwd`, `leader_pid`,
  `pane_live`, `tmux`. SP3–SP5 join against this; do not change it without a contract bump.
- **`resolve` return contract:** single JSON **object** when one session matches; JSON
  **array** when several do (ambiguity signal); `[]` + **exit 1** when none match.
- **SP2 foreground tiebreak:** when two interactive sessions share one pane,
  `cmd_resolve` picks the one holding the tty foreground. Mechanism: `ps -t <tty> -o
  pid=,pgid=,stat=`; the foreground pgid is flagged `+`. **The claude leader is often a
  *member* of the foreground group (pid ≠ pgid)** — map `leader_pid → its pgid` and test
  that pgid against the foreground set; do not assume `pgid == leader_pid`. The array is
  returned only when two interactive sessions are genuinely indistinguishable.

## Next sub-project (SP3) — scope sketch (not yet specced)

Hook-backed registry: enrich locator records at `SessionStart`/`SessionEnd` (push),
persisting under `~/.claude/session-manager/` (mirrors `registry.json`). Purpose: carry
metadata the pull scan can't see (e.g. session titles, parent chains across restarts).
SP1's pull remains ground truth; SP3 only enriches. **Start a new SP3 cycle with the
`superpowers:brainstorming` skill** — do not implement before a spec is approved.

## How to resume from a new session

1. Read this file + the SP2 spec/plan for the most recent context.
2. `git log --oneline` on `main` — SP1/SP2 commits are landed.
3. To start SP3: invoke `superpowers:brainstorming` (spec → plan → subagent-driven-dev).
