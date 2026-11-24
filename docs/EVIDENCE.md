# Evidence and Demo Plan

This file is the evidence index. Evidence must come from the current ConsentX build. Design documents and old test logs do not prove ConsentX works.

## Required evidence

| Evidence ID | Capture | Proves | Planned location | Status |
|---|---|---|---|---|
| E-01 | Clean-start setup and app health | R-01, reproducibility | `evidence/manual-walkthrough-2026-11-24.md`, `evidence/manual-health.json` | Captured (synthetic isolated DB) |
| E-02 | UI/API shows exactly P1–P3 | R-02 | `evidence/manual-purposes-api.json`, `evidence/manual-walkthrough-2026-11-24.md` | API and browser observed; screenshot still pending |
| E-03 | Grant event with notice version/hash | R-03, R-04 | `evidence/manual-lifecycle-responses.json`, `evidence/manual-lifecycle-audit.json` | Captured |
| E-04 | Allowed consumer request and returned synthetic payload | R-05 | `evidence/manual-lifecycle-responses.json`, `evidence/manual-walkthrough-2026-11-24.md` | Captured |
| E-05 | Withdrawal event then denied next request with no payload | R-03, R-06 | `evidence/manual-lifecycle-responses.json`, `evidence/manual-lifecycle-audit.json` | Captured |
| E-06 | Purpose isolation: P1 grant does not authorize P2/P3 | R-02, R-05 | `evidence/test-results.txt`, `evidence/manual-p3-deny.json`, `evidence/manual-walkthrough-2026-11-24.md` | Captured for P2 and P3 |
| E-07 | Notice v2/hash, stale-consent denial, fresh re-consent | R-04, R-09 | `evidence/manual-lifecycle-responses.json`, `evidence/manual-lifecycle-audit.json` | Captured |
| E-08 | JSON and CSV exports with matching consent, access-decision and notice-publication events | R-07 | `evidence/manual-lifecycle-audit.json`, `evidence/manual-lifecycle-audit.csv`, filtered exports, and `evidence/live-export-ui-check.*` | Live endpoints returned HTTP 200 and matching row counts; Chrome link click was blocked by `ERR_BLOCKED_BY_CLIENT` |
| E-09 | At least 12 tests pass on clean test database | R-08 | `evidence/test-results.txt` | Captured: 24 passed |
| E-10 | End-to-end recorded walkthrough | R-09 | `evidence/demo.*` | Not captured (browser run logged, no screenshot/video saved) |
| E-11 | Final pseudocode and submission checklist | R-10, R-11 | `docs/DEMO_PSEUDOCODE.md`, submission evidence | Pseudocode captured and reviewed; submission proof pending |

## Observed UI check (2026-11-24)

The user's screenshot shows ConsentX rendered at `localhost:5001` with styling loaded, notice v1.0 and its SHA-256 visible, a demo-account selector, three purpose cards and the mock-consumer/audit sections. This confirms the page is being served through the app rather than opened as a raw template. It does **not** prove button interactions, API decisions, persistence, export contents or the full demo sequence. The screenshot remains in the conversation and has not been copied into the project evidence folder.

## Version baseline

ConsentX `1.2.0` is the current local demo baseline. It includes purpose consent, withdrawal enforcement, notice versioning, audit exports, and audit filters. The version label does not mean all PS-002 requirements have passed; the test and evidence counts in `PROGRESS.md` remain authoritative.

## Demo script

1. Start from clean synthetic account and notice v1.
2. Show three purposes; grant P1 only.
3. Request P1 from the mock consumer; show ALLOW and the limited synthetic payload.
4. Request P2 without granting it; show DENY and no payload.
5. Withdraw P1; immediately request P1 again; show DENY and reason `CONSENT_WITHDRAWN`.
6. Publish notice v2; show the stale grant denied, then grant under v2 and show the request becomes allowed again.
7. Open audit timeline and export JSON/CSV; match the shown events to the demo steps.

## Evidence integrity rules

- Save exact command, environment and date with test output.
- Do not edit test output by hand; rerun after code changes.
- Use a fresh temporary test database so prior demo state cannot make tests pass accidentally.
- Keep personal credentials, API keys and real user data out of evidence.
