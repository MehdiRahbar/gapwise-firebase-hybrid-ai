package com.gapwise.hybrid

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import com.gapwise.hybrid.ai.HybridAiRepository
import com.gapwise.hybrid.engine.AnswerValue
import com.gapwise.hybrid.engine.DecisionStatus
import com.gapwise.hybrid.engine.GroundingStatus
import com.gapwise.hybrid.engine.InferenceModeChoice
import com.gapwise.hybrid.engine.OnDeviceModelOptionChoice
import com.gapwise.hybrid.engine.ProposalDecision
import com.gapwise.hybrid.engine.SamplePolicies
import com.gapwise.hybrid.ui.GapwiseUiState
import com.gapwise.hybrid.ui.GapwiseViewModel

private val GapwiseColors = darkColorScheme(
    primary = Color(0xFF5BF0CD),
    onPrimary = Color(0xFF062827),
    background = Color(0xFF09111E),
    surface = Color(0xFF102232),
    onBackground = Color(0xFFE9F3FA),
    onSurface = Color(0xFFE9F3FA)
)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT)
        )
        super.onCreate(savedInstanceState)
        val repo = HybridAiRepository(applicationContext)
        setContent {
            MaterialTheme(colorScheme = GapwiseColors) {
                val vm: GapwiseViewModel = viewModel(
                    factory = object : ViewModelProvider.Factory {
                        @Suppress("UNCHECKED_CAST")
                        override fun <T : ViewModel> create(modelClass: Class<T>): T =
                            GapwiseViewModel(repo) as T
                    }
                )
                val state by vm.uiState.collectAsState()
                val context = LocalContext.current
                GapwiseScreen(
                    state = state,
                    onSelectScenario = vm::selectScenario,
                    onQuestionChange = vm::updateQuestion,
                    onSourceChange = { vm.updateSourceText(it) },
                    onLoadSample = vm::loadSampleDocument,
                    onSetAnswer = vm::setAnswer,
                    onRespondAdaptive = vm::respondToAdaptiveQuestion,
                    onAddCondition = vm::addExtraCondition,
                    onApproveProposal = vm::approveProposalAsUnknown,
                    onDismissProposal = vm::dismissProposal,
                    onScopeChange = vm::setScopeAccepted,
                    onSourceVerifiedChange = vm::setSourceVerified,
                    onCoverageReviewedChange = vm::setCoverageReviewed,
                    onModeChange = vm::setInferenceMode,
                    onModelOptionChange = vm::setOnDeviceModelOption,
                    onConsentChange = vm::setCloudConsent,
                    onCheckDevice = vm::checkOnDeviceCapability,
                    onDownloadDevice = vm::downloadOnDeviceModel,
                    onRunHybrid = vm::runHybridInference,
                    onCancelHybrid = vm::cancelInference,
                    onShareAudit = {
                        val jsonText = vm.exportAuditJson()
                        val send = Intent(Intent.ACTION_SEND).apply {
                            type = "application/json"
                            putExtra(Intent.EXTRA_TEXT, jsonText)
                        }
                        context.startActivity(Intent.createChooser(send, "Export GAPWISE Audit JSON"))
                    }
                )
            }
        }
    }
}

