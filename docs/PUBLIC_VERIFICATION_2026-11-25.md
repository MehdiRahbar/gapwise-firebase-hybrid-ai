# Public verification — 2026-11-25

## Live application

- URL: <https://gapwise-hybrid-2026.web.app/>
- Alternate URL: <https://gapwise-hybrid-2026.firebaseapp.com/>
- Hosting release: `14c7ff3284b20e54`
- HTTP: 200 on both domains.
- Essential JavaScript/CSS/SVG assets: 2xx and hash-matched against the audited local `dist`.
- Console/page errors: 0 in the clean Chrome audit.
- Failed or bad requests: 0 in the final audit.
- Browser audit paths: Workbench, sidebar, sample scenario, ASK/NO/CONFLICT, Export Audit, Settings/Firebase/App Check, unavailable-Nano message, and mobile overflow.

## Security headers

The Hosting configuration includes `X-Content-Type-Options: nosniff`, strict referrer policy, restrictive Permissions-Policy, `X-Frame-Options: DENY`, and a CSP allowing only the Firebase/App Check and Google endpoints required by the application.

## Cost and credentials

No billing change, production configuration change, personal credential, or App Check debug token was used for this verification. The deterministic workflow remains available without a paid account. Cloud AI use remains subject to the Firebase project owner’s configuration and explicit consent.

## Evidence boundary

This verification checked the public application and its release wiring. It did not run Nano 4 inference. Current device evidence is documented conservatively in the judging guide and video claim review.

