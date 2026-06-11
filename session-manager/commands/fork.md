---
description: Fork the current Claude Code session into a new tmux pane or iTerm tab
allowed-tools:
  - Bash(*)
  - AskUserQuestion
---

# Fork Session

Fork the current session into a new tmux pane (if in tmux) or iTerm tab, allowing parallel work on the same context.

## Instructions

The fork script resolves the current session by id (`$CLAUDE_CODE_SESSION_ID`), finds the project that actually owns its transcript, and launches the fork from that record's real directory — so it works even if the working directory drifted during the session.

### Step 1 — Resolve and check for directory drift

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/fork-iterm.sh "$(pwd)" --resolve
```

This prints `SESSION_ID`, `OWNER_CWD` (where the session is resumable from), `CURRENT_DIR`, and `MATCH` (`yes`/`no`). If it exits non-zero, surface the error and stop — do not fork.

### Step 2 — Decide where to fork from

- **`MATCH=yes`** (current dir owns the session) — no choice needed. Run the fork directly (Step 3, Approach A).
- **`MATCH=no`** (you've moved away from the session's directory) — **ask the user** with `AskUserQuestion` which directory the forked session should run in. `claude -r` only resolves a session from the directory that owns it, so the two options are:
  - **A — Original directory (`OWNER_CWD`)**: fork continues in the project the conversation is about; all historical file paths / git state still match. *(Recommended.)*
  - **B — Current directory (`CURRENT_DIR`)**: copy the session record into the current directory's project and fork there. Use only if you deliberately want to continue against a different checkout/worktree — the conversation's historical paths will refer to the original location.

### Step 3 — Run the fork

Always pass `--quiet` so the success path prints only the managed ID (no `Forking…` / `Verifying…` chatter). This matters because the forked pane resumes a *copy of this transcript* — less fork chatter here means a cleaner top-of-context in the new pane. Errors are unaffected by `--quiet`.

Approach A (default / `MATCH=yes` / user chose A):
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/fork-iterm.sh --quiet
```

Approach B (user chose to relocate to the current directory):
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/fork-iterm.sh "$(pwd)" --fork-dir "$(pwd)" --relocate --quiet
```

The script detects tmux vs iTerm, opens the pane/tab at the fork directory, sends `claude -r <id> --fork-session`, and **verifies the session actually started** before reporting success: it polls the target pane/tab (up to ~20s) and requires `claude` to hold the foreground for several consecutive checks (a launch that fails — `claude` not on PATH, an immediate crash — falls back to the shell prompt and is reported failed). It only prints a managed ID (e.g. `sm-abc123`) on the last line of stdout **after** the session is confirmed up; on failure it exits non-zero, prints the captured pane/tab output, and does not register the session.

## Reporting to User

**Base your report on the script's exit code, not just on the pane/tab opening.**

- **Exit code 0 with a managed ID on stdout** — the fork was verified. Report **only the managed ID**, in a single line — e.g. `Forked → sm-abc123`. Do not append the session-manager command cheatsheet or extra explanation; keeping the report to one line minimizes the fork's footprint in the forked pane's transcript. (Exception: if Approach B was used, add one short line noting the forked session runs in the current directory but its history refers to the original location.)
- **Non-zero exit code** — the fork did NOT start (e.g., `claude` not on PATH, the session is not resumable, an immediate launch error). Do **not** report success or invent a managed ID. Surface the captured pane/tab output the script printed and explain what failed so the user can fix it (the orphan pane/tab was left open for inspection and was not registered).
