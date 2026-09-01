# Web UI Replaces the tmux-cc-attach TUI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `tmux-cc-attach` (no args) opens the web UI; the interactive TUI is removed; the web UI gains Launch (ended), Go-to-pane / Attach-‑CC (live), and Fork actions. `tmux-cc-attach --json` stays as the backend.

**Architecture:** The Python web server (`tmux-cc-web.py`) stays stdlib-only and shells out to a new bash executor (`session-open.sh`) for all terminal actions (osascript/tmux). `tmux-cc-attach` is slimmed to a `--json` backend plus a launcher that execs the web server. See spec: `docs/superpowers/specs/2026-09-01-web-ui-replaces-tui-design.md`.

**Tech Stack:** bash + `osascript`/`tmux` (terminal control), Python 3 stdlib (web server), jq (JSON in bash).

## Global Constraints

- Python is **stdlib-only** (no pip). Terminal control is **bash + osascript/tmux**, never osascript embedded in Python — the server shells out.
- The web server binds **loopback only**; action endpoints are **POST**, reject requests whose `Origin` (or `Host` if no Origin) is not the server's own `127.0.0.1:<port>`, and only act on a `session_id` **present in the current `--json` list**.
- `tmux-cc-attach --json` output contract is preserved and **read-only** (never prunes). Live entries add `pane` and `host`; `pid` stays.
- Commit messages ≤3 non-blank lines, **no** `Co-Authored-By` trailer.
- Existing helpers to reuse (in `tmux-cc-attach`, available via `TMUX_CC_LIB_ONLY=1`): `escape_applescript`, `escape_shell_single`, `project_of_dir`.
- Locator pane formats: `iterm:<iterm_session_id>` (host `iterm`), `tmux:<socket>:<pane_id>` (host `tmux`), `term:<id>` (host `apple-terminal`), or absent.
- After all tasks pass review: `./scripts/bump-plugin.sh session-manager minor`.

---

### Task 1: `--json` emits `pane` and `host` for live sessions

**Files:**
- Modify: `session-manager/scripts/tmux-cc-attach` (`live_sessions_json`)
- Test: `session-manager/tests/test-tmux-cc-attach.sh`

**Interfaces:**
- Produces: live JSON objects gain `pane` (string|"") and `host` (string|""), e.g. `{session_id, cwd, project, pid, pane, host, status:"live"}`.

- [ ] **Step 1: Add failing assertions** to the live-locator block in `test-tmux-cc-attach.sh`. The stub already lists `liveproc` with `leader_pid`; add `pane`/`host` to it and assert they survive:

```sh
# in the STUB python: liveproc entry becomes
#   {"session_id":"liveproc","cwd":"/tmp/liveproc","role":"interactive",
#    "leader_pid":4242,"pane":"iterm:GUID-1","host":"iterm"},
check "--json live carries pane" \
    "[ \"\$(printf '%s' \"\$ljout\" | jq -r '.[]|select(.session_id==\"liveproc\").pane')\" = 'iterm:GUID-1' ]"
check "--json live carries host" \
    "[ \"\$(printf '%s' \"\$ljout\" | jq -r '.[]|select(.session_id==\"liveproc\").host')\" = 'iterm' ]"
```

- [ ] **Step 2: Run tests, confirm the two new checks FAIL.** `bash session-manager/tests/test-tmux-cc-attach.sh`

- [ ] **Step 3: Emit pane/host.** In `live_sessions_json`, read pane/host from the locator and add to the object:

```sh
    while IFS='|' read -r sid cwd pid pane host; do
        [ -n "$sid" ] || continue
        resume_is_resumable "$sid" "$root" || continue
        proj=$(project_of_dir "$cwd")
        if [ ${#PROJECT_GLOBS[@]} -gt 0 ] && ! matches_any "$proj" "${PROJECT_GLOBS[@]}"; then
            continue
        fi
        jq -cn --arg id "$sid" --arg cwd "$cwd" --arg project "$proj" \
            --arg pid "$pid" --arg pane "$pane" --arg host "$host" \
            '{session_id:$id, cwd:$cwd, project:$project, pid:$pid, pane:$pane, host:$host, status:"live"}'
    done < <(printf '%s' "$LOCATOR_JSON" \
        | jq -r '.[] | select(.role=="interactive")
                 | [.session_id, (.cwd // ""), ((.leader_pid // "")|tostring),
                    (.pane // ""), (.host // "")] | join("|")' 2>/dev/null)
```

