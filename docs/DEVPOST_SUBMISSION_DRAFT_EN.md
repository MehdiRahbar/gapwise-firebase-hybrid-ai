# Devpost submission draft

## Publication status

`READY_FOR_OWNER_REVIEW — BLOCKED_BY_VIDEO_CLAIM_REVIEW`

The draft is prepared, but the final video must not be uploaded as-is because its closing card says `NANO4_VERIFIED`, while the current evidence record does not verify Nano 4 on the current device. Correct the narration/subtitles/card or attach a verified artifact before publication.

## Links

- Live application: <https://gapwise-hybrid-2026.web.app/>
- Alternate live application: <https://gapwise-hybrid-2026.firebaseapp.com/>
- GitHub repository: `NOT_CREATED_YET — owner publication approval required`
- YouTube video: `NOT_UPLOADED_YET — blocked pending video claim correction`
- Devpost submission: `DRAFT ONLY — not submitted`

## What GAPWISE does

GAPWISE is an evidence-first decision workbench for policies and source documents. It finds candidate prerequisites, asks for missing information, exposes contradictions, and keeps human attestations separate from model suggestions. The gate produces explainable `ASK`, `YES`, `NO`, and `CONFLICT` outcomes and exports an audit trail.

## Technical implementation

- Vite Web application with a deterministic source-audit and decision engine.
- Firebase AI Logic through the official Firebase JavaScript SDK.
- Firebase App Check for cloud-capable requests.
- Explicit `PREFER_ON_DEVICE`, `ONLY_ON_DEVICE`, `PREFER_IN_CLOUD`, and `ONLY_IN_CLOUD` modes.
- `ONLY_ON_DEVICE` fails closed when Chrome’s Prompt API is unavailable.
- Structured JSON parsing with bounded fields and fail-closed handling for malformed output.
- Android companion source with matching deterministic engine and launcher/adaptive icon resources.

## Evidence and limitations

The public live-site audit passed with HTTP 200, matching audited assets, no console/page errors, and successful sample workflows. Separate controlled evidence records an on-device Prompt API path on a supported test environment, but current-device evidence reports `v3Nano`/unreported SDK version and does not verify Nano 4 availability on this laptop. Nano 4 support is therefore not claimed for every judge or device.

The deterministic workflow is the reproducible fallback and is not misrepresented as real Nano inference. No billing, production configuration change, or new Nano 4 inference was performed during final submission preparation.

## License

Apache-2.0.

