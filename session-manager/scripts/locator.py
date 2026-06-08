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
