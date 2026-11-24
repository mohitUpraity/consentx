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
