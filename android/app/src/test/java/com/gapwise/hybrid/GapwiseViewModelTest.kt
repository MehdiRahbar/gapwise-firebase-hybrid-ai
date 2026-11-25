package com.gapwise.hybrid

import com.gapwise.hybrid.ai.HybridAiRepository
import com.gapwise.hybrid.ai.HybridConsentRequiredException
import com.gapwise.hybrid.engine.AnswerValue
import com.gapwise.hybrid.engine.DecisionStatus
import com.gapwise.hybrid.engine.GroundingStatus
import com.gapwise.hybrid.engine.InferenceModeChoice
import com.gapwise.hybrid.engine.OnDeviceModelOptionChoice
import com.gapwise.hybrid.ui.GapwiseViewModel
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class GapwiseViewModelTest {
    @Test
    fun documentEditInvalidatesHumanAttestations() {
        val vm = GapwiseViewModel(aiRepository = null)
        vm.loadSampleDocument()
        vm.setSourceVerified(true)
        vm.setCoverageReviewed(true)
        assertTrue(vm.uiState.value.sourceVerified)

        vm.updateSourceText("No refunds.")
        assertFalse(vm.uiState.value.sourceVerified)
        assertFalse(vm.uiState.value.coverageReviewed)
        assertEquals(DecisionStatus.ASK, vm.uiState.value.decision.status)
        assertTrue(vm.uiState.value.proposals.any { it.label == "No refunds." })
    }

    @Test
    fun addedProposalRemainsUnknownUntilHumanAnswersYes() {
        val vm = GapwiseViewModel(aiRepository = null)
        vm.loadSampleDocument()
        val firstUid = vm.uiState.value.proposals.first().uid
        vm.approveProposalAsUnknown(firstUid)
        val addedTerm = vm.uiState.value.policy.terms.last()
        assertEquals(null, vm.uiState.value.observations[addedTerm.id])
        assertEquals(DecisionStatus.ASK, vm.uiState.value.decision.status)
    }

    @Test
    fun shortDismissReasonIsRejectedWhileValidReasonDismissesCleanly() {
        val vm = GapwiseViewModel(aiRepository = null)
        vm.loadSampleDocument()
        val uid = vm.uiState.value.proposals.first().uid
        val beforePending = vm.uiState.value.proposals.size
        vm.dismissProposal(uid, "too")
        assertEquals(beforePending, vm.uiState.value.proposals.count { it.decision.name == "PENDING" })

        vm.dismissProposal(uid, "Already handled in manual intake review")
        assertEquals(beforePending - 1, vm.uiState.value.proposals.count { it.decision.name == "PENDING" })
    }

    @Test
    fun auditExportContainsExplicitVerificationDisclosures() {
        val vm = GapwiseViewModel(aiRepository = null)
        vm.setInferenceMode(InferenceModeChoice.ONLY_ON_DEVICE)
        vm.setAnswer("period", AnswerValue.YES)
        val exported = vm.exportAuditJson()
        assertTrue(exported.contains("\"independentVerification\": false"))
        assertTrue(exported.contains("\"consentGranted\": false"))
        assertTrue(exported.contains("GAPWISE-Android"))
    }

    @Test(expected = HybridConsentRequiredException::class)
    fun cloudCapableModeWithoutConsentFailsClosedWithExplicitException() {
        HybridAiRepository.requireCloudConsent(InferenceModeChoice.PREFER_ON_DEVICE, cloudConsent = false)
    }

    @Test
    fun onlyOnDeviceModePermitsInvocationWithoutCloudConsent() {
        HybridAiRepository.requireCloudConsent(InferenceModeChoice.ONLY_ON_DEVICE, cloudConsent = false)
        assertFalse(HybridAiRepository.validateProposalGrounding("fabricated citation not in text", "Actual policy line."))
        assertTrue(HybridAiRepository.validateProposalGrounding("Actual policy line.", "First line.\nActual policy line."))
    }

    @Test
    fun adaptivePlanPrioritizesSourceBlockerNeverRepeatsDunnoAndShortCircuitsNo() {
        val vm = GapwiseViewModel(aiRepository = null)
        vm.loadSampleDocument()
        val initialPlan = vm.uiState.value.adaptivePlan
        assertEquals(DecisionStatus.ASK, initialPlan.decision.status)
        assertTrue(initialPlan.recommendedBatch.size in 2..4)
        val topQ = initialPlan.nextQuestion!!
        assertEquals("discovered-clause", topQ.kind)
        assertTrue(topQ.sourceStartOffset >= 0)

        // Marking top question "dunno" keeps status ASK and removes it from active re-ask queue
        vm.respondToAdaptiveQuestion(topQ.requirementId, topQ.kind, "dunno")
        val afterDunno = vm.uiState.value.adaptivePlan
        assertEquals(DecisionStatus.ASK, afterDunno.decision.status)
        assertFalse(afterDunno.queue.any { it.uid == topQ.uid })
        assertTrue(afterDunno.unknownConfirmedLabels.any { it == topQ.label })

        // Answering any required term "no" immediately decides NOT ELIGIBLE
        val nextTerm = afterDunno.queue.first { it.kind == "term" }
        vm.respondToAdaptiveQuestion(nextTerm.requirementId, "term", "no")
        assertEquals(DecisionStatus.NO, vm.uiState.value.decision.status)
    }

    @Test
    fun defaultOnDeviceModelOptionIsPreviewAndSelectableBeforeReserve() {
        val vm = GapwiseViewModel(aiRepository = null)
        assertEquals(OnDeviceModelOptionChoice.PREVIEW, vm.uiState.value.onDeviceModelOption)
        vm.setOnDeviceModelOption(OnDeviceModelOptionChoice.PREVIEW_FAST)
        assertEquals(OnDeviceModelOptionChoice.PREVIEW_FAST, vm.uiState.value.onDeviceModelOption)
        vm.downloadOnDeviceModel()
    }
}
