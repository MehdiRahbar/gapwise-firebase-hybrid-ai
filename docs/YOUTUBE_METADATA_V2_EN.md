# YouTube metadata — V2 Premium

## Upload status

`BLOCKED_PENDING_VIDEO_CLAIM_CORRECTION`

The video assets are technically valid, but the current closing card makes a Nano 4 verification claim that is not supported by the current evidence record. Do not upload until the claim is corrected or a matching verified artifact is attached.

## Proposed title

`GAPWISE — Know What You Don't Know Before You Decide | Firebase AI Logic`

## Proposed description

GAPWISE is an evidence-first decision workbench for policies and source documents.

It separates deterministic source checks and human attestations from optional AI suggestions, then makes missing prerequisites and contradictions visible before a decision is accepted. The Web application uses Firebase AI Logic, Firebase App Check, structured output, and an explicit `ONLY_ON_DEVICE` fail-closed mode for browsers that expose the Prompt API.

Public demo: https://gapwise-hybrid-2026.web.app/

Judging notes:
- The sample workflow is deterministic and remains usable without Nano or a paid account.
- On unsupported Chrome hardware, the app reports on-device unavailability and does not silently claim Nano output.
- Cloud-capable inference requires explicit consent and the project’s App Check configuration.
- Separate controlled evidence exists for an on-device Prompt API path, but the current device record does not verify Gemini Nano 4 availability. Nano 4 is not claimed as universally available.

License: Apache-2.0.

## Suggested tags

`Firebase`, `Firebase AI Logic`, `Chrome`, `on-device AI`, `privacy`, `evidence`, `decision support`, `Gemini`, `web app`

## Suggested thumbnail

Do not use the existing `THUMBNAIL_GAPWISE_V2.jpg` or `THUMBNAIL_GAPWISE_V2_CLOSING.jpg` without correction: they expose a local URL or contain the unsupported `NANO4_VERIFIED` claim. A safe thumbnail must use the GAPWISE brand and evidence-first message without a Nano 4 verification assertion.

