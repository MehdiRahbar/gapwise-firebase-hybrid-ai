package com.gapwise.hybrid.ai

import android.content.Context
import com.gapwise.hybrid.engine.HybridAiLog
import com.gapwise.hybrid.engine.InferenceModeChoice
import com.gapwise.hybrid.engine.OnDeviceModelOptionChoice
import com.gapwise.hybrid.engine.PolicyScenario
import com.gapwise.hybrid.engine.SourceAuditor
import com.google.firebase.Firebase
import com.google.firebase.FirebaseApp
import com.google.firebase.ai.DownloadStatus
import com.google.firebase.ai.InferenceMode
import com.google.firebase.ai.OnDeviceConfig
import com.google.firebase.ai.OnDeviceModelOption
import com.google.firebase.ai.OnDeviceModelStatus
import com.google.firebase.ai.ai
import com.google.firebase.ai.annotations.Generable
import com.google.firebase.ai.type.GenerativeBackend
import com.google.firebase.ai.type.PublicPreviewAPI
import kotlinx.serialization.Serializable

/**
 * Structured output schema processed at compile-time via firebase-ai-ksp-processor (@Generable).
 */
@Serializable
@Generable(description = "Untrusted candidate missing requirements extracted from a policy document.")
data class GeneratedSuggestedCheck(
    val id: String = "",
    val label: String = "",
    val reason: String = "",
    val quote: String = ""
) {
    companion object
}

@Serializable
@Generable(description = "Top-level structured proposal returned by GAPWISE hybrid inference.")
data class GeneratedGapwiseProposal(
    val suggested_checks: List<GeneratedSuggestedCheck> = emptyList(),
    val possible_missing_categories: List<String> = emptyList(),
    val unsupported_assumptions: List<String> = emptyList()
) {
    companion object
}

data class HybridInferenceOutcome(
    val checks: List<GeneratedSuggestedCheck>,
    val log: HybridAiLog
)

class HybridConsentRequiredException(message: String) : IllegalStateException(message)

class HybridAiRepository(private val appContext: Context) {

    fun isFirebaseConfigured(): Boolean = FirebaseApp.getApps(appContext).isNotEmpty()

    @OptIn(PublicPreviewAPI::class)
    suspend fun checkOnDeviceStatus(
        modelOptionChoice: OnDeviceModelOptionChoice = OnDeviceModelOptionChoice.PREVIEW
    ): String {
        if (!isFirebaseConfigured()) {
            return "Firebase google-services.json absent (deterministic offline mode only)"
        }
        return runCatching {
            val model = Firebase.ai(backend = GenerativeBackend.googleAI()).generativeModel(
                modelName = CLOUD_MODEL_NAME,
                onDeviceConfig = OnDeviceConfig(
                    mode = InferenceMode.ONLY_ON_DEVICE,
                    modelOption = toSdkModelOption(modelOptionChoice)
                )
            )
            val status = model.onDeviceExtension?.checkStatus()
            val sdkModelName = if (status == OnDeviceModelStatus.AVAILABLE) {
                runCatching { model.onDeviceExtension?.getModelName() }.getOrNull()?.takeIf { it.isNotBlank() }
            } else {
                null
            }
            val msg = when (status) {
                OnDeviceModelStatus.AVAILABLE -> "AVAILABLE [${modelOptionChoice.name}] (AICore ready${sdkModelName?.let { " · model=$it" } ?: ""})"
                OnDeviceModelStatus.DOWNLOADABLE -> "DOWNLOADABLE [${modelOptionChoice.name}] (AICore download needed)"
                OnDeviceModelStatus.DOWNLOADING -> "DOWNLOADING [${modelOptionChoice.name}]"
                OnDeviceModelStatus.UNAVAILABLE -> "UNAVAILABLE on this device [${modelOptionChoice.name}]"
                else -> "Status [${modelOptionChoice.name}]: $status"
            }
            android.util.Log.i("GAPWISE_AI", "checkOnDeviceStatus option=${modelOptionChoice.name} status=$status modelName=${sdkModelName ?: "null"}")
            msg
        }.getOrElse { err ->
            "On-device status unavailable: ${err.message ?: err::class.java.simpleName}"
        }
    }

