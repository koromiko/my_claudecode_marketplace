# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A Claude Code plugin that provides three shell-based hooks: conditional tool auto-approval with sensitive-path guards, macOS permission-prompt notifications, and session-completion notifications.

## Architecture

All logic lives in `hooks/`. There are no skills, commands, or agents — only hook scripts registered in `hooks/hooks.json`.

### Hook Pipeline

1. **`auto-approve.sh`** (PreToolUse, no matcher — runs on every tool call): Decides whether to auto-approve or fall through to the normal permission prompt. Reads tool input JSON from stdin, outputs a JSON permission decision to stdout.
2. **`permission-notification.sh`** (Notification, matcher: `permission_prompt`): Fires only when Claude actually shows a permission prompt. Writes a session marker file to `/tmp/claude-hook-session-{session_id}` so the Stop hook knows a prompt occurred.
3. **`stop-notification.sh`** (Stop, no matcher): Fires when Claude finishes. Only sends a notification if the session marker file exists (i.e., a permission prompt was shown). Cleans up the marker.

### Auto-Approve Decision Logic

`auto-approve.sh` uses two helpers:

- **`is_sensitive_path()`** — returns true for paths matching sensitive directories (`.ssh/`, `.aws/`, `.gnupg/`, `.kube/`, `.docker/`) or file patterns (`.env*`, `*secret*`, `*credential*`, `*private_key*`, `*.pem`, key files). Used by Read, Glob, and Grep handlers.
- **`is_readonly_bash_command()`** — returns true for commands matching a prefix allowlist (git read-only, `ls`, `pwd`, `gh` read-only, version checks) AND containing no shell metacharacters (`|`, `;`, `&&`, `` ` ``, `$(`, `>`, `<`).

Exit conventions:
- `allow "reason"` → outputs JSON with `permissionDecision: "allow"` and exits 0
- `exit 0` with no output → no decision, falls through to default permission prompt

### Notification Flow

Both notification scripts derive a project name from the git root of `cwd`. They use `terminal-notifier` (activating iTerm2) and `say` for audio. The Stop hook guards against re-entry via `stop_hook_active` and only fires if the session marker exists.

## Testing Changes

After modifying hook scripts:

```bash
# Validate JSON structure
jq . hooks/hooks.json

# Test auto-approve with sample input
echo '{"tool_name":"Read","tool_input":{"file_path":"/some/file.txt"}}' | bash hooks/auto-approve.sh

# Test sensitive path detection (should produce no output = fall through)
echo '{"tool_name":"Read","tool_input":{"file_path":"/home/user/.ssh/id_rsa"}}' | bash hooks/auto-approve.sh

# Clear plugin cache to pick up changes
../../scripts/local_release.sh default-tools
```

## Prerequisites

macOS with `jq`, `terminal-notifier` (`brew install terminal-notifier`), and iTerm2 for notifications. The `say` command is used for audio alerts.
