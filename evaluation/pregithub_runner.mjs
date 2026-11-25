/**
 * Zero-leakage blind runner for the 120-case pre-GitHub evaluation.
 * Accepts ONLY visible_input JSON objects via stdin (never ground_truth).
 */
import { performance } from 'node:perf_hooks';
import { pathToFileURL } from 'node:url';
import { evaluate, evaluateStrict, STATUS } from '../web/engine.mjs';
import { analyzeSourceDocument, validateSourceQuote } from '../web/source-audit.mjs';

const raw = await new Promise((resolve, reject) => {
  let buf = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', (chunk) => (buf += chunk));
  process.stdin.on('end', () => resolve(buf));
  process.stdin.on('error', reject);
});

const payload = JSON.parse(raw);
const items = Array.isArray(payload) ? payload : payload.items || [];
const backupDir = process.argv.find((a) => a.startsWith('--backup='))?.slice('--backup='.length) || '';

let backupAudit = null;
let backupEvaluateStrict = null;
if (backupDir) {
  try {
    const modAudit = await import(pathToFileURL(`${backupDir}/web/source-audit.mjs`).href);
    const modEng = await import(pathToFileURL(`${backupDir}/web/engine.mjs`).href);
    backupAudit = modAudit;
    backupEvaluateStrict = modEng.evaluateStrict;
  } catch {
    backupAudit = null;
  }
}

function runGapwise(item, auditFn, strictFn, includeUnclassified) {
  const t0 = performance.now();
  const audit = auditFn(item.source_text, item.policy, { maxCandidates: 24, includeUnclassified });
  const novel = (audit.candidates || []).filter((c) => !c.matchedExisting);
  const conflictCount = (audit.conflictSignals || []).length;
  const pendingReviews = novel.length + conflictCount;
  const evalRes = strictFn(item.policy, item.observations, {
    scopeAccepted: item.scopeAccepted,
    sourceVerified: item.sourceVerified,
    coverageReviewed: item.coverageReviewed,
    sourceText: item.source_text,
    pendingReviews,
    truncatedCandidates: audit.truncatedCount || 0,
    truncatedByCharLimit: audit.truncatedByCharLimit || false,
    sourceConflictCount: conflictCount,
  });

  const topCandidate = novel[0] || (audit.conflictSignals?.[0] ? { label: audit.conflictSignals[0].summary, quote: '' } : null);
  const quoteCheck = topCandidate?.quote ? validateSourceQuote(topCandidate, item.source_text) : { found: false };
  let generatedQuestion = evalRes.nextQuestion?.label || '';
  if (!generatedQuestion && evalRes.status === STATUS.ASK) {
    if (topCandidate?.label) {
      generatedQuestion = `Verify omitted source clause: ${topCandidate.label}`;
    } else if ((evalRes.blocking || []).length > 0) {
      generatedQuestion = evalRes.blocking[0];
    }
  }

  return {
    sample_id: item.sample_id,
    predicted_condition: topCandidate?.label || '',
    novel_labels: novel.map((n) => n.label),
    novel_count: novel.length,
    conflict_signals: conflictCount,
    truncated_count: audit.truncatedCount || 0,
    unclassified_count: audit.unclassifiedCount || 0,
    generated_question: generatedQuestion,
    reference_quote: quoteCheck.found ? topCandidate.quote : '',
    provenance_valid: Boolean(quoteCheck.found),
    decision: evalRes.status,
    status_label: evalRes.statusLabel || evalRes.status,
    latency_ms: Number((performance.now() - t0).toFixed(3)),
    inferenceSource: 'deterministic_engine',
    consent: 'not_applicable_offline',
    error_class: 'none',
  };
}

const out = {
  naive_checklist: items.map((item) => {
    const t0 = performance.now();
    const res = evaluate(item.policy, item.observations, {
      scopeAccepted: item.scopeAccepted,
      sourceVerified: true,
    });
    return {
      sample_id: item.sample_id,
      predicted_condition: '',
      novel_labels: [],
      generated_question: res.nextQuestion?.label || '',
      reference_quote: '',
      provenance_valid: false,
      decision: res.status,
      latency_ms: Number((performance.now() - t0).toFixed(3)),
      inferenceSource: 'naive_baseline',
      consent: 'not_applicable_offline',
      error_class: 'none',
    };
  }),
  gapwise_strict: items.map((item) => runGapwise(item, analyzeSourceDocument, evaluateStrict, true)),
};

if (backupAudit && backupEvaluateStrict) {
  const preAuditFn = backupAudit.analyzeSourceDocument
    ? (text, pol, opts) => backupAudit.analyzeSourceDocument(text, pol, opts)
    : (text, pol, opts) => {
        const cands = backupAudit.scanDocumentForConditions(text, pol, opts);
        return { candidates: cands, conflictSignals: [], truncatedCount: 0, truncatedByCharLimit: false, unclassifiedCount: 0 };
      };
  out.gapwise_pre_audit = items.map((item) => runGapwise(item, preAuditFn, backupEvaluateStrict, false));
}

process.stdout.write(JSON.stringify(out));
