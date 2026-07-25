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
RE_CLAUDE_PID = re.compile(r"\bCLAUDE_PID=(\d+)")
RE_TMUX = re.compile(r"\bTMUX=(\S+)")
RE_ITERM = re.compile(r"\bITERM_SESSION_ID=(\S+)")
RE_TERM_SESSION = re.compile(r"\bTERM_SESSION_ID=(\S+)")
RE_TERM_PROGRAM = re.compile(r"\bTERM_PROGRAM=(\S+)")
# The claude TUI's own command (e.g. "claude", "claude -r", "/path/claude -r").
# Matches the claude program token; deliberately does NOT match node MCP-server
# children ("node .../xxx-mcp") or a ".claude" directory inside another path.
RE_CLAUDE = re.compile(r"(?:^|/)claude(?:\s|$)")


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
        claude_pid_m = RE_CLAUDE_PID.search(command)
        # Note: a proc may have tmux_socket but no tmux_pane (partially-stripped
        # env); build_sessions guards on both before using them.
        procs.append(
            {
                "pid": pid,
                "ppid": ppid,
                "tty": None if tty == "??" else tty.replace("/dev/", ""),
                "session_id": m.group(1),
                "claude_pid": int(claude_pid_m.group(1)) if claude_pid_m else None,
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


def build_process_table(ps_output):
    """pid -> {ppid, tty, command} for ALL processes in the ps output.

    Superset of build_ppid_map: ancestry walks, claude-TUI identification, and
    the TUI's tty are all read from this one table. tty normalized like
    parse_processes ("??" -> None, /dev/ stripped).
    """
    table = {}
    for line in ps_output.splitlines():
        parts = line.split(None, 3)
        if len(parts) < 2:
            continue
        try:
            pid, ppid = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        tty = parts[2] if len(parts) >= 3 else "??"
        command = parts[3] if len(parts) >= 4 else ""
        table[pid] = {
            "ppid": ppid,
            "tty": None if tty == "??" else tty.replace("/dev/", ""),
            "command": command,
        }
    return table


def nearest_claude_ancestor(pid, proc_table):
    """Nearest process at or above `pid` whose command is the claude TUI, else None.

    The claude TUI does not carry CLAUDE_CODE_SESSION_ID in its own start-time
    env (only its children do), so a session's tagged procs are its children; walk
    up to find the real TUI. Bounded by a seen-set against ppid cycles.
    """
    cur = pid
    seen = set()
    while cur is not None and cur not in seen:
        seen.add(cur)
        info = proc_table.get(cur)
        if info is None:
            return None
        if RE_CLAUDE.search(info["command"]):
            return cur
        cur = info["ppid"]
    return None


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


def tty_to_pane_index(tmux_index):
    """Invert {(socket, pane_id): {tty,...}} to {tty: (socket, pane_id)}.

    Used to place a session on the pane whose tty its claude TUI actually holds,
    rather than trusting a (possibly stale) TMUX_PANE env on a detached child.
    """
    inv = {}
    for (socket, pane_id), info in tmux_index.items():
        tty = info.get("tty")
        if tty:
            inv[tty] = (socket, pane_id)
    return inv


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


def _run(cmd):
    """Run a command, return stdout str or '' on any failure. Never raises."""
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=10, check=False
        ).stdout
    except Exception:
        return ""


def cwd_of(pid):
    """Working directory of pid via lsof (robust against spaces). None on failure."""
    out = _run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"])
    for line in out.splitlines():
        if line.startswith("n"):
            return line[1:]
    return None


def pane_foreground_ps(tty):
    """Best-effort `ps -t <tty> -o pid=,pgid=,stat=` output ('' on failure)."""
    if not tty:
        return ""
    return _run(["ps", "-t", tty, "-o", "pid=,pgid=,stat="])


def session_placement(members, rep, proc_table, tmux_index, tty_pane_idx):
    """Place a session on the pane its real claude TUI holds (claude-anchored).

    members: this session's tagged procs (parse_processes output).
    rep: the structural leader proc (resolve_roles' leader_pid), used only for
         iTerm/Apple-Terminal env-marker fallback.
    Returns {leader_pid, pane, host, tty, pane_live, tmux}.
    """
    # A session occupies a pane only where it has a LIVE presence: a tagged
    # member whose own tty is the TUI's tty. Detached stragglers (tty None)
    # that merely walk up to a reused TUI must not anchor the session to that
    # pane — otherwise a stale session ghosts onto the current occupant's pane
    # and collides on leader_pid. See spec addendum 2026-07-17.
    tui = None
    for m in members:
        cand = nearest_claude_ancestor(m["pid"], proc_table)
        if cand is None:
            continue
        cand_tty = proc_table.get(cand, {}).get("tty")
        if cand_tty and m.get("tty") == cand_tty:
            tui = cand
            break

    if tui is None:
        # Orphaned stragglers (detached children whose TUI has exited): do NOT
        # trust their stale TMUX_PANE env. Structural leader, no live pane.
        return {"leader_pid": rep["pid"], "pane": None, "host": None,
                "tty": rep.get("tty"), "pane_live": False, "tmux": None}

    tui_tty = proc_table[tui].get("tty")
    if tui_tty and tui_tty in tty_pane_idx:
        socket, pane_id = tty_pane_idx[tui_tty]
        pinfo = tmux_index.get((socket, pane_id))
        tmux_meta = ({"socket": socket, "session": pinfo["tmux_session"],
                      "window": pinfo["tmux_window"], "active": pinfo["active"]}
                     if pinfo else None)
        return {"leader_pid": tui, "pane": f"tmux:{socket}:{pane_id}", "host": "tmux",
                "tty": tui_tty, "pane_live": True, "tmux": tmux_meta}
    if rep.get("iterm_session_id"):
        return {"leader_pid": tui, "pane": f"iterm:{rep['iterm_session_id']}",
                "host": "iterm", "tty": tui_tty or rep.get("tty"),
                "pane_live": True, "tmux": None}
    if rep.get("term_session_id"):
        return {"leader_pid": tui, "pane": f"term:{rep['term_session_id']}",
                "host": "apple-terminal", "tty": tui_tty or rep.get("tty"),
                "pane_live": True, "tmux": None}
    return {"leader_pid": tui, "pane": None, "host": None,
            "tty": tui_tty or rep.get("tty"), "pane_live": True, "tmux": None}


def build_sessions(procs, ppid_map, tmux_index, cwd_fn=cwd_of, proc_table=None):
    """Assemble one record per session (see spec for schema).

    When proc_table is provided, placement is claude-anchored (the pane comes
    from the session's real claude TUI, not from a tagged child's env). When
    absent, the legacy env-based placement is used (SP1 behavior / unit fixtures).
    """
    roles = resolve_roles(procs, ppid_map)
    by_pid = {p["pid"]: p for p in procs}
    members_by_sid = {}
    for p in procs:
        members_by_sid.setdefault(p["session_id"], []).append(p)
    tty_pane_idx = tty_to_pane_index(tmux_index) if proc_table else {}

    sessions = []
    for sid, role in roles.items():
        rep = by_pid[role["leader_pid"]]
        if proc_table:
            place = session_placement(members_by_sid[sid], rep, proc_table,
                                      tmux_index, tty_pane_idx)
        else:
            place = _legacy_placement(rep, tmux_index)
        sessions.append(
            {
                "session_id": sid,
                "role": role["role"],
                "parent_session_id": role["parent_session_id"],
                "pane": place["pane"],
                "host": place["host"],
                "tty": place["tty"],
                "cwd": cwd_fn(place["leader_pid"]),
                "leader_pid": place["leader_pid"],
                "pane_live": place["pane_live"],
                "tmux": place["tmux"],
            }
        )
    sessions.sort(key=lambda s: (s["pane"] or "~", s["session_id"]))
    return sessions


def _legacy_placement(rep, tmux_index):
    """SP1 env-based placement (used when no proc_table is supplied)."""
    pane = host = tty = tmux_meta = None
    pane_live = True
    if rep.get("tmux_pane") and rep.get("tmux_socket"):
        socket = rep["tmux_socket"]
        pane = f"tmux:{socket}:{rep['tmux_pane']}"
        host = "tmux"
        pinfo = tmux_index.get((socket, rep["tmux_pane"]))
        if pinfo:
            tty = pinfo["tty"]
            tmux_meta = {"socket": socket, "session": pinfo["tmux_session"],
                         "window": pinfo["tmux_window"], "active": pinfo["active"]}
        else:
            tty = rep.get("tty")
            pane_live = False
    elif rep.get("iterm_session_id"):
        pane = f"iterm:{rep['iterm_session_id']}"
        host = "iterm"
        tty = rep.get("tty")
    elif rep.get("term_session_id"):
        pane = f"term:{rep['term_session_id']}"
        host = "apple-terminal"
        tty = rep.get("tty")
    else:
        tty = rep.get("tty")
    return {"leader_pid": rep["pid"], "pane": pane, "host": host, "tty": tty,
            "pane_live": pane_live, "tmux": tmux_meta}


def match_selector(s, args):
    """True if session record s matches the resolve selector in args.

    --session is role-agnostic (addresses a specific session). --pane / --tty
    return only the interactive session for that pane.
    """
    if args.session:
        return s["session_id"] == args.session
    if args.tty:
        want = args.tty.replace("/dev/", "")
        return s["tty"] == want and s["role"] == "interactive"
    if args.pane:
        if s["role"] != "interactive":
            return False
        p = args.pane
        if p.startswith(("tmux:", "iterm:", "term:")):
            return s["pane"] == p
        if p.startswith("%"):  # bare pane id: match across all sockets
            return s["host"] == "tmux" and bool(s["pane"]) and s["pane"].endswith(
                ":" + p
            )
        return False
    return False


def parse_pgid_stat(ps_output):
    """Parse `ps -t <tty> -o pid=,pgid=,stat=` into [(pid, pgid, stat), ...].

    Lines that don't start with two integers are skipped (best-effort).
    """
    rows = []
    for line in ps_output.splitlines():
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        try:
            pid, pgid = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        rows.append((pid, pgid, parts[2]))
    return rows


def foreground_pgids(ps_rows):
    """Process-group ids holding the tty foreground (ps stat contains '+')."""
    return {pgid for _pid, pgid, stat in ps_rows if "+" in stat}


def pick_foreground_winner(hits, ps_output):
    """Of several interactive sessions sharing one tty, return the one whose
    leader belongs to the pane's foreground process group; None if undeterminable.

    The pane's foreground process group is the pgid flagged '+' in `ps -t <tty>`.
    A session wins if its leader_pid's process group (looked up from the same ps
    rows) is that foreground group — note the leader is often a *member* of the
    group, not the group leader, so we map leader_pid -> pgid rather than assuming
    pgid == leader_pid. Returns None when zero or more than one hit matches (or the
    leader isn't on the tty), so the caller falls back to the ambiguity array —
    correctness is never sacrificed to force an answer.
    """
    rows = parse_pgid_stat(ps_output)
    fg = foreground_pgids(rows)
    pgid_of = {pid: pgid for pid, pgid, _stat in rows}
    matches = [h for h in hits if pgid_of.get(h.get("leader_pid")) in fg]
    return matches[0] if len(matches) == 1 else None


def list_tmux_sockets():
    """All tmux socket basenames for this user (plus the one from $TMUX)."""
    sockets = set()
    for path in glob.glob(f"/private/tmp/tmux-{os.getuid()}/*"):
        sockets.add(os.path.basename(path))
    env_tmux = os.environ.get("TMUX")
    if env_tmux:
        sockets.add(os.path.basename(env_tmux.split(",")[0]))
    return sorted(sockets)


def tmux_pane_index():
    """(socket, pane_id) -> pane meta across ALL tmux sockets. {} if none."""
    index = {}
    for socket in list_tmux_sockets():
        out = _run(["tmux", "-L", socket, "list-panes", "-a", "-F", TMUX_FMT])
        index.update(parse_tmux_panes(socket, out))
    return index


def gather_sessions():
    """Live scan -> assembled session records (the impure top-level)."""
    ps_output = _run(["ps", "-E", "-ww", "-o", "pid=,ppid=,tty=,command=", "-ax"])
    procs = parse_processes(ps_output, self_pid=os.getpid())
    ppid_map = build_ppid_map(ps_output)
    proc_table = build_process_table(ps_output)
    tmux_index = tmux_pane_index()
    return build_sessions(procs, ppid_map, tmux_index, proc_table=proc_table)


def cmd_list(_args):
    print(json.dumps(gather_sessions(), indent=2))


def cmd_resolve(args):
    sessions = gather_sessions()
    hits = [s for s in sessions if match_selector(s, args)]
    if not hits:
        print(json.dumps([], indent=2))
        sys.exit(1)
    if len(hits) > 1:
        # Multiple hits only arise from a --pane/--tty selector, so they all
        # share one tty; hits[0]'s tty is the pane's tty.
        winner = pick_foreground_winner(hits, pane_foreground_ps(hits[0].get("tty")))
        if winner is not None:
            hits = [winner]
    print(json.dumps(hits[0] if len(hits) == 1 else hits, indent=2))


def main():
    ap = argparse.ArgumentParser(description="Claude Code session locator.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list all live Claude sessions with pane/tty/cwd")
    rp = sub.add_parser("resolve", help="resolve a session by pane / tty / session id")
    g = rp.add_mutually_exclusive_group(required=True)
    g.add_argument("--pane", help="tmux:<socket>:%%N | %%N | iterm:<guid> | term:<guid>")
    g.add_argument("--tty", help="e.g. /dev/ttys016 or ttys016")
    g.add_argument("--session", help="Claude session id (uuid)")

    args = ap.parse_args()
    if args.cmd == "list":
        cmd_list(args)
    elif args.cmd == "resolve":
        cmd_resolve(args)


if __name__ == "__main__":
    main()