@Composable
fun GapwiseScreen(
    state: GapwiseUiState,
    onSelectScenario: (Int) -> Unit = {},
    onQuestionChange: (String) -> Unit = {},
    onSourceChange: (String) -> Unit = {},
    onLoadSample: () -> Unit = {},
    onSetAnswer: (String, AnswerValue) -> Unit = { _, _ -> },
    onRespondAdaptive: (String, String, String) -> Unit = { _, _, _ -> },
    onAddCondition: (String) -> Unit = {},
    onApproveProposal: (String) -> Unit = {},
    onDismissProposal: (String, String) -> Unit = { _, _ -> },
    onScopeChange: (Boolean) -> Unit = {},
    onSourceVerifiedChange: (Boolean) -> Unit = {},
    onCoverageReviewedChange: (Boolean) -> Unit = {},
    onModeChange: (InferenceModeChoice) -> Unit = {},
    onModelOptionChange: (OnDeviceModelOptionChoice) -> Unit = {},
    onConsentChange: (Boolean) -> Unit = {},
    onCheckDevice: () -> Unit = {},
    onDownloadDevice: () -> Unit = {},
    onRunHybrid: () -> Unit = {},
    onCancelHybrid: () -> Unit = {},
    onShareAudit: () -> Unit = {}
) {
    var extraInput by remember { mutableStateOf("") }
    var dismissTargetUid by remember { mutableStateOf<String?>(null) }
    var dismissReasonInput by remember { mutableStateOf("") }

    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .safeDrawingPadding()
                .imePadding()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text("GAPWISE · EVIDENCE GATE", color = Color(0xFF54F0D0), fontWeight = FontWeight.ExtraBold, fontSize = 14.sp)
            Text("Before you decide, see what is missing.", color = Color(0xFFE9F3FA), fontWeight = FontWeight.Bold, fontSize = 22.sp)

            Row(
                modifier = Modifier.horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                SamplePolicies.ALL.forEachIndexed { idx, sc ->
                    FilterChip(
                        selected = state.scenarioIndex == idx,
                        onClick = { onSelectScenario(idx) },
                        label = { Text(sc.title) },
                        colors = FilterChipDefaults.filterChipColors(
                            selectedContainerColor = Color(0xFF16453D),
                            selectedLabelColor = Color(0xFFBCFFE7)
                        )
                    )
                }
            }

            DecisionBanner(state)

            // Adaptive Next Questions Card
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFF173A39), RoundedCornerShape(12.dp))
                    .border(1.dp, Color(0xFF347C6B), RoundedCornerShape(12.dp))
                    .padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                val procBadge = when (state.aiLog?.inferenceSource) {
                    "on_device" -> "Locally processed (on_device)"
                    "in_cloud" -> "Cloud with permission (in_cloud)"
                    else -> "Locally processed (deterministic)"
                }
                Text(
                    "ADAPTIVE INQUIRY · ${state.adaptivePlan.statusSummary}",
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF98F8DC),
                    fontSize = 13.sp
                )
                Text(
                    procBadge,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = Color(0xFFA7EBDC)
                )
                state.adaptivePlan.recommendedBatch.forEach { q ->
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(Color(0xFF0E252B), RoundedCornerShape(8.dp))
                            .border(1.dp, Color(0xFF2E6760), RoundedCornerShape(8.dp))
                            .padding(8.dp),
                        verticalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        Text(q.question, fontWeight = FontWeight.SemiBold, fontSize = 13.sp, color = Color(0xFFE8FFF8))
                        if (q.sourceQuote.isNotBlank()) {
                            Text(
                                "Line ${q.sourceLine ?: "?"} [${q.sourceStartOffset}..${q.sourceEndOffset}]: \"${q.sourceQuote}\"",
                                fontSize = 11.sp,
                                color = Color(0xFFC7EAE2)
                            )
                        }
                        Row(
                            modifier = Modifier.horizontalScroll(rememberScrollState()),
                            horizontalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            OutlinedButton(onClick = { onRespondAdaptive(q.requirementId, q.kind, "yes") }) { Text("Yes") }
                            OutlinedButton(onClick = { onRespondAdaptive(q.requirementId, q.kind, "no") }) { Text("No") }
                            OutlinedButton(onClick = { onRespondAdaptive(q.requirementId, q.kind, "dunno") }) { Text("Don't know") }
                            OutlinedButton(onClick = { onRespondAdaptive(q.requirementId, q.kind, "skip") }) { Text("Skip") }
                        }
                    }
                }
                if (state.adaptivePlan.unknownConfirmedLabels.isNotEmpty()) {
                    Text(
                        "Confirmed unknown (kept ASK): ${state.adaptivePlan.unknownConfirmedLabels.joinToString("; ")}",
                        fontSize = 11.sp,
                        color = Color(0xFFF7DCB0)
                    )
                }
            }

            OutlinedTextField(
                value = state.question,
                onValueChange = onQuestionChange,
                label = { Text("Decision question") },
                modifier = Modifier.fillMaxWidth()
            )

            // Hybrid Inference Controls (Consent Gate + SDK Mode + Status)
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFF102232), RoundedCornerShape(12.dp))
                    .border(1.dp, Color(0xFF294051), RoundedCornerShape(12.dp))
                    .padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Text("Firebase AI Logic Hybrid Control", fontWeight = FontWeight.Bold, color = Color(0xFF8EF2D8))
                Row(
                    modifier = Modifier.horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    InferenceModeChoice.entries.forEach { mode ->
                        FilterChip(
                            selected = state.inferenceMode == mode,
                            onClick = { onModeChange(mode) },
                            label = { Text(mode.name) }
                        )
                    }
                }
                Text("On-Device ModelOption:", fontSize = 11.sp, color = Color(0xFF9FB8C7))
                Row(
                    modifier = Modifier.horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    OnDeviceModelOptionChoice.entries.forEach { opt ->
                        FilterChip(
                            selected = state.onDeviceModelOption == opt,
                            onClick = { onModelOptionChange(opt) },
                            label = { Text(opt.name) }
                        )
                    }
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Switch(checked = state.cloudConsent, onCheckedChange = onConsentChange)
                    Text(
                        "Explicit Cloud Consent (required for cloud-capable modes)",
                        fontSize = 12.sp,
                        modifier = Modifier.padding(start = 8.dp)
                    )
                }
                Button(
                    onClick = if (state.isInferring) onCancelHybrid else onRunHybrid,
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (state.isInferring) Color(0xFF7E464E) else Color(0xFF5BF0CD),
                        contentColor = if (state.isInferring) Color.White else Color(0xFF062827)
                    )
                ) {
                    Text(if (state.isInferring) "Stop waiting" else "Discover missing via Hybrid AI")
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                    OutlinedButton(onClick = onCheckDevice, modifier = Modifier.weight(1f)) {
                        Text("Check Capability", fontSize = 12.sp)
                    }
                    OutlinedButton(onClick = onDownloadDevice, modifier = Modifier.weight(1f)) {
                        Text("Download / WarmUp", fontSize = 12.sp)
                    }
                }
                Text("Device: ${state.onDeviceStatusText}", fontSize = 12.sp, color = Color(0xFF9FB8C7))
                Text(state.aiStatusText, fontSize = 12.sp, color = Color(0xFFC2DBE2))
                state.aiLog?.let { aiLog ->
                    val rawPreview = aiLog.rawOutput?.replace("\n", " ")?.take(220) ?: "(empty)"
                    Text(
                        "SDK Telemetry: source=${aiLog.inferenceSource} | opt=${aiLog.modelOption.name} | model=${aiLog.modelVersion ?: "unreported"} | elapsed=${aiLog.elapsedMs}ms | raw=$rawPreview",
                        fontSize = 11.sp,
                        color = Color(0xFF98F8DC)
                    )
                }
            }

            // Checklist Conditions
            Text("Checklist Conditions", fontWeight = FontWeight.Bold, color = Color(0xFF8EB0C4))
            state.policy.terms.forEach { term ->
                val current = state.observations[term.id] ?: AnswerValue.UNKNOWN
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(Color(0xFF0B1B29), RoundedCornerShape(10.dp))
                        .border(1.dp, Color(0xFF2B4557), RoundedCornerShape(10.dp))
                        .padding(10.dp)
                ) {
                    Text(term.label, fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
                    if (term.why.isNotBlank()) {
                        Text(term.why, fontSize = 12.sp, color = Color(0xFF9CB5C2))
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp), modifier = Modifier.padding(top = 6.dp)) {
                        listOf(
                            AnswerValue.UNKNOWN to "?",
                            AnswerValue.YES to "Yes",
                            AnswerValue.NO to "No",
                            AnswerValue.CONFLICT to "Conflict"
                        ).forEach { (ans, title) ->
                            FilterChip(
                                selected = current == ans,
                                onClick = { onSetAnswer(term.id, ans) },
                                label = { Text(title) }
                            )
                        }
                    }
                }
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(
                    value = extraInput,
                    onValueChange = { extraInput = it },
                    label = { Text("Add condition") },
                    modifier = Modifier.weight(1f)
                )
                OutlinedButton(onClick = {
                    onAddCondition(extraInput)
                    extraInput = ""
                }) {
                    Text("+ Add")
                }
            }

            // Source & Attestations
            OutlinedTextField(
                value = state.sourceText,
                onValueChange = onSourceChange,
                label = { Text("Independent Policy / Contract Source Text") },
                minLines = 4,
                modifier = Modifier.fillMaxWidth()
            )
            OutlinedButton(onClick = onLoadSample) {
                Text("Load fictional sample document")
            }

            CheckboxRow("Case is within policy scope", state.scopeAccepted, onScopeChange)
            CheckboxRow("I verified supplied source authenticity (human-attested, non-cryptographic)", state.sourceVerified, onSourceVerifiedChange)
            CheckboxRow("I reviewed all scanned/AI items for checklist coverage", state.coverageReviewed, onCoverageReviewedChange)
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFF132A36), RoundedCornerShape(8.dp))
                    .border(1.dp, Color(0xFF3C6578), RoundedCornerShape(8.dp))
                    .padding(10.dp),
                verticalArrangement = Arrangement.spacedBy(3.dp)
            ) {
                Text("Human Attestation Contract", fontSize = 12.sp, fontWeight = FontWeight.Bold, color = Color(0xFF8EF2D8))
                Text(
                    "Heuristics and AI never set Yes. Checked attestations assert manual source authenticity verification & pending review coverage for this versioned CONDITIONAL · HUMAN-ATTESTED record.",
                    fontSize = 11.sp,
                    color = Color(0xFFF5D3A3)
                )
            }

            // Source Audit Review Queue
            Text("Source Audit & AI Review Queue", fontWeight = FontWeight.Bold, color = Color(0xFF8EB0C4))
            val pending = state.proposals.filter { it.decision == ProposalDecision.PENDING }
            if (pending.isEmpty()) {
                Text("No unreviewed suggestions.", fontSize = 12.sp, color = Color(0xFF9FB8C7))
            } else {
                pending.forEach { prop ->
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(Color(0xFF0B1C2A), RoundedCornerShape(10.dp))
                            .border(1.dp, Color(0xFF315364), RoundedCornerShape(10.dp))
                            .padding(10.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        if (prop.groundingStatus == GroundingStatus.UNVERIFIED_SUGGESTION) {
                            Text(
                                "UNVERIFIED SUGGESTION (no verbatim quote match in source)",
                                color = Color(0xFFF7DCB0),
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }
                        Text(prop.label, fontWeight = FontWeight.Bold, fontSize = 14.sp)
                        Text(prop.reason, fontSize = 12.sp, color = Color(0xFFBBD2DC))
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(onClick = { onApproveProposal(prop.uid) }) {
                                Text("Add as UNKNOWN")
                            }
                            OutlinedButton(onClick = {
                                dismissTargetUid = prop.uid
                                dismissReasonInput = ""
                            }) {
                                Text("Dismiss")
                            }
                        }
                        if (dismissTargetUid == prop.uid) {
                            OutlinedTextField(
                                value = dismissReasonInput,
                                onValueChange = { dismissReasonInput = it },
                                label = { Text("Dismiss reason (>= 8 chars)") },
                                modifier = Modifier.fillMaxWidth()
                            )
                            Button(
                                enabled = dismissReasonInput.trim().length >= 8,
                                onClick = {
                                    onDismissProposal(prop.uid, dismissReasonInput)
                                    dismissTargetUid = null
                                }
                            ) {
                                Text("Confirm dismiss")
                            }
                        }
                    }
                }
            }

            OutlinedButton(onClick = onShareAudit, modifier = Modifier.fillMaxWidth()) {
                Text("Export Transparent Audit JSON")
            }
            Spacer(modifier = Modifier.height(16.dp))
        }
    }
}

