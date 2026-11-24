# Manual Browser Walkthrough — 2026-11-24

Environment: ConsentX v1.2.0 at `http://127.0.0.1:5002/`, using disposable SQLite database `/tmp/consentx-manual-20261124.sqlite3` (synthetic records only). Browser interaction was performed against the rendered app.

## Lifecycle observations

- Clean start showed notice v1.0, a SHA-256 hash, two demo accounts, three purpose cards, and no audit events.
- Granted Aarav/P1: P1 changed to Granted while P2/P3 remained Not granted.
- Requested Aarav/P1: HTTP 200 `ALLOW`, `ACTIVE_CONSENT`, with synthetic event IDs.
- Requested Aarav/P2 without granting: HTTP 403 `DENY`, `NO_ACTIVE_CONSENT`, payload null.
- Withdrew Aarav/P1 and requested again: HTTP 403 `DENY`, `CONSENT_WITHDRAWN`, payload null.
- Re-granted P1 under v1.0, published notice v2.0: UI displayed a new SHA-256 and marked P1 Re-consent needed.
- Requested P1 before re-consenting: HTTP 403 `DENY`, `NOTICE_MISMATCH`, payload null.
- Re-granted P1 under v2.0 and requested again: HTTP 200 `ALLOW`, `ACTIVE_CONSENT`, with synthetic payload.
- Created Mira/P2 grant, allowed request, withdrawal, and denied request to exercise audit filters.
- Filtered the browser audit view by Mira, P2, and Allowed/Denied. The export links updated to carry all selected filter parameters; displayed records matched the selected filters.
- Refreshed the page: consent state and audit events remained present from SQLite.

## Export verification

The following files were fetched from the running app's audit endpoint with the exact filter combinations shown in the browser. Both formats returned HTTP 200; each JSON/CSV pair had matching record counts and matching user, purpose, and decision.

- ALLOW: JSON/CSV HTTP 200; 1 matching records; all match user=student-002, purpose=P2, decision=ALLOW; expected reason ACTIVE_CONSENT; JSON/CSV row counts agree.
- DENY: JSON/CSV HTTP 200; 1 matching records; all match user=student-002, purpose=P2, decision=DENY; expected reason CONSENT_WITHDRAWN; JSON/CSV row counts agree.

## Scope note

This is a written observation log, not a screen recording or screenshot. The full lifecycle and filter interactions were observed in the browser, but no browser screenshot/video was saved. The automated 24-test report remains separate in `test-results.txt`.
- Additional purpose-isolation check: after Aarav had P1 and P2 grants but no P3 grant, selected P3 and requested data in the browser. Observed HTTP 403 `DENY`, `NO_ACTIVE_CONSENT`, and `payload: null`; saved the response at `evidence/manual-p3-deny.json`.
- Export-link attempt on the running app: clicking the JSON link in connected Chrome navigated to a browser error page (`ERR_BLOCKED_BY_CLIENT`). The page was restored to ConsentX. The live JSON and CSV routes were then fetched directly from localhost: both returned HTTP 200 with matching 54-row counts; see `evidence/live-export-ui-check.*`. This confirms endpoint output, but not a successful browser-managed file download.
