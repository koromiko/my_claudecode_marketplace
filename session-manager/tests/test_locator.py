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


if __name__ == "__main__":
    unittest.main()
