import {
  SAMPLE_POLICIES,
  evaluateStrict,
  applyExtraction,
  formulateExtractionPrompt,
  buildAdaptivePlan,
  applyAdaptiveResponse,
  computeCaseVersion,
  STATUS,
} from './engine.mjs';
import { DOCUMENTS } from './demo-policy-docs.mjs';
import { analyzeSourceDocument } from './source-audit.mjs';
import {
  connectHybrid,
  extractWithHybrid,
  hybridReady,
  prepareDeviceModel,
  getHybridStatus,
  envConfig,
  envAppCheckKey,
  classifyInferenceError,
  createRequestCoordinator,
  resolveInferenceTimeoutMs,
} from './firebase-hybrid.mjs';
import { recordLocalEvidence } from './evidence-bridge.mjs';

const $ = (id) => document.getElementById(id);
const h = (s) =>
  String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const state = {
  index: 0,
  policy: structuredClone(SAMPLE_POLICIES[0]),
  answers: {},
  unknownConfirmedIds: [],
  deferredIds: [],
  sourceText: '',
  sourceName: 'none',
  sourceAudit: null,
  proposals: [],
  history: [],
  aiLog: null,
  attestations: {
    sourceVerifiedAt: null,
    sourceVerifiedBy: null,
    coverageReviewedAt: null,
    coverageReviewedBy: null,
    caseVersion: null,
  },
  busy: false,
};

function currentVerifier() {
  const name = $('reviewerName')?.value.trim();
  return name ? name.slice(0, 120) : 'Anonymous local user (identity not verified)';
}

function log(kind, detail) {
  state.history.unshift({ time: new Date().toISOString(), kind, detail: String(detail).slice(0, 400) });
  state.history = state.history.slice(0, 80);
  renderHistory();
}

function saveLocalEvidence(event, payload) {
  recordLocalEvidence(event, payload).catch(() => {});
}

function decisionEvidence() {
  const ev = decision();
  return {
    status: ev.status,
    statusLabel: ev.statusLabel,
    answered: ev.answered,
    missingCount: Array.isArray(ev.missing) ? ev.missing.length : null,
    conflictingCount: Array.isArray(ev.conflicting) ? ev.conflicting.length : null,
    pendingReviews: ev.pendingReviews,
  };
}

const coordinator = createRequestCoordinator();
let activeTickTimer = null;
let pendingSimpleReveal = null;

function clearAnalyzeUi() {
  if (activeTickTimer) {
    clearInterval(activeTickTimer);
    activeTickTimer = null;
  }
  state.busy = false;
  $('analyzeBtn').disabled = false;
  $('cancelAnalyzeBtn').hidden = true;
}

function fenceNewCase(reason) {
  const res = coordinator.invalidateCase(reason);
  clearAnalyzeUi();
  if (res.abortedPrevious) {
    log('Stale run fenced', `${reason} (epoch ${res.epoch}; old response cannot modify new case)`);
  }
}

function invalidateAttestations({
  clearSourceVerified = false,
  clearCoverage = true,
  clearAi = false,
  clearSourceProposals = false,
  reason = '',
} = {}) {
  let changed = false;
  if (clearAi) {
    fenceNewCase(reason || 'input_modified');
  }
  if (clearSourceVerified && ($('sourceVerified').checked || state.attestations.sourceVerifiedAt)) {
    $('sourceVerified').checked = false;
    state.attestations.sourceVerifiedAt = null;
    state.attestations.sourceVerifiedBy = null;
    changed = true;
  }
  if (clearCoverage && ($('coverageReviewed').checked || state.attestations.coverageReviewedAt)) {
    $('coverageReviewed').checked = false;
    state.attestations.coverageReviewedAt = null;
    state.attestations.coverageReviewedBy = null;
    changed = true;
  }
  if (clearAi && (state.aiLog || !$('modelSuggestions').hidden)) {
    state.aiLog = null;
    $('modelSuggestions').hidden = true;
    $('aiProgress').textContent = hybridReady()
      ? 'Input changed — previous AI output cleared. Run Discover missing conditions again.'
      : 'Input changed — deterministic scan updated.';
    changed = true;
  }
  if (clearSourceProposals) {
    state.proposals = state.proposals.filter((x) => x.origin === 'manual');
  } else if (clearAi) {
    state.proposals = state.proposals.filter((x) => x.origin !== 'firebase-ai-logic');
  }
  if (changed && reason) log('Attestations invalidated', reason);
}

function renderHistory() {
  const el = $('auditHistory');
  if (!el) return;
  el.innerHTML =
    state.history
      .slice(0, 6)
      .map(
        (x) =>
          `<div class="history-item"><span>${h(new Date(x.time).toLocaleTimeString())}</span> <b>${h(x.kind)}</b><small>${h(x.detail)}</small></div>`
      )
      .join('') || '<p class="smalltext">Actions and decisions appear here.</p>';
}

function reset(i) {
  fenceNewCase('case_switched');
  state.index = i;
  state.policy = structuredClone(SAMPLE_POLICIES[i]);
  state.answers = {};
  state.unknownConfirmedIds = [];
  state.deferredIds = [];
  state.sourceText = '';
  state.sourceName = 'none';
  state.sourceAudit = null;
  state.proposals = [];
  state.history = [];
  state.aiLog = null;
  state.attestations = { sourceVerifiedAt: null, sourceVerifiedBy: null, coverageReviewedAt: null, coverageReviewedBy: null, caseVersion: null };
  $('question').value = state.policy.question;
  $('sourceText').value = '';
  $('sourceNameInput').value = '';
  $('sourceFile').value = '';
  $('sourceVerified').checked = false;
  $('coverageReviewed').checked = false;
  $('scopeAccepted').checked = true;
  $('modelSuggestions').hidden = true;
  $('aiProgress').textContent = 'Deterministic assessment ready. Connect Firebase for real model suggestions.';
  $('sourceLabel').textContent = `Source: ${state.policy.source} · Scope: ${state.policy.scope}`;
  renderExamples();
  log('Case opened', state.policy.title);
  render();
}

function renderExamples() {
  $('examples').innerHTML = SAMPLE_POLICIES.map(
    (p, i) =>
      `<button type="button" class="example ${i === state.index ? 'active' : ''}" data-index="${i}" aria-pressed="${i === state.index}"><b>${h(p.title)}</b><small>${h(p.tag)}</small></button>`
  ).join('');
  $('examples')
    .querySelectorAll('button')
    .forEach((b) => b.addEventListener('click', () => reset(Number(b.dataset.index))));
}

function pending() {
  return state.proposals.filter((x) => x.status === 'pending');
}

