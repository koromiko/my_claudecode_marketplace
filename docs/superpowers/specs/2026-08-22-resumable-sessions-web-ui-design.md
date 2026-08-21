# Resumable Sessions Web UI — Design

**Date:** 2026-08-22
**Plugin:** session-manager
**Status:** Approved (brainstorming) — pending implementation plan

## Summary

A local web page that lists resumable Claude Code sessions, grouped by project,
with per-session metadata (title, last activity, turn count, cwd, end reason).
Clicking **Copy** puts a paste-and-run `cd <cwd> && claude -r <id>` command on
the clipboard. Data is served live by a Python stdlib HTTP server that reuses
`tmux-cc-attach` as the single source of truth for *which* sessions are
resumable.

Non-goals: the page never resumes a session server-side (copy-to-clipboard
only); no persistence, no auth beyond binding to loopback; not a general
session dashboard.

## Context / current state

- Resume records: `~/.claude/session-manager/resume/<id>.json` →
  `{session_id, cwd, ts_start, ts_end, reason}`, written by the SessionEnd hook
  `hooks/remove-session.sh`.
- Transcripts: `~/.claude/projects/<encoded-cwd>/<id>.jsonl`.
- `scripts/tmux-cc-attach` already decides "resumable": within age window
  (`RESUME_MAX_AGE_DAYS`, default 14), transcript exists, not autonomous
  (`"type":"agent-setting"`), not currently live (`locator.py`), plus project
  grouping (parent of `git rev-parse --git-common-dir`).
- Convention: Python 3 stdlib only, no external deps (cf. `locator.py`,
  `claude-usage-analyzer`). Bash scripts expose a `TMUX_CC_LIB_ONLY` sourcing
  hook for unit tests; tests live in `session-manager/tests/`.

> Note: the global `convention-audit:convention-checker` agent was unavailable
> in the design session; the code shape below is grounded directly in the
> precedents above rather than a checker verdict.

## Architecture

Bash owns "which sessions are resumable"; Python owns "serve + enrich". This
avoids duplicating the resumable definition and letting the two drift.

```
Browser ──HTTP──► tmux-cc-web.py (stdlib http.server, 127.0.0.1)
                    │  GET /             → single-page HTML+JS
                    │  GET /api/sessions → JSON
                    ▼
            tmux-cc-attach --resume-only --json   (source of truth: which)
                    +
            ~/.claude/projects/*/<id>.jsonl        (enrichment: title, turns)
```

### Component 1 — `tmux-cc-attach --json`

New flag on the existing script. When set, it builds the resume work list
exactly as today (age / resumable / autonomous / live filters, project
resolution, `--project` globs still honored) and prints JSON to stdout, then
exits **before** any iTerm/osascript preflight or attach action.

- Implies/compatible with `--resume-only`; skips the `osascript`/iTerm-app
  preflight so it runs headless (e.g. from the web server, over SSH).
- Output: a JSON array, one object per resumable session:
  `{"session_id","cwd","project","ts_end","reason"}`.
- Purpose: single source of truth for *which* sessions are resumable, testable
  in isolation.

### Component 2 — `scripts/tmux-cc-web.py`

Python 3 stdlib only (`http.server`, `socketserver`, `json`, `subprocess`,
`os`, `webbrowser`, `argparse`). Binds `127.0.0.1`.

Routes:
- `GET /` → the single self-contained HTML page (inline CSS/JS, no CDN).
- `GET /api/sessions` → JSON. Calls `tmux-cc-attach --resume-only --json`,
  then enriches each entry from its transcript, groups by `project`, sorts by
  `ts_end` desc within each group.

Enrichment per session (from `~/.claude/projects/*/<id>.jsonl`):
- `title`: first real human user message — skip records that are
  `<teammate-message>`, slash-command inputs, and agent/meta records
  (`type` != `user`, or `agentSetting`/command envelopes). Truncated to a
  display length (e.g. 120 chars).
- `turns`: count of human `type=="user"` records.
- `copy_command`: `cd '<cwd>' && claude -r '<id>'` (single-quote-escaped).

Caching: in-memory dict keyed by `(session_id, transcript_mtime)`; a changed
transcript re-parses, refreshes are cheap. Missing/unreadable transcript →
`title` falls back to the cwd basename, `turns` = null.

CLI: `python3 scripts/tmux-cc-web.py [--port N] [--no-open] [--host H]`.
Default: pick a free port, open the browser via `webbrowser.open`.

### Component 3 — page (served inline by Component 2)

- Project groups as collapsible sections: project path + session count.
- Session row: title, relative age ("3 days ago") with absolute timestamp on
  hover, turn count, end reason, shortened cwd, and a **Copy** button
  (`navigator.clipboard.writeText(copy_command)` with a "copied ✓" flash;
  falls back to a hidden `<textarea>` + `execCommand` if clipboard API absent).
- Top bar: client-side search box (filters by title / cwd / session_id), a sort
  toggle (recent ↔ project), and a Refresh button that re-fetches
  `/api/sessions`.

## Data contract — `/api/sessions`

```json
[
  {
    "project": "/Users/me/Project/foo",
    "sessions": [
      {
        "session_id": "…",
        "cwd": "/Users/me/Project/foo/wt-x",
        "ts_end": 1787060992,
        "reason": "other",
        "title": "Add a web UI for resumable sessions",
        "turns": 42,
        "copy_command": "cd '/Users/me/Project/foo/wt-x' && claude -r '…'"
      }
    ]
  }
]
```

## Error handling

- `tmux-cc-attach --json` non-zero or unparseable → `/api/sessions` returns
  HTTP 500 with a JSON error; the page shows an inline error banner, not a
  blank list.
- Empty resumable list → page shows a friendly "nothing to resume" state.
- Port in use → server tries the next free port (or errors clearly if
  `--port` was explicit).

## Testing

- `tests/test-tmux-cc-web.py` (stdlib `unittest`): title extraction across
  message shapes (plain user, teammate-message, slash-command, agent/meta),
  turn counting, cache keying by mtime, `copy_command` quoting, `/api/sessions`
  grouping/sorting shape (feed a fake `tmux-cc-attach` via PATH or a seam).
- Extend `tests/test-tmux-cc-attach.sh` for `--json`: correct JSON shape,
  honors `--project`, skips iTerm preflight (runs without iTerm), exits before
  attach. Uses the existing `TMUX_CC_LIB_ONLY` sourcing pattern where possible.

## Packaging

- New command doc `commands/list-resumable-web.md`; README section.
- `./scripts/bump-plugin.sh session-manager minor` before commit (new feature).

## Open questions

None blocking. Port-conflict UX and exact title-truncation length are
implementation details.
