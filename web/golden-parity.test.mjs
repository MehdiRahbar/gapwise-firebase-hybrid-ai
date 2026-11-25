import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { SAMPLE_POLICIES, evaluateStrict } from './engine.mjs';
import { analyzeSourceDocument } from './source-audit.mjs';

const golden = JSON.parse(fs.readFileSync(new URL('../evaluation/golden_cases.json', import.meta.url), 'utf8'));

test('Cross-platform golden_cases.json parity holds in Node engine', () => {
  for (const tc of golden.cases) {
    const policy = tc.policy
      ? {
          id: tc.policy.id || tc.policy_id,
          title: tc.policy.title || '',
          tag: 'Golden parity',
          scope: tc.policy.scope || '',
          source: 'Golden corpus',
          question: tc.policy.question || '',
          terms: (tc.policy.terms || []).map((t) => ({ cost: 1, weight: 5, ...t })),
        }
      : SAMPLE_POLICIES.find((p) => p.id === tc.policy_id);
    assert.ok(policy, `Unknown policy ${tc.policy_id}`);
    const audit = analyzeSourceDocument(tc.source_text, policy, { maxCandidates: 24, includeUnclassified: true });
    const res = evaluateStrict(policy, tc.observations, {
      scopeAccepted: tc.scope_accepted,
      sourceVerified: tc.source_verified,
      coverageReviewed: tc.coverage_reviewed,
      sourceText: tc.source_text,
      pendingReviews: audit.novelCount,
      truncatedCandidates: audit.truncatedCount,
      truncatedByCharLimit: audit.truncatedByCharLimit,
      sourceConflictCount: audit.conflictSignals.length,
    });
    assert.equal(res.status, tc.expected_status, `${tc.id}: expected ${tc.expected_status}, got ${res.status}`);
    if (tc.expected_cert_tier) {
      assert.equal(res.certificationTier, tc.expected_cert_tier, `${tc.id}: cert tier`);
    }
    if (typeof tc.expected_min_novel === 'number') {
      assert.ok(audit.novelCount >= tc.expected_min_novel, `${tc.id}: expected novel >= ${tc.expected_min_novel}, got ${audit.novelCount}`);
    }
    if (typeof tc.expected_min_truncated === 'number') {
      assert.ok(audit.truncatedCount >= tc.expected_min_truncated, `${tc.id}: expected truncated >= ${tc.expected_min_truncated}, got ${audit.truncatedCount}`);
    }
  }
});