    @OptIn(PublicPreviewAPI::class)
    suspend fun downloadOnDeviceModel(
        modelOptionChoice: OnDeviceModelOptionChoice = OnDeviceModelOptionChoice.PREVIEW,
        onProgress: (String) -> Unit
    ): String {
        if (!isFirebaseConfigured()) {
            return "Firebase google-services.json absent (deterministic offline mode only)"
        }
        return runCatching {
            val model = Firebase.ai(backend = GenerativeBackend.googleAI()).generativeModel(
                modelName = CLOUD_MODEL_NAME,
                onDeviceConfig = OnDeviceConfig(
                    mode = InferenceMode.ONLY_ON_DEVICE,
                    modelOption = toSdkModelOption(modelOptionChoice)
                )
            )
            val ext = model.onDeviceExtension
                ?: return@runCatching "OnDeviceExtension unavailable for ${modelOptionChoice.name}"
            when (val status = ext.checkStatus()) {
                OnDeviceModelStatus.AVAILABLE -> {
                    runCatching { ext.warmUp() }
                    val name = runCatching { ext.getModelName() }.getOrNull()?.takeIf { it.isNotBlank() }
                    return@runCatching "AVAILABLE [${modelOptionChoice.name}] (warmed up · model=${name ?: "unreported"})"
                }
                OnDeviceModelStatus.UNAVAILABLE -> {
                    return@runCatching "UNAVAILABLE on this device [${modelOptionChoice.name}]"
                }
                else -> Unit
            }
            var finalError: String? = null
            ext.download().collect { dl ->
                when (dl) {
                    is DownloadStatus.DownloadStarted ->
                        onProgress("Downloading [${modelOptionChoice.name}]: started (${dl.bytesToDownload / 1024} KB)")
                    is DownloadStatus.DownloadInProgress ->
                        onProgress("Downloading [${modelOptionChoice.name}]: ${dl.totalBytesDownloaded / 1024} KB")
                    DownloadStatus.DownloadCompleted ->
                        onProgress("Download completed [${modelOptionChoice.name}]; checking availability...")
                    is DownloadStatus.DownloadFailed -> {
                        finalError = "${dl.exception::class.java.simpleName}: ${dl.exception.message ?: "download failed"}"
                        android.util.Log.e("GAPWISE_AI", "downloadOnDeviceFailed option=${modelOptionChoice.name} err=$finalError")
                    }
                }
            }
            if (finalError != null) {
                "Download failed [${modelOptionChoice.name}]: $finalError"
            } else {
                val postStatus = ext.checkStatus()
                if (postStatus == OnDeviceModelStatus.AVAILABLE) {
                    runCatching { ext.warmUp() }
                }
                val name = runCatching { ext.getModelName() }.getOrNull()?.takeIf { it.isNotBlank() }
                "Post-download status [${modelOptionChoice.name}]: $postStatus${name?.let { " · model=$it" } ?: ""}"
            }
        }.getOrElse { err ->
            "Download error [${err::class.java.simpleName}]: ${err.message ?: "unknown"}"
        }
    }

