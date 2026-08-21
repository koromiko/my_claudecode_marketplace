import os, sys, tempfile, unittest
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


if __name__ == "__main__":
    unittest.main()
