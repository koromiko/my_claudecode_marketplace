# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a Claude Code plugin for managing terminal sessions across tmux panes and iTerm tabs. It provides:
- Session forking (continue a Claude session in a new pane/tab)
- Command execution in new tracked panes/tabs
- Output capture and command sending to managed panes
- Registry-based pane tracking across Claude sessions

## Plugin Structure

```
.claude-plugin/plugin.json      # Plugin manifest (name, version, description)
commands/
  fork.md                       # Fork current Claude session to new pane/tab
  run-in-pane.md                # Run command in new tracked pane/tab
skills/
  pane-context/SKILL.md         # Skill for interacting with managed panes
scripts/
  fork-iterm.sh                 # Legacy fork script (tmux and iTerm)
  session-manager.sh            # Unified management script with subcommands
```

## Key Components

### session-manager.sh

Unified script with subcommands for pane management:

| Subcommand | Usage | Description |
|------------|-------|-------------|
| `run` | `run <cmd> [--working-dir <path>]` | Run command in new pane/tab, return managed ID |
| `capture` | `capture <id> [--lines N] [--no-sync]` | Capture output from pane (default 100 lines) |
| `send` | `send <id> <cmd> [--no-sync]` | Send command to existing pane |
| `list` | `list [--auto-cleanup] [--no-sync]` | List all managed panes with real-time status |
| `status` | `status <id>` | Check if pane is active/stale |
| `sync` | `sync [--auto-remove]` | Validate registry against actual tmux panes |
| `cleanup` | `cleanup` | Remove stale registry entries |

### locator.py (session ↔ pane indexer/resolver)

Read-only, pull-based tool (macOS) that maps running Claude Code sessions to
terminal panes by scanning process environments. No daemon, no state — every
query re-scans, so results are never stale. Foundation for the larger
session-locator system (focus adapters / daemon / hooks, SP2–SP5); other tools
consume its JSON contract.

CLI:
- `locator.py list` — JSON array, one record per live Claude session.
- `locator.py resolve --pane tmux:<socket>:%N | %N | iterm:<guid> | term:<guid>` — the interactive session in that pane.
- `locator.py resolve --tty <tty>` — the interactive session on that tty.
- `locator.py resolve --session <uuid>` — that specific session (role-agnostic).

Record schema (the contract): `session_id`, `role` (interactive|child),
`parent_session_id`, `pane` (socket-qualified), `host`, `tty`, `cwd`,
`leader_pid`, `pane_live`, `tmux`. `resolve --pane/--tty` return only the
`interactive` record; `list` shows children too.

How it works: a running Claude process carries `CLAUDE_CODE_SESSION_ID` plus its
host pane id (`TMUX_PANE` / `ITERM_SESSION_ID`) in one environment, so the
session↔pane mapping is recoverable without UI scraping. Roles are resolved by
process ancestry — a session whose leader descends from another Claude session is
a `child` (subagent / headless invocation). Pane ids are socket-qualified because
they are not unique across tmux servers. See
`docs/superpowers/specs/2026-06-07-session-locator-sp1-design.md`.

Resolution is **claude-anchored**: a session's pane and `leader_pid` come from its
real `claude` TUI process, and the pane is derived from that TUI's live tty — never
from a `TMUX_PANE` env value on a possibly-detached child, so a stray child never
ghosts a session onto a pane its TUI does not occupy. The TUI is identified by the
`CLAUDE_PID` a tagged child carries in its environment (validated as a live `claude`
process), falling back to a `nearest_claude_ancestor` ppid-walk when absent. This
resolves sessions whose only tagged members are detached — no live stdio MCP server
on the TUI's tty — which the earlier on-tty-member rule left unplaced (SP2.2). When
one `claude` TUI is reused across sessions, a stale straggler and the live occupant
name the same pid and both appear placed in `list`; `resolve --pane`/`--tty` breaks
the tie via foreground pgid, then by which session has a live on-tty member,
returning the single live occupant.

