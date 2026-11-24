# Progress Tracker

Last reviewed: 2026-11-24. This page tracks ConsentX implementation and its own evidence.

## Overall

- Stage: v1.6.0 field-scoped simulator implemented; v1.7 roadmap documented, identity and operator boundaries added, concurrency hardened, and withdrawal queue/work cancellation implemented
- Version: **1.7.0-dev4** (37 automated tests pass; T-060–T-062, T-064–T-066 verified)
- Mandatory requirements complete: **7 / 11**
- PS-002 task baseline: **13 / 26** complete (10 in progress); v1.7 roadmap: **6 / 14** complete
- Evidence items captured: **8 / 11** (R-02 has API/browser evidence but still needs a saved UI screenshot; recorded demo and submission proof remain open)
- Lifecycle tests passing: **37 / 12 required** (v1.7.0-dev4; concurrency, demo identity, operator authorization, revocation queue, and scoped work cancellation verified)
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