- [ ] **Step 4: Run tests, confirm ALL PASS.** `bash session-manager/tests/test-tmux-cc-attach.sh`

- [ ] **Step 5: Commit.**
```bash
git add session-manager/scripts/tmux-cc-attach session-manager/tests/test-tmux-cc-attach.sh
git commit -m "feat(session-manager): emit pane/host for live sessions in --json"
```

---

### Task 2: `session-open.sh` — `open` and `attach` subcommands

**Files:**
- Create: `session-manager/scripts/session-open.sh`
- Test: `session-manager/tests/test-session-open.sh`

**Interfaces:**
- Produces: `session-open.sh open <cwd> <session_id> [--fork]` and `session-open.sh attach <session_id>`. Each prints `ok` and exits 0 on success. Sourcing with `SESSION_OPEN_LIB_ONLY=1` defines helpers without running.
- Consumes: `escape_applescript`, `escape_shell_single` from `tmux-cc-attach` (sourced lib-only).

- [ ] **Step 1: Write failing tests** in `test-session-open.sh`. Put a fake `osascript` on PATH that records its stdin to a file; assert the built command:

```sh
#!/bin/bash
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/../scripts/session-open.sh"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
fails=0
check() { if eval "$2"; then echo "ok - $1"; else echo "FAIL - $1"; fails=$((fails+1)); fi; }

# fake osascript captures the AppleScript it receives
cat > "$TMP/osascript" <<'FAKE'
#!/bin/bash
cat > "$OSA_CAPTURE"
echo "1"
FAKE
chmod +x "$TMP/osascript"
export PATH="$TMP:$PATH" OSA_CAPTURE="$TMP/osa.txt"

bash "$SCRIPT" open "/tmp/my proj" "id1" >/dev/null
check "open builds resume command" "grep -q \"cd '/tmp/my proj' && claude -r 'id1'\" \"$TMP/osa.txt\""
check "open uses a new iTerm window" "grep -q 'create window with default profile' \"$TMP/osa.txt\""

bash "$SCRIPT" open "/tmp/p" "id2" --fork >/dev/null
check "open --fork adds --fork-session" "grep -q \"claude -r 'id2' --fork-session\" \"$TMP/osa.txt\""

bash "$SCRIPT" attach "id3" >/dev/null
check "attach builds tmux -CC attach" "grep -q \"tmux -CC attach -t 'id3'\" \"$TMP/osa.txt\""

[ "$fails" -eq 0 ] && { echo ALL PASS; exit 0; } || { echo "$fails FAILED"; exit 1; }
```

- [ ] **Step 2: Run tests, confirm they FAIL** (script missing). `bash session-manager/tests/test-session-open.sh`

- [ ] **Step 3: Create `session-open.sh`** with `open`/`attach` (reuses the `create_group_window` osascript pattern from the current `tmux-cc-attach`):

```sh
#!/usr/bin/env bash
# session-open.sh — terminal actions for the sessions web UI (macOS/iTerm/tmux).
set -uo pipefail

SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
# Reuse escaping helpers from tmux-cc-attach's lib section.
TMUX_CC_LIB_ONLY=1 . "$SELF_DIR/tmux-cc-attach"

die() { echo "$*" >&2; exit 1; }

# Open a command in a fresh iTerm window; returns nonzero on failure.
open_iterm_window() {
    local cmd="$1" escaped out
    escaped=$(escape_applescript "$cmd")
    out=$(osascript 2>/dev/null <<OSA
tell application "iTerm"
  activate
  set w to (create window with default profile)
  tell current session of w to write text "$escaped"
  return (id of w) as string
end tell
OSA
)
    [ -n "$out" ] || die "failed to open iTerm window"
}

cmd_open() {
    local cwd="$1" sid="$2" fork="${3:-}" ecwd esid line
    ecwd=$(escape_shell_single "$cwd"); esid=$(escape_shell_single "$sid")
    line="cd '$ecwd' && claude -r '$esid'"
    [ "$fork" = "--fork" ] && line="$line --fork-session"
    open_iterm_window "$line" && echo ok
}

cmd_attach() {
    local sid="$1" esid
    esid=$(escape_shell_single "$sid")
    open_iterm_window "tmux -CC attach -t '$esid'" && echo ok
}

case "${1:-}" in
    open)   shift; [ $# -ge 2 ] || die "usage: open <cwd> <id> [--fork]"; cmd_open "$@" ;;
    attach) shift; [ $# -ge 1 ] || die "usage: attach <id>"; cmd_attach "$@" ;;
    focus)  shift; cmd_focus "$@" ;;          # defined in Task 3
    "")     die "usage: session-open.sh {open|attach|focus} …" ;;
    *)      die "unknown subcommand: $1" ;;
esac
```

