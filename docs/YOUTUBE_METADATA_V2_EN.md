# YouTube metadata — V2 Premium

## Upload status

`READY_FOR_OWNER_REVIEW — CORRECTED_EVIDENCE_CLAIMS`

The corrected video preserves the real on-device Firebase AI Logic evidence and explains the Chrome component/manifest provenance and JavaScript model-version limitation.

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
- Separate controlled evidence from Laptop 2 records eight successful `ONLY_ON_DEVICE` Firebase AI Logic requests across two runs. Chrome v4 / Gemma 4 component and manifest evidence supports the Gemini Nano 4 identification; JavaScript reports the adapter but not an exact model version. This is not Google certification and Nano 4 is not claimed as universally available.

License: Apache-2.0.

## Suggested tags

`Firebase`, `Firebase AI Logic`, `Chrome`, `on-device AI`, `privacy`, `evidence`, `decision support`, `Gemini`, `web app`

## Suggested thumbnail

Use the corrected safe thumbnail from the local submission staging package. Do not use the older candidates: one exposes a local URL and the other contains the obsolete `NANO4_VERIFIED` wording.

