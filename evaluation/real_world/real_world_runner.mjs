/**
 * Zero-leakage blind runner for the 36-case real-world public document benchmark.
 * Reads ONLY visible_input items from stdin (never ground_truth).
 */
import { performance } from 'node:perf_hooks';
import { evaluate, evaluateStrict, STATUS } from '../../web/engine.mjs';
import { analyzeSourceDocument, validateSourceQuote } from '../../web/source-audit.mjs';

const raw = await new Promise((resolve, reject) => {
  let buf = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', (chunk) => (buf += chunk));
  process.stdin.on('end', () => resolve(buf));
  process.stdin.on('error', reject);
});

const items = JSON.parse(raw);

function runGapwise(item, useStrictAudit) {
  const t0 = performance.now();
  if (!useStrictAudit) {
    const res = evaluate(item.policy, item.observations, {
      scopeAccepted: item.scopeAccepted,
      sourceVerified: item.sourceVerified,
    });
    return {
      sample_id: item.sample_id,
      decision: res.status,
      novel_labels: [],
      provenance_valid: false,
      latency_ms: Number((performance.now() - t0).toFixed(3)),
    };
  }
  const audit = analyzeSourceDocument(item.source_text, item.policy, { maxCandidates: 24, includeUnclassified: true });
  const novel = (audit.candidates || []).filter((c) => !c.matchedExisting);
  const conflictCount = (audit.conflictSignals || []).length;
  const evalRes = evaluateStrict(item.policy, item.observations, {
    scopeAccepted: item.scopeAccepted,
    sourceVerified: item.sourceVerified,
    coverageReviewed: item.coverageReviewed,
    sourceText: item.source_text,
    pendingReviews: novel.length + conflictCount,
    truncatedCandidates: audit.truncatedCount || 0,
    truncatedByCharLimit: audit.truncatedByCharLimit || false,
    sourceConflictCount: conflictCount,
  });
  const top = novel[0];
  const quoteCheck = top?.quote ? validateSourceQuote(top, item.source_text) : { found: false };
  return {
    sample_id: item.sample_id,
    decision: evalRes.status,
    novel_labels: novel.map((n) => n.label),
    novel_count: novel.length,
    truncated_count: audit.truncatedCount || 0,
    conflict_signals: conflictCount,
    provenance_valid: Boolean(quoteCheck.found),
    latency_ms: Number((performance.now() - t0).toFixed(3)),
  };
}

process.stdout.write(
  JSON.stringify({
    naive_checklist: items.map((x) => runGapwise(x, false)),
    gapwise_strict: items.map((x) => runGapwise(x, true)),
  })
);