When a session is **idle with no live tagged child** (no stdio MCP server, no in-flight
Bash-tool shell), the pull scan cannot see it — the TUI itself carries no
`CLAUDE_CODE_SESSION_ID`. A **hook-backed registry** (SP3) closes this gap: a
`SessionStart` hook writes `~/.claude/session-manager/sessions/<session_id>.json`
(`{session_id, claude_pid, cwd, ts}`) and a `SessionEnd` hook deletes it. When the pull
scan places no session for a pane, `merge_registry_sessions` synthesizes the record from
the registry, placed claude-anchored on the recorded `claude_pid` — but only if that pid
is still a live `claude` (dead entries are ignored and swept). Live-scan discovery always
wins over the registry (dedup by `session_id`), so SP1's pull remains ground truth. See
`docs/superpowers/specs/2026-07-27-session-locator-sp3-hook-backed-registry-design.md`.

Resolve return contract (important for SP2 consumers): `resolve` prints a single
JSON object when exactly one session matches, a JSON array when several do, and
`[]` with exit code 1 when none do. **The array case is the ambiguity signal** —
e.g. two independent interactive sessions sharing one pane. SP1 does not break
that tie at the SP1 layer; SP2 added a foreground tiebreak in `cmd_resolve`, so
`resolve --pane`/`--tty` now return a single object whenever the pane foreground
is determinable, and the array only when two interactive sessions are genuinely
indistinguishable. Consumers must still handle the array case (test for a list /
`len > 1`).

Tests: `python3 session-manager/tests/test_locator.py -v`.

### Resume store (ended sessions)

A separate store from the live registry above, for sessions that have already
ended. The `SessionEnd` hook (`hooks/remove-session.sh`) writes
`${CLAUDE_SM_HOME:-$HOME/.claude/session-manager}/resume/<session_id>.json`
(`{session_id, cwd, ts_start, ts_end, reason}`) before deleting the live
`sessions/<id>.json` file. `cwd` comes from the start record when present,
falling back to the `SessionEnd` payload's `cwd`. `ts_end` is always the
hook's own `date +%s` at removal time, never read from any payload. `ts_start`
comes from the start record's `ts`; when that's missing or non-numeric,
`ts_start` is set equal to the computed `ts_end`. No record is written if no
`cwd` is known (`claude -r` needs it to resume).

`locator.py` never reads or sweeps `resume/` — it only ever reads and sweeps
`sessions/`. The two stores are independent; `resume/` entries are pruned
only at read time by `tmux-cc-attach` (below), never by the locator.

Tests: `bash session-manager/tests/test-record-session.sh`.

### tmux-cc-attach (attach live sessions, resume ended ones)

`scripts/tmux-cc-attach` is the vendored copy of the former
`~/.local/bin/tmux-cc-attach` global script. Resume is **on by default**: a
plain run lists both live tmux sessions to attach and recent resumable ended
sessions from the `resume/` store, grouped by project (`project_of_dir`).

Resume-specific flags:
- `--no-resume` — live sessions only.
- `--resume-only` — ended sessions only; skips the tmux-server preflight.
- `--since <days>` — recency window override; validated as a non-negative
  integer (dies otherwise).
- `RESUME_MAX_AGE_DAYS` (env, default `14`) — default recency window.

`-o`/`--only` (name glob) applies to live sessions only. `-p`/`--project`
and `--since` filter resume entries too.

Read-time hygiene runs on every listing: entries past the age window,
entries whose transcript (`~/.claude/projects/*/<session_id>.jsonl`) is gone,
and entries whose `session_id` is currently live (per `locator.py list`) are
omitted from the list. Under `-n` (dry-run) the omission still happens, but
the stale/no-transcript record files are not deleted.

Each picked resume entry launches via `resume_attach_command`:
`tmux -CC new-session -c '<cwd>' "claude -r '<id>'"` — a fresh tmux session
in the owning cwd, attached in iTerm control mode.

Tests: `bash session-manager/tests/test-tmux-cc-attach.sh`.

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

### Registry System

Panes are tracked in `~/.claude/session-manager/registry.json`:
- Unique managed IDs: `sm-{6-char-random}` format
- Maps to underlying tmux pane IDs or iTerm session IDs
- Persists across Claude sessions

