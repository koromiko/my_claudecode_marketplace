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
