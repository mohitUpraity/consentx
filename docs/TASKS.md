# Task Plan

Status key: `[ ]` Not started, `[/]` In progress, `[x]` Done, `[-]` Blocked. Mark a task Done only after its listed proof is saved and linked. Requirements map to `docs/REQUIREMENTS.md`.

## PS-002 major task tracker

This is the top-level view of the challenge deliverables. The detailed tasks below are the work needed to close each row. A workstream is Done only when its acceptance criteria and evidence are complete.

| Major PS-002 workstream | Related requirements | Detailed tasks | Current status | Completion proof |
|---|---|---|---|---|
| A. Synthetic service, users and exactly three purposes | R-01, R-02 | T-001, T-010, T-011, T-020, T-030 | In progress | UI/API expose CampusPulse, two synthetic users and only P1–P3; automated exact-catalog test passes. |
| B. Purpose-specific grant/withdraw and notice version/hash | R-03, R-04 | T-010–T-013, T-020, T-030 | In progress | Append-only grant/withdraw records include purpose, UTC timestamp and active notice version/hash; notice hash independently verified. |
| C. Mock downstream consumer enforces current consent | R-05, R-06 | T-021–T-023, T-031 | In progress | API allows only matching current grants; missing, withdrawn, stale and unverifiable states deny with no payload. |
| D. Audit records and export | R-07 | T-010, T-022, T-032, T-033, T-046, T-049, T-050, T-051 | In progress | API exports captured and consistency checked; full-history paging and filter reset verified in browser; saved screenshot remains pending. |
| E. 12+ lifecycle/enforcement tests | R-08 | T-023, T-040, T-041, T-046, T-052 | Done | 37 tests pass; fixture explicitly uses a temporary DB, restores TESTING config, and avoids the demo DB; output saved at `evidence/test-results.txt`. |
| F. Required demo and pseudocode | R-09, R-10 | T-031, T-042–T-044 | In progress | Recorded grant → allow → withdraw → deny → notice change → stale deny → re-consent flow; pseudocode matches code. |
| G. Hackathon submission items | R-11 | T-045 | Not started | Repository privacy/collaboration proof, the required structure PDF, and mentor-demo preparation have not been verified. |

**Current overall state:** Workstream E (automated lifecycle/enforcement tests) is complete. Other workstreams remain in progress or not started because full acceptance proof is pending. Update this table together with detailed task checkboxes and `PROGRESS.md`.

## M0 — Define and baseline

- [x] T-001 Confirm CampusPulse and the three purpose/data examples (R-01, R-02). Proof: purpose table in requirements and running UI.
- [x] T-002 Define the consent state transitions, notice-change behavior and fail-closed rules directly from PS-002 (R-03–R-06). Proof: enforcement order in `ARCHITECTURE.md`.
- [/] T-003 Pick implementation stack and document setup commands (all). Proof pending: app is visible at localhost:5001 in the user screenshot; capture clean setup notes.

## M1 — Consent and notice model

- [/] T-010 Define schema for users, purposes, notices, consent events and access-decision events (R-02–R-04, R-07). Code exists; schema tests/evidence pending.
- [/] T-011 Seed deterministic synthetic users, three purposes and notice v1 (R-01, R-02, R-04). UI shows these values; save stable clean-start evidence.
- [/] T-012 Implement grant/withdraw as append-only events; derive current status from event history (R-03, R-06). Code exists; interaction and event-history proof pending.
- [/] T-013 Implement notice registration/version/hash and stale-consent policy (R-04). Code exists; independently verify hash and notice-change behavior.

## M2 — Enforcement API