### Terminal Detection

1. Checks `$TMUX` env var for tmux
2. Uses AppleScript to detect running iTerm
3. Creates panes/tabs in detected terminal

## Commands

### /session-manager:fork
Fork the current Claude session into a new tmux pane or iTerm tab. Uses `fork-iterm.sh` to detect the current session, open a forked session, and **return a managed ID** for tracking via session-manager.sh commands.

#### Session resolution (forking works even when the working dir drifts)

`claude -r <id>` is **strictly cwd-scoped**: it resolves a session only from the directory that owns it (`~/.claude/projects/<cwd-encoded>/<id>.jsonl` for the *current* cwd). Resuming from any other directory fails with "No conversation found" (verified empirically against Claude Code 2.1.x). The working directory can also drift during a session. So the script does not trust the caller's pwd:

1. **Authoritative session id from the environment**: `SESSION_ID="${CLAUDE_CODE_SESSION_ID:-...}"`. Falls back to `detect_session_id` (project files / debug symlink) only when the env var is absent (older CLI / out-of-session).
2. **Owner discovery** (`find_session_owner_file`): glob `~/.claude/projects/*/<id>.jsonl` to find the project that actually owns the record (the encoded dir name is lossy, so resolve by id, not by re-encoding a path).
3. **Launch cwd from the record** (`session_launch_cwd`): read the canonical `cwd` from inside the transcript and fork from there (**Approach A**, default). The fork continues in the project the conversation is about, so historical paths / git state still match.

When the caller's directory differs from the session's owning directory, `/fork` offers a choice (via `--resolve` → `MATCH=no` → `AskUserQuestion`):
- **A — original directory** (default, recommended): launch from `OWNER_CWD`.
- **B — relocate to current directory** (`--relocate`): copy (never move) the record into the current dir's project and fork there. Used only for a deliberate move to a different checkout/worktree; the conversation's historical paths still refer to the original location.

Script flags: `[current_dir] [--fork-dir <dir>] [--relocate] [--resolve]`. `--resolve` prints `SESSION_ID` / `OWNER_CWD` / `CURRENT_DIR` / `MATCH` and exits without forking.

#### Fork snapshot (the fork opens on a closed turn, not a half-finished one)

The fork is dispatched from *inside* the turn that requested it, so the live transcript on disk still has that turn open — its last row is an unresolved `tool_use` (the fork command itself), with no result and no closing message. A child resuming that record verbatim inherits the truncation: the forked pane renders a final turn stuck mid-tool-call. This cannot be fixed by waiting, because the turn cannot close until the fork script returns.

`write_fork_snapshot` therefore copies the record to a fresh session id and cuts it at the last **closed** turn — the last main-chain assistant row that carries reply text, opens no tool call, and leaves none awaiting a `tool_result` (a thinking-only or `tool_use` row opens a turn rather than closing one). `mode` / `permission-mode` set after the cut are carried over; lines are copied byte-for-byte; the source is never touched. `claude -r <snapshot-id> --fork-session` then rewrites the whole history under its own new id, so the snapshot is not the fork's record.

`/fork` forks the session that is running the command (`SESSION_ID == CLAUDE_CODE_SESSION_ID`), whose final turn is unfinished by construction — that turn is dropped whole (`in_flight=1`), so the fork branches from just before the request and carries no trace of it. An externally supplied `--session-id` (the tmux hotkey) belongs to another session whose last turn may legitimately have ended, so only trailing incomplete structure is trimmed. With no closed turn to cut at, the live record is forked as before.

Snapshots are recorded in `~/.claude/session-manager/fork-snapshots.list` and deleted by a later fork once older than `FORK_SNAPSHOT_TTL` (default 600s), not at the end of the fork that made them: cleanup then rests on no startup timing, and a fork that failed to launch keeps its snapshot so the pane's command can be retried. (A child reads its snapshot ~1s into startup, measured by deleting it at T+1s/T+2s/T+3.2s — all loaded fine — so an immediate delete would also have worked; the sweep just removes the assumption and cleans up failures too.)

