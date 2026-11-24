# Progress Tracker

Last reviewed: 2026-11-24. This page tracks ConsentX implementation and its own evidence.

## Overall

- Stage: v2.0.0 complete — field-scoped PEP, independent consumer adapters, revocation delivery/failure/retry, My Privacy & downloadable receipts, tamper-evident SHA-256 audit ledger, live browser diagnostics, dark mode, and Render deployment config implemented
- Version: **2.0.0** (50 automated tests pass; T-060–T-072 implemented and verified)
- Mandatory requirements complete: **7 / 11** (code complete; R-01/R-02/R-09 screenshot & recorded demo video and R-11 repo/PDF submission remain manual capture/submission steps)
- PS-002 task baseline: **15 / 26** complete (remaining items are screenshot/video recording and R-11 submission)
- v1.7/v2.0 roadmap: **13 / 14** complete (T-060–T-072 done; T-073 clean-start demo video recording remains)
- Evidence items captured: **9 / 11** (`evidence/test-results.txt` 50 passed; clean-start screenshots/video and submission proof remain open)
- Lifecycle tests passing: **50 / 12 required** (v2.0.0; concurrency, identity isolation, operator gate, revocation delivery/failure/retry/idempotency, My Privacy, receipts, and SHA-256 audit chain verified)
- Test procedures: lifecycle/filter checks, audit detail rendering, and full-history paging are browser verified; v1.5.0 dashboard, notice history, and decision trace are implemented and API-tested; current UI screenshot and recorded demo remain pending
- Major PS-002 workstreams: tracked in the summary table at the top of `docs/TASKS.md`
- Demo: lifecycle verified in isolated browser run and API evidence saved; screen recording and final rehearsal remain
- v1.7 scope: see [`ROADMAP_v1.7.md`](ROADMAP_v1.7.md); independent adapters, delivery/acknowledgement, retries, and privacy receipts are still unimplemented.

These counts change only when implementation exists and its proof is recorded. A design document alone does not mark a runtime requirement Done.

## Requirement status

| Requirement | Status | Evidence link |
|---|---|---|
| R-01 Synthetic service/users | In progress | Isolated browser walkthrough log; saved screenshot/video still needed |
| R-02 Exactly three purposes | In progress | API state capture and browser observation; saved UI screenshot still needed |
| R-03 Grant/withdraw records | Done | `evidence/manual-lifecycle-audit.json` preserves grant and withdrawal records |
| R-04 Notice version/hash | Done | `evidence/manual-lifecycle-responses.json`; suite verifies hash and stale grants |
| R-05 Mock API enforcement | Done | Captured allow/deny responses and 37 passing lifecycle tests, including decision-trace checks |
| R-06 Withdrawal denial | Done | Captured withdrawal/next-request denial and purpose-isolation test |
| R-07 Audit/export | Done | Matching JSON/CSV exports and filtered export files captured |
| R-08 12+ passing tests | Done | `evidence/test-results.txt` (37 passed) |
| R-09 Demo flow | In progress | Full sequence exercised and logged; required recording remains pending |
| R-10 Pseudocode | Done | `docs/DEMO_PSEUDOCODE.md` reviewed against `app.py` and lifecycle evidence |
| R-11 Submission materials | Not started | — |

## Update rule

When a task is completed, update `TASKS.md`, this tracker and `EVIDENCE.md` together. Link the actual proof. If a test or demo regresses, change the affected status back to In progress and note the failure.