- [/] T-020 Implement consent read/update API with input validation and identity boundary (R-02, R-03). Code exists; API examples and validation verification pending.
- [/] T-021 Implement mock data-access endpoint; check identity, exact purpose, latest event and notice version before creating a payload (R-05, R-06). Code exists; allow/deny captures and tests pending.
- [/] T-022 Ensure every denial has a reason code, is audited and releases no protected payload (R-05–R-07). Code exists; response assertions and audit verification pending.
- [x] T-023 Keep test fixtures/bypass isolated from demo configuration (quality constraints). Proof: `tests/test_ps002.py` patches `DB_PATH` to a per-test temporary directory, restores `TESTING` config after each case, and explicitly asserts test DB differs from the normal demo DB; no bypass route/config exists in `app.py`.

## M3 — Interface and audit

- [/] T-030 Build consent screen with three independent purpose controls and notice version/hash context (R-02–R-04). User screenshot confirms styled screen; interaction proof pending.
- [/] T-031 Build mock consumer panel showing request, decision, reason and payload/no-payload result (R-05, R-06, R-09). UI exists; full walkthrough pending.
- [/] T-032 Build readable audit timeline with filters for user, purpose and decision (R-07). API and browser filter checks pass; saved screen capture remains pending. Chrome blocked the export-link click (`ERR_BLOCKED_BY_CLIENT`) although the live export endpoints return valid files. Null-safe optional filter binding fixed and verified after server restart.
- [x] T-033 Implement JSON and CSV audit exports with stable fields/timestamps (R-07). Proof: `evidence/manual-lifecycle-audit.json`, `evidence/manual-lifecycle-audit.csv`; automated shape and row-count checks pass.
- [x] T-050 Show the audit evidence fields clearly in each timeline row: event type, synthetic user, purpose, result/action, reason/details, notice version/hash, timestamp, and event ID (R-07). Proof: v1.3.0 browser observation in `evidence/v1.3-audit-timeline-check.md`; full 24-test suite in `evidence/test-results.txt`.
- [x] T-051 Let reviewers inspect the full matching audit history in the UI instead of only the newest 12 rows; indicate visible and total counts and progressively load older events (R-07). Proof: browser check in `evidence/v1.4-audit-history-check.md` shows 12→24→48, filter reset to 12 of 42, and all 42 loaded; filtered export URL retained P1.
- [x] T-052 Present the PS-002 lifecycle in dedicated judge-facing views and explain each server-side request check (R-02–R-09). Proof: v1.5.0 UI and tests T-26–T-28; saved screenshot/recording remains an independent evidence item.

## M4 — Verification and demo

- [x] T-040 Implement at least 12 distinct lifecycle/enforcement tests (R-08). Proof: 32 cases in `tests/test_ps002.py`, mapped in `docs/TEST_PLAN.md`.
- [x] T-041 Run tests on isolated temporary databases; fix failures; save exact command/output and date (R-08). Proof: `evidence/test-results.txt` (37 passed).
- [x] T-042 Capture allow, withdrawal, deny, notice-change, stale-deny and re-consent evidence (R-03–R-09). Proof: `evidence/manual-lifecycle-responses.json`, `evidence/manual-lifecycle-audit.json`, and `evidence/manual-walkthrough-2026-11-24.md`.
- [x] T-043 Write pseudocode that mirrors the final enforcement code (R-10). Proof: `docs/DEMO_PSEUDOCODE.md` reviewed against `app.py` and verified lifecycle evidence.
- [ ] T-044 Rehearse and record a clean-start demo; verify exported audit trail matches the screen flow (R-09). Proof: demo artifact and evidence checklist.
- [ ] T-045 Complete private repository, collaboration, PDF and mentor-demo submission checklist (R-11). Proof: checklist in evidence index.
- [x] T-046 Log every rejected access decision, including unknown user/purpose requests, so audit behavior matches R-07. Proof: tests T-12/T-13 assert denial audit rows.
- [x] T-047 Write feature-by-feature verification procedures, expected results, plain-language explanations, and demo notes. Proof: `docs/TEST_PLAN.md` and `docs/WALKTHROUGH.md` (manual UI checks are still pending).
- [x] T-049 Record notice publication as a system audit event and include it in JSON/CSV exports. Proof: T-10/T-14/T-16 verify notice event and export contents.