    @OptIn(PublicPreviewAPI::class)
    suspend fun extractMissingRequirements(
        policy: PolicyScenario,
        question: String,
        sourceText: String,
        modeChoice: InferenceModeChoice,
        cloudConsent: Boolean,
        modelOptionChoice: OnDeviceModelOptionChoice = OnDeviceModelOptionChoice.PREVIEW
    ): HybridInferenceOutcome {
        val t0 = System.currentTimeMillis()
        requireCloudConsent(modeChoice, cloudConsent)
        if (!isFirebaseConfigured()) {
            throw IllegalStateException(
                "Firebase is not configured (missing gitignored android/app/google-services.json)."
            )
        }

        val sdkMode = when (modeChoice) {
            InferenceModeChoice.PREFER_ON_DEVICE -> InferenceMode.PREFER_ON_DEVICE
            InferenceModeChoice.ONLY_ON_DEVICE -> InferenceMode.ONLY_ON_DEVICE
            InferenceModeChoice.PREFER_IN_CLOUD -> InferenceMode.PREFER_IN_CLOUD
            InferenceModeChoice.ONLY_IN_CLOUD -> InferenceMode.ONLY_IN_CLOUD
        }

        val model = Firebase.ai(backend = GenerativeBackend.googleAI()).generativeModel(
            modelName = CLOUD_MODEL_NAME,
            onDeviceConfig = OnDeviceConfig(
                mode = sdkMode,
                modelOption = toSdkModelOption(modelOptionChoice)
            )
        )

        val prompt = buildExtractionPrompt(policy, question, sourceText)
        val objResponse = model.generateObject(
            jsonSchema = GeneratedGapwiseProposal.firebaseAISchema(),
            prompt = prompt
        )

        val elapsed = System.currentTimeMillis() - t0
        val source = objResponse.response.inferenceSource
        val sourceWire = source.toString().lowercase().replace(" ", "_")
        val modelVersion = objResponse.response.modelVersion?.takeIf { it.isNotBlank() }
        val extModelName = if (sourceWire == "on_device") {
            runCatching { model.onDeviceExtension?.getModelName() }.getOrNull()?.takeIf { it.isNotBlank() }
        } else {
            null
        }
        val effectiveVersion = listOfNotNull(
            modelVersion,
            extModelName?.takeIf { it != modelVersion }
        ).joinToString(" / ").ifBlank { null }
        val parsed = objResponse.getObject()

        val validChecks = parsed?.suggested_checks
            ?.filter { it.label.isNotBlank() }
            ?.take(8)
            .orEmpty()

        val rawSnippet = objResponse.response.text
        val log = HybridAiLog(
            inferenceSource = sourceWire,
            adapterLabel = if (sourceWire == "on_device") "firebase-ai-ondevice-aicore" else "firebase-ai-cloud",
            modelVersion = effectiveVersion,
            elapsedMs = elapsed,
            mode = modeChoice,
            consentGranted = cloudConsent,
            errorClass = if (parsed == null) "MalformedOutputError" else "none",
            rawOutput = rawSnippet,
            message = "inferenceSource=$sourceWire · option=${modelOptionChoice.name} · ${elapsed}ms · model=${effectiveVersion ?: "unreported"}",
            modelOption = modelOptionChoice
        )
        android.util.Log.i(
            "GAPWISE_AI",
            "extractDone mode=${modeChoice.name} option=${modelOptionChoice.name} source=$sourceWire elapsedMs=$elapsed version=${effectiveVersion ?: "unreported"} suggestions=${validChecks.size} rawLen=${rawSnippet?.length ?: 0}"
        )
        return HybridInferenceOutcome(validChecks, log)
    }

    @OptIn(PublicPreviewAPI::class)
    private fun toSdkModelOption(choice: OnDeviceModelOptionChoice): OnDeviceModelOption = when (choice) {
        OnDeviceModelOptionChoice.PREVIEW -> OnDeviceModelOption.PREVIEW
        OnDeviceModelOptionChoice.PREVIEW_FAST -> OnDeviceModelOption.PREVIEW_FAST
        OnDeviceModelOptionChoice.STABLE -> OnDeviceModelOption.STABLE
    }

    private fun buildExtractionPrompt(policy: PolicyScenario, question: String, sourceText: String): String {
        val listed = policy.terms.joinToString("\n") { "- ${it.id}: ${it.label}" }
        val snippet = sourceText.take(6000).ifBlank { "(none supplied)" }
        return """
            You are a cautious evidence auditor for GAPWISE.
            Task: inspect the decision question, listed conditions, and supplied source document, and propose missing prerequisites, exceptions, or conflicts.
            Safety rules:
            1. Return ONLY structured fields matching the schema; never invent answers or certify approval.
            2. Every item in suggested_checks MUST copy a verbatim substring into `quote` from the source document, or leave `quote` empty string "".

            Question: $question
            Already listed checklist items:
            $listed

            Supplied source text:
            $snippet
        """.trimIndent()
    }

    companion object {
        const val CLOUD_MODEL_NAME = "gemini-3.5-flash-lite"

        fun requireCloudConsent(modeChoice: InferenceModeChoice, cloudConsent: Boolean) {
            if (modeChoice != InferenceModeChoice.ONLY_ON_DEVICE && !cloudConsent) {
                throw HybridConsentRequiredException(
                    "Cloud-capable mode (${modeChoice.name}) blocked without explicit user consent. Enable Cloud Consent or switch to ONLY_ON_DEVICE."
                )
            }
        }

        fun validateProposalGrounding(quote: String, sourceText: String): Boolean =
            SourceAuditor.validateSourceQuote(quote, sourceText)
    }
}
