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
