# GAPWISE judging guide

## Fast public demonstration

1. Open <https://gapwise-hybrid-2026.web.app/> in Chrome.
2. Open Workbench and load a sample scenario.
3. Read the source and evidence trail. Use `ASK` when a prerequisite is missing, `NO` when a prohibition is present, and `CONFLICT` when the source disagrees.
4. Provide the human evidence and attestations required by the scenario.
5. Export the audit and inspect the recorded decision, evidence, and model status.

This path is useful on every browser because the deterministic engine does not need Nano or a paid account.

## Unsupported Chrome hardware

Gemini Nano availability depends on Chrome version, operating system, hardware, model download state, regional rollout, and browser capability. If the UI reports `On-device unavailable`, that is an honest capability result. Do not treat a deterministic sample response as Nano output.

When a judge has an eligible Chrome device and the project owner has enabled the required Firebase/App Check configuration, the judge may connect Firebase and choose `ONLY_ON_DEVICE`. The app then records `on_device` only when the runtime reports that source. If the browser cannot create the local model, the request fails closed and no cloud fallback is used.

## Separately verified Nano 4 evidence

The evidence was captured on the second laptop: AMD Ryzen 5 5500U, 32 GB RAM, Chrome 157. It records eight successful Firebase AI Logic requests across two runs with `ONLY_ON_DEVICE`, `source=on_device`, and no recorded errors. Chrome Internals and the component manifest show `gemma4_component` version `2026.8.7.929`, `BaseModelSpec.name=gemma4-2b-it`, and `prompt_api_gemma4=Available`.

The JavaScript API did not report the exact model version. The Gemini Nano 4 identification is therefore supported by the Chrome v4 feature/component/manifest chain plus the real on-device Firebase path; it is not official Google certification or a direct JavaScript model-version attestation. The evidence was captured on Laptop 2 and must not be re-run or attributed to the main laptop.

## Privacy and cost

Do not paste private documents into the public demo. Cloud-capable modes transmit prompts only after explicit consent and require App Check. If the judge cannot or does not want to authorize cloud use, remain on the deterministic sample workflow.

