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

## SP3 — hook-backed registry (specced: `docs/superpowers/specs/2026-07-27-session-locator-sp3-hook-backed-registry-design.md`)

Hook-backed registry at `SessionStart`/`SessionEnd`, persisting under
`~/.claude/session-manager/sessions/`. Purpose (broadened from the original sketch):
**discovery**, not just enrichment — resolve an idle session that has no live tagged
child (no MCP server, no in-flight Bash-tool shell), which the pull scan cannot see.
The hook stamps `{session_id, claude_pid, cwd, ts}`; the locator falls back to the
registry, liveness-validated on `claude_pid`, only when the pull scan places nothing
(so SP1's pull stays ground truth).

**Storage decision:** per-session files (`sessions/<session_id>.json`), NOT a shared
file. The earlier "mirrors `registry.json`" sketch predated the concurrency point:
every session's `SessionStart` fires independently, and `registry.json` /
`fork-snapshots.list` use non-atomic no-lock writes — a shared file would race.
Per-session files (single writer each) remove the race and match the ambient
`~/.claude/projects/*/<session_id>.jsonl` convention `fork-iterm.sh` relies on.

Session titles / cross-restart parent chains (the original enrichment idea) are
deferred — not needed for the fork use case that motivated SP3.

## How to resume from a new session

1. Read this file + the SP2 / SP3 spec+plan for the most recent context.
2. `git log --oneline` on `main` — SP1/SP2/SP2.x commits are landed.
3. Later sub-projects: invoke `superpowers:brainstorming` (spec → plan → subagent-driven-dev).
