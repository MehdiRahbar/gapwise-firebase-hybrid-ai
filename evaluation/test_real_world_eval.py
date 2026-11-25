import json
import unittest
from pathlib import Path

CORPUS = Path(__file__).resolve().parent / 'real_world' / 'real_world_corpus.json'


class TestRealWorldEval(unittest.TestCase):
    def test_real_world_corpus_size_and_provenance(self):
        data = json.loads(CORPUS.read_text(encoding='utf-8'))
        cases = data['cases']
        self.assertGreaterEqual(len(cases), 30)
        langs = {c['visible_input']['lang'] for c in cases}
        self.assertEqual(langs, {'en', 'tr', 'fa'})
        splits = {c['visible_input']['split'] for c in cases}
        self.assertEqual(splits, {'dev', 'heldout_blind'})
        seen_ids = set()
        for c in cases:
            v = c['visible_input']
            g = c['ground_truth']
            self.assertNotIn(v['sample_id'], seen_ids)
            seen_ids.add(v['sample_id'])
            self.assertTrue(v['source_url'].startswith('https://'))
            self.assertTrue(v['captured_utc'].endswith('Z'))
            self.assertGreaterEqual(len(v['source_text']), 40)
            self.assertNotIn('gt_decision', v)
            self.assertIn(g['gt_decision'], {'YES', 'NO', 'CONFLICT', 'OUT_OF_SCOPE', 'ASK'})


if __name__ == '__main__':
    unittest.main()