## Next PS-002 verification checkpoint

At this checkpoint, 32 automated tests pass against isolated temporary databases. Expanded audit-row fields and full-history paging are confirmed in the live browser. The v1.5 control-center screenshot and recorded demo artifacts remain open.

## Documentation rule for each update

Every feature update must add or revise its entry in `docs/WALKTHROUGH.md`: purpose in plain language, PS-002 requirement, preconditions, exact steps, expected result, a negative check, demo explanation, and proof status. Keep `TEST_PLAN.md`, this tracker, `RELEASES.md`, and `PROGRESS.md` aligned. Automated pass status never substitutes for pending browser or export evidence.

## Suggested order

Complete M0 first, then M1 and M2 before polishing M3. Do not record a feature as implemented merely because it appears in a mockup or README. Finish M4 against the running build.

## ConsentX v1.7 implementation roadmap

The product direction and scope are defined in [ROADMAP_v1.7.md](ROADMAP_v1.7.md). These tasks extend PS-002 without replacing the existing lifecycle requirements. Status begins Not started; update only with implementation and linked proof.

| Task | Phase | Deliverable | Acceptance evidence | Status |
|---|---|---|---|---|
| T-060 | Foundation | Concurrent access-decision integrity | Parallel isolated requests produce a distinct request ID and exactly one audit row each; full suite passes. | [x] Done |
| T-061 | Foundation | Explicit demo identity boundary and user isolation | Cross-user spoof attempt is rejected; supported demo identity flow is documented and tested. | [x] Done |
| T-062 | Foundation | Operator authorization for notice publishing | Non-operator cannot publish; operator path and test evidence are documented. | [x] Done |
| T-063 | Consumers | Three independent simulated consumer adapters | Each consumer has a registered purpose/field boundary and observable adapter behavior. | [x] Done (`adapters.py`, T-43–T-46) |
| T-064 | Consumers | Cross-consumer and field-scope policy cases | Authorized requests allow only permitted fields; mismatch and overreach deny with no payload. | [x] Done |
| T-065 | Orchestration | Persistent revocation jobs | Withdrawal creates a unique job per affected consumer with status, timestamps, and attempts. | [x] Done |
| T-066 | Orchestration | Purpose-scoped pending work cancellation | Affected queued work is cancelled/blocked; unrelated-purpose work remains queued. | [x] Done |
| T-067 | Orchestration | Local adapter delivery and acknowledgement persistence | Adapter receives an instruction and its generated response is stored with a linked event ID. | [x] Done (T-43) |
| T-068 | Orchestration | Failure and retry path | Simulated outage remains unresolved, retries are counted, and later acknowledgement resolves it. | [x] Done (T-45–T-47) |
| T-069 | User privacy | My Privacy view | User can inspect permissions, recipients/fields, withdrawal progress, and unresolved actions. | [x] Done (T-48) |
| T-070 | User privacy | Downloadable privacy receipt | Receipt links consent, notice, affected services, pending work, and acknowledgements; limitation is clear. | [x] Done (T-49) |
| T-071 | Evidence | Unified event linkage and integrity verification | Linked history validates; altered event is detected by an automated test. | [x] Done (T-39–T-42) |
| T-072 | Verification | End-to-end scenario test set | Withdrawal blocks the P3 analytics consumer, affects only P3 work, supports retry/ack, and leaves P1 usable. | [x] Done (T-44) |
| T-073 | Demo | Clean-start judge walkthrough | Recorded success and failure paths match stored user receipt and operator evidence. | [ ] Not started |

**Execution rule:** T-060–T-072 are implemented and verified in `tests/test_ps002.py` (50 tests passing). Only T-073 (clean-start recorded walkthrough) and R-11 submission packaging remain open.
