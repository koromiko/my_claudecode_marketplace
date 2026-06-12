# session-manager

Manage Claude Code sessions across tmux panes and iTerm tabs - fork sessions, run commands, and capture output.

## Overview

This plugin provides comprehensive terminal session management for Claude Code:

- **Fork Sessions**: Branch your current Claude session into a new pane/tab for parallel work
- **Fork the Focused Pane**: A tmux key-binding that forks the Claude session in whichever pane you're *looking at* — not just the one you're driving
- **Run Commands**: Execute commands in new tracked panes/tabs with unique IDs
- **Capture Output**: Retrieve output from managed panes
- **Send Commands**: Send commands to existing managed panes
- **Track Status**: Monitor which panes are active or stale

The plugin automatically detects your terminal environment and uses the appropriate method:
- **tmux**: Creates new panes in your current tmux window
- **iTerm2**: Opens new tabs in your current iTerm window

## Prerequisites

- **macOS** - This plugin only works on macOS
- **Python 3** - Required for JSON manipulation
- **One of the following**:
  - **tmux** - If running inside a tmux session, no additional setup needed
  - **iTerm2** - Must be installed and running (if not using tmux)
    - Install via Homebrew: `brew install --cask iterm2`
    - Or download from: https://iterm2.com/

## Commands

### /session-manager:fork

Fork your current Claude Code session into a new tmux pane or iTerm tab.

```
/session-manager:fork
```

This will:
1. Auto-detect if you're running in tmux or iTerm
2. Auto-detect your current session from Claude's session files
3. Open a new tmux pane or iTerm tab
4. Start a forked Claude session with all the context from the original
5. Verify the forked session actually started in the target pane/tab before reporting success — it only returns a managed ID once the fork is confirmed up, and exits non-zero if `claude` never launched

> Verification waits up to ~10s (override with `FORK_VERIFY_TIMEOUT`) using a content-independent signal: it checks that a non-shell process (`claude`/node) has taken over the target's foreground. For tmux it reads the pane's foreground command; for iTerm it reads the specific session's tty and inspects its foreground process group. (It deliberately does not scan rendered output, since a forked session displays the prior conversation verbatim — which can contain arbitrary marker text.)
>
> iTerm tabs are tracked by their real iTerm **session id** (not a synthetic placeholder), so `capture`, `send`, and `status` target the exact tab regardless of which tab is focused, and `cleanup` correctly detects closed iTerm tabs as stale.

### /session-manager:run-in-pane

Run a bash command in a new tracked pane/tab.

```
/session-manager:run-in-pane npm run dev --working-dir /path/to/project
```

This will:
1. Create a new tmux pane or iTerm tab
2. Execute the command
3. Return a managed ID (e.g., `sm-abc123`) for tracking

## Fork the Focused Pane (tmux key-binding)

`/session-manager:fork` forks the session you're *currently in*. The fork hotkey instead forks the Claude session running in whichever tmux pane is **focused** — useful when you're driving one pane and want to branch a session running in another, without switching to it first.

Add this to your `~/.tmux.conf` (adjust the path to your checkout):

```tmux
# Prefix + F: fork the Claude session in the focused pane into a split beside it.
bind-key F run-shell "$HOME/Project/my_claudecode_marketplace/session-manager/scripts/fork-active-pane.sh '#{pane_id}'"
```

Reload tmux (`tmux source-file ~/.tmux.conf`), then press your prefix followed by `F` on any pane:

- If a Claude session is running there, it forks into a new split beside that pane, and the tmux status line reports the managed ID (e.g. `Forked → sm-abc123`).
- If no Claude session is in the pane — or two are running and the focused one can't be determined — the status line says so and nothing is forked.

A tmux `run-shell` binding runs detached from the pane, so it can't read that pane's session from the environment. Instead the hotkey resolves the pane's session with the locator (below), then forks it through the same verified `fork-iterm.sh` path the `/fork` command uses.

### locator.py — session ↔ pane resolver

`scripts/locator.py` maps running Claude Code sessions to terminal panes by scanning process environments. It is read-only, macOS-only, and re-scans on every query (so results are never stale). Useful on its own:

```bash
# List every live Claude session with its pane, tty, cwd, and role
python3 scripts/locator.py list

# Resolve the session in a specific pane / tty / by id
python3 scripts/locator.py resolve --pane tmux:default:%5
python3 scripts/locator.py resolve --pane %5          # bare pane id (any socket)
python3 scripts/locator.py resolve --tty ttys016      # by tty
python3 scripts/locator.py resolve --session <uuid>   # by session id
```

`resolve --pane` / `--tty` return the single interactive session in that pane (a JSON object), or a JSON array on the rare occasion two interactive sessions share a pane and the focused one can't be told apart, or `[]` with exit code 1 when none match.

## Interacting with Managed Panes

After creating a pane with `run-in-pane`, you can interact with it using the session-manager script:

### Capture Output
```bash
./scripts/session-manager.sh capture sm-abc123 --lines 50
```

### Send Commands
```bash
./scripts/session-manager.sh send sm-abc123 "npm test"
```

### List All Panes
```bash
./scripts/session-manager.sh list
```

### Check Status
```bash
./scripts/session-manager.sh status sm-abc123
```

### Cleanup Stale Entries
```bash
./scripts/session-manager.sh cleanup
```

## Registry

Managed panes are tracked in `~/.claude/session-manager/registry.json`. This allows:
- Persistence across Claude sessions
- Tracking of pane metadata (working directory, initial command, creation time)
- Status monitoring (active vs stale)

## Error Handling

The plugin provides helpful error messages if:
- Not running on macOS
- Not in tmux AND iTerm2 is not installed/running
- Pane ID not found in registry
- Terminal pane no longer exists (stale)

## Examples

### Start a dev server and capture its output

```
/session-manager:run-in-pane npm run dev
```

Later, capture what's happening:
```bash
./scripts/session-manager.sh capture sm-xyz789
```

### Run tests in a separate pane

```
/session-manager:run-in-pane npm test -- --watch
```

### Fork session for parallel exploration

```
/session-manager:fork
```
