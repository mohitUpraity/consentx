# Mentor Demo Pseudocode

This pseudocode follows the current `/api/data-access` decision order in `app.py`. Identity here means membership in the demo's synthetic user allowlist; this prototype does not implement login or production authentication.

```text
function requestData(userId, purposeId):
    if userId is not one of the configured synthetic demo users:
        write audit decision DENY with reason UNKNOWN_USER
        return HTTP 403 with decision DENY, reason UNKNOWN_USER, payload null

    if purposeId is not exactly P1, P2, or P3:
        write audit decision DENY with reason INVALID_PURPOSE
        return HTTP 400 with decision DENY, reason INVALID_PURPOSE, payload null

    currentNotice = load active notice
    latestEvent = load newest consent event for this user and this purpose

    if latestEvent does not exist:
        reason = NO_ACTIVE_CONSENT
    else if latestEvent.action is not grant:
        reason = CONSENT_WITHDRAWN
    else if latestEvent.noticeVersion/hash differs from currentNotice.version/hash:
        reason = NOTICE_MISMATCH
    else:
        reason = ACTIVE_CONSENT

    decision = ALLOW only when reason is ACTIVE_CONSENT; otherwise DENY
    write an audit decision with decision, reason, user, purpose and current notice reference

    if decision is DENY:
        return HTTP 403 with decision DENY, reason, payload null

    payload = the synthetic payload mapped to this exact purpose
    return HTTP 200 with decision ALLOW, reason ACTIVE_CONSENT, payload
```

**Review status:** Compared with the current handler on 2026-11-24. It matches the app's user-before-purpose validation, reason codes, append-only latest-event policy, withdrawal-before-notice-mismatch order, audit-before-response behavior, and payload creation only after ALLOW. Automated lifecycle tests and the saved manual API capture provide behavioral evidence; see `evidence/test-results.txt` and `evidence/manual-lifecycle-responses.json`.
