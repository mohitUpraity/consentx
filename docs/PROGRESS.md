# Progress Tracker

Last reviewed: 2026-11-24. This page tracks ConsentX implementation and its own evidence.

## Overall

- Stage: First local UI/API slice; interaction verification pending
- Mandatory requirements complete: **0 / 11**
- Tasks complete: **3 / 23** (12 in progress)
- Evidence items captured: **0 / 11**
- Lifecycle tests passing: **0 / 12 required** (not run)
- Test procedures: written in `docs/TEST_PLAN.md`; automated tests and a passing run are still pending
- Major PS-002 workstreams: tracked in the summary table at the top of `docs/TASKS.md`
- Demo: UI visible at `http://localhost:5001` in the user's screenshot; required lifecycle not yet verified end to end

These counts change only when implementation exists and its proof is recorded. A design document alone does not mark a runtime requirement Done.

## Requirement status

| Requirement | Status | Evidence link |
|---|---|---|
| R-01 Synthetic service/users | In progress | Localhost screenshot shows CampusPulse and demo account selector |
| R-02 Exactly three purposes | In progress | Localhost screenshot shows three purpose cards; API interaction not verified |
| R-03 Grant/withdraw records | In progress | API/UI code exists; state-change proof pending |
| R-04 Notice version/hash | In progress | Screenshot shows v1.0 and SHA-256; re-consent flow pending |
| R-05 Mock API enforcement | In progress | Endpoint/UI code exists; allow/deny proof pending |
| R-06 Withdrawal denial | In progress | Endpoint/UI code exists; withdrawal then denial not demonstrated |
| R-07 Audit/export | In progress | UI links/endpoints exist; exported records not verified |
| R-08 12+ passing tests | Not started | — |
| R-09 Demo flow | In progress | UI is present; complete sequence not demonstrated |
| R-10 Pseudocode | In progress | Draft exists; align with verified runtime behavior |
| R-11 Submission materials | Not started | — |

## Update rule

When a task is completed, update `TASKS.md`, this tracker and `EVIDENCE.md` together. Link the actual proof. If a test or demo regresses, change the affected status back to In progress and note the failure.
