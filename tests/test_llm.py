import http.server
import json
import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from evolve_demo import llm  # noqa: E402


class FakeServer(http.server.BaseHTTPRequestHandler):
    script = []      # list of (status, body, headers) answers, consumed in order
    seen = []        # (path, authorization header, json body) of each request

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeServer.seen.append((self.path, self.headers.get("Authorization"), body))
        status, payload, headers = FakeServer.script.pop(0)
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def do_GET(self):
        FakeServer.seen.append((self.path, self.headers.get("Authorization"), None))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({"data": [{"id": "gpt-6-luna"}, {"id": "another-model"}]}).encode())

    def log_message(self, *args):
        pass


def ok(text):
    return 200, {"choices": [{"message": {"content": text}, "finish_reason": "stop"}]}, {}


class LLMClientTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), FakeServer)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}/v1"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        FakeServer.script, FakeServer.seen = [], []
        self._env = dict(os.environ)
        for k in ("LLM_PROVIDER", "BTELLIGENT_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "LLM_API_KEY", "REWRITER_MODEL", "LLM_CACHE_DIR"):
            os.environ.pop(k, None)
        os.environ.update(LLM_API_BASE=self.base, BTELLIGENT_API_KEY="test-key")
        llm.load_dotenv = lambda *a, **k: None   # ignore a real .env during tests

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_request_format_and_answer(self):
        FakeServer.script = [ok("hello")]
        self.assertEqual(llm.complete("hi", system="be brief", temperature=0.2, reasoning_effort="low"), "hello")
        path, auth, body = FakeServer.seen[0]
        self.assertEqual(path, "/v1/chat/completions")
        self.assertEqual(auth, "Bearer test-key")
        self.assertEqual(body["model"], "gpt-6-luna")
        self.assertIs(body["stream"], False)
        self.assertEqual(body["messages"], [{"role": "system", "content": "be brief"}, {"role": "user", "content": "hi"}])
        self.assertEqual((body["temperature"], body["reasoning_effort"]), (0.2, "low"))

    def test_optional_parameters_are_omitted(self):
        FakeServer.script = [ok("x")]
        llm.complete("hi")
        self.assertNotIn("temperature", FakeServer.seen[0][2])
        self.assertNotIn("reasoning_effort", FakeServer.seen[0][2])

    def test_openrouter_defaults(self):
        os.environ.update(LLM_PROVIDER="openrouter", OPENROUTER_API_KEY="or-key")
        FakeServer.script = [ok("x")]
        llm.complete("hi")
        self.assertEqual(FakeServer.seen[0][1], "Bearer or-key")
        self.assertEqual(FakeServer.seen[0][2]["model"], "google/gemini-3.5-flash-lite")

    def test_retries_rate_limit_then_succeeds(self):
        FakeServer.script = [(429, {"error": "slow down"}, {"Retry-After": "0"}), (503, {"error": "busy"}, {"Retry-After": "0"}), ok("done")]
        self.assertEqual(llm.complete("hi"), "done")
        self.assertEqual(len(FakeServer.seen), 3)

    def test_gives_up_after_retries(self):
        FakeServer.script = [(500, {"error": "x"}, {"Retry-After": "0"})] * 3
        with self.assertRaisesRegex(llm.LLMError, "giving up after 3 attempts"):
            llm.complete("hi", retries=2)

    def test_client_error_is_not_retried(self):
        FakeServer.script = [(400, {"error": "bad model"}, {})]
        with self.assertRaisesRegex(llm.LLMError, "HTTP 400"):
            llm.complete("hi")
        self.assertEqual(len(FakeServer.seen), 1)

    def test_missing_key_and_unknown_provider(self):
        os.environ.pop("BTELLIGENT_API_KEY")
        with self.assertRaisesRegex(llm.LLMError, "BTELLIGENT_API_KEY"):
            llm.complete("hi")
        os.environ["LLM_PROVIDER"] = "nope"
        with self.assertRaisesRegex(llm.LLMError, "unknown LLM_PROVIDER"):
            llm.complete("hi")

    def test_empty_answer_is_an_error(self):
        FakeServer.script = [(200, {"choices": [{"message": {"content": None}, "finish_reason": "length"}]}, {})]
        with self.assertRaisesRegex(llm.LLMError, "length"):
            llm.complete("hi")

    def test_list_models(self):
        self.assertEqual(llm.list_models(), ["another-model", "gpt-6-luna"])
        self.assertEqual(FakeServer.seen[0][:2], ("/v1/models", "Bearer test-key"))

    def test_cache(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["LLM_CACHE_DIR"] = d
            FakeServer.script = [ok("first")]
            self.assertEqual(llm.complete("same prompt"), "first")
            self.assertEqual(llm.complete("same prompt"), "first")   # served from cache, no second request
            self.assertEqual(len(FakeServer.seen), 1)
            FakeServer.script = [ok("other")]
            self.assertEqual(llm.complete("different prompt"), "other")


if __name__ == "__main__":
    unittest.main()
