# Requirements and Acceptance Criteria

Source: `../PS-002.pdf` (PS-002). Requirement text here is a project checklist, not legal advice. Status starts as **Not started** and changes only when the stated proof exists.

## Product scope

Build one synthetic service called **CampusPulse**. Use synthetic accounts and synthetic event data. The prototype demonstrates consent evidence and technical access enforcement only.

The three independent purposes are:

| ID | Purpose | Example mock data released only for this purpose |
|---|---|---|
| P1 | Event reminders | opted-in reminder channel and upcoming event IDs |
| P2 | Personalized event suggestions | synthetic interests and suggested event IDs |
| P3 | Anonymous usage analytics | aggregated synthetic feature-use counts |

A grant for one purpose must never authorize another purpose. Do not add a fourth consent purpose without revising the PS-002 scope and recording why.

## Mandatory requirements

| ID | Requirement | Acceptance criterion | Required proof | Status |
|---|---|---|---|---|
| R-01 | Single synthetic service and synthetic users | CampusPulse is the only service in the demo; all accounts and payloads are clearly synthetic. | Seed/demo data file and demo screenshot or recording. | Not started |
| R-02 | Exactly three itemized purposes | UI and API expose P1, P2, P3 only; consent is stored separately for each user-purpose pair. | Purpose list/API test plus UI screenshot. | Not started |
| R-03 | Record grant and withdrawal | Each action records user, purpose, action, timestamp, notice version and notice hash; prior events remain inspectable. | Database/audit export showing grant and withdrawal rows. | Not started |
| R-04 | Notice versioning | Each consent event references the exact active notice version and SHA-256 digest; changing the notice makes old consent stale under our stated demo policy. | Notice v1/v2 records, independently recalculated hash, stale-consent test. | Not started |
| R-05 | Mock downstream API enforcement | Every data request checks the current consent for the exact user, purpose and current notice before returning data. Missing, withdrawn, stale or unverifiable consent is denied by default. | API request/response capture for allow and deny cases; automated tests. | Not started |
| R-06 | Withdrawal blocks subsequent requests | After a withdrawal succeeds, the next request for that same purpose returns a denial and no protected payload. Other purposes remain unaffected. | Before/after API response capture and purpose-isolation tests. | Not started |
| R-07 | Audit records and export | Consent events and every allow/deny decision are auditable and exportable as JSON and CSV. | Export files with required fields and parser/shape checks. | Not started |
| R-08 | At least 12 lifecycle/enforcement tests | At least 12 distinct automated tests pass from a clean test database. Test cases and manual procedures are specified in `docs/TEST_PLAN.md`; they still need an automated suite and a passing run. | Full test command output and test report committed under `evidence/`. | Not started |
| R-09 | Required demonstration | Show grant → allowed sharing → withdrawal → denied next request → notice change → stale denial → fresh re-consent. | Short recorded walkthrough plus matching audit export. | Not started |
| R-10 | Pseudocode for mentor demo | One concise pseudocode snippet matches the implemented enforcement decision order. | `docs/DEMO_PSEUDOCODE.md` and slide/demo copy. | Not started |
| R-11 | Submission materials | Team repository is private, required collaborator/ownership steps are completed, the requested structure PDF is present, and mentor demo is prepared. | Repository settings/checklist and submitted PDF/demo link. | Not started |

## Quality constraints

- Consent is purpose-specific; no broad global consent flag.
- A denial response contains a stable reason code and no protected payload.
- Use UTC timestamps in records and exports.
- Notice hash is evidence of content identity, not proof the user read or understood the notice.
- No real personal data, external data-sharing partner, or production-compliance claim.
- Test-only bypasses must be unavailable in the demo/production configuration.

## Explicit out of scope

Legal certification, universal DPDP/GDPR compliance, real downstream integrations, real user accounts, performance claims, and processing real personal data.
