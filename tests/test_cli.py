import contextlib
import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from evolve_demo import cli, llm  # noqa: E402


def run(*argv):
    """Run the CLI in-process; returns (exit code, parsed JSON from stdout)."""
    out = io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        try:
            cli.main(list(argv))
        except SystemExit as e:
            code = e.code
    return code, json.loads(out.getvalue())


class CLITest(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)
        llm.load_dotenv = lambda *a, **k: None   # ignore a real .env during tests

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_argument_errors_are_json_input_errors(self):
        code, out = run("run", "evolve/initial_prompt.txt", "--split", "heldout")
        self.assertEqual((code, out["kind"]), (1, "input"))
        code, out = run()
        self.assertEqual((code, out["kind"]), (1, "input"))

    def test_unreadable_prompt_file(self):
        os.environ["BTELLIGENT_API_KEY"] = "x"
        code, out = run("run", "does/not/exist.txt")
        self.assertEqual((code, out["kind"]), (1, "input"))

    def test_missing_key_is_a_setup_error(self):
        for k in ("LLM_API_KEY", "BTELLIGENT_API_KEY", "LLM_PROVIDER"):
            os.environ.pop(k, None)
        code, out = run("baseline", "--limit", "1")
        self.assertEqual((code, out["kind"]), (2, "setup"))
        self.assertIn("BTELLIGENT_API_KEY", out["error"])

    def test_unreachable_opensearch_is_a_setup_error(self):
        os.environ["BTELLIGENT_API_KEY"] = "x"
        url = cli.osr.URL
        cli.osr.URL = "http://127.0.0.1:9"   # nothing listens on the discard port
        try:
            code, out = run("baseline", "--limit", "1")
        finally:
            cli.osr.URL = url
        self.assertEqual((code, out["kind"]), (2, "setup"))
        self.assertIn("docker compose", out["error"])


if __name__ == "__main__":
    unittest.main()
