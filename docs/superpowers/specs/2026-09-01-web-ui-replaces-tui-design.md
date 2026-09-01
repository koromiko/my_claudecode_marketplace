# Web UI Replaces the tmux-cc-attach TUI — Design

**Status:** approved design (2026-09-01)

## Goal

Make `tmux-cc-attach` (no args) open the web UI, remove the interactive TUI,
and give the web UI real actions — Launch (ended), Go-to-pane / Attach-‑CC
(live), Fork — so it fully replaces the TUI. `tmux-cc-attach --json` stays as
the web server's data backend.

## Decisions (from brainstorming)

1. Web UI gains **real launch/attach** (server executes commands), not
   copy-only.
2. **Hard-remove** the interactive TUI; keep `--json` + the web server.
3. Live-session primary action is **focus the existing pane** (locator knows
   where it runs); Fork is secondary.
4. Keep the **`tmux-cc-attach` name**: no-arg → web UI; `--json` → backend.
5. Launch/Fork opens in a **new iTerm window** (reuses `create_group_window`).
6. **Keep a minimal `tmux -CC` attach** for live sessions running under tmux
   (in addition to Go-to-pane and Fork).

## Convention basis

All terminal control in this plugin is bash + `osascript`/`tmux`
(`create_group_window` / `add_gateway_tab` in `tmux-cc-attach`, iTerm-by-id
targeting in `session-manager.sh`); the Python web server is stdlib-only and
shells out. New actions therefore live in a **bash helper** the server invokes
via `subprocess`, never as osascript embedded in Python.

## Architecture

```
browser
  GET  /api/sessions           -> tmux-cc-attach --json (list; unchanged path)
  POST /api/open   {id,fork?}   -> session-open.sh open <cwd> <id> [--fork]
  POST /api/focus  {id}         -> session-open.sh focus <pane>
  POST /api/attach {id}         -> session-open.sh attach <id>   (tmux -CC)
        server validates id ∈ current --json list, checks Origin/Host,
        then shells out to session-open.sh (osascript / tmux)
```

### Component 1 — `tmux-cc-attach` (slimmed to a backend + launcher)

Keep:
- `--json` mode: resume-store read + `live_sessions_json` + project grouping,
  and the flags `--json` honors (`--project`, `--since`).
- Helper functions used by `--json`: resume-store readers, `project_of_dir`,
  `matches_any`, `run_locator_list`, `live_session_ids`, `live_sessions_json`,
  `resume_is_resumable`, `resume_is_autonomous`, `resume_within_age`.
- Non-destructive read-only pruning behavior for `--json`.

Add:
- `--json` live output gains `pane` and `host` fields (from locator) so the
  page can offer focus / attach. `pid` stays (dedup key).

Remove (the TUI):
- Interactive report, per-project group-selection prompt, iTerm control-mode
  grouped attach of live tmux sessions, resume-launch path, the tmux-server
  preflight, and the flags `--no-resume`, `--resume-only`, `-y`, `-n`,
  `-o/--only`. `attach_command_for` / `create_group_window` move to
  `session-open.sh` (still needed by the executor).

New default behavior:
- Any invocation that is not `--json` **execs the web server**:
  `python3 <dir>/tmux-cc-web.py "$@"`, passing `--port/--host/--no-open`
  through. `--json` continues to print JSON and exit.

### Component 2 — `scripts/session-open.sh` (new; the action executor)

bash + osascript/tmux. Subcommands (each prints `ok` on success, non-zero +
stderr on failure). Lib-only sourcing via `SESSION_OPEN_LIB_ONLY=1` for tests.

- `open <cwd> <session_id> [--fork]` — new iTerm window running
  `cd '<cwd>' && claude -r '<id>' [--fork-session]` (via `create_group_window`).
- `focus <pane>` — raise the existing session:
  - iTerm pane (`iterm:…:<GUID>`): osascript iterate windows/tabs/sessions,
    match `id of s == <GUID>`, `tell s to select`, bring its window to front,
    `activate`.
  - tmux pane (`tmux:<target>`): `tmux select-window`/`select-pane -t <target>`
    then `switch-client`; if the client is an iTerm `-CC` gateway, `activate`
    iTerm too.
  - Unknown/again-not-found: exit non-zero with a clear message.
