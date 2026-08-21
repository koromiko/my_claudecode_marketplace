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
                if not isinstance(rec, dict):
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
                if not isinstance(rec, dict):
                    continue
                if rec.get("type") != "user":
                    continue
                text = _content_text((rec.get("message") or {}).get("content"))
                if _is_human_title(text):
                    n += 1
    except OSError:
        return None
    return n


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
