/**
 * Zero-leakage evaluator for balanced_corpus_200.json.
 * Compares: (1) naive_checklist, (2) permissive_doc_baseline (skips cross-ref/unclassified/spelled conflicts),
 * and (3) gapwise_strict_one_turn.
 */
import { performance } from 'node:perf_hooks';
import { evaluate, evaluateStrict, STATUS } from '../../web/engine.mjs';
import { analyzeSourceDocument } from '../../web/source-audit.mjs';

const raw = await new Promise((resolve, reject) => {
  let buf = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', (c) => (buf += c));
  process.stdin.on('end', () => resolve(buf));
  process.stdin.on('error', reject);
});

const items = JSON.parse(raw);

function runNaiveChecklist(item) {
  const t0 = performance.now();
  const res = evaluate(item.policy, item.observations, {
    scopeAccepted: item.scopeAccepted,
    sourceVerified: item.sourceVerified,
  });
  return {
    sample_id: item.sample_id,
    decision: res.status,
    error_class: 'none',
    latency_ms: Number((performance.now() - t0).toFixed(3)),
  };
}

function runPermissiveDocBaseline(item) {
  // Representative heuristic doc checker WITHOUT cross-reference/unclassified/short-ban/spelled-conflict/overlong fail-closed gates
  const t0 = performance.now();
  const base = evaluate(item.policy, item.observations, {
    scopeAccepted: item.scopeAccepted,
    sourceVerified: item.sourceVerified,
  });
  let dec = base.status;
  if (dec === STATUS.YES && !item.coverageReviewed) dec = STATUS.ASK;
  const audit = analyzeSourceDocument(item.source_text, item.policy, { maxCandidates: 12, includeUnclassified: false });
  if (dec === STATUS.YES) {
    const blockingClauses = (audit.candidates || []).filter(
      (c) => !c.matchedExisting && c.cueType !== 'cross-reference' && c.label.length >= 24
    );
    if (blockingClauses.length > 0) dec = STATUS.ASK;
  }
  return {
    sample_id: item.sample_id,
    decision: dec,
    error_class: 'none',
    latency_ms: Number((performance.now() - t0).toFixed(3)),
  };
}

function runGapwiseStrict(item) {
  const t0 = performance.now();
  const audit = analyzeSourceDocument(item.source_text, item.policy, { maxCandidates: 24, includeUnclassified: true });
  const novel = (audit.candidates || []).filter((c) => !c.matchedExisting);
  const conflictCount = (audit.conflictSignals || []).length;
  const res = evaluateStrict(item.policy, item.observations, {
    scopeAccepted: item.scopeAccepted,
    sourceVerified: item.sourceVerified,
    coverageReviewed: item.coverageReviewed,
    sourceText: item.source_text,
    pendingReviews: novel.length + conflictCount,
    truncatedCandidates: audit.truncatedCount || 0,
    truncatedByCharLimit: audit.truncatedByCharLimit || false,
    sourceConflictCount: conflictCount,
  });
  return {
    sample_id: item.sample_id,
    decision: res.status,
    novel_count: novel.length,
    conflict_signals: conflictCount,
    error_class: 'none',
    latency_ms: Number((performance.now() - t0).toFixed(3)),
  };
}

process.stdout.write(
  JSON.stringify({
    naive_checklist: items.map(runNaiveChecklist),
    permissive_doc_baseline: items.map(runPermissiveDocBaseline),
    gapwise_strict_one_turn: items.map(runGapwiseStrict),
  })
);
