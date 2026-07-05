#!/usr/bin/env python3
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import locator  # noqa: E402

UUID_A = "83ae8ca6-0000-0000-0000-000000000001"
UUID_B = "c392555a-0000-0000-0000-000000000002"
UUID_C = "52e3b60e-0000-0000-0000-000000000003"
UUID_D = "0f2cf83f-0000-0000-0000-000000000004"

DEFAULT_SOCK = "/private/tmp/tmux-501/default,2611,7"


def pline(pid, ppid, tty, **env):
    """Build one `ps -E` output line: pid ppid tty <command + environ>."""
    env_str = " ".join(f"{k}={v}" for k, v in env.items())
    return f"{pid} {ppid} {tty} node /usr/bin/claude {env_str}"


class TestParseProcesses(unittest.TestCase):
    def test_extracts_markers_and_normalizes_tty(self):
        out = pline(
            2001, 1900, "??",
            CLAUDE_CODE_SESSION_ID=UUID_A,
            TMUX_PANE="%86",
            TMUX=DEFAULT_SOCK,
            ITERM_SESSION_ID="w0t6p0:GUID",
            TERM_SESSION_ID="w0t6p0:GUID",
            TERM_PROGRAM="tmux",
        )
        procs = locator.parse_processes(out)
        self.assertEqual(len(procs), 1)
        p = procs[0]
        self.assertEqual(p["pid"], 2001)
        self.assertEqual(p["ppid"], 1900)
        self.assertIsNone(p["tty"])  # "??" -> None
        self.assertEqual(p["session_id"], UUID_A)
        self.assertEqual(p["tmux_pane"], "%86")
        self.assertEqual(p["tmux_socket"], "default")  # basename of socket path
        self.assertEqual(p["iterm_session_id"], "w0t6p0:GUID")
        self.assertEqual(p["term_session_id"], "w0t6p0:GUID")
        self.assertEqual(p["term_program"], "tmux")

    def test_excludes_scanner_noise_without_real_uuid(self):
        # A grep/ps line whose command contains the literal regex text but no
        # real uuid must NOT be parsed as a session.
        noise = ("9999 8888 ttys999 grep -E "
                 "CLAUDE_CODE_SESSION_ID=[0-9a-fA-F]{8} TMUX_PANE=[^ ]+")
        real = pline(2001, 1900, "ttys016",
                     CLAUDE_CODE_SESSION_ID=UUID_A, TMUX_PANE="%86", TMUX=DEFAULT_SOCK)
        procs = locator.parse_processes(noise + "\n" + real)
        self.assertEqual([p["session_id"] for p in procs], [UUID_A])

    def test_excludes_self_pid(self):
        out = pline(4242, 1, "ttys016", CLAUDE_CODE_SESSION_ID=UUID_A)
        self.assertEqual(locator.parse_processes(out, self_pid=4242), [])


class TestBuildPpidMap(unittest.TestCase):
    def test_maps_all_processes_not_just_claude(self):
        out = "\n".join([
            "1900 1800 ttys016 -zsh",                 # plain shell, no session
            pline(2001, 1900, "??", CLAUDE_CODE_SESSION_ID=UUID_A),
            "garbage line",                             # ignored
        ])
        m = locator.build_ppid_map(out)
        self.assertEqual(m[1900], 1800)   # non-claude proc present (ancestry needs it)
        self.assertEqual(m[2001], 1900)
        self.assertNotIn("garbage", m)


class TestBuildProcessTable(unittest.TestCase):
    def test_captures_all_procs_with_tty_and_command(self):
        out = "\n".join([
            "79481 79313 ttys008 claude",
            "79770 79492 ttys008 node /npx/abc/.bin/context7-mcp",
            "94268 94266 ?? node /npx/def/.bin/some-mcp",
            "1900 1800 ttys016 -zsh",
            "garbage line",                       # non-numeric pid -> skipped
        ])
        t = locator.build_process_table(out)
        self.assertEqual(t[79481], {"ppid": 79313, "tty": "ttys008", "command": "claude"})
        self.assertEqual(t[79770]["command"], "node /npx/abc/.bin/context7-mcp")
        self.assertIsNone(t[94268]["tty"])        # "??" -> None
        self.assertEqual(t[1900]["ppid"], 1800)   # non-claude proc present for ancestry
        self.assertNotIn("garbage", t)


