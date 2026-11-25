"""Structural & zero-leakage unit tests for the 200-case balanced first-turn benchmark."""
import json
import unittest
from collections import Counter
from pathlib import Path

CORPUS_PATH = Path(__file__).resolve().parent / 'balanced_200' / 'balanced_corpus_200.json'


class TestBalancedEval200(unittest.TestCase):
    def test_exact_200_balanced_stratification_and_splits(self):
        data = json.loads(CORPUS_PATH.read_text(encoding='utf-8'))
        cases = data['cases']
        self.assertEqual(len(cases), 200)
        classes = Counter(c['ground_truth']['gt_decision'] for c in cases)
        self.assertEqual(dict(classes), {'YES': 40, 'NO': 40, 'ASK': 40, 'CONFLICT': 40, 'OUT_OF_SCOPE': 40})
        splits = Counter(c['visible_input']['split'] for c in cases)
        self.assertEqual(splits['dev'], 150)
        self.assertEqual(splits['heldout_blind'], 50)
        held_classes = Counter(c['ground_truth']['gt_decision'] for c in cases if c['visible_input']['split'] == 'heldout_blind')
        self.assertEqual(dict(held_classes), {'YES': 10, 'NO': 10, 'ASK': 10, 'CONFLICT': 10, 'OUT_OF_SCOPE': 10})

    def test_full_provenance_and_zero_ground_truth_leakage(self):
        data = json.loads(CORPUS_PATH.read_text(encoding='utf-8'))
        seen_ids = set()
        for c in data['cases']:
            vis = c['visible_input']
            gt = c['ground_truth']
            self.assertNotIn(vis['sample_id'], seen_ids)
            seen_ids.add(vis['sample_id'])
            for req in ('source_url', 'source_sha256', 'retrieval_utc', 'policy_effective_date', 'jurisdiction'):
                self.assertTrue(str(vis.get(req, '')).strip(), f"Missing {req} on {vis['sample_id']}")
            for secret in ('gt_decision', 'gold_audit_status', 'rationale', 'missing_facts'):
                self.assertNotIn(secret, vis)
            self.assertTrue(gt['visible_facts'])
            self.assertTrue(gt['rationale'])


if __name__ == '__main__':
    unittest.main()
