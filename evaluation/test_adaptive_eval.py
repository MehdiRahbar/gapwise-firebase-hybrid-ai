"""Structural & sealed-oracle zero-leakage tests for the 100-case adaptive benchmark."""
import json
import unittest
from collections import Counter
from pathlib import Path

CORPUS_PATH = Path(__file__).resolve().parent / 'adaptive_100' / 'adaptive_corpus_100.json'


class TestAdaptiveEval100(unittest.TestCase):
    def test_100_cases_with_at_least_70_answerable_and_20_unresolvable(self):
        data = json.loads(CORPUS_PATH.read_text(encoding='utf-8'))
        cases = data['cases']
        self.assertEqual(len(cases), 100)
        answerable = sum(1 for c in cases if c['ground_truth']['answerable'])
        unresolvable = sum(1 for c in cases if not c['ground_truth']['answerable'])
        self.assertGreaterEqual(answerable, 70)
        self.assertGreaterEqual(unresolvable, 20)
        splits = Counter(c['visible_input']['split'] for c in cases)
        self.assertEqual(splits['heldout_blind'], 25)
        self.assertEqual(splits['dev'], 75)

    def test_sealed_oracle_never_leaks_into_visible_input(self):
        data = json.loads(CORPUS_PATH.read_text(encoding='utf-8'))
        for c in data['cases']:
            vis = c['visible_input']
            self.assertNotIn('oracle_key', vis)
            self.assertNotIn('clause_outcomes', vis)
            self.assertNotIn('gt_final_status', vis)
            self.assertNotIn('answerable', vis)
            self.assertNotIn('dunno', vis.get('observations', {}).values())


if __name__ == '__main__':
    unittest.main()