- `attach <session_id>` — new iTerm window running `tmux -CC attach -t '<id>'`
  (reuses `attach_command_for`).

### Component 3 — `tmux-cc-web.py` (endpoints + page)

Server:
- New POST routes `/api/open`, `/api/focus`, `/api/attach`. Each:
  1. Reads a JSON body `{session_id, fork?}`.
  2. **Validates** `session_id` is present in a fresh `load_sessions` list
     (never trust an arbitrary id from the client) and, for focus/attach, that
     it is a live session with a `pane`/host that supports the action.
  3. Shells out to `session-open.sh` with the looked-up `cwd`/`pane`.
  4. Returns `{ok:true}` or `{error:…}` (HTTP 400/404/500 as appropriate).
- **Safety:** loopback bind (already); reject requests whose `Origin` (or,
  absent Origin, `Host`) is not the server's own `127.0.0.1:<port>` — blocks a
  malicious localhost page from POSTing actions (CSRF). GET routes unchanged.
- Enrichment already carries `copy_command`/`fork_command`; `pane`/`host`/`pid`
  pass through from `--json` for live sessions and are used server-side to
  resolve focus/attach (pane/pid not exposed as actionable data to the client
  beyond what the buttons need).

Page:
- Ended rows: **Launch** (POST /api/open) + Copy.
- Live rows: **Go to pane** (POST /api/focus) + **Fork** (POST /api/open
  `{fork:true}`) + Copy; plus **Attach ‑CC** (POST /api/attach) when
  `host == "tmux"`.
- Buttons show inline success/failure feedback ("Opened ✓" / "Focused ✓" /
  error text); Copy remains the always-safe fallback for every row.

## Data flow

`GET /api/sessions` renders the list → user clicks an action → `POST` with the
`session_id` → server re-derives the session from `--json`, validates, and runs
`session-open.sh` → iTerm/tmux acts → server returns status → button flashes.

## Deprecation / removal

- Delete the TUI code paths and now-dead flags from `tmux-cc-attach`; update its
  `--help`/usage to describe only `--json` and the web-launch default.
- `tmux-cc-attach` and `/session-manager:list-resumable-web` both open the web
  UI (documented as equivalent).
- Docs updated: `session-manager/README.md`, `commands/list-resumable-web.md`,
  `session-manager/CLAUDE.md` (note the TUI is gone; document `session-open.sh`
  and the POST endpoints).

## Testing

- `session-open.sh` lib-only tests (`SESSION_OPEN_LIB_ONLY=1`) with stubbed
  `osascript`/`tmux` on PATH: assert `open` builds the right
  `cd … && claude -r …[ --fork-session]` command, `attach` builds
  `tmux -CC attach -t …`, and `focus` dispatches by pane type (iterm vs tmux).
- Python endpoint tests: `/api/open` runs the executor for a known id; unknown
  id → 404; non-loopback `Origin` → 403; `/api/focus` resolves the live
  session's pane; `/api/attach` only for `host=="tmux"`. Executor stubbed via
  an env-injected fake `session-open.sh` that records its argv.
- Keep existing `--json` / web `GET` tests; add `pane`/`host` assertions to the
  live `--json` test. Delete TUI-only tests from `test-tmux-cc-attach.sh`.

## Known limits (documented, not silently dropped)

- Focus/attach across mixed hosts (plain iTerm vs tmux vs tmux-in-‑CC) is
  handled per-host; exotic or stale setups return a clear "can't focus/attach"
  rather than guessing.
- The server executes local terminal actions; safety rests on loopback binding
  + Origin/Host check + id-must-exist validation. It is a personal-machine
  tool, not a shared service.

## Out of scope

- Remote / multi-user serving, authentication beyond loopback+Origin.
- Re-implementing the old per-project grouped multi-attach workflow.
- Killing/cleanup of stale sessions from the UI.
