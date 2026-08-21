# Resumable Sessions Web UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local web page that lists resumable Claude Code sessions grouped by project, each with a title/age/turn-count/reason and a Copy button that puts `cd <cwd> && claude -r <id>` on the clipboard.

**Architecture:** `tmux-cc-attach` gains a headless `--json` mode that prints the authoritative resumable list (single source of truth for *which* sessions). A Python stdlib HTTP server (`tmux-cc-web.py`) shells out to it, enriches each session with a title + turn count parsed from the transcript, groups/sorts, and serves a single self-contained HTML page. No resume runs server-side — the page copies a command.

**Tech Stack:** Bash (existing `tmux-cc-attach`, `jq`), Python 3 stdlib only (`http.server`, `json`, `subprocess`, `glob`, `shlex`, `webbrowser`, `argparse`), vanilla HTML/CSS/JS.

## Global Constraints

- Python 3 stdlib only — no pip/external deps (matches `locator.py`, `claude-usage-analyzer`).
- Server binds loopback only (default host `127.0.0.1`).
- `jq` is required for the bash `--json` path (already a dependency of the script).
- Tests live in `session-manager/tests/`; bash unit tests reuse the `TMUX_CC_LIB_ONLY` sourcing seam and stub `CLAUDE_SM_HOME`/`CLAUDE_PROJECTS_DIR`/`TMUX_CC_LOCATOR`.
- "Resumable" is defined solely by `tmux-cc-attach` (age window, transcript exists, not autonomous, not currently live). The web layer never re-implements that filter.
- Commit messages: max 3 non-blank lines, no `Co-Authored-By` trailer.
- After implementation: `./scripts/bump-plugin.sh session-manager minor` before the final commit.

## File Structure

- Modify `session-manager/scripts/tmux-cc-attach` — add `--json` flag: store `RESUME_TS`, guard iTerm/tmux preflight, emit JSON array, exit before attach.
- Modify `session-manager/tests/test-tmux-cc-attach.sh` — `--json` assertions.
- Create `session-manager/scripts/tmux-cc-web.py` — enrichment helpers + HTTP server + inline HTML page + CLI.
- Create `session-manager/tests/test-tmux-cc-web.py` — stdlib `unittest` for the Python helpers + a live-server integration test.
- Create `session-manager/commands/list-resumable-web.md` — command doc.
- Modify `session-manager/README.md` — feature section.
- Modify (via bump script) `session-manager/.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json`.

---

### Task 1: `--json` mode on `tmux-cc-attach`

**Files:**
- Modify: `session-manager/scripts/tmux-cc-attach`
- Test: `session-manager/tests/test-tmux-cc-attach.sh`

**Interfaces:**
- Produces: `tmux-cc-attach --json` → prints a JSON array to stdout, one object per resumable session: `{"session_id":str,"cwd":str,"project":str,"ts_end":number,"reason":str}`; prints `[]` when none; exits 0. Implies `--resume-only`; skips iTerm/osascript/tmux preflight. Honors `--project`/`--since`.

- [ ] **Step 1: Write the failing tests** — append to `session-manager/tests/test-tmux-cc-attach.sh`, immediately before the final `[ "$fails" -eq 0 ] && ...` line. Reuses the `livesid`/`oldsid`/`ghostsid`/`autosid2` fixtures already set up earlier in that file.

