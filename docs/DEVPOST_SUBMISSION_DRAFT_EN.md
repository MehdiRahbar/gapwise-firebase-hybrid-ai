# Devpost submission draft

## Publication status

`SUBMITTED_TO_CONTEST — PUBLIC_LINKS_VERIFIED`

The corrected video states the evidence provenance precisely: real Firebase AI Logic on-device inference, Chrome v4 / Gemma 4 component and manifest evidence from Laptop 2, eight successful requests across two runs, and the JavaScript model-version limitation.

## Links

- Live application: <https://gapwise-hybrid-2026.web.app/>
- Alternate live application: <https://gapwise-hybrid-2026.firebaseapp.com/>
- GitHub repository: <https://github.com/MehdiRahbar/gapwise-firebase-hybrid-ai> (`main` baseline: `31bdea2d64e86dfa6319e12ea26f4737343b8649`)
- YouTube video: <https://youtu.be/sEtk_Cvqax0>
- Devpost submission: <https://devpost.com/software/gapwise-find-what-s-missing-before-you-decide> (`Submitted to #BuildHybridAI 2026` publicly visible; private logged-in submission form fields/attestations remain owner-only).

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

The public live-site audit passed with HTTP 200, matching audited assets, no console/page errors, and successful sample workflows. Separate controlled evidence from Laptop 2 records the real on-device path and the Chrome v4 / Gemma 4 component identity. The JavaScript model version remains unreported, so the product identification is evidence-based provenance rather than official Google certification. Nano 4 support is not claimed for every judge or device.

The deterministic workflow is the reproducible fallback and is not misrepresented as real Nano inference. No billing, production configuration change, or new Nano 4 inference was performed during final submission preparation.

## License

Apache-2.0.