Note: `escape_shell_single` already returns the inner-escaped form for single quotes, so wrap with `'…'` as shown (mirror how `attach_command_for`/`resume_attach_command` used it in the original). Verify against those before finalizing.

- [ ] **Step 4: `chmod +x` and run tests, confirm the open/attach checks PASS** (focus tests come in Task 3). `chmod +x session-manager/scripts/session-open.sh && bash session-manager/tests/test-session-open.sh`

- [ ] **Step 5: Commit.**
```bash
git add session-manager/scripts/session-open.sh session-manager/tests/test-session-open.sh
git commit -m "feat(session-manager): session-open.sh open/attach actions"
```

---

### Task 3: `session-open.sh` — `focus <pane>` subcommand

**Files:**
- Modify: `session-manager/scripts/session-open.sh` (add `cmd_focus`)
- Test: `session-manager/tests/test-session-open.sh`

**Interfaces:**
- Produces: `session-open.sh focus <pane>` where `<pane>` is a locator pane string. iTerm panes focus via osascript by GUID; tmux panes via `tmux -S <socket> select-window/select-pane -t <pane_id>` + `switch-client`; `apple-terminal`/unknown → nonzero with a message.

- [ ] **Step 1: Add failing focus tests.** Extend `test-session-open.sh`: for tmux, put a fake `tmux` on PATH capturing argv; for iTerm, reuse the fake `osascript`:

```sh
cat > "$TMP/tmux" <<'FAKE'
#!/bin/bash
echo "$@" >> "$TMUX_CAPTURE"
FAKE
chmod +x "$TMP/tmux"; export TMUX_CAPTURE="$TMP/tmux.txt"

bash "$SCRIPT" focus "iterm:GUID-9" >/dev/null
check "focus iterm selects by GUID" "grep -q 'GUID-9' \"$TMP/osa.txt\" && grep -qi 'select' \"$TMP/osa.txt\""

bash "$SCRIPT" focus "tmux:/tmp/sock:%3" >/dev/null
check "focus tmux selects the pane" "grep -q '%3' \"$TMUX_CAPTURE\""
check "focus tmux uses the socket" "grep -q '/tmp/sock' \"$TMUX_CAPTURE\""

bash "$SCRIPT" focus "term:xyz" >/dev/null 2>&1; rc=$?
check "focus unsupported host errors" "[ $rc -ne 0 ]"
```

- [ ] **Step 2: Run tests, confirm the focus checks FAIL.** `bash session-manager/tests/test-session-open.sh`

- [ ] **Step 3: Implement `cmd_focus`** in `session-open.sh` (add above the `case`):

```sh
focus_iterm() {   # $1 = iTerm session GUID
    local guid="$1" escaped
    escaped=$(escape_applescript "$guid")
    osascript 2>/dev/null <<OSA >/dev/null || die "iTerm session not found: $guid"
tell application "iTerm"
  activate
  repeat with w in windows
    repeat with t in tabs of w
      repeat with s in sessions of t
        if (id of s) is "$escaped" then
          tell s to select
          tell t to select
          set index of w to 1
          return "ok"
        end if
      end repeat
    end repeat
  end repeat
  error "not found"
end tell
OSA
    echo ok
}

focus_tmux() {    # $1 = "<socket>:<pane_id>"
    local rest="$1" socket pane_id
    socket="${rest%%:*}"; pane_id="${rest#*:}"
    [ -n "$socket" ] && [ -n "$pane_id" ] || die "bad tmux pane: $rest"
    tmux -S "$socket" select-window -t "$pane_id" 2>/dev/null || \
        die "tmux window not found: $pane_id"
    tmux -S "$socket" select-pane   -t "$pane_id" 2>/dev/null || true
    tmux -S "$socket" switch-client -t "$pane_id" 2>/dev/null || true
    echo ok
}

cmd_focus() {
    local pane="${1:-}"
    [ -n "$pane" ] || die "usage: focus <pane>"
    case "$pane" in
        iterm:*) focus_iterm "${pane#iterm:}" ;;
        tmux:*)  focus_tmux  "${pane#tmux:}" ;;
        *)       die "cannot focus host for pane: $pane" ;;
    esac
}
```