function adaptivePlan() {
  return buildAdaptivePlan(state.policy, state.answers, state.sourceAudit, {
    scopeAccepted: $('scopeAccepted').checked,
    sourceVerified: $('sourceVerified').checked,
    coverageReviewed: $('coverageReviewed').checked,
    sourceText: state.sourceText,
    sourceName: state.sourceName,
    proposals: state.proposals,
    unknownConfirmedIds: state.unknownConfirmedIds,
    deferredIds: state.deferredIds,
  });
}

function decision() {
  return adaptivePlan().decision;
}

function setSource(text, name) {
  state.sourceText = String(text || '').slice(0, 35000);
  state.sourceName = (name || $('sourceNameInput').value.trim() || 'user-pasted').slice(0, 160);
  if (name && $('sourceNameInput').value.trim() !== state.sourceName) {
    $('sourceNameInput').value = state.sourceName;
  }
  state.unknownConfirmedIds = [];
  state.deferredIds = [];
  invalidateAttestations({ clearSourceVerified: true, clearCoverage: true, clearAi: true, clearSourceProposals: true });
  const audit = analyzeSourceDocument(state.sourceText, state.policy, { maxCandidates: 24, includeUnclassified: true });
  state.sourceAudit = audit;
  for (const x of audit.candidates.filter((c) => !c.matchedExisting)) {
    enqueue(x);
  }
  for (const sig of audit.conflictSignals) {
    enqueue({
      id: null,
      label: `Potential internal policy contradiction (lines ${sig.lineA} & ${sig.lineB})`,
      reason: sig.summary + ' Review and confirm whether this document contradicts itself.',
      origin: 'conflict-scan',
      cueType: 'contradiction-cue',
      line: sig.lineB,
      quote: '',
    });
  }
  log('Source changed', `${state.sourceName}; ${audit.candidates.length} candidate clauses, ${pending().length} need review`);
  render();
}

function enqueue(proposal) {
  const label = String(proposal.label || '').trim().slice(0, 360);
  if (!label) return;
  const norm = (s) => s.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
  if (state.proposals.some((x) => norm(x.label) === norm(label))) return;
  const id = `review_${state.proposals.length}_${Math.floor(Math.random() * 1e8).toString(36)}`;
  const quoteText = String(proposal.quote || '').trim();
  const quoteVerified = Boolean(quoteText && state.sourceText.includes(quoteText));
  const groundingStatus = quoteVerified ? 'exact_quote_verified' : 'unverified_suggestion';
  state.proposals.push({
    uid: id,
    label,
    reason: String(proposal.reason || '').slice(0, 480),
    origin: proposal.origin || 'ai-suggestion',
    cueType: proposal.cueType || 'ai',
    line: proposal.line || null,
    quote: quoteText.slice(0, 700),
    quoteVerified,
    groundingStatus,
    status: 'pending',
  });
}

function renderProposals() {
  const target = $('reviewQueue');
  const items = state.proposals;
  const unresolved = pending();
  $('reviewCounter').textContent = `${unresolved.length} awaiting review`;
  if (!items.length) {
    target.innerHTML =
      '<p class="smalltext">Load a source document or run AI to discover candidate requirements. No unreviewed suggestions yet.</p>';
    return;
  }
  target.innerHTML = items
    .map(
      (x) =>
        `<div class="review-item ${x.status === 'pending' ? '' : 'review-finished'}"><div class="review-heading"><b>${h(x.label)}</b><span class="smalltext ${x.quoteVerified || x.origin === 'conflict-scan' ? '' : 'warn-tag'}">${h(x.origin)} · ${x.quoteVerified ? 'exact quote' : x.origin === 'conflict-scan' ? 'conflict check' : 'unverified suggestion'} · ${h(x.status)}</span></div><p>${h(x.reason)}</p>${
          x.quoteVerified
            ? `<p class="source-quote">“${h(x.quote)}” · exact quote found</p>`
            : x.origin === 'conflict-scan'
            ? ''
            : `<p class="source-quote unverified-quote"><strong>unverified suggestion</strong> — ${x.quote ? `“${h(x.quote)}” · quote not found in source` : 'no source quote returned by model'}; not doc-grounded and does not prove coverage</p>`
        }${x.status === 'dismissed' && x.dismissalReason ? `<p class="smalltext">Dismissed reason: ${h(x.dismissalReason)}</p>` : ''}${
          x.status === 'pending'
            ? `<div class="review-actions"><button type="button" class="primary tiny" data-review="add" data-id="${h(x.uid)}">Add as unknown</button><button type="button" class="outline tiny" data-review="dismiss" data-id="${h(x.uid)}">Dismiss with reason</button></div><div class="dismiss-box" data-dismiss-box="${h(x.uid)}" ${x.dismissOpen ? '' : 'hidden'}><input type="text" maxlength="500" aria-label="Dismissal reason" placeholder="Why does this clause not apply or is it already covered? (min 8 chars)" data-dismiss-input="${h(x.uid)}" value="${h(x.draftReason || '')}"><p class="dismiss-error" data-dismiss-err="${h(x.uid)}" ${x.dismissError ? '' : 'hidden'}>${h(x.dismissError || '')}</p><div class="review-actions"><button type="button" class="primary tiny" data-review="confirm-dismiss" data-id="${h(x.uid)}">Confirm dismiss</button><button type="button" class="outline tiny" data-review="cancel-dismiss" data-id="${h(x.uid)}">Cancel</button></div></div>`
            : ''
        }</div>`
    )
    .join('');

  target.querySelectorAll('[data-dismiss-input]').forEach((inp) =>
    inp.addEventListener('input', () => {
      const x = state.proposals.find((y) => y.uid === inp.dataset.dismissInput);
      if (x) x.draftReason = inp.value;
    })
  );
  target.querySelectorAll('[data-review]').forEach((b) =>
    b.addEventListener('click', () => {
      const x = state.proposals.find((y) => y.uid === b.dataset.id);
      if (!x || x.status !== 'pending') return;
      if (b.dataset.review === 'add') {
        const prefix = x.quoteVerified || x.origin === 'conflict-scan' ? '' : '[unverified suggestion — no verified source quote] ';
        addRequirement(x.label, prefix + (x.reason || 'Candidate extracted from a source; not verified'), x.uid);
        x.status = 'added';
        log('Requirement added', x.label);
        invalidateAttestations({ clearCoverage: true });
        render();
        return;
      }
      if (b.dataset.review === 'dismiss') {
        x.dismissOpen = true;
        x.dismissError = '';
        render();
        target.querySelector(`[data-dismiss-input="${CSS.escape(x.uid)}"]`)?.focus();
        return;
      }
      if (b.dataset.review === 'cancel-dismiss') {
        x.dismissOpen = false;
        x.dismissError = '';
        render();
        return;
      }
      if (b.dataset.review === 'confirm-dismiss') {
        const why = (x.draftReason || '').trim();
        if (why.length < 8) {
          x.dismissError = 'Please enter at least 8 characters explaining why this clause does not apply.';
          render();
          target.querySelector(`[data-dismiss-input="${CSS.escape(x.uid)}"]`)?.focus();
          return;
        }
        x.status = 'dismissed';
        x.dismissalReason = why.slice(0, 500);
        x.dismissOpen = false;
        x.dismissError = '';
        log('Candidate dismissed', `${x.label}: ${x.dismissalReason} (by ${currentVerifier()})`);
        invalidateAttestations({ clearCoverage: true });
        render();
      }
    })
  );
}