class TestParseTmuxPanes(unittest.TestCase):
    SAMPLE = "%86\t/dev/ttys016\t1900\twork\t3\t1\n%0\t/dev/ttys020\t1700\tmisc\t0\t0"

    def test_parses_and_keys_by_socket_and_pane(self):
        idx = locator.parse_tmux_panes("default", self.SAMPLE)
        self.assertEqual(
            idx[("default", "%86")],
            {"tty": "ttys016", "pane_pid": 1900, "tmux_session": "work",
             "tmux_window": "3", "active": True},
        )
        self.assertFalse(idx[("default", "%0")]["active"])

    def test_same_pane_id_on_two_sockets_is_distinct(self):
        # The multi-socket fix: %0 on two sockets must not collide.
        a = locator.parse_tmux_panes("default", "%0\t/dev/ttys020\t1\ts\t0\t1")
        b = locator.parse_tmux_panes("sm_e2e", "%0\t/dev/ttys099\t2\ts\t0\t1")
        merged = {**a, **b}
        self.assertEqual(merged[("default", "%0")]["tty"], "ttys020")
        self.assertEqual(merged[("sm_e2e", "%0")]["tty"], "ttys099")
        self.assertEqual(len(merged), 2)


class TestResolveRoles(unittest.TestCase):
    def test_child_session_demoted_to_child_of_interactive(self):
        # Case (b): two sessions in one pane. B (pid 2002) is spawned by A (pid 2001).
        procs = [
            {"pid": 2001, "ppid": 1900, "session_id": UUID_A, "tmux_pane": "%86"},
            {"pid": 2002, "ppid": 2001, "session_id": UUID_B, "tmux_pane": "%86"},
        ]
        ppid_map = {2001: 1900, 2002: 2001, 1900: 1800}
        roles = locator.resolve_roles(procs, ppid_map)
        self.assertEqual(roles[UUID_A]["role"], "interactive")
        self.assertIsNone(roles[UUID_A]["parent_session_id"])
        self.assertEqual(roles[UUID_A]["leader_pid"], 2001)
        self.assertEqual(roles[UUID_B]["role"], "child")
        self.assertEqual(roles[UUID_B]["parent_session_id"], UUID_A)
        self.assertEqual(roles[UUID_B]["leader_pid"], 2002)

    def test_one_session_two_panes_leader_is_topmost(self):
        # Case (a): session A appears in procs tagged %5 (leader) and %6 (re-parented
        # child member of the SAME session). Leader is the topmost member.
        procs = [
            {"pid": 1001, "ppid": 900, "session_id": UUID_C, "tmux_pane": "%5"},
            {"pid": 1002, "ppid": 1001, "session_id": UUID_C, "tmux_pane": "%6"},
        ]
        ppid_map = {1001: 900, 1002: 1001, 900: 800}
        roles = locator.resolve_roles(procs, ppid_map)
        self.assertEqual(roles[UUID_C]["leader_pid"], 1001)  # the %5 one
        self.assertEqual(roles[UUID_C]["role"], "interactive")
        self.assertIsNone(roles[UUID_C]["parent_session_id"])