- [ ] **Step 4: Run tests, confirm ALL PASS.** `bash session-manager/tests/test-session-open.sh`

- [ ] **Step 5: Commit.**
```bash
git add session-manager/scripts/session-open.sh session-manager/tests/test-session-open.sh
git commit -m "feat(session-manager): session-open.sh focus action (iterm/tmux)"
```

---

### Task 4: web server action endpoints (`/api/open`, `/api/focus`, `/api/attach`)

**Files:**
- Modify: `session-manager/scripts/tmux-cc-web.py`
- Test: `session-manager/tests/test-tmux-cc-web.py`

**Interfaces:**
- Consumes: `session-open.sh` (path from `SESSION_OPEN` env or `<script-dir>/session-open.sh`); `load_sessions` for id lookup.
- Produces: `find_session(groups, session_id)` returning the enriched session dict or `None`; `_same_origin(headers, host, port)` bool; POST handlers returning `{ok:true}` / `{error:…}`.

- [ ] **Step 1: Write failing tests.** Add a `LiveActions` class. Inject a fake executor via `SESSION_OPEN` that records argv; drive the server with `urllib` POSTs.

```python
class LiveActions(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        d = os.path.join(self.root, "-proj"); os.makedirs(d, exist_ok=True)
        _write(os.path.join(d, "e1.jsonl"), ['{"type":"user","message":{"content":"hi"}}'])
        _write(os.path.join(d, "l1.jsonl"),
               ['{"type":"user","message":{"content":"live"},"timestamp":"1970-01-01T00:00:30Z"}'])
        self.argfile = os.path.join(self.root, "args.txt")
        self.stub = os.path.join(self.root, "session-open.sh")
        _write(self.stub, ["#!/bin/bash", 'printf "%s\\n" "$*" >> ' + shlex.quote(self.argfile), "echo ok"])
        os.chmod(self.stub, 0o755)
        payload = ('[{"session_id":"e1","cwd":"/tmp/a","project":"/pa","ts_end":5,'
                   '"reason":"x","status":"ended"},'
                   '{"session_id":"l1","cwd":"/tmp/b","project":"/pb","pid":"7",'
                   '"pane":"iterm:GUID","host":"iterm","status":"live"}]')
        self.attach = ["bash", "-c", "printf '%s' " + shlex.quote(payload)]

    def _serve(self):
        srv = web.WebServer(("127.0.0.1", 0), self.attach, self.root)
        srv.session_open = self.stub
        t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
        return srv, srv.server_address[1]

    def _post(self, port, path, body, origin=None):
        data = json.dumps(body).encode()
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path), data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        if origin: req.add_header("Origin", origin)
        return urllib.request.urlopen(req, timeout=5)

    def test_open_runs_executor(self):
        srv, port = self._serve()
        try:
            r = self._post(port, "/api/open", {"session_id": "e1"},
                           origin="http://127.0.0.1:%d" % port)
            self.assertEqual(json.loads(r.read())["ok"], True)
            self.assertIn("open /tmp/a e1", open(self.argfile).read())
        finally:
            srv.shutdown(); srv.server_close()

    def test_unknown_id_404(self):
        srv, port = self._serve()
        try:
            with self.assertRaises(urllib.error.HTTPError) as cm:
                self._post(port, "/api/open", {"session_id": "nope"},
                           origin="http://127.0.0.1:%d" % port)
            self.assertEqual(cm.exception.code, 404)
        finally:
            srv.shutdown(); srv.server_close()

    def test_cross_origin_403(self):
        srv, port = self._serve()
        try:
            with self.assertRaises(urllib.error.HTTPError) as cm:
                self._post(port, "/api/open", {"session_id": "e1"}, origin="http://evil.example")
            self.assertEqual(cm.exception.code, 403)
        finally:
            srv.shutdown(); srv.server_close()

    def test_focus_resolves_pane(self):
        srv, port = self._serve()
        try:
            self._post(port, "/api/focus", {"session_id": "l1"},
                       origin="http://127.0.0.1:%d" % port)
            self.assertIn("focus iterm:GUID", open(self.argfile).read())
        finally:
            srv.shutdown(); srv.server_close()

    def test_attach_requires_tmux_host(self):
        srv, port = self._serve()
        try:
            with self.assertRaises(urllib.error.HTTPError) as cm:  # l1 is host=iterm
                self._post(port, "/api/attach", {"session_id": "l1"},
                           origin="http://127.0.0.1:%d" % port)
            self.assertIn(cm.exception.code, (400, 409))
        finally:
            srv.shutdown(); srv.server_close()
```

