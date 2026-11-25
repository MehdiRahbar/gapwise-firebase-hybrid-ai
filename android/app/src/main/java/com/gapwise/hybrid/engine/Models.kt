package com.gapwise.hybrid.engine

import kotlinx.serialization.Serializable

enum class DecisionStatus {
    YES,
    NO,
    CONFLICT,
    OUT_OF_SCOPE,
    ASK
}

enum class AnswerValue {
    UNKNOWN,
    YES,
    NO,
    CONFLICT;

    companion object {
        fun fromWire(value: String?): AnswerValue = when (value?.trim()?.lowercase()) {
            "yes" -> YES
            "no" -> NO
            "conflict" -> CONFLICT
            else -> UNKNOWN
        }
    }
}

enum class InferenceModeChoice(val label: String) {
    PREFER_ON_DEVICE("Prefer on-device; cloud fallback with consent"),
    ONLY_ON_DEVICE("On-device only; zero cloud fallback"),
    PREFER_IN_CLOUD("Prefer cloud; on-device fallback"),
    ONLY_IN_CLOUD("Cloud only")
}

enum class OnDeviceModelOptionChoice(val label: String) {
    PREVIEW("PREVIEW"),
    PREVIEW_FAST("PREVIEW_FAST"),
    STABLE("STABLE")
}

enum class GroundingStatus {
    EXACT_QUOTE_VERIFIED,
    UNVERIFIED_SUGGESTION
}

@Serializable
data class PolicyTerm(
    val id: String,
    val label: String,
    val why: String = "",
    val cost: Int = 1,
    val weight: Int = 1
)

data class PolicyScenario(
    val id: String,
    val title: String,
    val tag: String,
    val scope: String,
    val source: String,
    val question: String,
    val terms: List<PolicyTerm>,
    val sampleSourceText: String
)

data class DiscoveredClause(
    val label: String,
    val reason: String,
    val origin: String,
    val cueType: String,
    val line: Int,
    val quote: String,
    val matchedExisting: Boolean,
    val startOffset: Int = -1,
    val endOffset: Int = -1
)

data class AdaptiveQuestion(
    val uid: String,
    val kind: String,
    val requirementId: String,
    val label: String,
    val question: String,
    val why: String,
    val sourceLine: Int? = null,
    val sourceQuote: String = "",
    val sourceStartOffset: Int = -1,
    val sourceEndOffset: Int = -1,
    val quoteVerified: Boolean = false,
    val priorityScore: Int = 0,
    val independent: Boolean = true,
    val deferred: Boolean = false
)

data class AdaptivePlan(
    val decision: DecisionResult,
    val caseVersion: String,
    val statusSummary: String,
    val queue: List<AdaptiveQuestion>,
    val nextQuestion: AdaptiveQuestion?,
    val recommendedBatch: List<AdaptiveQuestion>,
    val unknownConfirmedLabels: List<String>,
    val unresolvableByUser: Boolean
)

data class ConflictSignal(
    val lineA: Int,
    val lineB: Int,
    val summary: String
)

data class SourceAuditResult(
    val candidates: List<DiscoveredClause>,
    val novelCount: Int,
    val truncatedByCharLimit: Boolean,
    val truncatedCount: Int,
    val externalReferenceCount: Int,
    val unclassifiedCount: Int,
    val staleSignals: Int,
    val conflictSignals: List<ConflictSignal>,
    val coverageUncertain: Boolean,
    val uncertaintyReasons: List<String>
)

data class EvaluationOptions(
    val scopeAccepted: Boolean = true,
    val sourceVerified: Boolean = false,
    val coverageReviewed: Boolean = false,
    val sourceText: String = "",
    val pendingReviews: Int = 0,
    val truncatedCandidates: Int = 0,
    val truncatedByCharLimit: Boolean = false,
    val sourceConflictCount: Int = 0,
    val sourceConflictResolved: Boolean = false
)

data class DecisionResult(
    val status: DecisionStatus,
    val statusLabel: String,
    val certificationTier: String?,
    val independentVerification: Boolean,
    val headline: String,
    val detail: String,
    val blocking: List<String>,
    val missing: List<PolicyTerm>,
    val nextQuestion: PolicyTerm?,
    val warnings: List<String>
)

data class ProposalItem(
    val uid: String,
    val label: String,
    val reason: String,
    val origin: String,
    val cueType: String,
    val line: Int?,
    val quote: String,
    val quoteVerified: Boolean,
    val groundingStatus: GroundingStatus,
    val decision: ProposalDecision = ProposalDecision.PENDING,
    val dismissReason: String = ""
)

enum class ProposalDecision {
    PENDING,
    ADDED,
    DISMISSED
}

data class HybridAiLog(
    val inferenceSource: String,
    val adapterLabel: String,
    val modelVersion: String?,
    val elapsedMs: Long,
    val mode: InferenceModeChoice,
    val consentGranted: Boolean,
    val errorClass: String,
    val rawOutput: String? = null,
    val message: String = "",
    val modelOption: OnDeviceModelOptionChoice = OnDeviceModelOptionChoice.PREVIEW
)