```bash
# --json emits a JSON array of resumable sessions, honoring the same filters.
jout=$(TMUX_CC_LOCATOR=/nonexistent bash "$SCRIPT" --json 2>/dev/null)
check "--json is valid array" \
    "printf '%s' \"\$jout\" | jq -e 'type==\"array\"' >/dev/null"
check "--json includes livesid" \
    "printf '%s' \"\$jout\" | jq -e '.[]|select(.session_id==\"livesid\")' >/dev/null"
check "--json livesid cwd" \
    "[ \"\$(printf '%s' \"\$jout\" | jq -r '.[]|select(.session_id==\"livesid\").cwd')\" = '/tmp/live' ]"
check "--json livesid ts_end numeric" \
    "printf '%s' \"\$jout\" | jq -e '.[]|select(.session_id==\"livesid\").ts_end|type==\"number\"' >/dev/null"
check "--json drops stale/ghost/auto" \
    "[ \"\$(printf '%s' \"\$jout\" | jq -r '[.[]|select(.session_id|IN(\"oldsid\",\"ghostsid\",\"autosid2\"))]|length')\" = '0' ]"
check "--json no report text" \
    "! printf '%s' \"\$jout\" | grep -q 'Attaching/resuming'"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `bash session-manager/tests/test-tmux-cc-attach.sh`
Expected: the six new `--json` checks FAIL (current script treats `--json` as unknown option and dies).

- [ ] **Step 3: Add the `JSON_MODE` flag default** — in the flag-defaults block near `RESUME_ONLY=0` (around line 40), add:

```bash
JSON_MODE=0
```

- [ ] **Step 4: Parse the `--json` flag** — in the `while [ $# -gt 0 ]` arg-parse loop, add a case next to `--resume-only`:

```bash
        --json)         JSON_MODE=1; RESUME_ONLY=1; RESUME=1; shift ;;
```

- [ ] **Step 5: Guard the preflight for JSON mode** — replace the preflight block:

```bash
command -v tmux >/dev/null 2>&1 || die "tmux not found on PATH"
command -v osascript >/dev/null 2>&1 || die "osascript not found (macOS only)"
[ -d "$ITERM_APP" ] || die "iTerm2 not installed at $ITERM_APP"
if [ "$RESUME_ONLY" -eq 0 ]; then
    tmux list-sessions >/dev/null 2>&1 || die "no tmux server running"
fi
```

with:

```bash
if [ "$JSON_MODE" -eq 1 ]; then
    command -v jq >/dev/null 2>&1 || die "jq required for --json"
else
    command -v tmux >/dev/null 2>&1 || die "tmux not found on PATH"
    command -v osascript >/dev/null 2>&1 || die "osascript not found (macOS only)"
    [ -d "$ITERM_APP" ] || die "iTerm2 not installed at $ITERM_APP"
    if [ "$RESUME_ONLY" -eq 0 ]; then
        tmux list-sessions >/dev/null 2>&1 || die "no tmux server running"
    fi
fi
```

- [ ] **Step 6: Declare and populate `RESUME_TS`** — in the resume work-list section, add `RESUME_TS=()` beside the other `RESUME_*` array declarations (`RESUME_IDS=()` etc.), and inside the resume loop add the timestamp right after `RESUME_REASON+=("$rreason")`:

```bash
        RESUME_TS+=("$rts")
```

(`$rts` already passed `resume_within_age`, so it is a validated integer.)

- [ ] **Step 7: Emit JSON and exit** — insert this block immediately after the `if [ "$RESUME" -eq 1 ]; then ... fi` resume-list block closes, and BEFORE the `if [ ${#SESSION_IDS[@]} -eq 0 ] && [ ${#RESUME_IDS[@]} -eq 0 ]; then echo "Nothing to attach or resume...` empty-check:

```bash
if [ "$JSON_MODE" -eq 1 ]; then
    if [ ${#RESUME_IDS[@]} -eq 0 ]; then
        printf '[]\n'
        exit 0
    fi
    for i in "${!RESUME_IDS[@]}"; do
        jq -cn \
            --arg id "${RESUME_IDS[i]}" \
            --arg cwd "${RESUME_CWDS[i]}" \
            --arg project "${RESUME_PROJECT[i]}" \
            --argjson ts_end "${RESUME_TS[i]}" \
            --arg reason "${RESUME_REASON[i]}" \
            '{session_id:$id, cwd:$cwd, project:$project, ts_end:$ts_end, reason:$reason}'
    done | jq -sc '.'
    exit 0
fi
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `bash session-manager/tests/test-tmux-cc-attach.sh`
Expected: `ALL PASS` (pre-existing checks plus the six `--json` checks).

- [ ] **Step 9: Update `usage()`** — add the `--json` line to the options list in the `usage()` heredoc, after the `--resume-only`/`--since` entries:

```
      --json              Print resumable sessions as JSON and exit (implies
                          --resume-only; skips iTerm/tmux preflight)
```

- [ ] **Step 10: Commit**

```bash
git add session-manager/scripts/tmux-cc-attach session-manager/tests/test-tmux-cc-attach.sh
git commit -m "feat(session-manager): add --json mode to tmux-cc-attach

Prints the resumable-session list as JSON headlessly; source of truth for the web UI."
```

---

### Task 2: Transcript helpers in `tmux-cc-web.py`

**Files:**
- Create: `session-manager/scripts/tmux-cc-web.py`
- Test: `session-manager/tests/test-tmux-cc-web.py`

**Interfaces:**
- Produces:
  - `build_copy_command(cwd:str, session_id:str) -> str` — shell-safe `cd <cwd> && claude -r <id>` (via `shlex.quote`).
  - `extract_title(transcript_path:str, maxlen:int=120) -> str|None` — first human user message, whitespace-collapsed, truncated; `None` if none/unreadable.
  - `count_turns(transcript_path:str) -> int|None` — number of `type=="user"` records with string content; `None` if unreadable.

- [ ] **Step 1: Write the failing tests** — create `session-manager/tests/test-tmux-cc-web.py`:

```python
import os, sys, tempfile, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
import importlib.util
spec = importlib.util.spec_from_file_location(
    "tmux_cc_web", os.path.join(HERE, "..", "scripts", "tmux-cc-web.py"))
web = importlib.util.module_from_spec(spec)
spec.loader.exec_module(web)


def _write(path, lines):
    with open(path, "w", encoding="utf-8") as fh:
        for ln in lines:
            fh.write(ln + "\n")


class CopyCommand(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(
            web.build_copy_command("/tmp/proj", "abc-123"),
            "cd /tmp/proj && claude -r abc-123")

    def test_space_in_cwd_is_quoted(self):
        cmd = web.build_copy_command("/tmp/my proj", "id1")
        self.assertIn("'/tmp/my proj'", cmd)
        self.assertTrue(cmd.startswith("cd "))


class ExtractTitle(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def test_plain_user(self):
        p = os.path.join(self.d, "a.jsonl")
        _write(p, ['{"type":"user","message":{"content":"Add a web UI"}}',
                   '{"type":"assistant","message":{"content":"ok"}}'])
        self.assertEqual(web.extract_title(p), "Add a web UI")

    def test_skips_teammate_and_command(self):
        p = os.path.join(self.d, "b.jsonl")
        _write(p, ['{"type":"user","message":{"content":"<teammate-message>hi</teammate-message>"}}',
                   '{"type":"user","message":{"content":"<command-name>/clear</command-name>"}}',
                   '{"type":"user","message":{"content":"Real question here"}}'])
        self.assertEqual(web.extract_title(p), "Real question here")

    def test_list_content_text(self):
        p = os.path.join(self.d, "c.jsonl")
        _write(p, ['{"type":"user","message":{"content":[{"type":"text","text":"Hello there"}]}}'])
        self.assertEqual(web.extract_title(p), "Hello there")

    def test_none_when_no_human(self):
        p = os.path.join(self.d, "d.jsonl")
        _write(p, ['{"type":"assistant","message":{"content":"x"}}'])
        self.assertIsNone(web.extract_title(p))

    def test_missing_file(self):
        self.assertIsNone(web.extract_title(os.path.join(self.d, "nope.jsonl")))

    def test_truncates(self):
        p = os.path.join(self.d, "e.jsonl")
        _write(p, ['{"type":"user","message":{"content":"%s"}}' % ("x" * 200)])
        self.assertEqual(len(web.extract_title(p, maxlen=120)), 120)


class CountTurns(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def test_counts_string_user_records(self):
        p = os.path.join(self.d, "a.jsonl")
        _write(p, ['{"type":"user","message":{"content":"one"}}',
                   '{"type":"assistant","message":{"content":"r"}}',
                   '{"type":"user","message":{"content":"two"}}'])
        self.assertEqual(web.count_turns(p), 2)

    def test_ignores_tool_result_list_records(self):
        p = os.path.join(self.d, "b.jsonl")
        _write(p, ['{"type":"user","message":{"content":"real"}}',
                   '{"type":"user","message":{"content":[{"type":"tool_result","content":"x"}]}}'])
        self.assertEqual(web.count_turns(p), 1)

    def test_missing_file(self):
        self.assertIsNone(web.count_turns(os.path.join(self.d, "nope.jsonl")))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 session-manager/tests/test-tmux-cc-web.py -v`
Expected: FAIL — module `tmux-cc-web.py` does not exist yet (import error).

- [ ] **Step 3: Create `tmux-cc-web.py` with the module docstring, imports, and the three helpers**

```python
#!/usr/bin/env python3
"""Local web UI listing resumable Claude Code sessions, grouped by project.

Reads the authoritative resumable list from `tmux-cc-attach --json`, enriches
each session with a title + turn count parsed from its transcript, and serves a
single-page browser UI whose Copy buttons put `cd <cwd> && claude -r <id>` on
the clipboard. Python 3 stdlib only.
"""
import argparse
import glob
import json
import os
import shlex
import subprocess
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TITLE_MAX = 120


def build_copy_command(cwd, session_id):
    return "cd %s && claude -r %s" % (shlex.quote(cwd), shlex.quote(session_id))


def _content_text(content):
    """Flatten a message .content (str, or list of parts) to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [p["text"] for p in content
                 if isinstance(p, dict) and isinstance(p.get("text"), str)]
        return "".join(parts)
    return ""


def _is_human_title(text):
    t = text.strip()
    if not t:
        return False
    if t.startswith("<teammate-message"):
        return False
    if t.startswith("<system-reminder"):
        return False
    if "<command-name>" in t or "<local-command" in t:
        return False
    return True


def extract_title(transcript_path, maxlen=TITLE_MAX):
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("type") != "user":
                    continue
                text = _content_text((rec.get("message") or {}).get("content"))
                if _is_human_title(text):
                    return " ".join(text.split())[:maxlen]
    except OSError:
        return None
    return None


def count_turns(transcript_path):
    n = 0
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("type") != "user":
                    continue
                if isinstance((rec.get("message") or {}).get("content"), str):
                    n += 1
    except OSError:
        return None
    return n
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 session-manager/tests/test-tmux-cc-web.py -v`
Expected: PASS for the `CopyCommand`, `ExtractTitle`, `CountTurns` classes.

- [ ] **Step 5: Commit**

```bash
git add session-manager/scripts/tmux-cc-web.py session-manager/tests/test-tmux-cc-web.py
git commit -m "feat(session-manager): transcript title/turn helpers for web UI"
```

---

### Task 3: Enrichment, caching, grouping, and `load_sessions`

**Files:**
- Modify: `session-manager/scripts/tmux-cc-web.py`
- Test: `session-manager/tests/test-tmux-cc-web.py`

**Interfaces:**
- Consumes: `build_copy_command`, `extract_title`, `count_turns` (Task 2).
- Produces:
  - `enrich(session:dict, projects_root:str, cache:dict) -> dict` — mutates+returns; adds `copy_command`, `title` (falls back to cwd basename), `turns`. Caches `(title, turns)` by `(session_id, transcript_mtime)`.
  - `group_and_sort(sessions:list[dict]) -> list[dict]` — `[{"project":str,"sessions":[...]}]`; sessions sorted by `ts_end` desc; groups ordered by most-recent `ts_end` desc.
  - `load_sessions(attach_cmd:list[str], projects_root:str, cache:dict) -> list[dict]` — runs `attach_cmd`, parses its JSON, enriches each, returns grouped/sorted; raises `RuntimeError` on non-zero exit.

- [ ] **Step 1: Write the failing tests** — append these classes to `session-manager/tests/test-tmux-cc-web.py` (before the `if __name__` guard):

```python
class GroupAndSort(unittest.TestCase):
    def test_groups_and_sorts(self):
        sessions = [
            {"session_id": "a", "project": "/p1", "ts_end": 10},
            {"session_id": "b", "project": "/p2", "ts_end": 50},
            {"session_id": "c", "project": "/p1", "ts_end": 30},
        ]
        groups = web.group_and_sort(sessions)
        # group with the most-recent session comes first (/p1 max ts 30 vs /p2 50 -> /p2 first)
        self.assertEqual([g["project"] for g in groups], ["/p2", "/p1"])
        p1 = [g for g in groups if g["project"] == "/p1"][0]
        self.assertEqual([s["session_id"] for s in p1["sessions"]], ["c", "a"])


class Enrich(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def _transcript(self, sid, lines):
        d = os.path.join(self.root, "-proj")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, sid + ".jsonl")
        _write(p, lines)
        return p

    def test_enrich_sets_fields(self):
        self._transcript("s1", ['{"type":"user","message":{"content":"Hello"}}'])
        cache = {}
        s = web.enrich({"session_id": "s1", "cwd": "/tmp/x", "project": "/p", "ts_end": 1},
                       self.root, cache)
        self.assertEqual(s["title"], "Hello")
        self.assertEqual(s["turns"], 1)
        self.assertEqual(s["copy_command"], "cd /tmp/x && claude -r s1")
        self.assertEqual(len(cache), 1)

    def test_enrich_uses_cache(self):
        self._transcript("s2", ['{"type":"user","message":{"content":"First"}}'])
        cache = {}
        web.enrich({"session_id": "s2", "cwd": "/tmp/x", "project": "/p", "ts_end": 1},
                   self.root, cache)
        # Pre-seed the cache entry with a different title; enrich must reuse it.
        key = list(cache.keys())[0]
        cache[key] = ("CACHED", 99)
        s = web.enrich({"session_id": "s2", "cwd": "/tmp/x", "project": "/p", "ts_end": 1},
                       self.root, cache)
        self.assertEqual(s["title"], "CACHED")
        self.assertEqual(s["turns"], 99)

    def test_enrich_missing_transcript_falls_back(self):
        cache = {}
        s = web.enrich({"session_id": "ghost", "cwd": "/tmp/foo/bar", "project": "/p", "ts_end": 1},
                       self.root, cache)
        self.assertEqual(s["title"], "bar")
        self.assertIsNone(s["turns"])


class LoadSessions(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def test_load_and_group(self):
        payload = '[{"session_id":"s1","cwd":"/tmp/a","project":"/pa","ts_end":5,"reason":"other"}]'
        cmd = ["bash", "-c", "printf '%s' " + shlex.quote(payload)]
        groups = web.load_sessions(cmd, self.root, {})
        self.assertEqual(groups[0]["project"], "/pa")
        self.assertEqual(groups[0]["sessions"][0]["copy_command"], "cd /tmp/a && claude -r s1")

    def test_load_raises_on_failure(self):
        cmd = ["bash", "-c", "echo boom >&2; exit 1"]
        with self.assertRaises(RuntimeError):
            web.load_sessions(cmd, self.root, {})
```

Note: `import shlex` is already imported at the top of the test module via the module under test? No — add `import shlex` to the test file's top imports if not present (the `LoadSessions` test uses it).

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 session-manager/tests/test-tmux-cc-web.py -v`
Expected: FAIL — `enrich`, `group_and_sort`, `load_sessions` not defined.

- [ ] **Step 3: Add the functions** — append to `tmux-cc-web.py` after `count_turns`:

```python
def _find_transcript(session_id, projects_root):
    hits = glob.glob(os.path.join(projects_root, "*", session_id + ".jsonl"))
    return hits[0] if hits else None


def _cwd_basename(cwd):
    return os.path.basename(cwd.rstrip("/")) or cwd


def enrich(session, projects_root, cache):
    sid = session["session_id"]
    session["copy_command"] = build_copy_command(session["cwd"], sid)
    path = _find_transcript(sid, projects_root)
    if not path:
        session["title"] = _cwd_basename(session["cwd"])
        session["turns"] = None
        return session
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = None
    key = (sid, mtime)
    if key in cache:
        title, turns = cache[key]
    else:
        title = extract_title(path)
        turns = count_turns(path)
        cache[key] = (title, turns)
    session["title"] = title or _cwd_basename(session["cwd"])
    session["turns"] = turns
    return session


def group_and_sort(sessions):
    groups = {}
    for s in sessions:
        groups.setdefault(s.get("project") or "(unknown)", []).append(s)
    for items in groups.values():
        items.sort(key=lambda s: s.get("ts_end") or 0, reverse=True)
    ordered = sorted(
        groups.keys(),
        key=lambda p: max((s.get("ts_end") or 0) for s in groups[p]),
        reverse=True)
    return [{"project": p, "sessions": groups[p]} for p in ordered]


def load_sessions(attach_cmd, projects_root, cache):
    proc = subprocess.run(attach_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        msg = proc.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(msg or "tmux-cc-attach --json failed")
    data = json.loads(proc.stdout.decode("utf-8", "replace") or "[]")
    for s in data:
        enrich(s, projects_root, cache)
    return group_and_sort(data)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 session-manager/tests/test-tmux-cc-web.py -v`
Expected: PASS for all Task 2 + Task 3 classes.

- [ ] **Step 5: Commit**

```bash
git add session-manager/scripts/tmux-cc-web.py session-manager/tests/test-tmux-cc-web.py
git commit -m "feat(session-manager): enrich/group/load resumable sessions for web UI"
```

---

### Task 4: HTTP server, HTML page, and CLI

**Files:**
- Modify: `session-manager/scripts/tmux-cc-web.py`
- Test: `session-manager/tests/test-tmux-cc-web.py`

**Interfaces:**
- Consumes: `load_sessions` (Task 3).
- Produces:
  - `PAGE_HTML:str` — the self-contained page.
  - `WebServer(ThreadingHTTPServer)` with attributes `attach_cmd`, `projects_root`, `cache`.
  - `Handler(BaseHTTPRequestHandler)` — `GET /` → HTML 200; `GET /api/sessions` → JSON groups 200, or `{"error":...}` 500 on failure; else 404.
  - `default_attach_path()`, `default_projects_root()`, `main(argv=None)`.

- [ ] **Step 1: Write the failing integration tests** — add `import threading`, `import urllib.request`, `import urllib.error` to the test file's top imports, then append to `session-manager/tests/test-tmux-cc-web.py` (before the `if __name__` guard):

```python
class LiveServer(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        d = os.path.join(self.root, "-proj")
        os.makedirs(d, exist_ok=True)
        _write(os.path.join(d, "s1.jsonl"),
               ['{"type":"user","message":{"content":"My session title"}}'])

    def _serve(self, attach_cmd):
        srv = web.WebServer(("127.0.0.1", 0), attach_cmd, self.root)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        return srv, srv.server_address[1]

    def test_api_and_index(self):
        payload = '[{"session_id":"s1","cwd":"/tmp/a","project":"/pa","ts_end":5,"reason":"other"}]'
        srv, port = self._serve(["bash", "-c", "printf '%s' " + shlex.quote(payload)])
        try:
            body = urllib.request.urlopen("http://127.0.0.1:%d/api/sessions" % port, timeout=5).read()
            groups = json.loads(body)
            self.assertEqual(groups[0]["sessions"][0]["title"], "My session title")
            html = urllib.request.urlopen("http://127.0.0.1:%d/" % port, timeout=5).read().decode()
            self.assertIn('id="app"', html)
        finally:
            srv.shutdown(); srv.server_close()

    def test_api_error_returns_500(self):
        srv, port = self._serve(["bash", "-c", "echo boom >&2; exit 1"])
        try:
            try:
                urllib.request.urlopen("http://127.0.0.1:%d/api/sessions" % port, timeout=5)
                self.fail("expected HTTP 500")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 500)
                self.assertIn("error", json.loads(e.read()))
        finally:
            srv.shutdown(); srv.server_close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 session-manager/tests/test-tmux-cc-web.py -v`
Expected: FAIL — `WebServer` not defined.

- [ ] **Step 3: Add the page HTML constant** — append to `tmux-cc-web.py`:

```python
PAGE_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Resumable Claude Code Sessions</title>
<style>
:root { color-scheme: light dark; --bg:#f6f7f9; --card:#fff; --fg:#1b1f24;
  --muted:#6b7280; --border:#e5e7eb; --accent:#2563eb; }
@media (prefers-color-scheme: dark) { :root { --bg:#0e1116; --card:#171b21;
  --fg:#e6e9ee; --muted:#9aa4b2; --border:#2a2f37; --accent:#4f8cff; } }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
  font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
header { position:sticky; top:0; background:var(--bg); border-bottom:1px solid var(--border);
  padding:12px 20px; display:flex; gap:12px; align-items:center; flex-wrap:wrap; }
header h1 { font-size:16px; margin:0 auto 0 0; }
input, button { font:inherit; color:var(--fg); background:var(--card);
  border:1px solid var(--border); border-radius:8px; padding:6px 10px; }
button { cursor:pointer; }
#search { min-width:220px; }
main { padding:16px 20px; max-width:1000px; margin:0 auto; }
.group { margin-bottom:18px; }
.group > summary { cursor:pointer; font-weight:600; padding:6px 4px; list-style:none; }
.group > summary::-webkit-details-marker { display:none; }
.group > summary .count { color:var(--muted); font-weight:400; margin-left:8px; }
.session { background:var(--card); border:1px solid var(--border); border-radius:10px;
  padding:10px 12px; margin:8px 0; display:flex; gap:12px; align-items:flex-start; }
.session .body { flex:1 1 auto; min-width:0; }
.session .title { font-weight:600; }
.session .meta { color:var(--muted); font-size:12px; margin-top:2px;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.copy { flex:0 0 auto; }
.copy.copied { border-color:var(--accent); color:var(--accent); }
#empty, #error { text-align:center; color:var(--muted); padding:40px; }
#error { color:#b91c1c; }
.hidden { display:none; }
</style>
</head>
<body>
<header>
  <h1>Resumable sessions</h1>
  <input id="search" type="search" placeholder="Filter title / cwd / id…" autocomplete="off">
  <button id="sort">Sort: recent</button>
  <button id="refresh">Refresh</button>
</header>
<main id="app">
  <div id="error" class="hidden"></div>
  <div id="empty" class="hidden">Nothing to resume.</div>
  <div id="list"></div>
</main>
<script>
let GROUPS = [];
let SORT = "recent"; // "recent" | "project"
const $ = (s) => document.querySelector(s);

function ago(ts) {
  if (!ts) return "";
  const s = Math.max(0, Math.floor(Date.now()/1000 - ts));
  const u = [["d",86400],["h",3600],["m",60]];
  for (const [label, secs] of u) { if (s >= secs) return Math.floor(s/secs)+label+" ago"; }
  return s+"s ago";
}
function when(ts) { return ts ? new Date(ts*1000).toLocaleString() : ""; }

async function copy(text, btn) {
  try { await navigator.clipboard.writeText(text); }
  catch (e) {
    const ta = document.createElement("textarea");
    ta.value = text; document.body.appendChild(ta); ta.select();
    document.execCommand("copy"); ta.remove();
  }
  const old = btn.textContent;
  btn.textContent = "Copied ✓"; btn.classList.add("copied");
  setTimeout(() => { btn.textContent = old; btn.classList.remove("copied"); }, 1200);
}

function matches(s, q) {
  if (!q) return true;
  q = q.toLowerCase();
  return (s.title||"").toLowerCase().includes(q)
      || (s.cwd||"").toLowerCase().includes(q)
      || (s.session_id||"").toLowerCase().includes(q);
}

function escapeHtml(s) {
  return (s||"").replace(/[&<>"']/g, (c) => (
    {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

function row(s, project) {
  const el = document.createElement("div");
  el.className = "session";
  const metaBits = [];
  if (s.ts_end) metaBits.push('<span title="'+escapeHtml(when(s.ts_end))+'">'+ago(s.ts_end)+"</span>");
  if (s.turns != null) metaBits.push(s.turns + " turns");
  if (s.reason) metaBits.push(escapeHtml(s.reason));
  metaBits.push(escapeHtml(project ? project : s.cwd));
  el.innerHTML =
    '<div class="body"><div class="title">' + escapeHtml(s.title || s.session_id) + "</div>" +
    '<div class="meta">' + metaBits.join(" · ") + "</div></div>";
  const btn = document.createElement("button");
  btn.className = "copy"; btn.textContent = "Copy";
  btn.addEventListener("click", () => copy(s.copy_command, btn));
  el.appendChild(btn);
  return el;
}

function render() {
  const q = $("#search").value.trim();
  const list = $("#list"); list.innerHTML = "";
  let shown = 0;

  if (SORT === "recent") {
    let flat = [];
    for (const g of GROUPS) for (const s of g.sessions) flat.push([g.project, s]);
    flat = flat.filter(([, s]) => matches(s, q))
               .sort((a, b) => (b[1].ts_end||0) - (a[1].ts_end||0));
    for (const [project, s] of flat) { list.appendChild(row(s, project)); shown++; }
  } else {
    for (const g of GROUPS) {
      const kids = g.sessions.filter((s) => matches(s, q));
      if (!kids.length) continue;
      const d = document.createElement("details");
      d.className = "group"; d.open = true;
      const sum = document.createElement("summary");
      sum.innerHTML = escapeHtml(g.project) + '<span class="count">' + kids.length + "</span>";
      d.appendChild(sum);
      for (const s of kids) { d.appendChild(row(s)); shown++; }
      list.appendChild(d);
    }
  }
  $("#empty").classList.toggle("hidden", shown !== 0);
}

async function load() {
  $("#error").classList.add("hidden");
  try {
    const r = await fetch("/api/sessions");
    if (!r.ok) { const j = await r.json().catch(() => ({})); throw new Error(j.error || ("HTTP " + r.status)); }
    GROUPS = await r.json();
    render();
  } catch (e) {
    $("#error").textContent = "Failed to load sessions: " + e.message;
    $("#error").classList.remove("hidden");
  }
}

$("#search").addEventListener("input", render);
$("#refresh").addEventListener("click", load);
$("#sort").addEventListener("click", () => {
  SORT = SORT === "recent" ? "project" : "recent";
  $("#sort").textContent = "Sort: " + SORT;
  render();
});
load();
</script>
</body>
</html>
"""
```

- [ ] **Step 4: Add the server, handler, and CLI** — append to `tmux-cc-web.py`:

```python
class Handler(BaseHTTPRequestHandler):
    server_version = "tmux-cc-web"

    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            self._send(200, PAGE_HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if self.path == "/api/sessions":
            try:
                groups = load_sessions(self.server.attach_cmd,
                                       self.server.projects_root, self.server.cache)
                self._send(200, json.dumps(groups).encode("utf-8"), "application/json")
            except Exception as exc:
                self._send(500, json.dumps({"error": str(exc)}).encode("utf-8"),
                           "application/json")
            return
        self._send(404, b"not found", "text/plain; charset=utf-8")


class WebServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr, attach_cmd, projects_root):
        super().__init__(addr, Handler)
        self.attach_cmd = attach_cmd
        self.projects_root = projects_root
        self.cache = {}


def default_attach_path():
    return os.environ.get("TMUX_CC_ATTACH") or \
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmux-cc-attach")


def default_projects_root():
    return os.environ.get("CLAUDE_PROJECTS_DIR") or \
        os.path.expanduser("~/.claude/projects")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Web UI for resumable Claude Code sessions")
    ap.add_argument("--port", type=int, default=0, help="port (default: a free port)")
    ap.add_argument("--host", default="127.0.0.1", help="bind host (default 127.0.0.1)")
    ap.add_argument("--no-open", action="store_true", help="do not open a browser")
    args = ap.parse_args(argv)

    attach_cmd = [default_attach_path(), "--json"]
    srv = WebServer((args.host, args.port), attach_cmd, default_projects_root())
    url = "http://%s:%d/" % (args.host, srv.server_address[1])
    print("tmux-cc-web serving at %s  (Ctrl-C to stop)" % url)
    if not args.no_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Make the script executable**

```bash
chmod +x session-manager/scripts/tmux-cc-web.py
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python3 session-manager/tests/test-tmux-cc-web.py -v`
Expected: PASS for all classes including `LiveServer`.

- [ ] **Step 7: Manual smoke check (optional but recommended)**

Run: `python3 session-manager/scripts/tmux-cc-web.py --no-open --port 8765` then in another shell `curl -s localhost:8765/api/sessions | jq 'length'` and `curl -s localhost:8765/ | grep -c 'Resumable sessions'`. Stop with Ctrl-C.
Expected: a number (>= 0) and `1`.

- [ ] **Step 8: Commit**

```bash
git add session-manager/scripts/tmux-cc-web.py session-manager/tests/test-tmux-cc-web.py
git commit -m "feat(session-manager): serve resumable-sessions web UI (page + server)"
```

---

### Task 5: Command doc, README, and version bump

**Files:**
- Create: `session-manager/commands/list-resumable-web.md`
- Modify: `session-manager/README.md`
- Modify (via script): `session-manager/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`

**Interfaces:**
- Consumes: the `tmux-cc-web.py` CLI (Task 4).

- [ ] **Step 1: Create the command doc** `session-manager/commands/list-resumable-web.md`:

````markdown
---
description: Open a local web UI listing resumable Claude Code sessions, grouped by project
allowed-tools:
  - Bash(*)
---

# Resumable Sessions Web UI

Launch a local web page that lists resumable Claude Code sessions (grouped by
project) with title, last-activity, turn count, and end reason. Each row has a
Copy button that puts `cd <cwd> && claude -r <id>` on the clipboard.

## Instructions

Start the server (it prints a URL and opens the browser):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/tmux-cc-web.py
```

Options: `--port N` (default: a free port), `--host H` (default `127.0.0.1`),
`--no-open` (do not open a browser). Stop with Ctrl-C.

## Reporting to User

1. Print the served URL.
2. Note the server is read-only and binds to loopback; clicking Copy does not
   resume anything — paste the copied command into a terminal to resume.
3. Remind them to stop it with Ctrl-C when done.
````

- [ ] **Step 2: Add a README section** — in `session-manager/README.md`, after the existing commands documentation, add:

````markdown
### /session-manager:list-resumable-web

Open a local web UI listing resumable sessions, grouped by project.

```
/session-manager:list-resumable-web
```

Starts a Python stdlib HTTP server (loopback only) that reads the resumable
list from `tmux-cc-attach --json` and enriches each session with a title and
turn count from its transcript. Each row's Copy button places
`cd <cwd> && claude -r <id>` on the clipboard; nothing is resumed server-side.

Run directly: `python3 scripts/tmux-cc-web.py [--port N] [--host H] [--no-open]`.
````

- [ ] **Step 3: Run the full test suite** to confirm nothing regressed

Run: `bash session-manager/tests/test-tmux-cc-attach.sh && python3 session-manager/tests/test-tmux-cc-web.py && python3 session-manager/tests/test_locator.py`
Expected: `ALL PASS`, `OK`, `OK`.

- [ ] **Step 4: Bump the plugin version**

```bash
./scripts/bump-plugin.sh session-manager minor
```

- [ ] **Step 5: Commit**

```bash
git add session-manager/commands/list-resumable-web.md session-manager/README.md \
        session-manager/.claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "docs(session-manager): document resumable-sessions web UI; bump minor"
```

---

## Self-Review

**Spec coverage:**
- Copy-to-clipboard `claude -r` → Task 2 `build_copy_command` (`cd <cwd> && claude -r <id>`), Task 4 page Copy button. ✓
- Live local server, reads store per request, refreshable, auto-opens browser → Task 4 `WebServer`/`main` (`webbrowser.open`, `/api/sessions` reads fresh each GET, Refresh button). ✓
- Single source of truth for "resumable" → Task 1 `--json`, consumed by Task 3 `load_sessions`. ✓
- Metadata: title, last activity + age, turn count, cwd + reason → Task 2/3 enrichment; Task 4 row rendering (`ago`/`when`, turns, reason, cwd). ✓
- Grouping by project + sort recent↔project + search → Task 3 `group_and_sort`; Task 4 JS `render`/`SORT`/`#search`. ✓
- Caching by (id, mtime) → Task 3 `enrich`. ✓
- Error handling (attach failure → 500 + banner; empty → friendly state) → Task 3 `load_sessions` raise, Task 4 handler 500 + `#error`/`#empty`. ✓
- Tests in `tests/` → Tasks 1–4. ✓
- Command doc + README + minor bump → Task 5. ✓

**Placeholder scan:** No TBD/TODO; every code step has concrete content. ✓

**Type consistency:** `load_sessions(attach_cmd, projects_root, cache)`, `enrich(session, projects_root, cache)`, `group_and_sort(sessions)`, `build_copy_command(cwd, session_id)`, `extract_title(path, maxlen)`, `count_turns(path)` — names/arities identical across tasks and tests. `WebServer` attributes `attach_cmd`/`projects_root`/`cache` match handler usage. JSON keys `session_id/cwd/project/ts_end/reason` (Task 1) match `enrich`/page consumers. ✓
