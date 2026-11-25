# GAPWISE

GAPWISE is an evidence-first decision workbench. It separates deterministic source checks and human attestations from optional AI-assisted suggestions, so a missing prerequisite, a contradiction, or an unverified assumption cannot silently become an approval.

## Public demo

- Live application: <https://gapwise-hybrid-2026.web.app/>
- Firebase project: `gapwise-hybrid-2026`
- The live demo is free to open and does not require a paid account for its deterministic sample workflow.

## Architecture

The Web application is a Vite single-page application under `web/`.

1. The deterministic engine audits source text, tracks scope and evidence, and produces `ASK`, `YES`, `NO`, or `CONFLICT` states.
2. Human answers and attestations remain explicit. A model suggestion never replaces source verification or coverage review.
3. Firebase AI Logic is the real integration boundary in `web/firebase-hybrid.mjs`. Cloud-capable modes use the Firebase Web SDK and Firebase App Check; they do not call a third-party API directly.
4. `ONLY_ON_DEVICE` is fail-closed. It uses the browser's Prompt API adapter when available and refuses cloud fallback when the local model is unavailable.
5. Cloud inference is opt-in through the UI and requires App Check configuration. The public build does not contain an App Check debug token.

The verified device evidence retained for this project is separate from this public source export. It must not be interpreted as a claim that Gemini Nano 4 is available on every Chrome device. On unsupported hardware, the sample workflow and deterministic gate remain usable, while on-device inference is reported as unavailable.

## Reproducible Web setup

Requirements: Node.js 20.19 or newer and a current Chromium-based browser. Python 3.11+ is needed only for the optional evaluation scripts.

```text
npm ci
copy .env.example .env.local
npm run build
npm run dev
```

Open the Vite URL shown by the command. Do not open `web/index.html` with `file://`.

`.env.local` contains public Firebase Web configuration values. Obtain them from the Firebase project owner or Firebase Console; never place private service-account keys, App Check debug tokens, keystores, or browser profiles in this repository.

Useful checks:

```text
npm test
npm run audit
python -m unittest discover -s evaluation -p "test_*.py" -v
```

The `deploy` script is intentionally not part of the judging workflow. Production deployment requires an authorized owner and a separate release review.

## Judging the application

Use the live URL first. Open Workbench, load a sample, inspect the source/evidence trail, answer a prerequisite with `YES`, `NO`, or `CONFLICT`, and export the audit. The sample flow is deterministic and is not presented as Nano inference.

If Chrome reports that the on-device model is unavailable, this is an expected capability result on unsupported hardware. Select a cloud-capable mode only when the judge has permission to send the prompt to the configured Firebase backend and App Check succeeds. See [docs/JUDGING_GUIDE_EN.md](docs/JUDGING_GUIDE_EN.md).

## Repository and licensing

This public export is prepared from a clean source tree without the original repository's unsanitized Git history, private evidence, Chrome profiles, generated build folders, or credentials. The project is licensed under Apache-2.0; see [LICENSE](LICENSE).

See [docs/ARCHITECTURE_EN.md](docs/ARCHITECTURE_EN.md), [docs/PUBLIC_VERIFICATION_2026-11-25.md](docs/PUBLIC_VERIFICATION_2026-11-25.md), and [SECURITY.md](SECURITY.md) for technical and release details.