Tests: `bash session-manager/tests/test-fork-snapshot.sh`.

#### Fork verification (only report success when the fork actually works)

`fork-iterm.sh` only prints a managed ID / exits 0 once the fork is confirmed:

1. **Pre-flight resumability** (`session_resumable_in`): confirm `<project-dir>/<session-id>.jsonl` exists for the chosen fork directory before spawning. By construction Approach A forks from the owning dir (always resumable) and `--relocate` copies the record first; an explicit `--fork-dir` that doesn't own the session errors with a hint to use `--relocate`.
2. **Stabilized liveness** (`verify_fork_tmux` / `verify_fork_iterm`): poll the pane/tab and require `claude`/`node` to hold the foreground for `FORK_STABILIZE_CHECKS` consecutive 1s checks (default 3, within `FORK_VERIFY_TIMEOUT`, default 20s). A command that fails to launch (`claude` not on PATH, immediate crash) falls back to the shell prompt, so the streak never accrues → reported failed. A vanished pane/tab → failed.

Two signals were tried and **rejected** because the terminal observation is ambiguous: (a) watching for the forked transcript `.jsonl` — an *interactive* fork doesn't write it until the first prompt (only `--print` flushes it at startup); (b) "a non-shell process took over the terminal" alone — a *failed* resume keeps `node` in the foreground showing an error rather than exiting. Hence resolve resumability up front, then confirm the process launched and survived.

Tunables (env vars): `FORK_VERIFY_TIMEOUT`, `FORK_STABILIZE_CHECKS`, `FORK_SNAPSHOT_TTL`. Helper functions can be unit-tested by sourcing with `FORK_LIB_ONLY=1` (see `tests/test-fork-verify.sh`, `tests/test-fork-snapshot.sh`).

### /session-manager:run-in-pane
Run a bash command in a new tmux pane or iTerm tab with automatic tracking. Returns a managed ID for subsequent operations.

**Preferred path for interactive commands.** Any command that will prompt the user mid-execution — 2FA, OAuth device flows, cloud-CLI logins (`aws sso login`, `gcloud auth login`, `gh auth login`, `az login`, `vercel login`, `firebase login`), credential prompts (`npm login`, `docker login`), SSH/sudo passphrase, interactive installers (`create-next-app`, `terraform apply`) — must be routed through `run-in-pane`, not the main Bash tool. Inline Bash has no TTY, so these commands hang. The agent workflow is: launch pane → tell the user what to do in that pane → wait for the user → `capture` the final output. See `commands/run-in-pane.md` and `skills/pane-context/SKILL.md` for the full list of triggers and the step-by-step flow.

## Testing

Test the session-manager script:
```bash
cd plugins/session-manager

# Test run command (in tmux)
./scripts/session-manager.sh run "echo hello" --working-dir /tmp
# Should output: sm-XXXXXX

# Test list
./scripts/session-manager.sh list

# Test capture
./scripts/session-manager.sh capture sm-XXXXXX

# Test send
./scripts/session-manager.sh send sm-XXXXXX "echo world"

# Test status
./scripts/session-manager.sh status sm-XXXXXX

# Test cleanup
./scripts/session-manager.sh cleanup
```

Unit-test the fork helpers (no terminal needed):
```bash
bash session-manager/tests/test-fork-verify.sh
# Sources fork-iterm.sh with FORK_LIB_ONLY=1 and exercises session_resumable_in

bash session-manager/tests/test-fork-snapshot.sh
# Cut points, in-flight turn dropping, mode carry-over, snapshot sweep
```

Test the fork script (now returns managed ID):
```bash
./scripts/fork-iterm.sh "$(pwd)"
# Should output managed ID: sm-XXXXXX

# Test sync
./scripts/session-manager.sh sync
# Shows stale entries

./scripts/session-manager.sh sync --auto-remove
# Removes stale entries
```

## Error Handling

The scripts exit with error codes on failure:
- macOS check failure
- No supported terminal detected
- Pane not found in registry
- tmux/iTerm operation failure
- Sessions directory not found (for fork)
