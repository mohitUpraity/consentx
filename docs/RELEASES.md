# Releases

## 1.0.0 — Initial local demo baseline

- Added CampusPulse consent UI, three purpose cards, notice version/hash display, mock data request panel and audit export links.
- Added Flask endpoints and SQLite persistence for synthetic consent events, notice versions and access decisions.
- Added audit logging for invalid-purpose and unknown-user access denials.
- Status: local baseline. The full PS-002 test suite and evidence package are still pending; see `PROGRESS.md`.

## 1.1.0 — Notice publication audit

- Added a system audit event when a new notice version is published.
- Included notice publication events in the combined JSON and CSV audit exports.
- Status: implemented and covered by the 19-case automated lifecycle suite. Manual demo/evidence capture remains pending.