@Composable
private fun DecisionBanner(state: GapwiseUiState) {
    val bg = when (state.decision.status) {
        DecisionStatus.YES -> Color(0xFF12353A)
        DecisionStatus.NO -> Color(0xFF352129)
        DecisionStatus.CONFLICT -> Color(0xFF3B3021)
        DecisionStatus.OUT_OF_SCOPE -> Color(0xFF1D2638)
        DecisionStatus.ASK -> Color(0xFF122B36)
    }
    val titleColor = when (state.decision.status) {
        DecisionStatus.NO -> Color(0xFFFFC2AD)
        DecisionStatus.CONFLICT -> Color(0xFFFFD992)
        DecisionStatus.OUT_OF_SCOPE -> Color(0xFF9FB8C7)
        else -> Color(0xFF72F2D6)
    }
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(bg, RoundedCornerShape(12.dp))
            .border(1.dp, Color(0xFF3D5966), RoundedCornerShape(12.dp))
            .padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp)
    ) {
        if (state.decision.status == DecisionStatus.YES) {
            Text(
                "Human-attested · NOT independently verified",
                fontSize = 11.sp,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF9EFFE3)
            )
        }
        Text(state.decision.statusLabel, fontWeight = FontWeight.ExtraBold, fontSize = 18.sp, color = titleColor)
        Text(state.decision.detail, fontSize = 13.sp, color = Color(0xFFC2DBE2))
        state.decision.nextQuestion?.let { next ->
            Text("Next question: ${next.label}", fontSize = 12.sp, fontWeight = FontWeight.SemiBold, color = Color(0xFF98F8DC))
        }
    }
}

@Composable
private fun CheckboxRow(label: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
        Checkbox(
            checked = checked,
            onCheckedChange = onChange,
            colors = CheckboxDefaults.colors(checkedColor = Color(0xFF5BF0CD))
        )
        Text(label, fontSize = 12.sp, color = Color(0xFFBED2DC))
    }
}

@Preview(showBackground = true)
@Composable
fun GapwiseScreenPreview() {
    MaterialTheme(colorScheme = GapwiseColors) {
        GapwiseScreen(state = GapwiseUiState())
    }
}
