import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from evolve_demo import evaluate  # noqa: E402


class HelperTest(unittest.TestCase):
    def test_render_keeps_other_braces(self):
        self.assertEqual(evaluate.render('use {"a": 1} for {profile}!', "P"), 'use {"a": 1} for P!')

    def test_check_prompt(self):
        evaluate.check_prompt("rewrite {profile}")
        with self.assertRaisesRegex(evaluate.PromptError, "placeholder"):
            evaluate.check_prompt("rewrite {Profile}")
        with self.assertRaisesRegex(evaluate.PromptError, "longer"):
            evaluate.check_prompt("{profile}" + "x" * evaluate.MAX_PROMPT_CHARS)

    def test_extract_query(self):
        self.assertEqual(evaluate.extract_query('  "Power BI" AND dbt \n'), '"Power BI" AND dbt')
        self.assertEqual(evaluate.extract_query('```lucene\n"Power BI" AND dbt\n```'), '"Power BI" AND dbt')
        self.assertEqual(evaluate.extract_query('```\nA OR B\n```'), "A OR B")

    def test_participant_splits(self):
        dev_ids, dev_qrels = evaluate.load_split("dev")
        val_ids, _ = evaluate.load_split("validation")
        self.assertEqual((len(dev_ids), len(val_ids)), (40, 20))
        self.assertFalse(set(dev_ids) & set(val_ids))
        self.assertEqual(set(dev_qrels), set(dev_ids))
        with self.assertRaises(ValueError):
            evaluate.load_split("train")


if __name__ == "__main__":
    unittest.main()
