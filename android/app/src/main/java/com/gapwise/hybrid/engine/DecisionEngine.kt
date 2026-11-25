package com.gapwise.hybrid.engine

object DecisionEngine {
    fun evaluateStrict(
        policy: PolicyScenario,
        observations: Map<String, AnswerValue>,
        options: EvaluationOptions
    ): DecisionResult {
        require(policy.terms.isNotEmpty()) { "Policy must define at least one required condition" }
        val seenIds = HashSet<String>()
        for (term in policy.terms) {
            require(term.id.isNotBlank() && seenIds.add(term.id)) {
                "Duplicate or empty condition id: ${term.id}"
            }
        }

        if (!options.scopeAccepted) {
            return DecisionResult(
                status = DecisionStatus.OUT_OF_SCOPE,
                statusLabel = "OUT OF SCOPE",
                certificationTier = null,
                independentVerification = false,
                headline = "OUTSIDE THE POLICY SCOPE",
                detail = "Because this case falls outside the stated policy boundaries, no approval or rejection applies.",
                blocking = listOf("Scope gate failed"),
                missing = emptyList(),
                nextQuestion = null,
                warnings = emptyList()
            )
        }

        val noTerms = policy.terms.filter { observations[it.id] == AnswerValue.NO }
        if (noTerms.isNotEmpty()) {
            return DecisionResult(
                status = DecisionStatus.NO,
                statusLabel = "NO · BLOCKING CONDITION FALSE",
                certificationTier = null,
                independentVerification = false,
                headline = "NOT ELIGIBLE UNDER THIS POLICY",
                detail = "Required condition failed: \"${noTerms.first().label}\". A single unmet condition blocks YES.",
                blocking = noTerms.map { it.label },
                missing = emptyList(),
                nextQuestion = null,
                warnings = emptyList()
            )
        }

        val conflictTerms = policy.terms.filter { observations[it.id] == AnswerValue.CONFLICT }
        if (conflictTerms.isNotEmpty()) {
            return DecisionResult(
                status = DecisionStatus.CONFLICT,
                statusLabel = "CONFLICTING EVIDENCE",
                certificationTier = null,
                independentVerification = false,
                headline = "CONFLICTING EVIDENCE",
                detail = "Contradictory status recorded for \"${conflictTerms.first().label}\". Resolve inconsistency before deciding.",
                blocking = conflictTerms.map { "${it.label} (conflict)" },
                missing = emptyList(),
                nextQuestion = null,
                warnings = emptyList()
            )
        }

        if (options.sourceConflictCount > 0 && !options.sourceConflictResolved) {
            return DecisionResult(
                status = DecisionStatus.CONFLICT,
                statusLabel = "CONFLICTING SOURCE POLICY",
                certificationTier = null,
                independentVerification = false,
                headline = "CONFLICTING SOURCE POLICY",
                detail = "The supplied document appears to contain internal contradictions. Reconcile or inspect before deciding.",
                blocking = listOf("${options.sourceConflictCount} internal source contradiction(s)"),
                missing = emptyList(),
                nextQuestion = null,
                warnings = emptyList()
            )
        }

        val missingTerms = policy.terms
            .filter { (observations[it.id] ?: AnswerValue.UNKNOWN) != AnswerValue.YES }
            .sortedWith(compareBy<PolicyTerm> { it.cost }.thenByDescending { it.weight })

        val trimmedSource = options.sourceText.trim()
        val missingGates = buildList {
            if (trimmedSource.length < 24) {
                add("Supply or paste the applicable policy/source text (minimum 24 characters) to inspect.")
            }
            if (options.truncatedByCharLimit) {
                add("Source exceeded the 30,000-character scan cap; review remaining text outside this tool.")
            }
            if (options.truncatedCandidates > 0) {
                add("Source scan truncated (${options.truncatedCandidates} additional/overlong clause(s) outside scanned limit).")
            }
            if (options.pendingReviews > 0) {
                add("${options.pendingReviews} discovered clause(s) / AI suggestion(s) still await human review.")
            }
            if (!options.sourceVerified) {
                add("Human source authenticity attestation is unchecked.")
            }
            if (!options.coverageReviewed) {
                add("Human coverage completeness attestation is unchecked.")
            }
        }

        if (missingTerms.isNotEmpty() || missingGates.isNotEmpty()) {
            val detail = when {
                missingTerms.isNotEmpty() ->
                    "${missingTerms.size} condition(s) are still unknown. Never assume YES without verification."
                missingGates.isNotEmpty() ->
                    missingGates.joinToString(" ")
                else -> "More information is required."
            }
            return DecisionResult(
                status = DecisionStatus.ASK,
                statusLabel = "ASK · EVIDENCE INCOMPLETE",
                certificationTier = null,
                independentVerification = false,
                headline = "MORE INFORMATION REQUIRED",
                detail = detail,
                blocking = missingTerms.map { it.label } + missingGates,
                missing = missingTerms,
                nextQuestion = missingTerms.firstOrNull(),
                warnings = missingGates
            )
        }

        return DecisionResult(
            status = DecisionStatus.YES,
            statusLabel = "CONDITIONAL · HUMAN-ATTESTED",
            certificationTier = "CONDITIONAL_HUMAN_ATTESTED",
            independentVerification = false,
            headline = "CONDITIONAL · HUMAN-ATTESTED (${policy.terms.size} LISTED CONDITIONS CONFIRMED)",
            detail = "All ${policy.terms.size} currently listed checklist conditions are attested YES based on user-supplied evidence.",
            blocking = emptyList(),
            missing = emptyList(),
            nextQuestion = null,
            warnings = listOf(
                "Self-attested only: external source validity and unknown-unknown rules outside supplied text cannot be excluded automatically."
            )
        )
    }

