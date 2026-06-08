#!/usr/bin/env python3
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


if __name__ == "__main__":
    unittest.main()
