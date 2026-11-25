"""Integrity and zero-leakage unit tests for the 120-case pre-GitHub blind suite."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pregithub_blind_100 import build_blind_suite  # noqa: E402


class TestPreGitHubBlindEval(unittest.TestCase):
    def test_at_least_100_cases_with_6_new_domains_and_3_languages(self):
        suite = build_blind_suite()
        self.assertGreaterEqual(len(suite), 100)
        self.assertEqual(len(suite), 120)
        domains = {c['visible_input']['domain'] for c in suite}
        self.assertEqual(len(domains), 6)
        self.assertFalse(domains & {'refund', 'event', 'software'})
        langs = {c['visible_input']['language'] for c in suite}
        self.assertEqual(langs, {'en', 'fa', 'tr'})

    def test_zero_label_leakage_in_visible_input(self):
        suite = build_blind_suite()
        forbidden = ('gt_decision', 'hidden_condition', 'hidden_tokens', 'expected_novel')
        for c in suite:
            vis = c['visible_input']
            gt = c['ground_truth']
            serialized = json.dumps(vis, ensure_ascii=False)
            for key in forbidden:
                self.assertNotIn(key, serialized)
            self.assertEqual(len(vis['document_hash']), 16)
            if gt['hidden_condition']:
                self.assertNotIn(gt['hidden_condition'], json.dumps(vis['policy'], ensure_ascii=False))

    def test_unique_sample_ids_and_realistic_distribution(self):
        suite = build_blind_suite()
        ids = [c['visible_input']['sample_id'] for c in suite]
        self.assertEqual(len(ids), len(set(ids)))
        gt_decisions = {c['ground_truth']['gt_decision'] for c in suite}
        self.assertEqual(gt_decisions, {'YES', 'NO', 'ASK', 'CONFLICT', 'OUT_OF_SCOPE'})


if __name__ == '__main__':
    unittest.main()
