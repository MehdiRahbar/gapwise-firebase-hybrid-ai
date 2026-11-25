/**
 * Zero-leakage line-delimited JSON adaptive engine runner (reads ONLY visible_input + oracle step replies).
 * Supports commands: {"op": "init", "items": [...]} and {"op": "step", "state": ..., "responses": [...], "confirm_coverage": bool}
 */
import readline from 'node:readline';
import { performance } from 'node:perf_hooks';
import { evaluate, evaluateStrict, buildAdaptivePlan, applyAdaptiveResponse, STATUS } from '../../web/engine.mjs';
import { analyzeSourceDocument } from '../../web/source-audit.mjs';

const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });

function summarizePlan(plan) {
  return {
    status: plan.decision.status,
    certificationTier: plan.decision.certificationTier,
    statusSummary: plan.statusSummary,
    nextQuestion: plan.nextQuestion,
    recommendedBatch: plan.recommendedBatch,
    queueLength: plan.queue.length,
    unknownConfirmedLabels: plan.unknownConfirmedLabels,
    unresolvableByUser: plan.unresolvableByUser,
  };
}

for await (const line of rl) {
  if (!line.trim()) continue;
  const req = JSON.parse(line);
  if (req.op === 'init') {
    const t0 = performance.now();
    const item = req.visible_input;
    const naiveRes = evaluate(item.policy, item.observations, {
      scopeAccepted: item.scopeAccepted,
      sourceVerified: item.sourceVerified,
    });
    const audit = analyzeSourceDocument(item.source_text, item.policy, { maxCandidates: 24, includeUnclassified: true });
    const proposals = (audit.candidates || [])
      .filter((c) => !c.matchedExisting)
      .map((c, idx) => ({
        uid: `scan_${idx}_${c.line || 0}`,
        label: c.label,
        reason: c.reason,
        origin: c.origin,
        cueType: c.cueType,
        line: c.line,
        startOffset: c.startOffset,
        endOffset: c.endOffset,
        quote: c.quote,
        quoteVerified: Boolean(c.quote && item.source_text.includes(c.quote)),
        status: 'pending',
      }));
    const snap = {
      observations: { ...(item.observations || {}) },
      unknownConfirmedIds: [],
      deferredIds: [],
      sourceText: item.source_text,
      sourceName: item.source_title || 'source',
      proposals,
      scopeAccepted: item.scopeAccepted,
      sourceVerified: item.sourceVerified,
      coverageReviewed: item.coverageReviewed,
    };
    const plan = buildAdaptivePlan(item.policy, snap.observations, audit, snap);
    const ms = Number((performance.now() - t0).toFixed(3));
    process.stdout.write(
      JSON.stringify({
        naive_status: naiveRes.status,
        single_turn_status: plan.decision.status,
        policy: item.policy,
        snapshot: snap,
        plan: summarizePlan(plan),
        latency_ms: ms,
      }) + '\n'
    );
  } else if (req.op === 'step') {
    const t0 = performance.now();
    const responses = [...(req.responses || [])];
    if (req.confirm_coverage) {
      responses.push({ kind: 'gate', requirementId: 'coverageReviewed', action: 'yes' });
    }
    const res = applyAdaptiveResponse(req.policy, req.snapshot, responses);
    // Automatically complete coverage review gate cleanly if NO pending proposals & NO unknown/missing facts remain
    let finalRes = res;
    if (
      res.plan.decision.status === STATUS.ASK &&
      res.plan.decision.missing.length === 0 &&
      res.proposals.filter((x) => x.status === 'pending').length === 0 &&
      !res.coverageReviewed &&
      res.unknownConfirmedIds.length === 0
    ) {
      finalRes = applyAdaptiveResponse(res.policy, { ...req.snapshot, ...res }, [
        { kind: 'gate', requirementId: 'coverageReviewed', action: 'yes' },
      ]);
    }
    const ms = Number((performance.now() - t0).toFixed(3));
    process.stdout.write(
      JSON.stringify({
        policy: finalRes.policy,
        snapshot: {
          observations: finalRes.observations,
          unknownConfirmedIds: finalRes.unknownConfirmedIds,
          deferredIds: finalRes.deferredIds,
          sourceText: req.snapshot.sourceText,
          sourceName: req.snapshot.sourceName,
          proposals: finalRes.proposals,
          scopeAccepted: finalRes.scopeAccepted,
          sourceVerified: finalRes.sourceVerified,
          coverageReviewed: finalRes.coverageReviewed,
        },
        plan: summarizePlan(finalRes.plan),
        latency_ms: ms,
      }) + '\n'
    );
  }
}
