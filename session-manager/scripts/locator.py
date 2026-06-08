#!/usr/bin/env python3
"""
locator.py — Claude Code session <-> terminal-pane indexer/resolver (SP1).

macOS-only, read-only, pull-based: every query re-scans live processes, so the
answer is always ground truth and never stale. No daemon, no hooks, no state.

Design: pure functions (parse_*, resolve_roles, build_sessions) take injected
command output for testability; thin wrappers (_run, *_index, cwd_of, gather_*)
are the only impure code. See docs/superpowers/specs/2026-06-07-session-locator-sp1-design.md
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys

# Strict marker formats so a scanner's own ps/grep command line never parses as
# a real record (it carries no real session uuid).
RE_SESSION = re.compile(
    r"CLAUDE_CODE_SESSION_ID=([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)
RE_TMUX_PANE = re.compile(r"\bTMUX_PANE=(%\d+)")
RE_TMUX = re.compile(r"\bTMUX=(\S+)")
RE_ITERM = re.compile(r"\bITERM_SESSION_ID=(\S+)")
RE_TERM_SESSION = re.compile(r"\bTERM_SESSION_ID=(\S+)")
RE_TERM_PROGRAM = re.compile(r"\bTERM_PROGRAM=(\S+)")


def parse_processes(ps_output, self_pid=None):
    """Parse `ps -E -ww -o pid=,ppid=,tty=,command=` output into claude records.

    Returns a list of dicts; only processes carrying a valid CLAUDE_CODE_SESSION_ID
    are included. self_pid (if given) is skipped (the scanner itself).
    """
    procs = []
    for line in ps_output.splitlines():
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        pid_s, ppid_s, tty, command = parts
        try:
            pid, ppid = int(pid_s), int(ppid_s)
        except ValueError:
            continue
        if self_pid is not None and pid == self_pid:
            continue
        m = RE_SESSION.search(command)
        if not m:
            continue
        tmux_env = RE_TMUX.search(command)
        socket = None
        if tmux_env:
            socket = os.path.basename(tmux_env.group(1).split(",")[0])
        pane = RE_TMUX_PANE.search(command)
        iterm = RE_ITERM.search(command)
        term_s = RE_TERM_SESSION.search(command)
        term_p = RE_TERM_PROGRAM.search(command)
        # Note: a proc may have tmux_socket but no tmux_pane (partially-stripped
        # env); build_sessions guards on both before using them.
        procs.append(
            {
                "pid": pid,
                "ppid": ppid,
                "tty": None if tty == "??" else tty.replace("/dev/", ""),
                "session_id": m.group(1),
                "tmux_pane": pane.group(1) if pane else None,
                "tmux_socket": socket,
                "iterm_session_id": iterm.group(1) if iterm else None,
                "term_session_id": term_s.group(1) if term_s else None,
                "term_program": term_p.group(1) if term_p else None,
            }
        )
    return procs


def build_ppid_map(ps_output):
    """pid -> ppid for ALL processes in the ps output (not just claude-tagged).

    Ancestry walks must traverse non-claude processes (shells, node wrappers), so
    this covers every line, unlike parse_processes.
    """
    m = {}
    for line in ps_output.splitlines():
        parts = line.split(None, 2)
        if len(parts) < 2:
            continue
        try:
            pid, ppid = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        m[pid] = ppid
    return m


TMUX_FMT = (
    "#{pane_id}\t#{pane_tty}\t#{pane_pid}\t#{session_name}\t"
    "#{window_index}\t#{pane_active}"
)


def parse_tmux_panes(socket_name, list_panes_output):
    """Parse `tmux list-panes -a -F TMUX_FMT` output, keyed by (socket, pane_id)."""
    panes = {}
    for line in list_panes_output.splitlines():
        cols = line.split("\t")
        if len(cols) != 6:
            continue
        pane_id, tty, pane_pid, sess, win, active = cols
        try:
            pane_pid_int = int(pane_pid)
        except ValueError:
            pane_pid_int = None
        panes[(socket_name, pane_id)] = {
            "tty": tty.replace("/dev/", ""),
            "pane_pid": pane_pid_int,
            "tmux_session": sess,
            "tmux_window": win,
            "active": active == "1",
        }
    return panes


def resolve_roles(procs, ppid_map):
    """Assign each session a role (interactive|child) and its leader pid.

    Leader of a session = its topmost process (whose parent is not in the same
    session group). A session is `child` if its leader's ancestry reaches another
    claude session before the top; otherwise `interactive`.
    """
    by_session = {}
    for p in procs:
        by_session.setdefault(p["session_id"], []).append(p)
    session_of_pid = {p["pid"]: p["session_id"] for p in procs}

    roles = {}
    for sid, members in by_session.items():
        pids = {p["pid"] for p in members}
        leaders = [p for p in members if p["ppid"] not in pids]
        leader = min(leaders or members, key=lambda p: p["pid"])

        parent_session = None
        cur = leader["ppid"]
        seen = set()
        while cur and cur not in seen:
            seen.add(cur)
            anc_sid = session_of_pid.get(cur)
            if anc_sid and anc_sid != sid:
                parent_session = anc_sid
                break
            cur = ppid_map.get(cur)

        roles[sid] = {
            "leader_pid": leader["pid"],
            "role": "child" if parent_session else "interactive",
            "parent_session_id": parent_session,
        }
    return roles