class TestBuildSessions(unittest.TestCase):
    def _full_proc(self, pid, ppid, sid, pane, socket="default", tty=None,
                   iterm=None, term=None):
        return {"pid": pid, "ppid": ppid, "session_id": sid, "tmux_pane": pane,
                "tmux_socket": socket if pane else None, "tty": tty,
                "iterm_session_id": iterm, "term_session_id": term}

    def test_tmux_record_enriched_and_pane_live(self):
        procs = [self._full_proc(2001, 1900, UUID_A, "%86")]
        ppid_map = {2001: 1900, 1900: 1800}
        tmux_index = {("default", "%86"): {
            "tty": "ttys016", "pane_pid": 1900, "tmux_session": "work",
            "tmux_window": "3", "active": True}}
        out = locator.build_sessions(procs, ppid_map, tmux_index,
                                     cwd_fn=lambda pid: "/tmp/x")
        self.assertEqual(len(out), 1)
        r = out[0]
        self.assertEqual(r["pane"], "tmux:default:%86")
        self.assertEqual(r["host"], "tmux")
        self.assertEqual(r["tty"], "ttys016")       # authoritative from tmux
        self.assertEqual(r["cwd"], "/tmp/x")
        self.assertTrue(r["pane_live"])
        self.assertEqual(r["tmux"]["session"], "work")
        self.assertEqual(r["role"], "interactive")

    def test_detached_straggler_flagged_not_live(self):
        procs = [self._full_proc(2001, 1900, UUID_A, "%99", tty="ttys016")]
        out = locator.build_sessions(procs, {2001: 1900}, {},  # empty index
                                     cwd_fn=lambda pid: None)
        r = out[0]
        self.assertEqual(r["pane"], "tmux:default:%99")
        self.assertFalse(r["pane_live"])     # pane not in index
        self.assertEqual(r["tty"], "ttys016")  # falls back to process tty

    def test_iterm_host_when_no_tmux(self):
        procs = [self._full_proc(3001, 2900, UUID_A, None, tty="ttys030",
                                 iterm="w0t6p0:GUID")]
        out = locator.build_sessions(procs, {3001: 2900}, {},
                                     cwd_fn=lambda pid: "/tmp/y")
        r = out[0]
        self.assertEqual(r["pane"], "iterm:w0t6p0:GUID")
        self.assertEqual(r["host"], "iterm")
        self.assertTrue(r["pane_live"])  # non-tmux -> always live (leader alive)

    def test_record_has_exactly_the_schema_keys(self):
        # Guards the contract SP2-SP5 join against: the record shape must not drift.
        procs = [self._full_proc(2001, 1900, UUID_A, "%86")]
        out = locator.build_sessions(procs, {2001: 1900}, {}, cwd_fn=lambda pid: None)
        self.assertEqual(
            set(out[0].keys()),
            {"session_id", "role", "parent_session_id", "pane", "host", "tty",
             "cwd", "leader_pid", "pane_live", "tmux"},
        )

    def test_apple_terminal_host(self):
        procs = [self._full_proc(3001, 2900, UUID_A, None, tty="ttys040",
                                 term="w0t0p0:TGUID")]
        out = locator.build_sessions(procs, {3001: 2900}, {},
                                     cwd_fn=lambda pid: "/tmp/z")
        r = out[0]
        self.assertEqual(r["pane"], "term:w0t0p0:TGUID")
        self.assertEqual(r["host"], "apple-terminal")
        self.assertEqual(r["tty"], "ttys040")

    def test_parent_and_child_both_get_records_in_one_pane(self):
        # A parent (A) and the child (B) it spawned, both in pane %86.
        procs = [
            self._full_proc(2001, 1900, UUID_A, "%86"),
            self._full_proc(2002, 2001, UUID_B, "%86"),
        ]
        ppid_map = {2001: 1900, 2002: 2001, 1900: 1800}
        out = locator.build_sessions(procs, ppid_map, {}, cwd_fn=lambda pid: None)
        by_sid = {r["session_id"]: r for r in out}
        self.assertEqual(by_sid[UUID_A]["role"], "interactive")
        self.assertIsNone(by_sid[UUID_A]["parent_session_id"])
        self.assertEqual(by_sid[UUID_B]["role"], "child")
        self.assertEqual(by_sid[UUID_B]["parent_session_id"], UUID_A)

    def test_sessions_sorted_by_pane_with_none_last(self):
        procs = [
            self._full_proc(3001, 2900, UUID_D, None),               # no host -> pane None
            self._full_proc(2001, 1900, UUID_A, "%86"),              # tmux:default:%86
            self._full_proc(2501, 1900, UUID_C, "%10", socket="alt"),  # tmux:alt:%10
        ]
        ppid_map = {2001: 1900, 2501: 1900, 3001: 2900, 1900: 1800, 2900: 2800}
        out = locator.build_sessions(procs, ppid_map, {}, cwd_fn=lambda pid: None)
        self.assertEqual(
            [r["pane"] for r in out],
            ["tmux:alt:%10", "tmux:default:%86", None],  # None sorts last via "~"
        )


