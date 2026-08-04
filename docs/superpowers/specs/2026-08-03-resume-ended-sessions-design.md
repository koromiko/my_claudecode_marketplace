# Resume ended sessions in `tmux-cc-attach` — design

Date: 2026-08-03
Status: approved for planning

## Problem

`tmux-cc-attach` can only reach *live* tmux sessions. A session that ended —
or ran under tmux and was closed — disappears from its view, even though
`claude -r <id>` can bring any of them back given the session's owning
directory. Live-attach is therefore a strict subset of what a user wants when
"restoring my sessions": ended sessions and sessions that never ran under tmux
are unreachable.

This adds a **resume path**, on by default, alongside the existing live-attach:
the SessionEnd hook records each ended session's resume key, and
`tmux-cc-attach` offers recent, still-resumable ended sessions next to the live
ones, launching each in a fresh tmux session under iTerm `-CC`.

## Goals

- Surface recently-ended, still-resumable Claude sessions in `tmux-cc-attach`
  and resume selected ones with `claude -r <id>` from the correct cwd.
- Resumed sessions come back in a fresh tmux session attached `-CC`, so they are
  immediately re-attachable/re-forkable by the existing tooling.
- Do not disturb the SP3 locator contract or its registry sweep.

## Non-goals

- No transcript summaries, friendly titles, or interactive fuzzy picker
  (selection reuses the existing report + glob filters + `-y`).
- No reason-based auto-filtering in v1 (the end `reason` is recorded and
  displayed, not acted on).
- No discovery of sessions that ended before this hook shipped (the store is
  hook-fed; see Migration).

## Hard constraint: resume records need a separate store

`locator.py:_scan_and_build()` calls `_sweep_dead_registry()` on **every**
invocation, which `os.remove`s any `sessions/<id>.json` whose `claude_pid` is
dead (`scripts/locator.py:592`). Ended sessions therefore cannot persist in
`sessions/`. Resume records live in a dedicated store the locator never reads or
sweeps:

```
~/.claude/session-manager/
  sessions/<id>.json   # live registry — locator input; contract UNCHANGED
  resume/<id>.json     # NEW resume store, one file per session
```

`${CLAUDE_SM_HOME}` overrides the base directory, matching the existing hooks.

## Components

### a. SessionEnd hook — `hooks/remove-session.sh` (extended)

Before deleting the live-registry file, capture the resume key and write it to
the resume store:

1. Read `cwd` and `ts` (start) from `sessions/<id>.json` if it still exists;
   otherwise fall back to `cwd` from the SessionEnd hook input.
2. Read `reason` from the SessionEnd hook input (recorded verbatim; the exact
   value set is TBD — verify against Claude Code before relying on any specific
   value).
3. Write `resume/<id>.json` atomically (tmp + `mv -f`, as `record-session.sh`
   does):

   ```json
   {"session_id":"…","cwd":"…","ts_start":…,"ts_end":…,"reason":"…"}
   ```

4. Delete `sessions/<id>.json` exactly as today.

Still `exit 0` on any error or missing `jq`; the hook never blocks shutdown. A
session that ends, is resumed, and ends again simply overwrites its
`resume/<id>.json` with a newer `ts_end`.

### b. Resume-store hygiene (read-time, in the CLI)

On each run that includes resume, before presenting the list:

- **Age prune** — drop (and unlink) entries whose `ts_end` is older than
  `--since` days (default `RESUME_MAX_AGE_DAYS=14`).
- **Resumability prune** — drop (and unlink) entries whose transcript
  `~/.claude/projects/*/<id>.jsonl` no longer exists.
- **Live dedup** — drop entries whose `session_id` is currently live
  (present in `locator.py list`), so a restarted session is not offered as
  "ended."

### c. `tmux-cc-attach` — vendored into `session-manager/scripts/`

The script is moved into `session-manager/scripts/tmux-cc-attach` (tracked +
testable) and `~/.local/bin/tmux-cc-attach` becomes a symlink to it.

Behavior: **resume is on by default.** A plain run lists live sessions to attach
and recent resumable ended sessions to resume, grouped by project.

Flags:

| Flag | Effect |
|------|--------|
| (default) | live-attach + resume recent ended |
| `--no-resume` | live only (previous default behavior) |
| `--resume-only` | ended only |
| `--since <days>` | recency window (default `RESUME_MAX_AGE_DAYS=14`) |
| `-p` / `-x` / `-n` / `-y` / `-d` | apply to both live and ended |
| `-o` (name glob) | live only — ended sessions have no tmux name; filter them with `-p` / `--since` |

Ended sessions are grouped by project using the existing `project_of_dir` logic
(cwd → `git --git-common-dir` parent, collapsing worktrees onto the main repo).
Resume launch reuses the existing AppleScript window/tab machinery, writing one
command per ended session:

```
tmux -CC new-session -c '<cwd>' "claude -r '<id>'"
```

which creates the fresh tmux session in the owning cwd and attaches it `-CC` in
a single step. `cwd` and `id` are shell-single-quote escaped via the existing
`escape_shell_single`.

## Data flow

```
SessionStart ── record-session.sh ─▶ sessions/<id>.json        (locator ground truth)
   │ session runs …
SessionEnd  ── remove-session.sh ─▶ read sessions/<id>.json
                                    → write resume/<id>.json
                                    → delete sessions/<id>.json
   │
tmux-cc-attach  (resume on by default)
   ├─ live:  tmux list-sessions ─▶ tmux -CC attach -t $N        (existing)
   └─ ended: read resume/*.json ─▶ prune(age, transcript, live-dedup)
             ─▶ group by project ─▶ tmux -CC new-session -c <cwd> 'claude -r <id>'
```

## Error handling

- Hook: missing `jq`, unreadable start record, or failed write → skip the resume
  record, `exit 0`. Never blocks session shutdown.
- CLI: a resume entry whose transcript is gone is pruned, not launched. `claude`
  not on PATH at resume time surfaces the same way live-attach failures do (the
  new tmux/iTerm pane shows claude's own error); no extra verification in v1.
- The locator's `_sweep_dead_registry` operates only on `sessions/`, so it can
  never touch `resume/`.

## Testing

- `tests/test-record-session.sh` (extended): SessionEnd writes
  `resume/<id>.json` with merged `ts_start`/`ts_end`/`reason` and deletes
  `sessions/<id>.json`; fallback to hook input when the start record is absent.
- New pure-function tests (source the CLI with a lib-only guard, mirroring
  `FORK_LIB_ONLY=1`): age prune, transcript-exists filter, live-dedup, and the
  `-n` dry-run emitting the correct `claude -r` commands grouped by project
  against a fixture resume store + fake transcript directory.

## Migration

The resume store fills only from the moment the extended SessionEnd hook ships;
sessions that ended earlier will not appear. This is inherent to a hook-fed
store and accepted. No data migration is required. Vendoring the script replaces
`~/.local/bin/tmux-cc-attach` with a symlink into the repo checkout.

## Dependencies / risks

- Depends on the SP3 registry layout and `${CLAUDE_SM_HOME}` convention.
- `reason` field values from the SessionEnd hook are unverified; recorded but not
  relied upon until confirmed.
- Vendoring assumes the repo checkout stays at a stable path for the symlink; if
  the checkout moves, the symlink must be repointed.