    fun computeCaseVersion(policy: PolicyScenario, sourceText: String = ""): String {
        val payload = buildString {
            append(policy.id.trim()).append("|")
            append(policy.question.trim()).append("|")
            policy.terms.forEach { append(it.id.trim()).append(":").append(it.label.trim()).append(";") }
            append("|").append(sourceText)
        }
        var hash = 0x811c9dc5u
        for (ch in payload) {
            hash = hash xor ch.code.toUInt()
            hash *= 0x01000193u
        }
        return "v_" + hash.toString(16).padStart(8, '0')
    }

    fun buildAdaptivePlan(
        policy: PolicyScenario,
        observations: Map<String, AnswerValue> = emptyMap(),
        auditResult: SourceAuditResult? = null,
        options: EvaluationOptions = EvaluationOptions(),
        proposals: List<ProposalItem> = emptyList(),
        unknownConfirmedIds: Set<String> = emptySet(),
        deferredIds: Set<String> = emptySet()
    ): AdaptivePlan {
        val decision = evaluateStrict(policy, observations, options)
        val pendingProps = proposals.filter { it.decision == ProposalDecision.PENDING }
        val items = mutableListOf<AdaptiveQuestion>()

        if (decision.status != DecisionStatus.NO && decision.status != DecisionStatus.OUT_OF_SCOPE) {
            for (conf in policy.terms.filter { observations[it.id] == AnswerValue.CONFLICT }) {
                items.add(
                    AdaptiveQuestion(
                        uid = "term_conflict:${conf.id}",
                        kind = "conflict",
                        requirementId = conf.id,
                        label = conf.label,
                        question = "Resolve policy conflict: ${conf.label}",
                        why = conf.why.ifBlank { "Conflicting evidence blocks approval until reconciled." },
                        priorityScore = 1000,
                        independent = false,
                        deferred = conf.id in deferredIds
                    )
                )
            }
            if ((auditResult?.conflictSignals?.isNotEmpty() == true) && !options.sourceConflictResolved) {
                val sig = auditResult.conflictSignals.first()
                items.add(
                    AdaptiveQuestion(
                        uid = "source_conflict:0",
                        kind = "conflict",
                        requirementId = "source_conflict",
                        label = sig.summary,
                        question = "Reconcile conflicting clauses: ${sig.summary}",
                        why = "Supplied document appears internally contradictory.",
                        sourceLine = sig.lineB,
                        priorityScore = 980,
                        independent = false,
                        deferred = false
                    )
                )
            }

            for (prop in pendingProps) {
                if (prop.uid in unknownConfirmedIds) continue
                val cueBoost = when {
                    prop.cueType == "negation-exception" -> 900
                    prop.cueType == "cross-reference" -> 860
                    prop.cueType == "temporal-deadline" -> 810
                    prop.origin == "firebase-ai-logic" && prop.quoteVerified -> 740
                    prop.origin == "firebase-ai-logic" -> 260
                    else -> 760
                }
                val penalty = if (prop.uid in deferredIds) -250 else 0
                val off = if (prop.quote.isNotBlank()) options.sourceText.indexOf(prop.quote) else -1
                items.add(
                    AdaptiveQuestion(
                        uid = "proposal:${prop.uid}",
                        kind = if (prop.origin == "firebase-ai-logic") "ai-proposal" else "discovered-clause",
                        requirementId = prop.uid,
                        label = prop.label,
                        question = "Does this condition apply and hold true here: ${prop.label}",
                        why = prop.reason,
                        sourceLine = prop.line,
                        sourceQuote = prop.quote,
                        sourceStartOffset = off,
                        sourceEndOffset = if (off >= 0) off + prop.quote.length else -1,
                        quoteVerified = prop.quoteVerified,
                        priorityScore = cueBoost + penalty,
                        independent = prop.cueType != "cross-reference" && prop.cueType != "contradiction-cue",
                        deferred = prop.uid in deferredIds
                    )
                )
            }

            for (term in decision.missing) {
                if (term.id in unknownConfirmedIds) continue
                val penalty = if (term.id in deferredIds) -250 else 0
                val ratio = term.weight.toDouble() / term.cost.coerceAtLeast(1).toDouble()
                items.add(
                    AdaptiveQuestion(
                        uid = "term:${term.id}",
                        kind = "term",
                        requirementId = term.id,
                        label = term.label,
                        question = "Verify condition: ${term.label}",
                        why = term.why.ifBlank { "Required checklist condition." },
                        priorityScore = (400 + ratio * 25).toInt() + penalty,
                        independent = true,
                        deferred = term.id in deferredIds
                    )
                )
            }
        }

        val sorted = items.sortedWith(compareByDescending<AdaptiveQuestion> { it.priorityScore }.thenBy { it.uid })
        val batch = mutableListOf<AdaptiveQuestion>()
        for (q in sorted) {
            if (batch.isEmpty()) {
                batch.add(q)
                if (!q.independent) break
            } else if (q.independent && batch.size < 4) {
                batch.add(q)
            }
        }

        val unknownConfirmedLabels = decision.missing
            .filter { it.id in unknownConfirmedIds }
            .map { it.label } + pendingProps.filter { it.uid in unknownConfirmedIds }.map { it.label }

        val remainingFacts = decision.missing.size + pendingProps.size
        val summary = when {
            decision.status == DecisionStatus.YES -> "Can decide now (CONDITIONAL · HUMAN-ATTESTED)"
            decision.status == DecisionStatus.NO -> "Can decide now (NOT ELIGIBLE)"
            decision.status == DecisionStatus.OUT_OF_SCOPE -> "Not covered (OUT_OF_SCOPE)"
            decision.status == DecisionStatus.CONFLICT -> "Source conflict"
            unknownConfirmedLabels.isNotEmpty() && sorted.isEmpty() ->
                "ASK · Irreducible gap (${unknownConfirmedLabels.size} unknown)"
            remainingFacts > 0 -> "Need $remainingFacts fact${if (remainingFacts == 1) "" else "s"}"
            decision.blocking.isNotEmpty() -> "Attestation / source review required"
            else -> "Need more information"
        }

        return AdaptivePlan(
            decision = decision,
            caseVersion = computeCaseVersion(policy, options.sourceText),
            statusSummary = summary,
            queue = sorted,
            nextQuestion = sorted.firstOrNull(),
            recommendedBatch = batch,
            unknownConfirmedLabels = unknownConfirmedLabels,
            unresolvableByUser = unknownConfirmedLabels.isNotEmpty() && sorted.isEmpty()
        )
    }
}