class TestSelector(unittest.TestCase):
    SESSIONS = [
        {"session_id": UUID_A, "role": "interactive", "pane": "tmux:default:%86",
         "host": "tmux", "tty": "ttys016"},
        {"session_id": UUID_B, "role": "child", "pane": "tmux:default:%86",
         "host": "tmux", "tty": "ttys016"},
        {"session_id": UUID_D, "role": "interactive", "pane": "iterm:w0t6p0:GUID",
         "host": "iterm", "tty": "ttys030"},
    ]

    def _filter(self, **kw):
        ns = locator.argparse.Namespace(pane=None, tty=None, session=None)
        for k, v in kw.items():
            setattr(ns, k, v)
        return [s for s in self.SESSIONS if locator.match_selector(s, ns)]

    def test_pane_full_address_returns_interactive_only(self):
        hits = self._filter(pane="tmux:default:%86")
        self.assertEqual([h["session_id"] for h in hits], [UUID_A])

    def test_pane_bare_id_matches_across_sockets_interactive_only(self):
        hits = self._filter(pane="%86")
        self.assertEqual([h["session_id"] for h in hits], [UUID_A])

    def test_tty_returns_interactive_only(self):
        hits = self._filter(tty="/dev/ttys016")  # accepts /dev/ prefix too
        self.assertEqual([h["session_id"] for h in hits], [UUID_A])

    def test_session_selector_returns_child_too(self):
        hits = self._filter(session=UUID_B)  # addresses a specific session, role-agnostic
        self.assertEqual([h["session_id"] for h in hits], [UUID_B])


