# Security and public-release policy

## Public configuration

Firebase Web configuration values and a reCAPTCHA Enterprise site key are client-side configuration. They are not service-account credentials. Their security comes from Firebase rules, App Check, authorized domains, quotas, and backend policy—not from keeping the browser configuration secret.

The repository contains only placeholders in `.env.example` and `android/app/google-services.json.example`. Do not commit a populated `.env.local`, `google-services.json`, a service-account JSON file, a private key, an App Check debug token, a Chrome profile, or device evidence containing personal identifiers.

## AI and App Check boundaries

Cloud-capable Firebase AI Logic modes require explicit user consent in the UI and App Check configuration. `ONLY_ON_DEVICE` is fail-closed and does not silently fall back to the cloud. Debug App Check mode is development-only and must never be enabled in a public build.

The live site was checked without credentials or a personal App Check debug token. A judge should use the deterministic sample workflow when local model support or cloud authorization is unavailable.

## History and evidence

The original working repository contains historical review hits for personal paths, email addresses, device identifiers, and private test artifacts. Its history has not been rewritten. This public export is a fresh source release with no copied `.git` directory and no private evidence folder.

Before publication, run a repository secret scan over the exact staged tree and review the resulting diff. If a credential is ever found, revoke it at the provider before discussing the code publicly.

## Reporting

Report a suspected vulnerability privately to the project owner. Do not include tokens, personal device identifiers, or private evidence in an issue or pull request.

