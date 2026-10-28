import base64
import http.server
import json
import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from evolve_demo import gcp_secrets  # noqa: E402

SECRETS = {"tjf-key": "the-key\n", "tjf-token": "the-token"}


class FakeGCP(http.server.BaseHTTPRequestHandler):
    """Metadata server and Secret Manager in one."""

    def do_GET(self):
        if self.path.startswith("/meta/"):
            if self.headers.get("Metadata-Flavor") != "Google":
                return self.reply(403, "")
            if self.path.endswith("project/project-id"):
                return self.reply(200, "demo-project", raw=True)
            return self.reply(200, {"access_token": "tok"})
        if self.headers.get("Authorization") != "Bearer tok":
            return self.reply(401, {})
        name = self.path.split("/secrets/")[1].split("/")[0]
        if not self.path.startswith("/sm/projects/demo-project/") or name not in SECRETS:
            return self.reply(404, {})
        return self.reply(200, {"payload": {"data": base64.b64encode(SECRETS[name].encode()).decode()}})

    def reply(self, status, body, raw=False):
        self.send_response(status)
        self.end_headers()
        self.wfile.write(body.encode() if raw else json.dumps(body).encode())

    def log_message(self, *args):
        pass


class GCPSecretsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), FakeGCP)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{cls.server.server_port}"
        gcp_secrets.METADATA, gcp_secrets.SECRET_MANAGER = base + "/meta", base + "/sm"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self._env = dict(os.environ)
        os.environ.pop("GCP_PROJECT", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_loads_secrets_into_environment(self):
        names = gcp_secrets.load("MY_KEY=tjf-key, MY_TOKEN=tjf-token")
        self.assertEqual(names, ["MY_KEY", "MY_TOKEN"])
        self.assertEqual((os.environ["MY_KEY"], os.environ["MY_TOKEN"]), ("the-key", "the-token"))

    def test_missing_secret(self):
        with self.assertRaisesRegex(gcp_secrets.SecretError, "cannot read secret 'nope'"):
            gcp_secrets.load("X=nope")

    def test_bad_mapping_and_empty(self):
        with self.assertRaises(gcp_secrets.SecretError):
            gcp_secrets.load("JUSTANAME")
        self.assertEqual(gcp_secrets.load(""), [])


if __name__ == "__main__":
    unittest.main()