function processingModeText() {
  if (!state.aiLog) return 'Locally processed (deterministic)';
  if (state.aiLog.source === 'on_device') return 'Locally processed (on_device)';
  if (state.aiLog.source === 'in_cloud') return 'Cloud with permission (in_cloud)';
  return `Fail-closed (${state.aiLog.errorClass || 'blocked'})`;
}

function render() {
  const plan = adaptivePlan();
  const ev = plan.decision;
  $('checklist').innerHTML = ev.records
    .map(
      (t) =>
        `<div class="condition"><div><div class="cond-title">${h(t.label)}</div><div class="cond-why">${h(t.why || 'Added requirement; independent proof not established')}</div></div><div class="cond-controls" role="group" aria-label="Evidence for ${h(t.label)}">${[
          ['yes', 'Yes'],
          ['no', 'No'],
          ['unknown', '?'],
          ['conflict', 'Conflict'],
        ]
          .map(
            ([v, label]) =>
              `<button type="button" data-id="${h(t.id)}" data-value="${v}" aria-pressed="${t.answer === v}">${label}</button>`
          )
          .join('')}</div></div>`
    )
    .join('');

  $('checklist')
    .querySelectorAll('button')
    .forEach((b) =>
      b.addEventListener('click', () => {
        const tid = b.dataset.id;
        const val = b.dataset.value;
        state.answers[tid] = val;
        if (val !== 'unknown') {
          state.unknownConfirmedIds = state.unknownConfirmedIds.filter((x) => x !== tid);
          state.deferredIds = state.deferredIds.filter((x) => x !== tid);
        }
        log('Evidence attested', `${tid} → ${val} (by ${currentVerifier()})`);
        render();
      })
    );

  $('progressLabel').textContent = `${ev.answered} / ${ev.total} answered`;
  if ($('adaptiveSummaryPill')) $('adaptiveSummaryPill').textContent = plan.statusSummary;
  const copy = {
    YES: [
      'CONDITIONAL · HUMAN-ATTESTED',
      'All listed conditions and coverage checkboxes were self-attested by a human reviewer. Independent completeness & document authenticity are NOT cryptographically verified.',
      '',
    ],
    NO: [
      'NOT ELIGIBLE UNDER THIS POLICY',
      'At least one listed required condition has been attested false. This is only a conclusion under the chosen policy.',
      'no',
    ],
    CONFLICT: [
      'CONFLICTING EVIDENCE',
      'Contradictory statements exist in observations or source text. Resolve the conflict before accepting any positive result.',
      'conflict',
    ],
    OUT_OF_SCOPE: ['OUTSIDE THE POLICY SCOPE', 'The user has not confirmed this policy applies to the case.', 'out'],
    ASK: ['MORE INFORMATION REQUIRED', 'The current evidence is insufficient for a positive decision.', ''],
  };
  const [label, base, css] = copy[ev.status];
  const specific = ev.status === STATUS.ASK ? `${ev.missing.length} listed requirements unanswered. ${ev.blocking.join(' ')}` : base;
  $('result').className = 'result ' + css;
  $('result').innerHTML =
    `<div class="section-label">DECISION / ${h(ev.statusLabel)} · ${h(plan.statusSummary)}</div>` +
    (ev.status === STATUS.YES
      ? `<span class="cert-tag">Human-attested · NOT independently verified</span>`
      : '') +
    `<div class="state">${h(label)}</div>` +
    `<p>${h(specific)}</p>` +
    `<div class="limit">All results are conditional on the listed requirements and supplied text. Case version: ${h(plan.caseVersion)}. Verifier: ${h(currentVerifier())}. Source attestation is not cryptographic verification.</div>`;

  const procBadge = `<span class="proc-badge">${h(processingModeText())}</span>`;
  const batchHtml = plan.recommendedBatch.length
    ? `<div class="adaptive-batch">${plan.recommendedBatch
        .map((q) => {
          const cite = q.sourceCitation
            ? `<div class="adaptive-cite">${h(q.sourceCitation.sourceName)} · Line ${h(q.sourceCitation.line ?? '?')}${q.sourceCitation.startOffset >= 0 ? ` [${q.sourceCitation.startOffset}..${q.sourceCitation.endOffset}]` : ''}${q.sourceCitation.quote ? `: “${h(q.sourceCitation.quote)}”` : ''}${q.sourceCitation.quote && !q.sourceCitation.quoteVerified ? ' (unverified quote)' : ''}</div>`
            : '';
          return `<div class="adaptive-item"><b>${h(q.question)}</b><p>${h(q.why)}</p>${cite}<div class="adaptive-actions"><button type="button" class="primary tiny" data-aq-act="yes" data-aq-id="${h(q.requirementId)}" data-aq-kind="${h(q.kind)}">Yes</button><button type="button" class="outline tiny" data-aq-act="no" data-aq-id="${h(q.requirementId)}" data-aq-kind="${h(q.kind)}">No</button><button type="button" class="outline tiny" data-aq-act="dunno" data-aq-id="${h(q.requirementId)}" data-aq-kind="${h(q.kind)}">I don't know</button><button type="button" class="outline tiny" data-aq-act="skip" data-aq-id="${h(q.requirementId)}" data-aq-kind="${h(q.kind)}">Skip</button></div></div>`;
        })
        .join('')}</div>`
    : `<p>${ev.status === STATUS.YES ? 'All known and source-grounded conditions are confirmed and human-attested.' : plan.unresolvableByUser ? `Blocked cleanly (${plan.unknownConfirmedLabels.length} fact(s) marked "I don't know" — never promoted to YES).` : 'Complete scope/source/coverage attestations or check source conflicts.'}</p>`;

  const unknownNote = plan.unknownConfirmedLabels.length
    ? `<p class="smalltext">Confirmed unknown (won't re-ask): ${h(plan.unknownConfirmedLabels.join('; '))}</p>`
    : '';

  $('nextQuestion').innerHTML =
    `<b>${h(plan.statusSummary)}</b>${procBadge}` +
    (plan.nextQuestion ? `<p>Asking top ${plan.recommendedBatch.length} independent follow-up item(s):</p>` : '') +
    batchHtml +
    unknownNote;

  $('nextQuestion')
    .querySelectorAll('[data-aq-act]')
    .forEach((btn) =>
      btn.addEventListener('click', () => {
        const res = applyAdaptiveResponse(
          state.policy,
          {
            observations: state.answers,
            unknownConfirmedIds: state.unknownConfirmedIds,
            deferredIds: state.deferredIds,
            sourceText: state.sourceText,
            sourceName: state.sourceName,
            proposals: state.proposals,
            scopeAccepted: $('scopeAccepted').checked,
            sourceVerified: $('sourceVerified').checked,
            coverageReviewed: $('coverageReviewed').checked,
          },
          {
            kind: btn.dataset.aqKind,
            requirementId: btn.dataset.aqId,
            action: btn.dataset.aqAct,
          }
        );
        state.policy = res.policy;
        state.answers = res.observations;
        state.proposals = res.proposals;
        state.unknownConfirmedIds = res.unknownConfirmedIds;
        state.deferredIds = res.deferredIds;
        state.sourceAudit = res.auditResult;
        log('Adaptive follow-up', `${btn.dataset.aqId} -> ${btn.dataset.aqAct} (${res.plan.statusSummary})`);
        render();
      })
    );

  const aiSummary = state.aiLog
    ? `${state.aiLog.source} · ${state.aiLog.elapsedMs} ms · adapter: ${state.aiLog.adapterLabel || state.aiLog.modelId || 'unspecified'} · ver: ${state.aiLog.modelVersion || 'unreported'} · consent: ${state.aiLog.consentState} · err: ${state.aiLog.errorClass || 'none'}`
    : 'Not used — deterministic heuristic scan only';

  $('evidenceTrail').innerHTML =
    `<div class="trail"><b>Scope</b><br>${h(state.policy.scope)}</div>` +
    `<div class="trail"><b>Source</b><br>${h(state.sourceName)} · ${ev.sourcePresent ? 'supplied' : 'missing'}</div>` +
    `<div class="trail"><b>AI inference</b><br>${h(aiSummary)}</div>` +
    `<div class="trail"><b>Checks</b><br>${ev.answered} attested · ${ev.missing.length} missing · ${ev.conflicting.length} conflicting · ${ev.pendingReviews} unreviewed suggestions</div>`;

  $('evidenceHealth').innerHTML =
    `<span class="metric ${ev.sourcePresent ? 'pass' : 'warn'}">Source: ${ev.sourcePresent ? 'provided' : 'missing'}</span>` +
    `<span class="metric ${ev.pendingReviews === 0 ? 'pass' : 'warn'}">Review: ${ev.pendingReviews} pending</span>` +
    `<span class="metric ${ev.coverageReviewed ? 'pass' : 'warn'}">Coverage: ${ev.coverageReviewed ? 'human-attested' : 'unverified'}</span>`;

  renderProposals();
  if ($('requiredSummaryHint')) $('requiredSummaryHint').textContent = `${ev.missing.length} missing · ${ev.answered}/${ev.total} answered`;
  if ($('sourceSummaryHint')) {
    $('sourceSummaryHint').textContent = ev.sourcePresent
      ? ev.coverageReviewed
        ? 'Source provided · coverage attested'
        : 'Source provided · review pending'
      : 'Source missing';
  }
  if ($('reviewSummaryHint')) $('reviewSummaryHint').textContent = `${ev.pendingReviews} to review`;
  if ($('evidenceSummaryHint')) $('evidenceSummaryHint').textContent = `${ev.answered} answered · ${ev.pendingReviews} pending`;
  if ($('sampleSummaryHint')) $('sampleSummaryHint').textContent = `${SAMPLE_POLICIES.length} cases`;
  if ($('simpleStatus')) $('simpleStatus').textContent = `Decision status: ${ev.statusLabel} · ${plan.statusSummary}`;
  if ($('simpleProvenance')) $('simpleProvenance').textContent = `Inference provenance: ${processingModeText()}.`;
  if (pendingSimpleReveal && document.body.dataset.view === 'simple') {
    const target = $(pendingSimpleReveal);
    if (target) target.open = true;
    pendingSimpleReveal = null;
  }
}

