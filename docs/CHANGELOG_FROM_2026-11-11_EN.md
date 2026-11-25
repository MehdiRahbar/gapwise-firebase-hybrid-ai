# Change disclosure from 2026-11-11

## History limitation

The canonical Git repository supplied for this release starts at root commit `7ba5ae5` on 2026-11-21. It does not contain a canonical baseline commit from 2026-11-11, so a claim of a complete line-by-line diff from November 11 would be inaccurate. This document describes the observable pre-existing components and the changes recorded after the available history begins.

## Components already present in the available root

The root snapshot already contained the Web workbench, deterministic decision engine, Firebase hybrid integration, tests, evaluation corpus/tools, Android companion module, Apache-2.0 license, and prior evidence/documentation. These are disclosed as pre-existing in the available repository snapshot rather than claimed as newly authored after November 11.

## Recorded post-November-11 work

- 2026-11-21: Firebase AI Logic hybrid integration, App Check/Hosting verification, structured parsing, `ONLY_ON_DEVICE`, and cloud App Check paths.
- 2026-11-22: fail-closed handling for overlong input, real-world evaluation tooling, Android companion work, physical-device observations, App Check separation, PII sanitation, multilingual parser/parity work, and balanced/adaptive benchmarks.
- 2026-11-23: Material 3 Web UI modernization, UI checkpoints, Android observability, Nano4 runner/checkpoint tooling, and video-preparation work.
- 2026-11-25: release-hardening work included the public-source export, CSP correction, browser audit tooling, logo/favicon and Android launcher resource integration, and final live-site verification.

The clean public export intentionally does not carry the original unsanitized Git history. No original history was rewritten.

