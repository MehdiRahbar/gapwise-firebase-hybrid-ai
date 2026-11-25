package com.gapwise.hybrid

import com.gapwise.hybrid.engine.AnswerValue
import com.gapwise.hybrid.engine.DecisionEngine
import com.gapwise.hybrid.engine.DecisionStatus
import com.gapwise.hybrid.engine.EvaluationOptions
import com.gapwise.hybrid.engine.PolicyScenario
import com.gapwise.hybrid.engine.PolicyTerm
import com.gapwise.hybrid.engine.SamplePolicies
import com.gapwise.hybrid.engine.SourceAuditor
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

@Serializable
data class GoldenCorpus(
    val version: String,
    val description: String,
    val cases: List<GoldenCase>
)

@Serializable
data class GoldenInlinePolicy(
    val id: String = "",
    val title: String = "",
    val scope: String = "",
    val question: String = "",
    val terms: List<PolicyTerm> = emptyList()
)

@Serializable
data class GoldenCase(
    val id: String,
    val policy_id: String,
    val policy: GoldenInlinePolicy? = null,
    val scope_accepted: Boolean,
    val source_verified: Boolean,
    val coverage_reviewed: Boolean,
    val observations: Map<String, String> = emptyMap(),
    val source_text: String,
    val expected_status: String,
    val expected_cert_tier: String? = null,
    val expected_min_novel: Int? = null,
    val expected_min_truncated: Int? = null
)

class GoldenParityTest {
    private val json = Json { ignoreUnknownKeys = true }

    private fun loadGoldenFile(): File {
        val candidates = listOf(
            File("../../evaluation/golden_cases.json"),
            File("../evaluation/golden_cases.json"),
            File("evaluation/golden_cases.json")
        )
        return candidates.firstOrNull { it.isFile }
            ?: error("Could not locate evaluation/golden_cases.json from ${File(".").absolutePath}")
    }

    @Test
    fun goldenCasesParityMatchesWebEngine() {
        val corpus = json.decodeFromString<GoldenCorpus>(loadGoldenFile().readText(Charsets.UTF_8))
        assertTrue("Expected at least 17 shared parity cases", corpus.cases.size >= 17)

        for (tc in corpus.cases) {
            val inline = tc.policy
            val policy = if (inline != null) {
                PolicyScenario(
                    id = inline.id.ifBlank { tc.policy_id },
                    title = inline.title,
                    tag = "Golden parity",
                    scope = inline.scope,
                    source = "Golden corpus",
                    question = inline.question,
                    terms = inline.terms,
                    sampleSourceText = tc.source_text
                )
            } else {
                SamplePolicies.byId(tc.policy_id)
            }
            assertNotNull("Unknown policy ${tc.policy_id}", policy)
            policy!!

            val audit = SourceAuditor.analyzeSourceDocument(
                text = tc.source_text,
                policy = policy,
                maxCandidates = 24,
                includeUnclassified = true
            )
            val obs = tc.observations.mapValues { AnswerValue.fromWire(it.value) }
            val result = DecisionEngine.evaluateStrict(
                policy = policy,
                observations = obs,
                options = EvaluationOptions(
                    scopeAccepted = tc.scope_accepted,
                    sourceVerified = tc.source_verified,
                    coverageReviewed = tc.coverage_reviewed,
                    sourceText = tc.source_text,
                    pendingReviews = audit.novelCount,
                    truncatedCandidates = audit.truncatedCount,
                    truncatedByCharLimit = audit.truncatedByCharLimit,
                    sourceConflictCount = audit.conflictSignals.size
                )
            )
            assertEquals("Case ${tc.id} status mismatch", DecisionStatus.valueOf(tc.expected_status), result.status)
            if (tc.expected_cert_tier != null) {
                assertEquals("Case ${tc.id} cert tier mismatch", tc.expected_cert_tier, result.certificationTier)
            }
            if (tc.expected_min_novel != null) {
                assertTrue(
                    "Case ${tc.id} expected novel >= ${tc.expected_min_novel}, got ${audit.novelCount}",
                    audit.novelCount >= tc.expected_min_novel
                )
            }
            if (tc.expected_min_truncated != null) {
                assertTrue(
                    "Case ${tc.id} expected truncated >= ${tc.expected_min_truncated}, got ${audit.truncatedCount}",
                    audit.truncatedCount >= tc.expected_min_truncated
                )
            }
            assertFalse("GAPWISE never asserts autonomous verification", result.independentVerification)
        }
    }

    @Test
    fun sourceQuoteValidatorAcceptsOnlyVerbatimMatches() {
        val doc = SamplePolicies.ALL.first().sampleSourceText
        assertTrue(SourceAuditor.validateSourceQuote("intact tamper-evident seal", doc))
        assertFalse(SourceAuditor.validateSourceQuote("invented nonexistent quote", doc))
        assertFalse(SourceAuditor.validateSourceQuote("", doc))
    }
}