function addRequirement(label, reason = '', reference = '') {
  const trimmed = String(label || '').trim();
  if (!trimmed || trimmed.length > 360) return false;
  if (state.policy.terms.some((x) => x.label.toLowerCase() === trimmed.toLowerCase())) return false;
  const id = 'r_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 7);
  state.policy.terms.push({ id, label: trimmed, why: String(reason).slice(0, 700), cost: 1, weight: 4, provenance: reference || 'manual' });
  state.answers[id] = 'unknown';
  invalidateAttestations({ clearSourceVerified: false, clearCoverage: true, clearAi: true });
  render();
  return true;
}

async function analyze() {
  if (state.busy) return;
  clearAnalyzeUi();
  const statusSnapshot = getHybridStatus();
  const mode = statusSnapshot.mode;
  const timeoutMs = resolveInferenceTimeoutMs(mode, statusSnapshot.deviceState);
  const timeoutSec = Math.round(timeoutMs / 1000);
  const bgDrainNote = statusSnapshot.backgroundLocalPending
    ? ' · previous cancelled Chrome turn is still draining in local queue'
    : '';
  const ticket = coordinator.beginRun({ kind: mode === 'ONLY_IN_CLOUD' ? 'cloud' : 'local' });
  state.busy = true;
  $('analyzeBtn').disabled = true;
  $('cancelAnalyzeBtn').hidden = false;
  const startedAt = Date.now();
  $('aiProgress').textContent = hybridReady()
    ? `Running ${mode} inference… 0s / ${timeoutSec}s limit (${mode === 'ONLY_ON_DEVICE' ? '0 cloud requests sent; ' : ''}weak-hardware local runs can exceed 2 min)${bgDrainNote}.`
    : 'Checking source and extracting candidates…';
  activeTickTimer = setInterval(() => {
    const secs = Math.floor((Date.now() - startedAt) / 1000);
    if (hybridReady() && state.busy && coordinator.isCurrent(ticket.runId, ticket.epoch)) {
      $('aiProgress').textContent = `Running ${mode} inference… ${secs}s / ${timeoutSec}s limit (${mode === 'ONLY_ON_DEVICE' ? '0 cloud requests sent; ' : ''}local CPU Nano can exceed 2 min)${bgDrainNote}.`;
    }
  }, 1000);
  const consentGiven = Boolean($('cloudConsent').checked);
  const scopeReq = {
    questionChars: $('question').value.length,
    sourceChars: state.sourceText.length,
    mode,
  };
  try {
    if (hybridReady()) {
      if (mode !== 'ONLY_ON_DEVICE' && !consentGiven) {
        throw new Error(
          mode === 'PREFER_ON_DEVICE'
            ? 'Allow cloud fallback or select ONLY_ON_DEVICE.'
            : 'Cloud transmission consent required.'
        );
      }
      const r = await extractWithHybrid(formulateExtractionPrompt($('question').value, state.policy, state.sourceText), {
        consentState: consentGiven,
        scopeRequest: scopeReq,
        signal: ticket.signal,
      });
      if (!coordinator.completeRun(ticket.runId, ticket.epoch)) {
        // Stale or cancelled response from an older case epoch must never mutate active state.
        return;
      }
      state.aiLog = {
        source: r.source,
        adapterLabel: r.adapterLabel,
        modelVersion: r.modelVersion,
        modelId: r.modelId,
        elapsedMs: r.elapsedMs,
        raw: r.raw,
        mode: r.mode,
        consentState: r.consentState,
        errorClass: r.errorClass,
        scopeRequest: r.scopeRequest,
      };
      saveLocalEvidence('inference', {
        source: r.source,
        adapterLabel: r.adapterLabel,
        modelVersion: r.modelVersion,
        modelId: r.modelId,
        elapsedMs: r.elapsedMs,
        raw: r.raw,
        mode: r.mode,
        consentState: r.consentState,
        errorClass: r.errorClass,
        scopeRequest: r.scopeRequest,
        decision: decisionEvidence(),
      });
      const processed = applyExtraction(state.policy, state.answers, r.parsed);
      for (const x of processed.suggestions) {
        if (!x.id) {
          enqueue({
            ...x,
            origin: 'firebase-ai-logic',
            quote: r.parsed?.suggested_checks?.find((y) => y.label === x.label)?.quote,
          });
        }
      }
      if (pending().length && document.body.dataset.view === 'simple') pendingSimpleReveal = 'source-audit-step';
      const extras = [...(r.parsed.possible_missing_categories || []), ...(r.parsed.unsupported_assumptions || [])];
      $('aiProgress').textContent = `Live Firebase inference: ${r.source} · ${r.elapsedMs}ms · adapter:${r.adapterLabel} · version:${r.modelVersion || 'unreported'} · err:${r.errorClass}; ${r.parsed.parse_error ? 'response malformed (fail-closed)' : ''}`.trim();
      log('Live AI inference', `${r.source} (${r.modelId}), ${processed.suggestions.length} proposals, ${extras.length} caution categories`);
      $('modelSuggestions').hidden = false;
      $('modelSuggestions').innerHTML = r.parsed.parse_error
        ? `<h3>AI output rejected fail-closed (${h(r.errorClass)})</h3><p>The model response violated strict JSON structure (raw output preserved in audit export). No condition was accepted or guessed.</p>`
        : `<h3>AI feedback · untrusted until reviewed</h3><p>${h(extras.join(' · ') || 'No additional categories explicitly returned')}</p>`;
    } else {
      if (!coordinator.completeRun(ticket.runId, ticket.epoch)) return;
      const audit = analyzeSourceDocument(state.sourceText, state.policy, { maxCandidates: 24, includeUnclassified: true });
      state.sourceAudit = audit;
      for (const x of audit.candidates.filter((c) => !c.matchedExisting)) enqueue(x);
      if (pending().length && document.body.dataset.view === 'simple') pendingSimpleReveal = 'source-audit-step';
      $('modelSuggestions').hidden = false;
      $('modelSuggestions').innerHTML =
        '<h3>Heuristic document scan only — no AI invoked</h3><p>The local text scanner uses non-exhaustive heuristic cues. Review each item before deciding. Connect Firebase for hybrid AI inference.</p>';
      $('aiProgress').textContent = `Deterministic document scan completed · ${audit.candidates.length} clause(s), ${audit.novelCount} novel. No LLM invoked.`;
      log('Document scan', `${audit.candidates.length} candidates (${audit.novelCount} novel)`);
    }
  } catch (err) {
    const terminal = coordinator.claimTerminalState(ticket.runId, ticket.epoch);
    if (terminal === 'stale') {
      // Stale request from an invalidated/switched case cannot modify UI or state.
      return;
    }
    const errClass = err?.errorClass || classifyInferenceError(err);
    const msg = err?.message || String(err);
    const cancellationKind =
      err?.cancellationKind ||
      (errClass === 'UserCancelledError'
        ? mode === 'ONLY_IN_CLOUD'
          ? 'real_transport_abort'
          : 'client_wait_abort_local_still_draining'
        : null);
    state.aiLog = {
      source: 'BLOCKED_OR_FAILED',
      adapterLabel: mode === 'ONLY_ON_DEVICE' ? 'chrome-prompt-api-adapter' : 'firebase-ai-cloud',
      modelVersion: null,
      modelId: null,
      elapsedMs: err?.elapsedMs || 0,
      raw: err?.raw ?? null,
      mode,
      consentState: consentGiven,
      errorClass: errClass,
      cancellationKind,
      scopeRequest: scopeReq,
    };
    saveLocalEvidence('inference', {
      source: state.aiLog.source,
      adapterLabel: state.aiLog.adapterLabel,
      modelVersion: state.aiLog.modelVersion,
      modelId: state.aiLog.modelId,
      elapsedMs: state.aiLog.elapsedMs,
      raw: state.aiLog.raw,
      mode: state.aiLog.mode,
      consentState: state.aiLog.consentState,
      errorClass: state.aiLog.errorClass,
      cancellationKind: state.aiLog.cancellationKind,
      scopeRequest: state.aiLog.scopeRequest,
      error: msg,
      decision: decisionEvidence(),
    });
    $('aiProgress').textContent = `Inference blocked/failed [${errClass}]: ${msg}`;
    if (['ModelTimeoutError', 'UserCancelledError', 'OnDeviceSessionError', 'OnDeviceUnavailableError', 'ConsentRequiredError'].includes(errClass)) {
      const cloudNote =
        mode === 'ONLY_ON_DEVICE'
          ? errClass === 'UserCancelledError'
            ? 'Client stopped waiting safely (epoch-fenced; 0 cloud requests sent). Note: Chrome @firebase/ai does not interrupt an already-dispatched local Nano turn mid-generation, so that old turn drains silently and cannot mutate any new case. To optionally use fast Cloud AI instead, reload and choose PREFER_ON_DEVICE or ONLY_IN_CLOUD with explicit cloud consent.'
            : 'ONLY_ON_DEVICE guarantees 0 cloud requests were sent. Deterministic checks remain active; to optionally allow Cloud AI instead, reload and choose a cloud-capable mode with explicit consent.'
          : errClass === 'UserCancelledError'
          ? 'Aborted cleanly (HTTP AbortSignal sent on cloud fetch). You can continue with deterministic checks or open settings to review inference mode and explicit cloud consent.'
          : 'You can continue with deterministic checks or open settings to review inference mode and explicit cloud consent.';
      $('modelSuggestions').hidden = false;
      $('modelSuggestions').innerHTML = `<h3>Stopped safely (${h(errClass)})</h3><p>${h(cloudNote)}</p><div class="actions"><button type="button" class="outline tiny" data-open-settings="1">Open Firebase &amp; consent settings</button></div>`;
      $('modelSuggestions').querySelector('[data-open-settings]')?.addEventListener('click', () => {
        $('envHint').hidden = !Object.keys(envConfig()).length;
        $('settingsDialog').showModal();
      });
    }
    log('AI error', `[${errClass}] ${msg}`);
  } finally {
    if (!coordinator.getState().activeRunId) {
      clearAnalyzeUi();
    }
    render();
  }
}

