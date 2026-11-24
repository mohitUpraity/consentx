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
| E-09 | At least 12 tests pass on clean test database | R-08 | `evidence/test-results.txt` | Captured: 52 passed |
| E-10 | End-to-end recorded walkthrough | R-09 | `evidence/demo.*` | Not captured (browser run logged, no screenshot/video saved) |
| E-11 | Final pseudocode and submission checklist | R-10, R-11 | `docs/DEMO_PSEUDOCODE.md`, submission evidence | Pseudocode updated for v2.0.0; submission proof pending |
| E-12 | Concurrent access requests each produce a unique persisted decision | v1.7 T-060 | `evidence/test-results.txt`, T-32 in `tests/test_ps002.py` | Captured: 16 simultaneous requests, 16 distinct IDs and 16 matching audit rows |
| E-13 | Withdrawal creates an auditable pending consumer instruction | v1.7 T-065 | `evidence/test-results.txt`, T-33/T-34, `/api/revocations`, and [browser check](../evidence/v1.7-revocation-queue-check.md) | Captured by isolated tests and browser run |
| E-14 | Withdrawal cancels only same-user, same-purpose queued work | v1.7 T-066 | `evidence/test-results.txt`, T-35, `/api/pending-actions`, and [browser check](../evidence/v1.7-revocation-queue-check.md) | Captured by isolated test and browser run |
| E-15 | Cross-user request spoofing is denied | v1.7 T-061 | `evidence/test-results.txt`, T-36 | Captured by isolated test |
| E-16 | Notice publication requires operator authorization | v1.7 T-062 | `evidence/test-results.txt`, T-37 | Captured by isolated test; UI shows disabled publishing in student mode |
| E-17 | Adapter delivery, outage failure, retry, and idempotency | v2.0 T-063, T-067, T-068, T-072 | `evidence/test-results.txt`, T-43–T-47 | Captured by isolated tests |
| E-18 | My Privacy view & downloadable JSON/HTML privacy receipts | v2.0 T-069, T-070 | `evidence/test-results.txt`, T-48, T-49 | Captured by isolated tests |
| E-19 | Unified SHA-256 hash-chain audit ledger & tamper detection | v2.0 T-071 | `evidence/test-results.txt`, T-39–T-42, `/api/audit/verify` | Captured by isolated tests |

## Observed UI check (2026-11-24)

The user's earlier screenshot shows the pre-v1.5 ConsentX screen at `localhost:5001` with notice v1.0, a demo-account selector, three purpose cards and the mock-consumer/audit sections. The updated v2.0.0 interface still needs a saved screenshot; the earlier image is not proof of the new layout.

## Version baseline

ConsentX `2.0.0` completes the v1.7 revocation-orchestration roadmap (T-060–T-072), adding independent consumer adapters, delivery/acknowledgement/retry workflows, My Privacy and downloadable privacy receipts, unified SHA-256 hash-chain verification, live in-browser diagnostics, light/dark mode, and Render deployment configuration. Clean-start video capture (T-073) and R-11 submission packaging remain open.

## Latest feature verification

- v1.3.0 audit detail fields: [browser check](../evidence/v1.3-audit-timeline-check.md).
- v1.4.0 full-history paging and filter reset: [browser check](../evidence/v1.4-audit-history-check.md).
- Test/demo database separation: [configuration review](../evidence/test-demo-isolation-review.md).
- Latest full automated run: [`test-results.txt`](../evidence/test-results.txt), 51 passed, including T-32 concurrency, T-33–T-35 revocation behavior, T-36 identity isolation, T-37 operator authorization, T-38 UI test-count sync, T-39–T-42 SHA-256 ledger integrity, T-43–T-47 adapter delivery/failure/retry/idempotency, T-48–T-50 My Privacy, receipts, and diagnostics, and T-51 `DEMO.md` + self-guided judge UI verification.

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