class TestForegroundTiebreak(unittest.TestCase):
    # `ps -t <tty> -o pid=,pgid=,stat=` rows. The "+" in stat marks a process in
    # the tty's FOREGROUND process group. A session wins if its leader's pgid
    # (looked up from these rows) is a foreground pgid. In THIS fixture the leaders
    # happen to be their own group leaders (pgid == pid); the
    # test_picks_leader_that_is_a_member_of_foreground_group case covers the
    # general case where the leader is only a member of the foreground group.
    PS_B_FOREGROUND = (
        "2001 2001 S\n"     # session A leader: running, background
        "2002 2002 S+\n"    # session B leader: foreground (+)
        "2050 2002 S+\n"    # a child of B, also foreground group
    )

    def test_parse_pgid_stat(self):
        rows = locator.parse_pgid_stat(self.PS_B_FOREGROUND)
        self.assertEqual(rows[0], (2001, 2001, "S"))
        self.assertEqual(rows[1], (2002, 2002, "S+"))
        self.assertEqual(len(rows), 3)

    def test_parse_pgid_stat_ignores_garbage(self):
        rows = locator.parse_pgid_stat("not a row\n\n1 2 R+\n")
        self.assertEqual(rows, [(1, 2, "R+")])

    def test_foreground_pgids(self):
        rows = locator.parse_pgid_stat(self.PS_B_FOREGROUND)
        self.assertEqual(locator.foreground_pgids(rows), {2002})

    def test_picks_the_foreground_session(self):
        hits = [
            {"session_id": UUID_A, "leader_pid": 2001, "tty": "ttys016"},
            {"session_id": UUID_B, "leader_pid": 2002, "tty": "ttys016"},
        ]
        winner = locator.pick_foreground_winner(hits, self.PS_B_FOREGROUND)
        self.assertIsNotNone(winner)
        self.assertEqual(winner["session_id"], UUID_B)

    def test_returns_none_when_no_hit_in_foreground(self):
        # Foreground pgid 9999 matches neither leader -> undeterminable -> None.
        hits = [
            {"session_id": UUID_A, "leader_pid": 2001, "tty": "ttys016"},
            {"session_id": UUID_B, "leader_pid": 2002, "tty": "ttys016"},
        ]
        self.assertIsNone(locator.pick_foreground_winner(hits, "9999 9999 S+\n"))

    def test_returns_none_when_two_hits_in_foreground(self):
        # Ambiguous: both leaders appear as foreground groups -> None (array fallback).
        hits = [
            {"session_id": UUID_A, "leader_pid": 2001, "tty": "ttys016"},
            {"session_id": UUID_B, "leader_pid": 2002, "tty": "ttys016"},
        ]
        ps = "2001 2001 S+\n2002 2002 S+\n"
        self.assertIsNone(locator.pick_foreground_winner(hits, ps))

    def test_returns_none_on_empty_ps(self):
        hits = [{"session_id": UUID_A, "leader_pid": 2001, "tty": "ttys016"}]
        self.assertIsNone(locator.pick_foreground_winner(hits, ""))

    def test_picks_leader_that_is_a_member_of_foreground_group(self):
        # Real-world (spike): the claude leader is a *member* of the foreground
        # process group (pid != pgid). Leader 14830 is in foreground pgid 14632;
        # the other session's leader (53492) is not on the tty -> single winner.
        ps = "14526 14526 Ss\n14632 14632 S+\n14830 14632 S+\n"
        hits = [
            {"session_id": UUID_A, "leader_pid": 14830, "tty": "ttys016"},
            {"session_id": UUID_B, "leader_pid": 53492, "tty": "ttys016"},
        ]
        winner = locator.pick_foreground_winner(hits, ps)
        self.assertIsNotNone(winner)
        self.assertEqual(winner["session_id"], UUID_A)


class TestResolveTiebreakWiring(unittest.TestCase):
    """cmd_resolve must collapse a two-interactive-session pane to the foreground
    one, and keep returning the array when the foreground is undeterminable."""

    def setUp(self):
        self._gather = locator.gather_sessions
        self._ps = locator.pane_foreground_ps
        self.two = [
            {"session_id": UUID_A, "role": "interactive", "pane": "tmux:default:%86",
             "host": "tmux", "tty": "ttys016", "leader_pid": 2001},
            {"session_id": UUID_B, "role": "interactive", "pane": "tmux:default:%86",
             "host": "tmux", "tty": "ttys016", "leader_pid": 2002},
        ]
        locator.gather_sessions = lambda: self.two

    def tearDown(self):
        locator.gather_sessions = self._gather
        locator.pane_foreground_ps = self._ps

    def _resolve_pane(self):
        import contextlib
        import io
        ns = locator.argparse.Namespace(pane="tmux:default:%86", tty=None, session=None)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            locator.cmd_resolve(ns)
        return json.loads(buf.getvalue())

    def test_breaks_tie_via_foreground(self):
        locator.pane_foreground_ps = lambda tty: "2001 2001 S\n2002 2002 S+\n"
        out = self._resolve_pane()
        self.assertIsInstance(out, dict)
        self.assertEqual(out["session_id"], UUID_B)

    def test_returns_array_when_undeterminable(self):
        locator.pane_foreground_ps = lambda tty: ""   # no foreground signal
        out = self._resolve_pane()
        self.assertIsInstance(out, list)
        self.assertEqual({r["session_id"] for r in out}, {UUID_A, UUID_B})


if __name__ == "__main__":
    unittest.main()
