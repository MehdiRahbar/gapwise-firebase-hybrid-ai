/**
 * Zero-leakage blind runner for fresh_public_corpus_30.json.
 * Compares: naive_checklist, permissive_doc_baseline, and unmodified gapwise_strict_one_turn.
 */
import { performance } from 'node:perf_hooks';
import { evaluate, evaluateStrict, STATUS } from '../../web/engine.mjs';
import { analyzeSourceDocument, validateSourceQuote } from '../../web/source-audit.mjs';

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
  const top = novel[0];
  const quoteCheck = top?.quote ? validateSourceQuote(top, item.source_text) : { found: false };
  return {
    sample_id: item.sample_id,
    decision: res.status,
    novel_count: novel.length,
    novel_labels: novel.map((n) => n.label),
    conflict_signals: conflictCount,
    provenance_valid: Boolean(quoteCheck.found),
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
