import { evaluate, evaluateStrict } from '../web/engine.mjs';
import { scanDocumentForConditions } from '../web/source-audit.mjs';

const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const cases = JSON.parse(Buffer.concat(chunks).toString('utf8'));

const summary = {
  naive_checklist: { decisions: 0, selective_errors: 0, false_positives: 0, correct_decisions: 0, total_ms: 0 },
  gapwise_v9_base: { decisions: 0, selective_errors: 0, false_positives: 0, correct_decisions: 0, total_ms: 0 },
  gapwise_v10_strict: { decisions: 0, selective_errors: 0, false_positives: 0, correct_decisions: 0, extra_questions: 0, hidden_detected: 0, total_ms: 0 },
};
const details = [];

for (const c of cases) {
  const { id, domain, category, policy, sourceText, initialAnswers, hiddenAnswers, scopeAccepted, groundTruth } = c;
  const fullObs = { ...initialAnswers };

  // 1. Naive baseline: only checks initial checklist terms without source or scope checks
  const t0 = performance.now();
  const initialVals = policy.terms.map(t => initialAnswers[t.id] || 'unknown');
  let naiveStatus = 'ASK';
  if (initialVals.includes('conflict')) naiveStatus = 'CONFLICT';
  else if (initialVals.includes('no')) naiveStatus = 'NO';
  else if (initialVals.every(v => v === 'yes')) naiveStatus = 'YES';
  const dtNaive = performance.now() - t0;

  // 2. GAPWISE v9 base evaluate() (with scope & sourceVerified flag, no source scanner)
  const t1 = performance.now();
  const v9Res = evaluate(policy, fullObs, { scopeAccepted, sourceVerified: Boolean(sourceText && sourceText.length >= 24) });
  const dtV9 = performance.now() - t1;

  // 3. GAPWISE v10 strict: scan independent source -> enqueue unmatched clauses -> review & attest hidden answers
  const t2 = performance.now();
  const scanned = scanDocumentForConditions(sourceText || '', policy);
  const unmatched = scanned.filter(x => !x.matchedExisting);
  const v10Policy = {
    ...policy,
    terms: [
      ...policy.terms,
      ...unmatched.map((u, idx) => ({
        id: `hidden_${idx}`,
        label: u.label,
        why: u.reason,
        cost: 1,
        weight: 4,
      })),
    ],
  };
  const v10Obs = { ...initialAnswers };
  // Before user answers hidden clauses, pending reviews must block YES
  const preReviewRes = evaluateStrict(v10Policy, v10Obs, {
    scopeAccepted,
    sourceVerified: Boolean(sourceText && sourceText.length >= 24),
    coverageReviewed: false,
    sourceText,
    pendingReviews: unmatched.length,
  });
  // Simulate honest user answering the newly surfaced hidden questions accurately
  unmatched.forEach((u, idx) => {
    const matchedHidden = Object.entries(hiddenAnswers || {}).find(([needle]) =>
      u.label.toLowerCase().includes(needle.toLowerCase())
    );
    v10Obs[`hidden_${idx}`] = matchedHidden ? matchedHidden[1] : 'unknown';
  });
  const v10Res = evaluateStrict(v10Policy, v10Obs, {
    scopeAccepted,
    sourceVerified: Boolean(sourceText && sourceText.length >= 24),
    coverageReviewed: true,
    sourceText,
    pendingReviews: 0,
  });
  const dtV10 = performance.now() - t2;

  const score = (bucket, pred, ms) => {
    bucket.total_ms += ms;
    if (pred !== 'ASK') bucket.decisions += 1;
    if (pred === 'YES' && groundTruth !== 'YES') {
      bucket.false_positives += 1;
      bucket.selective_errors += 1;
    } else if (pred !== 'ASK' && pred !== groundTruth) {
      bucket.selective_errors += 1;
    }
    if (pred === groundTruth) bucket.correct_decisions += 1;
  };

  score(summary.naive_checklist, naiveStatus, dtNaive);
  score(summary.gapwise_v9_base, v9Res.status, dtV9);
  score(summary.gapwise_v10_strict, v10Res.status, dtV10);
  summary.gapwise_v10_strict.extra_questions += unmatched.length;
  if (unmatched.length > 0) summary.gapwise_v10_strict.hidden_detected += 1;

  details.push({
    id,
    domain,
    category,
    groundTruth,
    naiveStatus,
    v9Status: v9Res.status,
    v10PreReviewStatus: preReviewRes.status,
    v10FinalStatus: v10Res.status,
    hiddenClausesDetected: unmatched.length,
  });
}

const n = cases.length;
const finalize = (b) => ({
  ...b,
  n,
  coverage: Number((b.decisions / n).toFixed(4)),
  accuracy: Number((b.correct_decisions / n).toFixed(4)),
  selective_error_rate: b.decisions ? Number((b.selective_errors / b.decisions).toFixed(4)) : 0,
  false_positive_yes_rate: Number((b.false_positives / n).toFixed(4)),
  avg_latency_ms: Number((b.total_ms / n).toFixed(4)),
});

console.log(JSON.stringify({
  n_cases: n,
  source_provenance: 'deterministic-local-js (web/engine.mjs + web/source-audit.mjs)',
  metrics: {
    naive_checklist: finalize(summary.naive_checklist),
    gapwise_v9_base: finalize(summary.gapwise_v9_base),
    gapwise_v10_strict: {
      ...finalize(summary.gapwise_v10_strict),
      avg_extra_questions: Number((summary.gapwise_v10_strict.extra_questions / n).toFixed(3)),
    },
  },
  details,
}, null, 2));
