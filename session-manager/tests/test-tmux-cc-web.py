import os, sys, tempfile, unittest, shlex
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
        self._transcript("s1", ['{"type":"user","message":{"content":"Hello"}}'])
        cache = {}
        s = web.enrich({"session_id": "s1", "cwd": "/tmp/x", "project": "/p", "ts_end": 1},
                       self.root, cache)
        self.assertEqual(s["title"], "Hello")
        self.assertEqual(s["turns"], 1)
        self.assertEqual(s["copy_command"], "cd /tmp/x && claude -r s1")
        self.assertEqual(len(cache), 1)

    def test_enrich_uses_cache(self):
        self._transcript("s2", ['{"type":"user","message":{"content":"First"}}'])
        cache = {}
        web.enrich({"session_id": "s2", "cwd": "/tmp/x", "project": "/p", "ts_end": 1},
                   self.root, cache)
        # Pre-seed the cache entry with a different title; enrich must reuse it.
        key = list(cache.keys())[0]
        cache[key] = ("CACHED", 99)
        s = web.enrich({"session_id": "s2", "cwd": "/tmp/x", "project": "/p", "ts_end": 1},
                       self.root, cache)
        self.assertEqual(s["title"], "CACHED")
        self.assertEqual(s["turns"], 99)

    def test_enrich_missing_transcript_falls_back(self):
        cache = {}
        s = web.enrich({"session_id": "ghost", "cwd": "/tmp/foo/bar", "project": "/p", "ts_end": 1},
                       self.root, cache)
        self.assertEqual(s["title"], "bar")
        self.assertIsNone(s["turns"])


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


if __name__ == "__main__":
    unittest.main()
