---
name: session-manager-pane-context
description: Use this skill when the user asks about capturing output from a managed pane or tab, sending commands to running panes, checking pane status, listing managed panes, or interacting with terminal sessions created by session-manager. ALSO use this skill when about to run a shell command that will need the user to interact with it — 2FA/MFA prompts, OAuth device flows, cloud-CLI logins (aws sso login, gcloud auth login, gh auth login, az login, vercel login, firebase login, heroku login, doctl auth init), credential prompts (npm login, docker login, huggingface-cli login), SSH/sudo passphrase, interactive installers/wizards (create-next-app, yo, terraform apply), or any command that opens a browser/asks for a device code. Triggers on questions like "capture output from pane", "send command to tab", "what panes are running", "check pane status", "get console context", "attach to pane", "run aws login", "needs 2FA", "login prompt", "needs user input", "OAuth flow", "interactive command".
---

# Pane Context Skill

This skill helps interact with terminal panes and tabs managed by the session-manager plugin.

## Overview

The session-manager plugin tracks panes/tabs created via `/session-manager:run-in-pane` in a registry at `~/.claude/session-manager/registry.json`. Each managed pane has a unique ID in the format `sm-XXXXXX`.

## Available Operations

### Capture Output from a Pane

Retrieve the current content/output from a managed pane:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/session-manager.sh capture <id> [--lines N]
```

- `<id>`: The managed pane ID (e.g., `sm-abc123`)
- `--lines N`: Number of lines to capture (default: 100)

Example:
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/session-manager.sh capture sm-abc123 --lines 50
```

### Send Command to a Pane

Execute a command in an existing managed pane:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/session-manager.sh send <id> <command>
```

Example:
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/session-manager.sh send sm-abc123 "npm test"
```

### List All Managed Panes

Show all panes tracked by session-manager:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/session-manager.sh list
```

Output includes: ID, type (tmux/iterm), pane ID, status, and initial command.

### Check Pane Status

Verify if a pane is still active or has become stale:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/session-manager.sh status <id>
```

Returns: `active` or `stale`

### Cleanup Stale Entries

Remove registry entries for panes that no longer exist:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/session-manager.sh cleanup
```

## Registry Location

The pane registry is stored at: `~/.claude/session-manager/registry.json`

Each entry contains:
- `id`: Managed pane ID
- `type`: Terminal type (`tmux` or `iterm`)
- `pane_id`: Underlying terminal pane/session ID
- `created_at`: ISO timestamp
- `working_directory`: Directory where command was started
- `initial_command`: The command that was run
- `status`: Current status

## Interactive Auth Flows (2FA, OAuth, CLI Logins)

Commands that require user interaction mid-execution — 2FA prompts, `aws sso login`, `gcloud auth login`, `gh auth login`, `az login`, `vercel login`, `firebase login`, `docker login`, `npm login`, SSH passphrases, `terraform apply` confirmations, interactive wizards — **must not** be run inline via the main Bash tool. Inline Bash has no attached TTY, so the command will hang or fail silently.

Route them through `/session-manager:run-in-pane` instead:

1. **Launch** the command in a tracked pane:
   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/session-manager.sh run "aws sso login --profile foo" --working-dir "$(pwd)"
   ```
   Capture the returned `sm-xxxxxx` ID.

2. **Tell the user what to do**, referencing the pane ID explicitly:
   > "Launched `aws sso login --profile foo` in pane `sm-xxxxxx`. Please complete the browser auth / enter the device code, then tell me when it's done."

3. **Confirm the command started** with a single `capture` — don't rely on `status`, which only reports whether the shell is alive:
   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/session-manager.sh capture sm-xxxxxx --lines 40
   ```
   If you see a `zsh: no matches found` or similar parse error, re-quote per the "Shell Interpretation Pitfalls" section below and re-launch.

4. **Wait for the user** to say they've completed the prompt. Do not loop-poll — it burns tokens and the user's browser flow takes as long as it takes.

5. **After confirmation**, `capture` again to read the final output (tokens written, success messages, error text) and continue the task.

### Recognizing an interactive command

If the command would open a browser, print a device code, prompt for a password/passphrase, ask a y/N question, or drop into an interactive wizard — it's interactive. When unsure, default to `run-in-pane`: the cost is one extra pane; the cost of guessing wrong inline is a hung Bash call.

## Best Practices

1. **Always list panes first** when the user asks about "their panes" or "running tabs"
2. **Check status** before sending commands to verify the pane still exists
3. **Capture output** to get context about what's happening in a pane
4. **Run cleanup** periodically to remove stale entries from closed panes

## Error Handling

- If a pane ID is not found, suggest running `list` to see available panes
- If a pane is stale, suggest running `cleanup` and creating a new pane
- If capture fails for iTerm, note that iTerm output capture is limited compared to tmux

## Shell Interpretation Pitfalls

Commands passed to `run` and `send` are **typed into an interactive shell** via `tmux send-keys` (or AppleScript for iTerm), not executed directly. The user's shell (zsh on macOS by default) parses and expands the string before running it — so shell metacharacters must be quoted the same way you would type them at a prompt.

### Symptom: pane shows `active` but nothing is running

`status` returns `active` (the shell is alive) but `capture` shows an error like `zsh: no matches found: <pattern>` and a bare prompt. The command aborted at parse time.

### Common traps

| Character | zsh behavior | Example that breaks |
|---|---|---|
| `*`, `?`, `[...]` | Glob expansion; aborts with `no matches found` if nothing matches (zsh `NOMATCH` is on by default) | `adb logcat ReactNativeJS:V *:S` — `*:S` looks like a glob |
| `!` | History expansion in interactive shells | `curl -H "X-Foo: bar!baz"` |
| `$VAR` | Expanded by the receiving shell, not the caller | `run "echo $HOME"` prints the pane's `$HOME`, not yours |
| `` ` `` | Command substitution | Same as above |
| `\|\|`, `&&`, `;`, `>` | Parsed as shell operators | Fine if intended; problem if they were meant literally |

### Fix

Single-quote anything with glob metacharacters when writing the command:

```bash
adb logcat 'ReactNativeJS:V' '*:S' -v threadtime
```

Or prepend `noglob` (zsh-specific):

```bash
noglob adb logcat ReactNativeJS:V *:S -v threadtime
```

When passing a command through `run`/`send`, remember there are **two levels of quoting**: the outer shell that invokes `session-manager.sh`, and the inner shell in the pane. If the command contains single quotes, wrap the whole thing in double quotes at the outer level and escape `$`, `` ` ``, `"`, `\` as needed.

### Before reporting "pane is running"

If a pane was just created with a complex command, `capture` it once to confirm the command actually started — don't rely on `active` status alone. `active` only means the shell is alive, not that your command survived parsing.
