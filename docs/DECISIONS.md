# Decision Log

Record important choices made while building ConsentX from the PS-002 requirements. Each decision should state its rationale and whether it is proposed or accepted.

| ID | Decision | Rationale / follow-up | Status |
|---|---|---|---|
| D-01 | `consentx/` is the sole ConsentX project root. | Keeps implementation, evidence and progress together. | Accepted |
| D-02 | Use one fictional service, CampusPulse, with three explicit purpose scopes. | Keeps the demo within PS-002 and gives each purpose a bounded synthetic payload. | Proposed; confirm in T-001 |
| D-03 | Use only synthetic accounts and data; make no legal-certification claim. | Matches the problem's stated scope. | Accepted |
| D-04 | Keep consent decisions as append-only events and deny access when consent is absent, stale or unverifiable. | Makes lifecycle evidence inspectable and avoids permissive fallback behavior. | Proposed; implement and test |
| D-05 | Proposed initial stack: Flask, SQLite and a small browser UI. | A compact local stack should be straightforward to run and demonstrate; confirm setup in T-003. | Proposed |

## Change history

Add a dated row when an accepted decision changes, with the reason and affected requirements.
