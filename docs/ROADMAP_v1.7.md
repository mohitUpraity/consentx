# ConsentX v1.7 — From Consent to Verified Action

## Product direction

Evolve ConsentX from a purpose-aware consent prototype into a **consent enforcement and revocation orchestration** prototype for a synthetic university event workflow. The product should show what a user's withdrawal causes across connected services, which queued work stops, which services acknowledge it, and what evidence the user can inspect.

This is a staged plan. Roadmap entries describe intended work and are not claims that those capabilities already exist. Keep the existing Flask/SQLite foundation and synthetic-data boundary. Do not add AI policy decisions, blockchain, or unnecessary infrastructure.

## Release target

**1.7.0 — Revocation orchestration foundation.** The release will be complete when the foundation, consumer adapters, withdrawal jobs, pending-action handling, user receipts, audit verification, and judge walkthrough meet their task acceptance criteria and have saved test/demo evidence. Until then, `VERSION` identifies the current in-progress development line.

## Implementation tasks

### Phase 1 — Strengthen the foundation

- **T-060 (first): Concurrent access-decision integrity.** Exercise simultaneous access requests against an isolated SQLite database. Require one unique request ID and one audit decision per request; address lock/transaction issues revealed by the test.
- **T-061: Demo identity boundary.** Make the synthetic identity boundary explicit and ensure a caller cannot act as another user merely by changing a request field. Keep the demo usable without introducing real personal data. **Implemented:** Flask session pinning rejects cross-user request fields; this is an explicit demo identity boundary, not real account authentication.
- **T-062: Notice publishing authorization.** Restrict notice publication to an operator role and document the demo authentication model. **Implemented:** the server requires a configured `CONSENTX_OPERATOR_TOKEN` and an operator session; no default token is shipped.

### Phase 2 — Independent consumer simulation

- **T-063: Consumer registry and adapters.** Model the existing notification, recommendation, and analytics services as separate simulated consumers with explicit purpose and field scopes. Keep their labels consistent with P1–P3; do not present the analytics example as personal-data sharing with an event partner.
- **T-064: Request contract and policy coverage.** Preserve consumer, purpose, operation, and field-scope evaluation; add tests for cross-consumer isolation and unauthorized fields.

### Phase 3 — Revocation orchestration (signature feature)

- **T-065: Revocation and delivery records.** Add persistent withdrawal IDs and per-consumer delivery state, timestamps, attempts, and acknowledgement references.
- **T-066: Pending work lifecycle.** Seed synthetic queued work by consumer/purpose and cancel or block only work affected by a withdrawal.
- **T-067: Adapter delivery and acknowledgements.** Deliver withdrawal instructions through actual local adapter functions/endpoints; persist each response and support pending/failed/acknowledged states.
- **T-068: Retry and failure simulation.** Let the judge simulate an unavailable consumer, retry delivery, and observe an honest unresolved state until acknowledgement.

### Phase 4 — User privacy center and receipts

- **T-069: My Privacy view.** Show permissions, recipients and fields shared, withdrawal progress, and unresolved actions in plain language.
- **T-070: Privacy receipt.** Generate a downloadable receipt tied to the withdrawal ID with consent/notice references, affected consumers, pending work, and acknowledgement history. State clearly that an acknowledgement is not proof of erasure of every copy.

### Phase 5 — Verification and judge demonstration

- **T-071: Unified evidence and integrity.** Link consent, access, withdrawal, delivery, pending-work, and acknowledgement events; add an integrity verification check and tamper/failure tests.
- **T-072: End-to-end scenario tests.** Verify P3 consumer access denial after withdrawal, affected work cancellation, retry/acknowledgement outcomes, and continued P1 access when only P3 is withdrawn.
- **T-073: Clean-start judge walkthrough.** Record the full success and failure paths with matching user receipt and operator evidence; update demo and evidence docs.

## Acceptance principles

1. A withdrawal blocks new access immediately, before any delivery attempt.
2. Only services associated with the withdrawn purpose receive a revocation instruction.
3. Unrelated purpose access and pending work remain unaffected.
4. Pending, failed, and acknowledged are distinct persisted states; no success is fabricated.
5. A consumer acknowledgement means the simulated consumer processed the instruction. It does not prove universal deletion or resolve retention obligations.
6. Every user-visible claim must be traceable to stored events and reproducible tests.

## Competitive position and limits

ConsentX's differentiator is purpose-aware downstream revocation orchestration with user-visible acknowledgement evidence and hash-chained audit verification. The pilot scenario is a proposed synthetic campus event workflow, not an institutional deployment or compliance certification.

## First execution checkpoint

T-060–T-072 are now implemented and verified in `v2.0.0` (52 passing automated tests in `evidence/test-results.txt`). Only T-073 (clean-start recorded judge walkthrough) remains open.
