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
