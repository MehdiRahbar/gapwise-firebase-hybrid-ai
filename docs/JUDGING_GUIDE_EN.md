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

## Separately verified Nano evidence

The project retains separate evidence from a controlled Chrome test. That evidence is not bundled with this public source export and must be reviewed as evidence, not inferred from the sample UI. The current public disclosure is conservative: the available current-device record confirms an on-device Prompt API path with a `v3Nano` label and an unreported SDK model version; it does not establish Gemini Nano 4 availability on this laptop or for all judges. No claim of universal Nano 4 support is made.

## Privacy and cost

Do not paste private documents into the public demo. Cloud-capable modes transmit prompts only after explicit consent and require App Check. If the judge cannot or does not want to authorize cloud use, remain on the deterministic sample workflow.