- [ ] **Step 2: Run tests, confirm the new class FAILS.** `python3 session-manager/tests/test-tmux-cc-web.py`

- [ ] **Step 3: Implement.** Add helpers + POST handling to `tmux-cc-web.py`:

```python
def find_session(groups, session_id):
    for g in groups:
        for s in g["sessions"]:
            if s.get("session_id") == session_id:
                return s
    return None


def _same_origin(headers, host, port):
    origin = headers.get("Origin")
    expected = {"http://127.0.0.1:%d" % port, "http://localhost:%d" % port}
    if origin is not None:
        return origin in expected
    h = headers.get("Host") or ""
    return h in {"127.0.0.1:%d" % port, "localhost:%d" % port}


def default_session_open_path():
    return os.environ.get("SESSION_OPEN") or \
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "session-open.sh")


def run_action(session_open, argv):
    proc = subprocess.run([session_open] + argv,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip() or "action failed")
```

In `WebServer.__init__` add `self.session_open = default_session_open_path()`.

Add `do_POST` to `Handler`:

```python
    def do_POST(self):
        parsed = urlparse(self.path)
        port = self.server.server_address[1]
        if not _same_origin(self.headers, self.server.server_address[0], port):
            self._send(403, json.dumps({"error": "cross-origin"}).encode(), "application/json")
            return
        routes = {"/api/open", "/api/focus", "/api/attach"}
        if parsed.path not in routes:
            self._send(404, b"not found", "text/plain; charset=utf-8"); return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, TypeError):
            self._send(400, json.dumps({"error": "bad body"}).encode(), "application/json"); return
        sid = body.get("session_id")
        groups = load_sessions(self.server.attach_cmd, self.server.projects_root, self.server.cache)
        s = find_session(groups, sid)
        if s is None:
            self._send(404, json.dumps({"error": "unknown session"}).encode(), "application/json"); return
        try:
            if parsed.path == "/api/open":
                argv = ["open", s["cwd"], sid] + (["--fork"] if body.get("fork") else [])
            elif parsed.path == "/api/focus":
                if not s.get("pane"):
                    self._send(400, json.dumps({"error": "no pane"}).encode(), "application/json"); return
                argv = ["focus", s["pane"]]
            else:  # /api/attach
                if s.get("host") != "tmux":
                    self._send(400, json.dumps({"error": "not a tmux session"}).encode(), "application/json"); return
                argv = ["attach", sid]
            run_action(self.server.session_open, argv)
            self._send(200, json.dumps({"ok": True}).encode(), "application/json")
        except Exception as exc:
            self._send(500, json.dumps({"error": str(exc)}).encode(), "application/json")
```

- [ ] **Step 4: Run tests, confirm ALL PASS.** `python3 session-manager/tests/test-tmux-cc-web.py`

- [ ] **Step 5: Commit.**
```bash
git add session-manager/scripts/tmux-cc-web.py session-manager/tests/test-tmux-cc-web.py
git commit -m "feat(session-manager): web UI action endpoints (open/focus/attach)"
```

---

### Task 5: page action buttons (Launch / Go-to-pane / Attach-‑CC / Fork)

**Files:**
- Modify: `session-manager/scripts/tmux-cc-web.py` (`PAGE_HTML` JS/CSS)
- Test: `session-manager/tests/test-tmux-cc-web.py` (HTML wiring assertion) + manual browser verification

**Interfaces:**
- Consumes: `POST /api/open|focus|attach` from Task 4; `s.status`, `s.host`, `s.copy_command`, `s.fork_command`.

- [ ] **Step 1: Add a wiring assertion** to the existing `LiveServer.test_api_and_index` (HTML is served inline, so assert the action code is present):

```python
            self.assertIn("/api/open", html)
            self.assertIn("/api/focus", html)
```

- [ ] **Step 2: Run tests, confirm it FAILS.** `python3 session-manager/tests/test-tmux-cc-web.py`

- [ ] **Step 3: Implement the buttons.** Replace `row()`'s action section so each button POSTs and flashes status. Add a helper:

```javascript
async function action(path, body, btn, okLabel) {
  const old = btn.textContent;
  try {
    const r = await fetch(path, {method:"POST", headers:{"Content-Type":"application/json"},
                                 body: JSON.stringify(body)});
    const j = await r.json().catch(() => ({}));
    if (!r.ok || !j.ok) throw new Error(j.error || ("HTTP " + r.status));
    btn.textContent = okLabel; btn.classList.add("copied");
  } catch (e) {
    btn.textContent = "Failed"; btn.title = String(e.message);
  }
  setTimeout(() => { btn.textContent = old; btn.classList.remove("copied"); }, 1400);
}

function actionButton(label, onClick, title) {
  const b = document.createElement("button");
  b.className = "copy"; b.textContent = label; if (title) b.title = title;
  b.addEventListener("click", () => onClick(b));
  return b;
}
```

In `row()`, build actions by status:

```javascript
  const actions = document.createElement("div");
  actions.className = "actions";
  if (isLive(s)) {
    actions.appendChild(actionButton("Go to pane",
      (b) => action("/api/focus", {session_id: s.session_id}, b, "Focused ✓"),
      "Focus the pane where this session is running"));
    if (s.host === "tmux")
      actions.appendChild(actionButton("Attach ‑CC",
        (b) => action("/api/attach", {session_id: s.session_id}, b, "Attaching ✓"),
        "Attach the tmux session in a new iTerm window (tmux -CC)"));
    actions.appendChild(actionButton("Fork",
      (b) => action("/api/open", {session_id: s.session_id, fork: true}, b, "Forked ✓"),
      "Fork this session into a new one"));
  } else {
    actions.appendChild(actionButton("Launch",
      (b) => action("/api/open", {session_id: s.session_id}, b, "Opened ✓"),
      "Resume this session in a new iTerm window"));
  }
  actions.appendChild(actionButton("Copy",
    (b) => copy(isLive(s) ? s.fork_command : s.copy_command, b), "Copy the command"));
  el.appendChild(actions);
  return el;
```

- [ ] **Step 4: Run tests, confirm ALL PASS.** `python3 session-manager/tests/test-tmux-cc-web.py`

- [ ] **Step 5: Manual browser verification.** Start `python3 session-manager/scripts/tmux-cc-web.py --port 8790`; confirm ended rows show Launch+Copy, live rows show Go-to-pane+Fork+Copy (+Attach-‑CC for tmux), buttons flash success, and cross-checking the running session's "Go to pane" focuses its tab. Stop the server after.

- [ ] **Step 6: Commit.**
```bash
git add session-manager/scripts/tmux-cc-web.py session-manager/tests/test-tmux-cc-web.py
git commit -m "feat(session-manager): web UI action buttons for live/ended sessions"
```

---

### Task 6: hard-remove the TUI; default run execs the web server

**Files:**
- Modify: `session-manager/scripts/tmux-cc-attach`
- Test: `session-manager/tests/test-tmux-cc-attach.sh`

**Interfaces:**
- Produces: no-arg (or any non-`--json`) invocation execs `python3 <dir>/tmux-cc-web.py "$@"`. `--json` unchanged. Removed flags now error via usage.

- [ ] **Step 1: Add failing tests.** A fake `python3` on PATH records argv and the web-launch is asserted; `--json` still works; a removed flag errors:

```sh
# fake python3 that records argv
cat > "$TMP/python3" <<'FAKE'
#!/bin/bash
echo "$@" > "$PY_CAPTURE"
FAKE
chmod +x "$TMP/python3"; export PY_CAPTURE="$TMP/py.txt"
PATH="$TMP:$PATH" bash "$SCRIPT" --port 8790 --no-open >/dev/null 2>&1
check "no-json execs web server" "grep -q 'tmux-cc-web.py' \"$PY_CAPTURE\""
check "web-launch passes flags through" "grep -q -- '--port 8790 --no-open' \"$PY_CAPTURE\""
check "removed --resume-only errors" "! bash \"$SCRIPT\" --resume-only >/dev/null 2>&1"
```
(Keep all existing `--json` checks.)

- [ ] **Step 2: Run tests, confirm the new checks FAIL.** `bash session-manager/tests/test-tmux-cc-attach.sh`

