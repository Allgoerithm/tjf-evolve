import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "evolve"))
import evaluator  # noqa: E402


def profile(pid, score, query, top_ids, error=None):
    return {"id": pid, "score": score, "points": int(score * 10), "query": query, "top_ids": top_ids, "error": error}


class FeedbackTest(unittest.TestCase):
    def test_feedback_lists_worst_and_best_profiles(self):
        per = [profile("business_intelligence_consultant_007", 0.0, "A AND B", []),
               profile("business_intelligence_consultant_010", 0.0, "A AND (", [], "query syntax error: x"),
               profile("business_intelligence_consultant_016", 0.6, "A OR B", ["CV_1", "CV_2"])]
        text = evaluator.feedback({"combined_score": 0.2, "n_profiles": 3, "n_zero": 2, "n_errors": 1,
                                   "per_profile": per})
        self.assertIn("Score 20.0% on 3 search profiles", text)
        self.assertIn("1 queries returned no CVs at all; 1 failed", text)
        self.assertIn("error: query syntax error", text)
        self.assertIn("must-have:", text)   # profile summary from the profile file
        best = text.split("Best profiles:")[1]
        self.assertIn("business_intelligence_consultant_016: 6 of 10 points, 2 hits", best)

    def test_prompt_without_placeholder_scores_zero_with_feedback(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("no placeholder here")
        try:
            r = evaluator.evaluate(f.name)
        finally:
            os.unlink(f.name)
        self.assertEqual(r.metrics["combined_score"], 0.0)
        self.assertIn("{profile}", r.artifacts["feedback"])


if __name__ == "__main__":
    unittest.main()