function exportAudit() {
  const ev = decision();
  const snapshot = {
    exportedAt: new Date().toISOString(),
    app: 'GAPWISE',
    version: '1.0.0',
    kind: 'human-attested-policy-check',
    certificationTier: ev.certificationTier,
    independentVerification: false,
    firebase: getHybridStatus(),
    question: $('question').value,
    policy: state.policy,
    source: {
      name: state.sourceName,
      text: state.sourceText,
      sourceVerified: $('sourceVerified').checked,
      coverageReviewed: $('coverageReviewed').checked,
      attestation: {
        verifier: currentVerifier(),
        sourceVerifiedAt: state.attestations.sourceVerifiedAt,
        coverageReviewedAt: state.attestations.coverageReviewedAt,
        caseVersion: computeCaseVersion(state.policy, state.sourceText),
        verificationLevel: 'human-self-attested-not-cryptographic',
      },
      scannerSummary: state.sourceAudit
        ? {
            novelCount: state.sourceAudit.novelCount,
            truncatedCount: state.sourceAudit.truncatedCount,
            truncatedByCharLimit: state.sourceAudit.truncatedByCharLimit,
            externalReferenceCount: state.sourceAudit.externalReferenceCount,
            unclassifiedCount: state.sourceAudit.unclassifiedCount,
            conflictSignals: state.sourceAudit.conflictSignals,
          }
        : null,
    },
    observations: state.answers,
    unknownConfirmedIds: state.unknownConfirmedIds,
    deferredIds: state.deferredIds,
    proposals: state.proposals,
    decision: ev,
    events: state.history,
    ai: state.aiLog,
    disclaimer: 'This export is a conditional human-attested record. Neither source authenticity nor ontology completeness is proved.',
  };
  const blob = new Blob([JSON.stringify(snapshot, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `gapwise_audit_${Date.now()}.json`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 3000);
  log('Audit exported', `${ev.statusLabel} (by ${currentVerifier()})`);
  $('exportStatus').textContent = `Exported transparent audit JSON (${ev.statusLabel}).`;
}

$('addConditionBtn').addEventListener('click', () => {
  if (addRequirement($('extraCondition').value, 'Added manually')) {
    $('extraCondition').value = '';
    log('Requirement manually added', 'New unknown condition');
  }
});
$('analyzeBtn').addEventListener('click', analyze);
$('cancelAnalyzeBtn').addEventListener('click', () => {
  coordinator.cancelActive('user_cancelled');
});
$('exportBtn').addEventListener('click', exportAudit);
$('scopeAccepted').addEventListener('change', () => {
  invalidateAttestations({ clearSourceVerified: false, clearCoverage: true, reason: 'Scope changed' });
  log('Scope attestation', String($('scopeAccepted').checked));
  render();
});
$('sourceVerified').addEventListener('change', () => {
  const checked = $('sourceVerified').checked;
  state.attestations.sourceVerifiedAt = checked ? new Date().toISOString() : null;
  state.attestations.sourceVerifiedBy = checked ? currentVerifier() : null;
  log('Source attestation', `${checked} (by ${currentVerifier()})`);
  render();
});
$('coverageReviewed').addEventListener('change', () => {
  const checked = $('coverageReviewed').checked;
  state.attestations.coverageReviewedAt = checked ? new Date().toISOString() : null;
  state.attestations.coverageReviewedBy = checked ? currentVerifier() : null;
  log('Coverage review', `${checked} (by ${currentVerifier()})`);
  render();
});
$('sourceText').addEventListener('input', () => {
  setSource($('sourceText').value, $('sourceNameInput').value.trim() || 'user pasted source');
});
$('sourceNameInput').addEventListener('input', () => {
  state.sourceName = $('sourceNameInput').value.trim() || 'user-named';
  invalidateAttestations({ clearSourceVerified: true, clearCoverage: true, clearAi: true, reason: 'Source name modified' });
  render();
});
$('sourceFile').addEventListener('change', async () => {
  const file = $('sourceFile').files?.[0];
  if (!file) return;
  if (file.size > 80_000 || !/\.(txt|md)$/i.test(file.name)) {
    $('sourceFile').value = '';
    $('aiProgress').textContent = 'Only UTF-8 .txt/.md files below 80KB are supported.';
    return;
  }
  let text = '';
  try {
    const bytes = new Uint8Array(await file.arrayBuffer());
    if (bytes.includes(0)) throw new Error('binary null byte');
    text = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
  } catch {
    $('sourceFile').value = '';
    $('aiProgress').textContent = 'Uploaded file is binary or invalid UTF-8 and was rejected.';
    return;
  }
  text = text.slice(0, 35000);
  $('sourceText').value = text;
  setSource(text, file.name);
});
$('loadSampleSourceBtn').addEventListener('click', () => {
  const text = DOCUMENTS[state.policy.id] || '';
  $('sourceText').value = text;
  setSource(text, 'fictional sample document');
  $('sourceDetails').open = true;
});
$('settingsBtn').addEventListener('click', () => {
  const cfg = envConfig();
  const hint = $('envHint');
  if (cfg.projectId) {
    hint.hidden = false;
    hint.textContent = `Build environment config detected for project "${cfg.projectId}" (leave JSON blank to use it).`;
  } else {
    hint.hidden = true;
  }
  $('settingsDialog').showModal();
});
$('settingsDialog').addEventListener('close', () => {
  if (!hybridReady() && $('connectStatus').textContent.includes('Initializing')) {
    $('connectStatus').textContent = '';
  }
  $('settingsBtn').focus();
});
$('cloudConsent').addEventListener('change', () => {
  log('Cloud consent updated', String($('cloudConsent').checked));
  if (!$('cloudConsent').checked && hybridReady() && getHybridStatus().mode !== 'ONLY_ON_DEVICE') {
    invalidateAttestations({ clearCoverage: false, clearAi: true, reason: 'Cloud consent revoked' });
    render();
  }
});
$('connectBtn').addEventListener('click', async () => {
  const btn = $('connectBtn');
  const el = $('connectStatus');
  btn.disabled = true;
  el.textContent = 'Initializing SDK and App Check…';
  try {
    const input = $('firebaseConfig').value.trim();
    const cfg = input ? JSON.parse(input) : envConfig();
    const site = $('appCheckKey').value.trim() || envAppCheckKey();
    const mode = $('inferenceMode').value;
    const r = await connectHybrid(cfg, site, { mode });
    $('modeBadge').textContent = `● LIVE FIREBASE ${mode}`;
    $('modeBadge').classList.add('live');
    el.textContent =
      mode === 'ONLY_IN_CLOUD'
        ? `Connected to project ${r.projectId}; App Check configured: ${r.appCheckConfigured} (${r.appCheckProvider}). Mode is ONLY_IN_CLOUD (reload page to switch project or mode).`
        : `Connected to project ${r.projectId}; App Check configured: ${r.appCheckConfigured} (${r.appCheckProvider}). On-device model not yet initialized (reload page to switch project or mode).`;
    $('enableDeviceBtn').hidden = mode === 'ONLY_IN_CLOUD';
    log('Firebase connected', `${r.projectId} · ${mode} · AppCheck:${r.appCheckProvider}`);
    saveLocalEvidence('firebase_connect', {
      connected: true,
      projectId: r.projectId,
      mode,
      appCheckConfigured: r.appCheckConfigured,
      appCheckProvider: r.appCheckProvider,
    });
  } catch (err) {
    btn.disabled = false;
    const msg = String(err?.message || err);
    el.textContent = `Connection failed: ${msg}`;
    log('Connection failed', msg);
    saveLocalEvidence('firebase_connect', { connected: false, mode: $('inferenceMode').value, error: msg });
  }
});
$('enableDeviceBtn').addEventListener('click', () => {
  const el = $('connectStatus');
  const startedAt = performance.now();
  let downloadProgress = 0;
  el.textContent = 'Initializing device model…';
  try {
    // No await before preparing device model: user activation is required.
    const promise = prepareDeviceModel((p) => {
      downloadProgress = Math.max(downloadProgress, Number(p) || 0);
      el.textContent = `Downloading local model: ${Math.round(p * 100)}%`;
    });
    Promise.resolve(promise)
      .then((res) => {
        if (res?.ready) {
          el.textContent = 'On-device model ready.';
          log('Device model', 'ready');
          saveLocalEvidence('device_model', {
            ready: true,
            availability: res.availability || 'ready',
            downloadProgress,
            elapsedMs: Math.round(performance.now() - startedAt),
            mode: getHybridStatus().mode,
            deviceState: getHybridStatus().deviceState,
          });
        } else {
          el.textContent = `On-device unavailable (${res?.availability || 'unavailable'}). Cloud fallback only with consent.`;
          log('Device model', `unavailable (${res?.availability || 'unavailable'})`);
          saveLocalEvidence('device_model', {
            ready: false,
            availability: res?.availability || 'unavailable',
            downloadProgress,
            elapsedMs: Math.round(performance.now() - startedAt),
            mode: getHybridStatus().mode,
            deviceState: getHybridStatus().deviceState,
          });
        }
      })
      .catch((err) => {
        const msg = String(err?.message || err).replace(/\.+$/, '');
        el.textContent = `On-device unavailable: ${msg}.`;
        log('Device model', 'unavailable');
        saveLocalEvidence('device_model', {
          ready: false,
          availability: 'unavailable',
          downloadProgress,
          elapsedMs: Math.round(performance.now() - startedAt),
          mode: getHybridStatus().mode,
          deviceState: getHybridStatus().deviceState,
          error: msg,
          errorClass: classifyInferenceError(err),
        });
      });
  } catch (err) {
    const msg = String(err?.message || err);
    el.textContent = `Device error: ${msg}`;
    saveLocalEvidence('device_model', {
      ready: false,
      availability: 'unavailable',
      downloadProgress,
      elapsedMs: Math.round(performance.now() - startedAt),
      mode: getHybridStatus().mode,
      deviceState: getHybridStatus().deviceState,
      error: msg,
      errorClass: classifyInferenceError(err),
    });
  }
});
$('customCaseBtn').addEventListener('click', () => {
  fenceNewCase('custom_case_started');
  state.index = -1;
  state.policy = {
    id: 'custom',
    title: 'My own evidence review',
    tag: 'Custom',
    scope: 'User supplied policy; applicability has not been independently verified',
    source: 'User supplied source',
    question: 'Can I proceed with this request?',
    terms: [{ id: 'applicability', label: 'This policy actually applies to this case', why: 'Confirm scope and applicable source', cost: 1, weight: 5 }],
  };
  state.answers = {};
  state.unknownConfirmedIds = [];
  state.deferredIds = [];
  state.proposals = [];
  state.sourceText = '';
  state.sourceName = 'none';
  state.sourceAudit = null;
  state.aiLog = null;
  state.history = [];
  state.attestations = { sourceVerifiedAt: null, sourceVerifiedBy: null, coverageReviewedAt: null, coverageReviewedBy: null, caseVersion: null };
  $('sourceText').value = '';
  $('sourceNameInput').value = '';
  $('sourceFile').value = '';
  $('sourceVerified').checked = false;
  $('coverageReviewed').checked = false;
  $('scopeAccepted').checked = false;
  $('question').value = state.policy.question;
  $('modelSuggestions').hidden = true;
  $('aiProgress').textContent = 'Deterministic assessment ready. Connect Firebase for real model suggestions.';
  $('sourceLabel').textContent = 'Custom source · no independent verification';
  renderExamples();
  log('Custom case', 'started');
  render();
});
$('question').addEventListener('input', () => {
  invalidateAttestations({
    clearSourceVerified: true,
    clearCoverage: true,
    clearAi: true,
    reason: 'Question edited',
  });
  render();
});

function syncConnectivityBanner() {
  const badge = $('modeBadge');
  if (!badge) return;
  if (!navigator.onLine) {
    badge.textContent = '● OFFLINE · LOCAL GATE ONLY';
    badge.classList.remove('live');
    if (!state.aiLog) {
      $('aiProgress').textContent = 'Offline detected: Cloud AI is unavailable; deterministic source checks and local gate work without network.';
    }
  } else if (hybridReady()) {
    badge.textContent = `● LIVE FIREBASE ${getHybridStatus().mode}`;
    badge.classList.add('live');
  } else {
    badge.textContent = '● DETERMINISTIC DEMO';
    badge.classList.remove('live');
  }
}

window.addEventListener('offline', () => {
  log('Network offline', 'Cloud AI paused; local deterministic gate active');
  syncConnectivityBanner();
});
window.addEventListener('online', () => {
  log('Network online', 'Connectivity restored');
  syncConnectivityBanner();
});

// The navigation controller only changes presentation. Decision, evidence,
// consent, and export state continue to be owned by the existing workbench.
const navToggle = $('navToggle');
const appNav = $('appNav');
const navScrim = $('navScrim');
let navRestoreFocus = null;
const mobileNavQuery = window.matchMedia('(max-width: 760px)');
const navFocusable = () => Array.from(appNav?.querySelectorAll('button:not([disabled]), a[href], input:not([disabled]), [tabindex]:not([tabindex="-1"])') || []);

function isMobileNav() {
  return mobileNavQuery.matches;
}

function syncNavMode() {
  if (isMobileNav()) {
    document.body.classList.remove('nav-collapsed');
    document.body.classList.remove('nav-open');
    navToggle?.setAttribute('aria-expanded', 'false');
    navToggle?.setAttribute('aria-label', 'Open navigation');
    navScrim?.setAttribute('aria-hidden', 'true');
    return;
  }
  document.body.classList.remove('nav-open');
  const collapsed = document.body.classList.contains('nav-collapsed');
  navToggle?.setAttribute('aria-expanded', String(!collapsed));
  navToggle?.setAttribute('aria-label', collapsed ? 'Expand navigation' : 'Collapse navigation');
  navScrim?.setAttribute('aria-hidden', 'true');
}

function setMobileNav(open, restoreFocus = true) {
  if (!isMobileNav()) return;
  if (open) {
    navRestoreFocus = document.activeElement;
    document.body.classList.add('nav-open');
    navScrim?.setAttribute('aria-hidden', 'false');
    navToggle?.setAttribute('aria-expanded', 'true');
    navToggle?.setAttribute('aria-label', 'Close navigation');
    requestAnimationFrame(() => navFocusable()[0]?.focus());
  } else {
    document.body.classList.remove('nav-open');
    navScrim?.setAttribute('aria-hidden', 'true');
    navToggle?.setAttribute('aria-expanded', 'false');
    navToggle?.setAttribute('aria-label', 'Open navigation');
    if (restoreFocus && navRestoreFocus instanceof HTMLElement) navRestoreFocus.focus();
  }
}

navToggle?.addEventListener('click', () => {
  if (isMobileNav()) {
    setMobileNav(!document.body.classList.contains('nav-open'));
    return;
  }
  const collapsed = document.body.classList.toggle('nav-collapsed');
  navToggle.setAttribute('aria-expanded', String(!collapsed));
  navToggle.setAttribute('aria-label', collapsed ? 'Expand navigation' : 'Collapse navigation');
});

navScrim?.addEventListener('click', () => setMobileNav(false));

document.querySelectorAll('[data-nav-target]').forEach((control) => {
  control.addEventListener('click', () => {
    const selector = control.getAttribute('data-nav-target');
    const target = selector ? document.querySelector(selector) : null;
    if (!target) return;
    if (!isMobileNav() && control.closest('.nav-item') && document.body.classList.contains('nav-collapsed')) {
      document.body.classList.remove('nav-collapsed');
      navToggle?.setAttribute('aria-expanded', 'true');
      navToggle?.setAttribute('aria-label', 'Collapse navigation');
    }
    if (target === $('sourceDetails')) target.open = true;
    target.scrollIntoView({
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
      block: 'start',
    });
    if (target instanceof HTMLElement && target.id === 'workbench') target.focus({ preventScroll: true });
    const navItem = control.closest('.nav-item');
    if (navItem) {
      document.querySelectorAll('.nav-item[aria-current="page"]').forEach((item) => item.removeAttribute('aria-current'));
      navItem.setAttribute('aria-current', 'page');
    }
    if (isMobileNav()) setMobileNav(false);
  });
});

document.querySelectorAll('[data-nav-action="settings"]').forEach((control) => {
  control.addEventListener('click', () => {
    $('settingsBtn')?.click();
    if (isMobileNav()) setMobileNav(false);
  });
});

$('examples')?.addEventListener('click', () => {
  if (isMobileNav()) setMobileNav(false);
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && isMobileNav() && document.body.classList.contains('nav-open')) {
    event.preventDefault();
    setMobileNav(false);
    return;
  }
  if (event.key !== 'Tab' || !isMobileNav() || !document.body.classList.contains('nav-open')) return;
  const items = navFocusable();
  if (!items.length) return;
  const first = items[0];
  const last = items[items.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
});

mobileNavQuery.addEventListener?.('change', syncNavMode);
syncNavMode();

const VIEW_STORAGE_KEY = 'gapwise.ui.view';
const viewSimpleBtn = $('viewSimpleBtn');
const viewAdvancedBtn = $('viewAdvancedBtn');

function readSavedView() {
  try {
    return window.localStorage.getItem(VIEW_STORAGE_KEY) === 'simple' ? 'simple' : 'advanced';
  } catch {
    return 'advanced';
  }
}

function saveView(view) {
  try {
    window.localStorage.setItem(VIEW_STORAGE_KEY, view);
  } catch {
    // Storage can be disabled by privacy settings; the current session still works.
  }
}

function syncAccordionA11y(details) {
  details.querySelector(':scope > summary')?.setAttribute('aria-expanded', String(details.open));
}

function applyViewMode(view, { persist = true, announce = true } = {}) {
  const next = view === 'simple' ? 'simple' : 'advanced';
  const previous = document.body.dataset.view || 'advanced';
  document.body.dataset.view = next;
  syncNavMode();
  viewSimpleBtn?.setAttribute('aria-pressed', String(next === 'simple'));
  viewAdvancedBtn?.setAttribute('aria-pressed', String(next === 'advanced'));
  viewSimpleBtn?.classList.toggle('active', next === 'simple');
  viewAdvancedBtn?.classList.toggle('active', next === 'advanced');
  if (persist) saveView(next);
  if (previous !== next) {
    document.querySelectorAll('.simple-accordion').forEach((details) => {
      details.open = next === 'advanced';
    });
  }
  document.querySelectorAll('.simple-accordion').forEach(syncAccordionA11y);
  if (announce && $('viewModeStatus')) $('viewModeStatus').textContent = `${next === 'simple' ? 'Simple' : 'Advanced'} interface selected.`;
}

document.querySelectorAll('.simple-accordion').forEach((details) => {
  syncAccordionA11y(details);
  details.addEventListener('toggle', () => syncAccordionA11y(details));
});
viewSimpleBtn?.addEventListener('click', () => applyViewMode('simple'));
viewAdvancedBtn?.addEventListener('click', () => applyViewMode('advanced'));
applyViewMode(readSavedView(), { persist: false, announce: false });

reset(0);
syncConnectivityBanner();
