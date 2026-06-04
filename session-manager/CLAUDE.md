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

#### Fork verification (only report success when the fork actually works)

`fork-iterm.sh` only prints a managed ID / exits 0 once the fork is confirmed:

1. **Pre-flight resumability** (`session_resumable_in`): confirm `<project-dir>/<session-id>.jsonl` exists for the chosen fork directory before spawning. By construction Approach A forks from the owning dir (always resumable) and `--relocate` copies the record first; an explicit `--fork-dir` that doesn't own the session errors with a hint to use `--relocate`.
2. **Stabilized liveness** (`verify_fork_tmux` / `verify_fork_iterm`): poll the pane/tab and require `claude`/`node` to hold the foreground for `FORK_STABILIZE_CHECKS` consecutive 1s checks (default 3, within `FORK_VERIFY_TIMEOUT`, default 20s). A command that fails to launch (`claude` not on PATH, immediate crash) falls back to the shell prompt, so the streak never accrues → reported failed. A vanished pane/tab → failed.

Two signals were tried and **rejected** because the terminal observation is ambiguous: (a) watching for the forked transcript `.jsonl` — an *interactive* fork doesn't write it until the first prompt (only `--print` flushes it at startup); (b) "a non-shell process took over the terminal" alone — a *failed* resume keeps `node` in the foreground showing an error rather than exiting. Hence resolve resumability up front, then confirm the process launched and survived.

Tunables (env vars): `FORK_VERIFY_TIMEOUT`, `FORK_STABILIZE_CHECKS`. Helper functions can be unit-tested by sourcing with `FORK_LIB_ONLY=1` (see `tests/test-fork-verify.sh`).

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

Unit-test the fork-verification helpers (no terminal needed):
```bash
bash session-manager/tests/test-fork-verify.sh
# Sources fork-iterm.sh with FORK_LIB_ONLY=1 and exercises session_resumable_in
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
