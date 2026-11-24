# Mentor Demo Pseudocode

This is the planned decision order. Keep it aligned with the implementation before presenting it as implemented.

```text
function requestData(authenticatedUser, requestedPurpose):
    if requestedPurpose is not one of P1, P2, P3:
        audit(DENY, INVALID_PURPOSE)
        return denyWithoutPayload(INVALID_PURPOSE)

    user = validateIdentity(authenticatedUser)
    if user is invalid:
        audit(DENY, UNAUTHENTICATED)
        return denyWithoutPayload(UNAUTHENTICATED)

    event = latestConsentEvent(user, requestedPurpose)
    if event is missing or event.action is not GRANT:
        audit(DENY, NO_ACTIVE_CONSENT)
        return denyWithoutPayload(NO_ACTIVE_CONSENT)

    notice = activeNotice()
    if event.noticeVersion != notice.version or event.noticeHash != notice.sha256:
        audit(DENY, NOTICE_MISMATCH)
        return denyWithoutPayload(NOTICE_MISMATCH)

    payload = syntheticPayloadFor(requestedPurpose)
    audit(ALLOW, ACTIVE_CONSENT)
    return allowWithPayload(payload)
```

**Status:** Planned, not yet implemented or runtime-verified.
