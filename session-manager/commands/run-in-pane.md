---
description: Run a bash command in a new tmux pane or iTerm tab with tracking. Preferred path for interactive commands that need the user (2FA, OAuth, cloud-CLI logins, SSH passphrase).
allowed-tools:
  - Bash(*)
argument-hint: <command> [--working-dir <path>]
---

# Run in Pane

Run a bash command in a new tmux pane or iTerm tab, with automatic tracking via the session-manager registry.

## When To Use This

Use this command whenever the shell command you're about to run will need a human to do something mid-execution. Running such commands inline via the main Bash tool hangs (no attached TTY / no user) or fails silently.

Trigger examples — route these through `run-in-pane`, not inline Bash:

- **2FA / MFA prompts**: anything that pops a browser, shows a device code, or asks for a TOTP (`aws sso login`, `gcloud auth login`, `gh auth login`, `az login`, `vercel login`, `okta-aws-cli`, Duo/Okta flows)
- **OAuth device flows**: CLIs that print `https://...` + a user code and wait (`gh auth login --web`, `firebase login`, `supabase login`, `heroku login`, `doctl auth init`)
- **Credential prompts**: `npm login`, `pip login`, `docker login`, `huggingface-cli login`, `gpg --gen-key`, `ssh-keygen` with passphrase
- **SSH/sudo passphrase**: any `ssh`/`scp`/`rsync` to a host with a passphrase-protected key, `sudo` without cached creds
- **Interactive installers / wizards**: `npm init`, `create-next-app`, `yo <generator>`, `gh repo create` without flags, `terraform apply` (confirmation prompt)
- **Long-running attached processes the user might need to interact with**: `docker compose up` (no `-d`), `vault login -method=oidc`

### Agent workflow for interactive commands

1. Launch the command in a pane:
   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/session-manager.sh run "<cmd>" --working-dir "$(pwd)"
   ```
2. Tell the user exactly what to do, naming the pane ID:
   > "Launched `<cmd>` in pane `sm-xxxxxx`. Please complete the prompt there (browser / 2FA / password), then let me know when it's done."
3. `capture sm-xxxxxx` once right away to confirm the command actually started (shell parsing pitfalls — see below).
4. Wait for the user to confirm. Don't poll in a tight loop; don't guess completion from `status` alone — `active` just means the shell is alive.
5. After the user confirms, `capture sm-xxxxxx` again to read the final output and continue the task.

Do NOT try to run these commands inline and then "handle" the prompt — there is no way to type into an inline Bash call.

## Instructions

Execute the session-manager script with the `run` subcommand, passing the user's command and optional working directory.

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/session-manager.sh run "<command>" --working-dir "$(pwd)"
```

The script will:
1. Detect if running inside tmux (creates new pane) or iTerm (creates new tab)
2. Execute the command in the new pane/tab
3. Register the pane with a unique managed ID (format: `sm-XXXXXX`)
4. Return the managed ID for future reference

## Output

On success, the script outputs the managed ID (e.g., `sm-abc123`). Report this ID to the user so they can:
- Capture output: `session-manager.sh capture sm-abc123`
- Send commands: `session-manager.sh send sm-abc123 "another command"`
- Check status: `session-manager.sh status sm-abc123`

## Examples

Run a dev server:
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/session-manager.sh run "npm run dev" --working-dir "/path/to/project"
```

Run tests in background:
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/session-manager.sh run "npm test -- --watch"
```

Start a database:
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/session-manager.sh run "docker-compose up postgres"
```

## Quoting Caveat

The command string is **typed into an interactive shell** (zsh on macOS) via `tmux send-keys`. It is parsed by that shell, so glob characters (`*`, `?`, `[...]`), history-expansion `!`, and `$VAR` are interpreted there — not executed literally.

A common failure mode: commands like `adb logcat ReactNativeJS:V *:S` abort at launch with `zsh: no matches found: *:S` because zsh tries to glob-expand `*:S`. The pane will report `active` status (the shell is alive) but nothing is running.

**Rule of thumb:** single-quote any argument containing glob metacharacters, then let the outer shell handle the rest:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/session-manager.sh run "adb logcat 'ReactNativeJS:V' '*:S' -v threadtime"
```

**Always verify with `capture` after launching a non-trivial command** — `active` status alone does not mean your command survived shell parsing. See the `session-manager:pane-context` skill for the full list of pitfalls.
