# Task Plan

Status key: `[ ]` Not started, `[/]` In progress, `[x]` Done, `[-]` Blocked. Mark a task Done only after its listed proof is saved and linked. Requirements map to `docs/REQUIREMENTS.md`.

## PS-002 major task tracker

This is the top-level view of the challenge deliverables. The detailed tasks below are the work needed to close each row. A workstream is Done only when its acceptance criteria and evidence are complete.

| Major PS-002 workstream | Related requirements | Detailed tasks | Current status | Completion proof |
|---|---|---|---|---|
| A. Synthetic service, users and exactly three purposes | R-01, R-02 | T-001, T-010, T-011, T-020, T-030 | In progress | UI/API expose CampusPulse, two synthetic users and only P1–P3; automated exact-catalog test passes. |
| B. Purpose-specific grant/withdraw and notice version/hash | R-03, R-04 | T-010–T-013, T-020, T-030 | In progress | Append-only grant/withdraw records include purpose, UTC timestamp and active notice version/hash; notice hash independently verified. |
| C. Mock downstream consumer enforces current consent | R-05, R-06 | T-021–T-023, T-031 | In progress | API allows only matching current grants; missing, withdrawn, stale and unverifiable states deny with no payload. |
| D. Audit records and export | R-07 | T-010, T-022, T-032, T-033, T-046, T-049 | In progress | Consent, all allow/deny decisions and notice publications appear in matching JSON/CSV exports; invalid user/purpose denials are audited. |
| E. 12+ lifecycle/enforcement tests | R-08 | T-040, T-041, T-046 | Done | 19 tests pass against isolated temporary DBs; output saved at `evidence/test-results.txt`. |
| F. Required demo and pseudocode | R-09, R-10 | T-031, T-042–T-044 | In progress | Recorded grant → allow → withdraw → deny → notice change → stale deny → re-consent flow; pseudocode matches code. |
| G. Hackathon submission items | R-11 | T-045 | Not started | Private repo/collaboration steps, required structure PDF and mentor demo are ready. |

**Current overall state:** no major workstream is complete yet. UI and initial API code exist, but their runtime behavior and evidence are not verified. Update this table together with the detailed task checkboxes and `PROGRESS.md`.

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
- [ ] T-023 Keep test fixtures/bypass isolated from demo configuration (quality constraints). Proof: configuration review.

## M3 — Interface and audit

- [/] T-030 Build consent screen with three independent purpose controls and notice version/hash context (R-02–R-04). User screenshot confirms styled screen; interaction proof pending.
- [/] T-031 Build mock consumer panel showing request, decision, reason and payload/no-payload result (R-05, R-06, R-09). UI exists; full walkthrough pending.
- [/] T-032 Build readable audit timeline with filters for user, purpose and decision (R-07). UI exists; verify data behavior and filters.
- [/] T-033 Implement JSON and CSV audit exports with stable fields/timestamps (R-07). Links exist; save and validate actual exports.

## M4 — Verification and demo

- [x] T-040 Implement at least 12 distinct lifecycle/enforcement tests (R-08). Proof: 19 cases in `tests/test_ps002.py`, mapped in `docs/TEST_PLAN.md`.
- [x] T-041 Run tests on isolated temporary databases; fix failures; save exact command/output and date (R-08). Proof: `evidence/test-results.txt` (19 passed).
- [ ] T-042 Capture allow, withdrawal, deny, notice-change, stale-deny and re-consent evidence (R-03–R-09). Proof: `evidence/` files referenced by the evidence index.
- [ ] T-043 Write pseudocode that mirrors the final enforcement code (R-10). Proof: `DEMO_PSEUDOCODE.md` reviewed against implementation.
- [ ] T-044 Rehearse and record a clean-start demo; verify exported audit trail matches the screen flow (R-09). Proof: demo artifact and evidence checklist.
- [ ] T-045 Complete private repository, collaboration, PDF and mentor-demo submission checklist (R-11). Proof: checklist in evidence index.
- [x] T-046 Log every rejected access decision, including unknown user/purpose requests, so audit behavior matches R-07. Proof: tests T-12/T-13 assert denial audit rows.
- [x] T-047 Write feature-by-feature verification procedures and expected results. Proof: `docs/TEST_PLAN.md` (this documents the plan; it does not mean tests have passed).
- [x] T-049 Record notice publication as a system audit event and include it in JSON/CSV exports. Proof: T-10/T-14/T-16 verify notice event and export contents.

## Next PS-002 verification checkpoint

At this checkpoint, the automated suite has been run against the features built so far. Remaining manual UI walkthrough and saved demo/export artifacts are still open; rerun the full suite after the next code change and complete those manual proofs before marking the related requirements Done.

## Suggested order

Complete M0 first, then M1 and M2 before polishing M3. Do not record a feature as implemented merely because it appears in a mockup or README. Finish M4 against the running build.
