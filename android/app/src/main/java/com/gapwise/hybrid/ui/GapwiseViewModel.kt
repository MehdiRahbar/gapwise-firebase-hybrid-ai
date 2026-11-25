package com.gapwise.hybrid.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gapwise.hybrid.ai.HybridAiRepository
import com.gapwise.hybrid.engine.AdaptivePlan
import com.gapwise.hybrid.engine.AnswerValue
import com.gapwise.hybrid.engine.DecisionEngine
import com.gapwise.hybrid.engine.DecisionResult
import com.gapwise.hybrid.engine.EvaluationOptions
import com.gapwise.hybrid.engine.GroundingStatus
import com.gapwise.hybrid.engine.HybridAiLog
import com.gapwise.hybrid.engine.InferenceModeChoice
import com.gapwise.hybrid.engine.OnDeviceModelOptionChoice
import com.gapwise.hybrid.engine.PolicyScenario
import com.gapwise.hybrid.engine.PolicyTerm
import com.gapwise.hybrid.engine.ProposalDecision
import com.gapwise.hybrid.engine.ProposalItem
import com.gapwise.hybrid.engine.SamplePolicies
import com.gapwise.hybrid.engine.SourceAuditResult
import com.gapwise.hybrid.engine.SourceAuditor
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.time.Instant

data class GapwiseUiState(
    val scenarioIndex: Int = 0,
    val policy: PolicyScenario = SamplePolicies.ALL.first(),
    val question: String = SamplePolicies.ALL.first().question,
    val observations: Map<String, AnswerValue> = emptyMap(),
    val sourceName: String = "none",
    val sourceText: String = "",
    val verifierName: String = "",
    val scopeAccepted: Boolean = true,
    val sourceVerified: Boolean = false,
    val coverageReviewed: Boolean = false,
    val sourceAudit: SourceAuditResult? = null,
    val proposals: List<ProposalItem> = emptyList(),
    val unknownConfirmedIds: Set<String> = emptySet(),
    val deferredIds: Set<String> = emptySet(),
    val decision: DecisionResult = DecisionEngine.evaluateStrict(
        SamplePolicies.ALL.first(),
        emptyMap(),
        EvaluationOptions()
    ),
    val adaptivePlan: AdaptivePlan = DecisionEngine.buildAdaptivePlan(SamplePolicies.ALL.first()),
    val inferenceMode: InferenceModeChoice = InferenceModeChoice.PREFER_ON_DEVICE,
    val onDeviceModelOption: OnDeviceModelOptionChoice = OnDeviceModelOptionChoice.PREVIEW,
    val cloudConsent: Boolean = false,
    val isInferring: Boolean = false,
    val aiStatusText: String = "Deterministic audit ready. Configure mode & run hybrid inference.",
    val onDeviceStatusText: String = "Not checked yet",
    val aiLog: HybridAiLog? = null,
    val activeEpoch: Int = 0
)

@Serializable
data class AndroidAuditExport(
    val exportedAt: String,
    val app: String = "GAPWISE-Android",
    val question: String,
    val policyId: String,
    val decisionStatus: String,
    val certificationTier: String?,
    val independentVerification: Boolean,
    val sourceVerified: Boolean,
    val coverageReviewed: Boolean,
    val verifier: String,
    val inferenceSource: String?,
    val modelVersion: String?,
    val consentGranted: Boolean,
    val observations: Map<String, String>,
    val unverifiedSuggestionCount: Int
)

