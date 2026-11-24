# Releases

## 1.0.0 — Initial local demo baseline

- Added CampusPulse consent UI, three purpose cards, notice version/hash display, mock data request panel and audit export links.
- Added Flask endpoints and SQLite persistence for synthetic consent events, notice versions and access decisions.
- Added audit logging for invalid-purpose and unknown-user access denials.
- Status: initial feature baseline; later code through v1.2.0 is covered by the 24-case suite. Manual feature walkthrough and evidence capture remain pending; see `PROGRESS.md`.

## 1.1.0 — Notice publication audit

- Added a system audit event when a new notice version is published.
- Included notice publication events in the combined JSON and CSV audit exports.
- Status: implemented and covered by the 24-case automated lifecycle suite. Manual demo/evidence capture remains pending.

## 1.2.0 — Audit filters

- Added audit filtering by synthetic user, purpose and ALLOW/DENY outcome.
- JSON and CSV export links preserve the selected filters.
- Made audit-filter event binding null-safe when an older cached page omits those optional controls; restarted the local server to load the current matching template.
- Status: 24 automated tests pass, including API filter and filtered-export cases. Browser lifecycle and filter interactions were exercised on an isolated database; recording and remaining screenshot/export-link proof are pending. See [the v1.2 walkthrough](WALKTHROUGH.md#feature-6--filter-audit-records-v12).

## 1.3.0 — Readable audit evidence

- Expanded audit timeline rows to show event kind, synthetic user, purpose, action/decision, reason/details, notice version/hash, timestamp, and event ID.
- Kept existing filter and export behavior; each visible row can now be matched to its exported record.
- Status: verified; all 24 automated tests pass and browser confirms the expanded timeline fields. Saved screenshot and recorded demo remain pending. See `evidence/v1.3-audit-timeline-check.md`.

## 1.4.0 — Full audit history

- Added an event count and progressive **Load older events** control so the interface can expose the complete filtered audit history, 12 rows at a time.
- Changing user, purpose, or decision filters resets the visible window to the newest 12 matching events; export links continue to use the active filters.
- Status: verified; the v1.4.0 baseline's 25-case suite passed and browser confirmed full-history paging, filter reset, the end-of-history state, and filtered export URLs. The current suite has 28 cases. See `evidence/v1.4-audit-history-check.md`.

## 1.5.0 — Judge-facing control center

- Reorganized the UI into five navigable views: Dashboard, Consent Management, Data Access Simulator, Notice Versions, and Audit & Tests.
- Added a dashboard with live counts, three purpose states, active notice digest, and the request-time policy order.
- Added a server-generated decision trace that explains each policy check and shows when the synthetic payload is released or withheld.
- Added newest-first notice history and an editable revision flow that chooses the next version and warns that old grants become stale.
- Added tests for allow/deny traces and notice-history ordering; the current 28-case suite passes.
- Status: automated verification passed. A screenshot and recorded clean-start walkthrough remain open evidence items.

## 1.6.0 — Consumer and field-scoped requests

- Added consumer identity, operation, and requested data fields to simulated access requests.
- Enforced consumer-purpose field scopes and returned only the selected fields on allow.
- Added the latest-decision dashboard and expanded quality-assurance explanation.
- Status: implementation and 31 isolated tests recorded in `evidence/test-results.txt`.

## 1.7.0-dev1 — Roadmap and concurrent request integrity

- Defined the product direction as consent enforcement plus downstream revocation action tracking.
- Added tasks for request integrity, demo identity/operator boundaries, independent consumers, revocation delivery, pending-work cancellation, retries, user privacy receipts, and end-to-end evidence.
- Scope and acceptance limits are documented in `ROADMAP_v1.7.md`; detailed tracking is in `TASKS.md`.
- Hardened SQLite write transactions so access requests acquire the writer lock before evaluating policy and writing their audit decision.
- Added T-32, which sends 16 concurrent requests and verifies unique response IDs and one persisted audit row per request.
- Status: T-060 implemented and verified; 32 isolated tests passed at this development checkpoint.

## 1.7.0-dev2 — Persistent withdrawal instructions

- Added purpose-mapped revocation jobs in the same transaction as consent withdrawal, with unique ID, consumer, status, timestamps, attempts, and acknowledgement reference fields.
- Added user-filtered `GET /api/revocations`, linked `REVOCATION_QUEUED` audit events, and a queued-status list in Consent Management.
- Added T-33/T-34 for job creation, user isolation, and grant-without-job behavior; cross-consumer and field-scope policy coverage is tracked as T-064.
- Status: T-060, T-064 and T-065 implemented and verified; all 34 isolated tests pass. Adapter delivery, pending-work cancellation, acknowledgement and retries remain unimplemented.

## 1.7.0-dev3 — Purpose-scoped pending work cancellation

- Seeded clearly synthetic queued reminders, recommendations, and analytics exports for the two demo users.
- A withdrawal now cancels only that user's queued actions for the withdrawn purpose and links each cancelled action to the revocation ID.
- Added `/api/pending-actions`, displayed the queue and cancellation status in Consent Management, and added T-35 isolation coverage.
- Status: T-066 implemented and verified; all 35 isolated tests pass. Simulated consumer delivery, acknowledgement, retries, and downloadable privacy receipts remain open.

## 1.7.0-dev4 — Demo identity and operator boundaries

- Pinned student actions to a signed Flask session identity; cross-user `user_id` spoof attempts deny without returning another user's state or payload.
- Restricted notice publication to an operator session unlocked by `CONSENTX_OPERATOR_TOKEN`; no default operator token is shipped, and publishing stays disabled in student mode.
- Added T-36/T-37 for cross-user isolation and operator-only notice publication.
- Made the operator control binding null-safe so a stale template cannot crash the whole JavaScript app if it omits the new control.
- Status: T-061/T-062 implemented and verified; all 37 isolated tests pass. This is a synthetic demo identity boundary, not real account authentication. Downstream adapter delivery, acknowledgements, retries, and privacy receipts remain open.

## 2.0.0 — Revocation orchestration, My Privacy, receipts, and SHA-256 audit ledger

- Added `adapters.py` with DB-persisted simulated consumer adapters (`notification-service`, `recommendation-service`, `analytics-service`), online/offline outage toggles, delivery (`POST /api/revocations/<id>/deliver`), idempotent retry (`POST /api/revocations/<id>/retry`), and manual queued-work simulation (`POST /api/pending-actions/simulate`).
- Added `audit_chain.py` with a unified tamper-evident SHA-256 hash-chained `audit_ledger` (`GET /api/audit/verify`, `GET /api/audit/ledger`) covering consent, access decisions, notice publications, queued-work cancellations, deliveries, failures, retries, and acknowledgements.
- Added **My Privacy** (`GET /api/my-privacy`) and downloadable **JSON / print-friendly HTML Privacy Receipts** (`GET /api/privacy-receipt/<id>`), including linked evidence IDs and the erasure-limitation disclaimer.
- Added in-browser live diagnostics (`GET /api/diagnostics`), simulator quick-attack presets + out-of-scope field testing, dynamic suite test count (`test_38`), light/dark theme toggle, fixed CSS variables and 5th metric card layout, and added `gunicorn` + `render.yaml` for persistent Render deployment.
- Status: 50 isolated automated tests pass (`evidence/test-results.txt`). Clean-start demo recording and R-11 submission packaging remain open.
