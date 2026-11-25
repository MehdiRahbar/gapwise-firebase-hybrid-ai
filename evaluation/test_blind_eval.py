import unittest
from evaluation.blind_eval import build_cases

class TestBlindEval(unittest.TestCase):
    def test_40_blind_cases_balanced(self):
        cases = build_cases()
        self.assertEqual(len(cases), 40)
        gts = {c["groundTruth"] for c in cases}
        self.assertEqual(gts, {"YES", "NO", "ASK", "CONFLICT", "OUT_OF_SCOPE"})

    def test_no_ground_truth_inside_policy_or_source(self):
        for c in build_cases():
            self.assertNotIn("groundTruth", c["policy"])
            self.assertNotIn("hiddenAnswers", c["policy"])

if __name__ == "__main__":
    unittest.main()
