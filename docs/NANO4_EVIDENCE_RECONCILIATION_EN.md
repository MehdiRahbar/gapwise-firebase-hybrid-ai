# Nano 4 evidence reconciliation

The Nano 4 evidence was captured on the second laptop, not on the main development laptop. No reproduction is required on the main laptop.

## What the imported handoff proves

- Hardware: AMD Ryzen 5 5500U, 32 GB RAM, Chrome Desktop 157.0.8103.80.
- Chrome component evidence: `gemma4_component`, version `2026.8.7.929`, ready at 100%; Chrome Internals reported `prompt_api_gemma4: Available`.
- Manifest evidence: `BaseModelSpec.name = gemma4-2b-it`, spec version `2026.06.10.0000`, and a 2,523.23 MiB model folder with `weights.bin`.
- Runtime path: Firebase AI Logic on project `gapwise-hybrid-2026`, `InferenceMode.ONLY_ON_DEVICE`, active adapter `chrome-prompt-api-adapter`, cloud consent off.
- Inference: 8 successful requests across `nano4_proof_20261124_164110` and `nano4_video_20261124_164308`; every recorded inference has `source = on_device`, `errorClass = none`, and elapsed times from 10,387 ms to 29,876 ms.
- The evidence archive has 77 files; all 77 hashes match `COMPLETE_SHA256_MANIFEST.json`.

## What remains a limitation

The JavaScript response did not report an exact model version: `modelVersion = null` / `unreported`. The Nano 4 product identification is therefore evidence-based provenance from Chrome Internals, the component store, the manifest, feature flags, model files, and the successful Firebase AI Logic path. It is not a Google certification and is not a direct JavaScript model-version attestation.

The handoff also records that `cloudRequests = 0` is based on the configured `ONLY_ON_DEVICE` constraint, unchecked cloud consent, and `source = on_device`; it is not a packet-capture audit. The public judging guide must retain this distinction.

