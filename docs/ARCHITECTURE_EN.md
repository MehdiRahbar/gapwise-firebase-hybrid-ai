# GAPWISE architecture

## Decision pipeline

The application has a conservative decision pipeline:

`source text -> deterministic audit -> proposed checks -> human evidence -> decision gate -> audit export`

The deterministic engine is authoritative for the gate. `YES` requires the required conditions and attestations; `NO` records a prohibition; `CONFLICT` blocks a positive decision when source claims disagree; `ASK` means information or coverage is still insufficient.

## Firebase AI Logic hybrid path

`web/firebase-hybrid.mjs` uses the official Firebase JavaScript SDK and `firebase/ai` with `GoogleAIBackend`. The adapter exposes four explicit inference modes:

- `PREFER_ON_DEVICE`
- `ONLY_ON_DEVICE`
- `PREFER_IN_CLOUD`
- `ONLY_IN_CLOUD`

The local path is bridged through the browser Prompt API. The cloud path is configured through Firebase AI Logic and uses structured JSON output. The application records source, adapter, model/version when reported, elapsed time, timeout, mode, consent state, and parse/error class in local evidence.

`ONLY_ON_DEVICE` checks for the browser LanguageModel API and rejects the request when it is unavailable. It does not silently send the prompt to the cloud. Cloud-capable modes require explicit consent and App Check setup.

## Trust boundaries

- Source text and human answers are user-controlled inputs.
- Model proposals are untrusted suggestions and are displayed with their evidence quotes.
- The deterministic gate and explicit attestations control the final status.
- Firebase App Check helps protect cloud requests; it is not an authorization substitute for Firebase rules or project configuration.
- Local evidence is an export aid, not a tamper-proof compliance record.

## Android companion

The Android module mirrors the deterministic decision engine and includes the GAPWISE launcher/adaptive icon resources. It is source-only in this public export; no private `google-services.json`, keystore, APK, or device profile is included.