class GapwiseViewModel(
    private val aiRepository: HybridAiRepository? = null
) : ViewModel() {

    private val _uiState = MutableStateFlow(GapwiseUiState())
    val uiState: StateFlow<GapwiseUiState> = _uiState.asStateFlow()

    private var activeJob: Job? = null
    private var runSeq: Long = 0

    fun selectScenario(index: Int) {
        val policy = SamplePolicies.ALL.getOrElse(index) { SamplePolicies.ALL.first() }
        invalidateInFlight("Switched scenario")
        _uiState.update { cur ->
            val next = cur.copy(
                scenarioIndex = index,
                policy = policy,
                question = policy.question,
                observations = emptyMap(),
                unknownConfirmedIds = emptySet(),
                deferredIds = emptySet(),
                sourceName = "none",
                sourceText = "",
                scopeAccepted = true,
                sourceVerified = false,
                coverageReviewed = false,
                sourceAudit = null,
                proposals = emptyList(),
                aiLog = null,
                aiStatusText = "Loaded ${policy.title}. Paste policy text or load sample document."
            )
            recomputeDecision(next)
        }
    }

    fun loadSampleDocument() {
        val sample = _uiState.value.policy.sampleSourceText
        updateSourceText(sample, name = "fictional sample document")
    }

    fun updateQuestion(question: String) {
        invalidateInFlight("Question edited")
        _uiState.update { cur ->
            recomputeDecision(
                cur.copy(
                    question = question,
                    sourceVerified = false,
                    coverageReviewed = false,
                    aiLog = null
                )
            )
        }
    }

    fun updateSourceText(text: String, name: String? = null) {
        invalidateInFlight("Source edited")
        _uiState.update { cur ->
            val audit = if (text.isBlank()) {
                null
            } else {
                SourceAuditor.analyzeSourceDocument(text, cur.policy, maxCandidates = 24, includeUnclassified = true)
            }
            val proposals = audit?.candidates
                ?.filter { !it.matchedExisting }
                ?.mapIndexed { idx, cand ->
                    ProposalItem(
                        uid = "scan_${cur.activeEpoch}_$idx",
                        label = cand.label,
                        reason = cand.reason,
                        origin = cand.origin,
                        cueType = cand.cueType,
                        line = cand.line,
                        quote = cand.quote,
                        quoteVerified = SourceAuditor.validateSourceQuote(cand.quote, text),
                        groundingStatus = if (SourceAuditor.validateSourceQuote(cand.quote, text)) {
                            GroundingStatus.EXACT_QUOTE_VERIFIED
                        } else {
                            GroundingStatus.UNVERIFIED_SUGGESTION
                        }
                    )
                }.orEmpty()
            recomputeDecision(
                cur.copy(
                    sourceText = text,
                    sourceName = name ?: cur.sourceName,
                    sourceVerified = false,
                    coverageReviewed = false,
                    unknownConfirmedIds = emptySet(),
                    deferredIds = emptySet(),
                    sourceAudit = audit,
                    proposals = proposals,
                    aiLog = null
                )
            )
        }
    }

    fun setAnswer(termId: String, value: AnswerValue) {
        _uiState.update { cur ->
            val nextObs = cur.observations.toMutableMap().apply { put(termId, value) }
            val nextUnknown = if (value != AnswerValue.UNKNOWN) cur.unknownConfirmedIds - termId else cur.unknownConfirmedIds
            val nextDeferred = if (value != AnswerValue.UNKNOWN) cur.deferredIds - termId else cur.deferredIds
            recomputeDecision(cur.copy(observations = nextObs, unknownConfirmedIds = nextUnknown, deferredIds = nextDeferred))
        }
    }

    fun respondToAdaptiveQuestion(requirementId: String, kind: String, action: String) {
        _uiState.update { cur ->
            val act = action.trim().lowercase()
            if (kind == "term") {
                return@update when (act) {
                    "skip", "defer" -> recomputeDecision(cur.copy(deferredIds = cur.deferredIds + requirementId))
                    "dunno", "unknown" -> {
                        val nextObs = cur.observations.toMutableMap().apply { put(requirementId, AnswerValue.UNKNOWN) }
                        recomputeDecision(
                            cur.copy(
                                observations = nextObs,
                                unknownConfirmedIds = cur.unknownConfirmedIds + requirementId,
                                deferredIds = cur.deferredIds - requirementId
                            )
                        )
                    }
                    "yes", "no", "conflict" -> {
                        val ans = AnswerValue.fromWire(act)
                        val nextObs = cur.observations.toMutableMap().apply { put(requirementId, ans) }
                        recomputeDecision(
                            cur.copy(
                                observations = nextObs,
                                unknownConfirmedIds = cur.unknownConfirmedIds - requirementId,
                                deferredIds = cur.deferredIds - requirementId
                            )
                        )
                    }
                    else -> cur
                }
            }

            if (kind == "discovered-clause" || kind == "ai-proposal") {
                val target = cur.proposals.firstOrNull { it.uid == requirementId } ?: return@update cur
                if (act == "skip" || act == "defer") {
                    return@update recomputeDecision(cur.copy(deferredIds = cur.deferredIds + requirementId))
                }
                if (act in listOf("yes", "no", "conflict", "dunno", "unknown")) {
                    val nextId = "src_${cur.policy.terms.size + 1}"
                    val ans = if (act == "dunno" || act == "unknown") AnswerValue.UNKNOWN else AnswerValue.fromWire(act)
                    val updatedTerms = if (cur.policy.terms.any { it.label.equals(target.label, ignoreCase = true) }) {
                        cur.policy.terms
                    } else {
                        cur.policy.terms + PolicyTerm(id = nextId, label = target.label, why = target.reason, cost = 1, weight = 5)
                    }
                    val nextObs = cur.observations.toMutableMap().apply { put(nextId, ans) }
                    val updatedProposals = cur.proposals.map {
                        if (it.uid == requirementId) it.copy(decision = ProposalDecision.ADDED) else it
                    }
                    val nextUnknown = if (ans == AnswerValue.UNKNOWN) cur.unknownConfirmedIds + requirementId + nextId else cur.unknownConfirmedIds - requirementId
                    val reAudited = if (cur.sourceText.isNotBlank()) {
                        SourceAuditor.analyzeSourceDocument(cur.sourceText, cur.policy.copy(terms = updatedTerms), maxCandidates = 24, includeUnclassified = true)
                    } else cur.sourceAudit
                    return@update recomputeDecision(
                        cur.copy(
                            policy = cur.policy.copy(terms = updatedTerms),
                            observations = nextObs,
                            proposals = updatedProposals,
                            unknownConfirmedIds = nextUnknown,
                            deferredIds = cur.deferredIds - requirementId,
                            sourceAudit = reAudited
                        )
                    )
                }
            }
            cur
        }
    }

    fun addExtraCondition(rawLabel: String) {
        val clean = rawLabel.trim().take(240)
        if (clean.isEmpty()) return
        _uiState.update { cur ->
            val id = "extra_${cur.policy.terms.size + 1}"
            val updatedTerms = cur.policy.terms + PolicyTerm(
                id = id,
                label = clean,
                why = "Manually added condition",
                cost = 1,
                weight = 5
            )
            recomputeDecision(
                cur.copy(
                    policy = cur.policy.copy(terms = updatedTerms),
                    coverageReviewed = false
                )
            )
        }
    }

    fun approveProposalAsUnknown(uid: String) {
        _uiState.update { cur ->
            val target = cur.proposals.firstOrNull { it.uid == uid } ?: return@update cur
            val updatedProposals = cur.proposals.map {
                if (it.uid == uid) it.copy(decision = ProposalDecision.ADDED) else it
            }
            val nextId = "src_${cur.policy.terms.size + 1}"
            // Even added requirements start UNKNOWN — never auto-confirmed YES.
            val updatedTerms = cur.policy.terms + PolicyTerm(
                id = nextId,
                label = target.label,
                why = target.reason,
                cost = 1,
                weight = 5
            )
            recomputeDecision(
                cur.copy(
                    policy = cur.policy.copy(terms = updatedTerms),
                    proposals = updatedProposals,
                    coverageReviewed = false
                )
            )
        }
    }

    fun dismissProposal(uid: String, reason: String) {
        val cleanReason = reason.trim()
        if (cleanReason.length < 8) return
        _uiState.update { cur ->
            val updated = cur.proposals.map {
                if (it.uid == uid) it.copy(decision = ProposalDecision.DISMISSED, dismissReason = cleanReason) else it
            }
            recomputeDecision(cur.copy(proposals = updated))
        }
    }

    fun setScopeAccepted(value: Boolean) {
        _uiState.update { cur ->
            recomputeDecision(cur.copy(scopeAccepted = value, coverageReviewed = if (!value) false else cur.coverageReviewed))
        }
    }

    fun setSourceVerified(value: Boolean) {
        _uiState.update { cur -> recomputeDecision(cur.copy(sourceVerified = value)) }
    }

    fun setCoverageReviewed(value: Boolean) {
        _uiState.update { cur -> recomputeDecision(cur.copy(coverageReviewed = value)) }
    }

    fun setInferenceMode(mode: InferenceModeChoice) {
        _uiState.update { it.copy(inferenceMode = mode) }
    }

    fun setOnDeviceModelOption(option: OnDeviceModelOptionChoice) {
        _uiState.update { it.copy(onDeviceModelOption = option) }
    }

    fun setCloudConsent(consent: Boolean) {
        _uiState.update { it.copy(cloudConsent = consent) }
    }

    fun checkOnDeviceCapability() {
        val repo = aiRepository ?: return
        val opt = _uiState.value.onDeviceModelOption
        viewModelScope.launch {
            val status = repo.checkOnDeviceStatus(opt)
            _uiState.update { it.copy(onDeviceStatusText = status) }
        }
    }

    fun downloadOnDeviceModel() {
        val repo = aiRepository ?: return
        val opt = _uiState.value.onDeviceModelOption
        viewModelScope.launch {
            _uiState.update { it.copy(onDeviceStatusText = "Starting AICore download/warm-up [${opt.name}]...") }
            val result = repo.downloadOnDeviceModel(opt) { progressText ->
                _uiState.update { it.copy(onDeviceStatusText = progressText) }
            }
            _uiState.update { it.copy(onDeviceStatusText = result) }
        }
    }

    fun runHybridInference() {
        val repo = aiRepository ?: return
        val snapshot = _uiState.value
        val epoch = snapshot.activeEpoch
        runSeq += 1
        val currentRunId = runSeq
        activeJob?.cancel()

        _uiState.update {
            it.copy(
                isInferring = true,
                aiStatusText = "Running Firebase AI Logic (${snapshot.inferenceMode.name} · ${snapshot.onDeviceModelOption.name})..."
            )
        }
        activeJob = viewModelScope.launch {
            try {
                val outcome = repo.extractMissingRequirements(
                    policy = snapshot.policy,
                    question = snapshot.question,
                    sourceText = snapshot.sourceText,
                    modeChoice = snapshot.inferenceMode,
                    cloudConsent = snapshot.cloudConsent,
                    modelOptionChoice = snapshot.onDeviceModelOption
                )
                // Epoch & run fencing prevents stale responses from mutating switched cases.
                _uiState.update { cur ->
                    if (cur.activeEpoch != epoch || runSeq != currentRunId) return@update cur
                    val aiProposals = outcome.checks.mapIndexed { idx, chk ->
                        val verified = HybridAiRepository.validateProposalGrounding(chk.quote, cur.sourceText)
                        ProposalItem(
                            uid = "ai_${epoch}_${currentRunId}_$idx",
                            label = chk.label.trim(),
                            reason = chk.reason.ifBlank { "AI suggestion (untrusted until reviewed)" },
                            origin = "firebase-ai-logic",
                            cueType = "ai",
                            line = null,
                            quote = chk.quote.trim(),
                            quoteVerified = verified,
                            groundingStatus = if (verified) {
                                GroundingStatus.EXACT_QUOTE_VERIFIED
                            } else {
                                GroundingStatus.UNVERIFIED_SUGGESTION
                            }
                        )
                    }
                    recomputeDecision(
                        cur.copy(
                            isInferring = false,
                            proposals = cur.proposals + aiProposals,
                            coverageReviewed = false,
                            aiLog = outcome.log,
                            aiStatusText = outcome.log.message
                        )
                    )
                }
            } catch (ce: CancellationException) {
                throw ce
            } catch (err: Exception) {
                _uiState.update { cur ->
                    if (cur.activeEpoch != epoch || runSeq != currentRunId) return@update cur
                    cur.copy(
                        isInferring = false,
                        aiStatusText = "Blocked/Failed [${err::class.java.simpleName}]: ${err.message ?: "unknown error"}"
                    )
                }
            }
        }
    }

    fun cancelInference() {
        activeJob?.cancel()
        activeJob = null
        _uiState.update { cur ->
            cur.copy(isInferring = false, aiStatusText = "Cancelled waiting for model inference (UserCancelledError).")
        }
    }

    fun exportAuditJson(): String {
        val s = _uiState.value
        val payload = AndroidAuditExport(
            exportedAt = Instant.now().toString(),
            question = s.question,
            policyId = s.policy.id,
            decisionStatus = s.decision.status.name,
            certificationTier = s.decision.certificationTier,
            independentVerification = s.decision.independentVerification,
            sourceVerified = s.sourceVerified,
            coverageReviewed = s.coverageReviewed,
            verifier = s.verifierName.ifBlank { "Anonymous local user (identity not verified)" },
            inferenceSource = s.aiLog?.inferenceSource,
            modelVersion = s.aiLog?.modelVersion,
            consentGranted = s.cloudConsent,
            observations = s.observations.mapValues { it.value.name.lowercase() },
            unverifiedSuggestionCount = s.proposals.count { it.groundingStatus == GroundingStatus.UNVERIFIED_SUGGESTION }
        )
        return AUDIT_JSON.encodeToString(payload)
    }

    companion object {
        private val AUDIT_JSON = Json {
            prettyPrint = true
            encodeDefaults = true
        }
    }

    private fun invalidateInFlight(reason: String) {
        activeJob?.cancel()
        activeJob = null
        runSeq += 1
        _uiState.update { cur ->
            cur.copy(
                activeEpoch = cur.activeEpoch + 1,
                isInferring = false,
                aiStatusText = if (cur.isInferring) "Reset in-flight inference ($reason)." else cur.aiStatusText
            )
        }
    }

    private fun recomputeDecision(state: GapwiseUiState): GapwiseUiState {
        val pendingCount = state.proposals.count { it.decision == ProposalDecision.PENDING }
        val opts = EvaluationOptions(
            scopeAccepted = state.scopeAccepted,
            sourceVerified = state.sourceVerified,
            coverageReviewed = state.coverageReviewed,
            sourceText = state.sourceText,
            pendingReviews = pendingCount,
            truncatedCandidates = state.sourceAudit?.truncatedCount ?: 0,
            truncatedByCharLimit = state.sourceAudit?.truncatedByCharLimit ?: false,
            sourceConflictCount = state.sourceAudit?.conflictSignals?.size ?: 0
        )
        val plan = DecisionEngine.buildAdaptivePlan(
            policy = state.policy,
            observations = state.observations,
            auditResult = state.sourceAudit,
            options = opts,
            proposals = state.proposals,
            unknownConfirmedIds = state.unknownConfirmedIds,
            deferredIds = state.deferredIds
        )
        return state.copy(decision = plan.decision, adaptivePlan = plan)
    }
}
