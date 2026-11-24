# Live ConsentGuard UI review

Observed in the browser on 2026-11-24. These are interface observations from the user-provided deployed links, not a source-code or security audit of those services. I used navigation only and did not submit a grant, withdrawal, notice publication, simulator request, or diagnostic run.

## TC328 — Manus deployment

URL: <https://consentguard-rap2vz2h.manus.space/>

- A dark left rail organizes the app into Dashboard, Consent Management, API Simulator, Notice Manager, and Audit & Tests.
- The consent view explains purpose isolation and shows one card per purpose with current state, notice version, and a direct grant/withdraw control. The selected demo user showed all three purposes withdrawn under v3.
- The simulator previews a `POST /api/downstream/share` request and reserves space for a server decision trace. It says that consent is read from the database for every request and that the default is fail closed.
- The notice manager accepts editable notice text, increments the next version, warns that older grants become stale, and lists earlier text and SHA-256 digests.
- The audit view exposes CSV/JSON exports and displays event type/decision, user/purpose, reason, request ID, notice digest and timestamp. It showed 19 access decisions, 12 recent consent events, and 24 listed audit rows.
- The page offered an automated lifecycle suite, but its observed status was **Not run yet**. No live test result was claimed from this inspection.
- Review note: the displayed v1, v2, and v3 notice records had the same text and SHA-256 digest. A notice-change demo is clearer when the actual notice content changes.

## TC204 — Vercel deployment

URL: <https://consent-guard-2.vercel.app/#dashboard>

- The app has a left navigation for Dashboard, Manage Consent, Data Access Simulator, Audit Log, Analytics, Notice & Versions, Demo Users, and Diagnostic Tests (14).
- The simulator identifies a Flask PEP gateway, lets the reviewer select a synthetic user and purpose, and displays the HTTP result and reason. The visible saved result was HTTP 403 after withdrawal, with “Zero protected bytes delivered.”
- The app emphasizes purpose-level checks and a concrete downstream denial state. This is easy to explain to judges because the request, status and outcome are on one screen.
- The sign-in page offered demo accounts. The active session changed while navigating to the requested dashboard anchor; I did not enter credentials or mutate consent/notice data.
- The diagnostic-test count appeared in navigation, but I did not run the external app's diagnostics, so this review does not verify those tests.

## What ConsentX adopts

- A five-view navigation so a judge can move directly between orientation, consent choices, the PEP request, notice evidence, and audit exports.
- A dashboard that states the problem in operational terms: a stored consent choice is only useful if the data-access path checks it.
- A server-generated decision trace that pairs the HTTP result with each policy check and says whether data was released or withheld.
- A visible notice revision history with exact stored content, version, timestamp, and digest. The app blocks publishing unchanged text as a new version.
- Audit counts, filterable evidence, and CSV/JSON exports remain available in their own view.

The first version remains within PS-002's synthetic prototype scope. The follow-up real-world-impact phase should add a credible deployment scenario only after the core demo and evidence are complete.