- [ ] **Step 3: Remove the TUI and add the launcher.** Delete from `tmux-cc-attach`: the tmux-session work-list build, the report/print loop, `parse_group_selection` usage + selection prompt, `create_group_window`/`add_gateway_tab`/`attach_command_for` (now in `session-open.sh`), the iTerm/tmux preflight, and the flags `-n`, `-y`, `-a`, `--no-group`, `-o/--only`, `-x/--exclude`, `-d/--delay`, `--no-resume`, `--resume-only`. Keep `escape_applescript`, `escape_shell_single`, `project_of_dir`, resume-store readers, locator helpers, `live_sessions_json`, and the whole `--json` path (with `--project`/`--since`). Replace the arg loop + post-parse body with:

```sh
JSON_MODE=0
WEB_ARGS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --json)         JSON_MODE=1; RESUME_ONLY=1; RESUME=1; shift ;;
        -p|--project)   [ $# -ge 2 ] || die "--project needs a glob"; PROJECT_GLOBS+=("$2"); shift 2 ;;
        --since)        [ $# -ge 2 ] || die "--since needs days"; case "$2" in ''|*[!0-9]*) die "--since needs a non-negative integer" ;; esac; RESUME_MAX_AGE_DAYS="$2"; shift 2 ;;
        --port|--host)  WEB_ARGS+=("$1" "$2"); shift 2 ;;
        --no-open)      WEB_ARGS+=("$1"); shift ;;
        -h|--help)      usage; exit 0 ;;
        *)              die "unknown option: $1 (try --help)" ;;
    esac
done

if [ "$JSON_MODE" -eq 0 ]; then
    exec python3 "$(cd "$(dirname "$0")" && pwd)/tmux-cc-web.py" ${WEB_ARGS[@]+"${WEB_ARGS[@]}"}
fi
command -v jq >/dev/null 2>&1 || die "jq required for --json"
# … existing resume-build + JSON emission block …
```

Update `usage()` to describe only: default → web UI (`--port/--host/--no-open`), `--json` backend (`--project/--since`).

- [ ] **Step 4: Delete TUI-only tests** from `test-tmux-cc-attach.sh` (report/group-selection/attach-command assertions and `parse_group_selection` checks if `parse_group_selection` is removed — keep the function only if still used; otherwise drop both). Keep resume-helper and `--json` tests.

- [ ] **Step 5: Run tests, confirm ALL PASS.** `bash session-manager/tests/test-tmux-cc-attach.sh`

- [ ] **Step 6: Commit.**
```bash
git add session-manager/scripts/tmux-cc-attach session-manager/tests/test-tmux-cc-attach.sh
git commit -m "feat(session-manager): tmux-cc-attach opens web UI; remove interactive TUI"
```

---

### Task 7: docs + version bump

**Files:**
- Modify: `session-manager/README.md`, `session-manager/commands/list-resumable-web.md`, `session-manager/CLAUDE.md`
- Modify: `session-manager/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` (via bump script)

- [ ] **Step 1: Update `session-manager/CLAUDE.md`.** In the `tmux-cc-attach` section: state the interactive TUI is removed, the default run opens the web UI, and `--json` remains the backend (now emitting `pane`/`host`). Add a `session-open.sh` component subsection (open/focus/attach; osascript/tmux; lib-only tests). In the `tmux-cc-web.py` section: document the POST endpoints, the Origin/Host + id-in-list safety, and the per-status buttons.

- [ ] **Step 2: Update `session-manager/README.md`** and `commands/list-resumable-web.md`: `tmux-cc-attach` (no args) opens the web UI (equivalent to `/session-manager:list-resumable-web`); live rows Go-to-pane / Attach-‑CC / Fork, ended rows Launch; the TUI is gone.

- [ ] **Step 3: Grep for stale TUI references** and fix: `grep -rn "resume-only\|--no-resume\|attach.*tmux -CC\|interactive" session-manager/README.md session-manager/CLAUDE.md session-manager/commands`.

- [ ] **Step 4: Bump version + clear cache.** `./scripts/bump-plugin.sh session-manager minor`

- [ ] **Step 5: Full test sweep.** Run every suite: `test-tmux-cc-web.py`, `test-tmux-cc-attach.sh`, `test-session-open.sh`, `test_locator.py`, `test-record-session.sh`, `test-fork-*.sh`.

- [ ] **Step 6: Commit.**
```bash
git add -A
git commit -m "docs(session-manager): web UI replaces the TUI; bump minor"
```
