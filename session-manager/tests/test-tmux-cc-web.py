import os, tempfile, unittest, shlex
import json
import threading
import urllib.request
import urllib.error
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

    def test_fork_command(self):
        self.assertEqual(
            web.build_fork_command("/tmp/proj", "abc-123"),
            "cd /tmp/proj && claude -r abc-123 --fork-session")


class ParseDays(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(web.parse_days("7"), 7)

    def test_absent(self):
        self.assertIsNone(web.parse_days(None))

    def test_non_int(self):
        self.assertIsNone(web.parse_days("abc"))

    def test_negative_clamped_to_zero(self):
        self.assertEqual(web.parse_days("-5"), 0)

    def test_huge_clamped(self):
        self.assertEqual(web.parse_days("999999999999"), 100000)


class BuildAttachCmd(unittest.TestCase):
    def test_no_days_leaves_command_unchanged(self):
        self.assertEqual(
            web.build_attach_cmd(["tmux-cc-attach", "--json"], None),
            ["tmux-cc-attach", "--json"])

    def test_days_appends_since(self):
        self.assertEqual(
            web.build_attach_cmd(["a", "--json"], 7),
            ["a", "--json", "--since", "7"])

    def test_does_not_mutate_input(self):
        base = ["a", "--json"]
        web.build_attach_cmd(base, 7)
        self.assertEqual(base, ["a", "--json"])


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

    def test_counts_only_human_turns(self):
        p = os.path.join(self.d, "c.jsonl")
        _write(p, ['{"type":"user","message":{"content":"Real human message"}}',
                   '{"type":"user","message":{"content":"<command-name>/clear</command-name>"}}',
                   '{"type":"user","message":{"content":"<teammate-message>hi</teammate-message>"}}',
                   '{"type":"assistant","message":{"content":"ok"}}'])
        self.assertEqual(web.count_turns(p), 1)

    def test_counts_list_form_human_message(self):
        p = os.path.join(self.d, "d.jsonl")
        _write(p, ['{"type":"user","message":{"content":[{"type":"text","text":"hi"}]}}'])
        self.assertEqual(web.count_turns(p), 1)

    def test_skips_non_dict_json_line(self):
        p = os.path.join(self.d, "e.jsonl")
        _write(p, ['"hello"',
                   '{"type":"user","message":{"content":"real"}}'])
        self.assertEqual(web.count_turns(p), 1)


class LastActivity(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def test_returns_latest_timestamp_epoch(self):
        p = os.path.join(self.d, "a.jsonl")
        _write(p, ['{"type":"user","timestamp":"1970-01-01T00:00:10Z"}',
                   '{"type":"assistant","timestamp":"1970-01-01T00:00:42Z"}',
                   '{"type":"summary"}'])
        self.assertEqual(web.last_activity(p), 42.0)

    def test_takes_max_even_if_out_of_order(self):
        p = os.path.join(self.d, "b.jsonl")
        _write(p, ['{"type":"user","timestamp":"1970-01-01T00:01:00Z"}',
                   '{"type":"assistant","timestamp":"1970-01-01T00:00:30Z"}'])
        self.assertEqual(web.last_activity(p), 60.0)

    def test_none_when_no_timestamps(self):
        p = os.path.join(self.d, "c.jsonl")
        _write(p, ['{"type":"user","message":{"content":"hi"}}'])
        self.assertIsNone(web.last_activity(p))

    def test_missing_file(self):
        self.assertIsNone(web.last_activity(os.path.join(self.d, "nope.jsonl")))


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

    def test_sorts_by_last_activity_over_ts_end(self):
        # last_activity wins over ts_end for ordering.
        sessions = [
            {"session_id": "a", "project": "/p1", "ts_end": 100, "last_activity": 5},
            {"session_id": "b", "project": "/p2", "ts_end": 1, "last_activity": 99},
        ]
        groups = web.group_and_sort(sessions)
        self.assertEqual([g["project"] for g in groups], ["/p2", "/p1"])


class DedupeLiveByPid(unittest.TestCase):
    def test_keeps_most_recent_per_pid(self):
        sessions = [
            {"session_id": "old", "status": "live", "pid": "100", "last_activity": 10},
            {"session_id": "new", "status": "live", "pid": "100", "last_activity": 50},
            {"session_id": "solo", "status": "live", "pid": "200", "last_activity": 5},
        ]
        out = web.dedupe_live_by_pid(sessions)
        ids = {s["session_id"] for s in out}
        self.assertEqual(ids, {"new", "solo"})

    def test_leaves_ended_and_pidless_untouched(self):
        sessions = [
            {"session_id": "e1", "status": "ended", "ts_end": 1},
            {"session_id": "e2", "status": "ended", "ts_end": 2},
            {"session_id": "lv", "status": "live", "last_activity": 3},  # no pid
        ]
        out = web.dedupe_live_by_pid(sessions)
        self.assertEqual(len(out), 3)


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
        # No timestamp in the transcript -> last_activity falls back to ts_end.
        self._transcript("s1", ['{"type":"user","message":{"content":"Hello"}}'])
        cache = {}
        s = web.enrich({"session_id": "s1", "cwd": "/tmp/x", "project": "/p", "ts_end": 1},
                       self.root, cache)
        self.assertEqual(s["title"], "Hello")
        self.assertEqual(s["turns"], 1)
        self.assertEqual(s["copy_command"], "cd /tmp/x && claude -r s1")
        self.assertEqual(s["last_activity"], 1)
        self.assertEqual(len(cache), 1)

    def test_enrich_reads_last_activity(self):
        self._transcript("sa", [
            '{"type":"user","message":{"content":"Hi"},"timestamp":"1970-01-01T00:00:10Z"}',
            '{"type":"assistant","message":{"content":"Yo"},"timestamp":"1970-01-01T00:00:20Z"}'])
        s = web.enrich({"session_id": "sa", "cwd": "/tmp/x", "project": "/p", "ts_end": 999},
                       self.root, {})
        self.assertEqual(s["last_activity"], 20.0)

    def test_enrich_uses_cache(self):
        self._transcript("s2", ['{"type":"user","message":{"content":"First"}}'])
        cache = {}
        web.enrich({"session_id": "s2", "cwd": "/tmp/x", "project": "/p", "ts_end": 1},
                   self.root, cache)
        # Pre-seed the cache entry with different values; enrich must reuse them.
        key = list(cache.keys())[0]
        cache[key] = ("CACHED", 99, 12345)
        s = web.enrich({"session_id": "s2", "cwd": "/tmp/x", "project": "/p", "ts_end": 1},
                       self.root, cache)
        self.assertEqual(s["title"], "CACHED")
        self.assertEqual(s["turns"], 99)
        self.assertEqual(s["last_activity"], 12345)

    def test_enrich_sets_fork_command(self):
        self._transcript("sf", ['{"type":"user","message":{"content":"Hi"}}'])
        s = web.enrich({"session_id": "sf", "cwd": "/tmp/x", "project": "/p", "ts_end": 1},
                       self.root, {})
        self.assertEqual(s["fork_command"], "cd /tmp/x && claude -r sf --fork-session")

    def test_enrich_passes_status_and_fork_for_live(self):
        # A live session carries status but no ts_end/reason; enrich keeps status
        # and derives last_activity from the transcript.
        self._transcript("lv", [
            '{"type":"user","message":{"content":"Working"},"timestamp":"1970-01-01T00:00:30Z"}'])
        s = web.enrich({"session_id": "lv", "cwd": "/tmp/x", "project": "/p", "status": "live"},
                       self.root, {})
        self.assertEqual(s["status"], "live")
        self.assertEqual(s["fork_command"], "cd /tmp/x && claude -r lv --fork-session")
        self.assertEqual(s["last_activity"], 30.0)

    def test_enrich_missing_transcript_falls_back(self):
        cache = {}
        s = web.enrich({"session_id": "ghost", "cwd": "/tmp/foo/bar", "project": "/p", "ts_end": 1},
                       self.root, cache)
        self.assertEqual(s["title"], "bar")
        self.assertIsNone(s["turns"])
        self.assertEqual(s["last_activity"], 1)


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

    def test_load_passes_since_when_days_given(self):
        argfile = os.path.join(self.root, "args.txt")
        stub = os.path.join(self.root, "stub.sh")
        _write(stub, ["#!/bin/bash",
                      'printf "%s" "$*" > ' + shlex.quote(argfile),
                      'printf "[]"'])
        os.chmod(stub, 0o755)
        web.load_sessions([stub, "--json"], self.root, {}, days=7)
        with open(argfile) as fh:
            self.assertIn("--since 7", fh.read())


class LiveServer(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        d = os.path.join(self.root, "-proj")
        os.makedirs(d, exist_ok=True)
        _write(os.path.join(d, "s1.jsonl"),
               ['{"type":"user","message":{"content":"My session title"}}'])
        _write(os.path.join(d, "s2.jsonl"),
               ['{"type":"user","message":{"content":"Live one"},"timestamp":"1970-01-01T00:00:30Z"}'])

    def _serve(self, attach_cmd):
        srv = web.WebServer(("127.0.0.1", 0), attach_cmd, self.root)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        return srv, srv.server_address[1]

    def test_api_and_index(self):
        payload = ('[{"session_id":"s1","cwd":"/tmp/a","project":"/pa","ts_end":5,'
                   '"reason":"other","status":"ended"},'
                   '{"session_id":"s2","cwd":"/tmp/b","project":"/pb","status":"live"}]')
        srv, port = self._serve(["bash", "-c", "printf '%s' " + shlex.quote(payload)])
        try:
            body = urllib.request.urlopen("http://127.0.0.1:%d/api/sessions?days=7" % port, timeout=5).read()
            groups = json.loads(body)
            flat = {s["session_id"]: s for g in groups for s in g["sessions"]}
            self.assertEqual(flat["s1"]["title"], "My session title")
            self.assertEqual(flat["s1"]["status"], "ended")
            self.assertEqual(flat["s2"]["status"], "live")
            self.assertEqual(flat["s2"]["fork_command"], "cd /tmp/b && claude -r s2 --fork-session")
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


if __name__ == "__main__":
    unittest.main()
