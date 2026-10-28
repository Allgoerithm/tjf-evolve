import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
try:
    from fastapi.testclient import TestClient
    from evolve_demo import leaderboard
except ImportError:   # server extra not installed
    leaderboard = None

PROMPT = "Rewrite {profile} as a query."


def fake_evaluate(prompt, split):
    score = 0.3 if "better" in prompt else 0.1
    return {"combined_score": score if split == "heldout" else score + 0.05, "n_profiles": 2, "n_errors": 0,
            "n_zero": 1, "per_profile": []}


@unittest.skipIf(leaderboard is None, "install with: uv sync --extra server")
class LeaderboardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        leaderboard.DB_PATH = os.path.join(self.tmp.name, "lb.sqlite3")
        leaderboard.MIN_SECONDS_BETWEEN = 0
        store = leaderboard.Store()
        app = leaderboard.create_app(token="secret", store=store, scorer=leaderboard.Scorer(store, fake_evaluate))
        self.client = TestClient(app)
        self.auth = {"Authorization": "Bearer secret"}

    def tearDown(self):
        self.tmp.cleanup()

    def wait_done(self):
        for _ in range(100):
            rows = self.client.get("/api/submissions").json()
            if all(r["status"] in ("done", "failed") for r in rows):
                return rows
            time.sleep(0.05)
        self.fail("scoring did not finish")

    def submit(self, name, prompt=PROMPT, **extra):
        return self.client.post("/submit", json={"participant": name, "rewriting_prompt": prompt, **extra},
                                headers=self.auth)

    def test_baseline_row_and_ranking(self):
        self.assertEqual(self.submit("Ada", "a better prompt: {profile}", meta_prompt={"s.txt": "x"}).status_code, 200)
        rows = self.wait_done()
        self.assertEqual([r["participant"] for r in rows], ["Ada", "baseline"])
        self.assertEqual((rows[0]["heldout_score"], rows[0]["validation_score"]), (0.3, 0.35))
        page = self.client.get("/").text
        self.assertIn("Ada", page)
        self.assertIn("30.0%", page)

    def test_rejections(self):
        self.assertEqual(self.client.post("/submit", json={"participant": "A", "rewriting_prompt": PROMPT}).status_code, 401)
        self.assertEqual(self.submit("A", "no placeholder").status_code, 400)
        self.assertEqual(self.submit("Baseline").status_code, 400)
        self.assertEqual(self.submit("").status_code, 422)
        self.assertEqual(self.submit("A", meta_prompt={"big.txt": "x" * 60_000}).status_code, 400)

    def test_one_pending_submission_per_participant(self):
        class IdleScorer(leaderboard.Scorer):
            def start(self):   # never scores: submissions stay queued
                pass

        leaderboard.DB_PATH = os.path.join(self.tmp.name, "idle.sqlite3")
        store = leaderboard.Store()
        self.client = TestClient(leaderboard.create_app(token="secret", store=store,
                                                        scorer=IdleScorer(store, fake_evaluate)))
        self.assertEqual(self.submit("Bo").status_code, 200)
        r = self.submit("Bo")
        self.assertEqual(r.status_code, 429)
        self.assertIn("still being scored", r.json()["detail"])

    def test_html_is_escaped(self):
        self.submit("<script>x</script>", "evil {profile} <b>")
        self.wait_done()
        self.assertNotIn("<script>x", self.client.get("/").text)
        sid = next(r["id"] for r in self.client.get("/api/submissions").json() if r["participant"].startswith("<"))
        self.assertIn("&lt;b&gt;", self.client.get(f"/submission/{sid}").text)

    def test_heldout_details_are_not_exposed(self):
        self.submit("Cy")
        rows = self.wait_done()
        for r in rows:
            self.assertNotIn("rewriting_prompt", r)
            self.assertNotIn("per_profile", r)


if __name__ == "__main__":
    unittest.main()
