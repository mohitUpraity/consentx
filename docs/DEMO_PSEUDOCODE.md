# Mentor Demo Pseudocode

This pseudocode matches the `/api/data-access` enforcement handler and revocation pipeline in `app.py` (v2.0.0). Identity here is a session-pinned synthetic demo identity; this prototype does not implement production authentication.

```text
function requestData(userId, purposeId, consumerId, operation, requestedFields):
    activeUser = current session synthetic user
    if activeUser is missing:
        return HTTP 401 with decision DENY, reason NO_DEMO_IDENTITY, payload null

    if userId is not in DEMO_USERS:
        log DENY (UNKNOWN_USER) to access_decisions and SHA-256 audit_ledger
        return HTTP 403 with decision DENY, reason UNKNOWN_USER, payload null

    if userId != activeUser:
        log DENY (IDENTITY_MISMATCH) to access_decisions and SHA-256 audit_ledger
        return HTTP 403 with decision DENY, reason IDENTITY_MISMATCH, payload null

    if purposeId is not one of {P1, P2, P3}:
        log DENY (INVALID_PURPOSE) to access_decisions and SHA-256 audit_ledger
        return HTTP 400 with decision DENY, reason INVALID_PURPOSE, payload null

    policyFields = allowed fields for (consumerId, purposeId)
    if requestedFields is empty/invalid -> reason = INVALID_REQUEST
    else if policyFields is empty      -> reason = CONSUMER_PURPOSE_MISMATCH
    else if operation != "READ"        -> reason = OPERATION_NOT_ALLOWED
    else if not requestedFields <= policyFields -> reason = FIELD_SCOPE_EXCEEDED

    currentNotice = load active notice
    latestEvent = load newest consent event for (userId, purposeId)

    if reason is not set:
        if latestEvent is missing               -> reason = NO_ACTIVE_CONSENT
        else if latestEvent.action != "grant"   -> reason = CONSENT_WITHDRAWN
        else if latestEvent.notice != currentNotice -> reason = NOTICE_MISMATCH
        else                                    -> reason = ACTIVE_CONSENT

    decision = ALLOW iff reason == ACTIVE_CONSENT, else DENY
    log decision + consumerId + operation + requestedFields to access_decisions and SHA-256 audit_ledger

    if decision == DENY:
        return HTTP 403 with decision DENY, reason, payload null

    payload = filter(PURPOSES[purposeId].payload, requestedFields)
    return HTTP 200 with decision ALLOW, reason ACTIVE_CONSENT, payload, decision_trace
```

## Withdrawal & Revocation Orchestration Pseudocode

```text
function withdrawConsent(userId, purposeId):
    append WITHDRAW consent event tied to active notice (version + SHA-256)
    append CONSENT_WITHDRAWN to SHA-256 audit_ledger
    cancel QUEUED pending_actions matching (userId, purposeId, consumerId)
    create revocation_job (status = PENDING, attempts = 0)
    append REVOCATION_QUEUED and WORK_CANCELLED to SHA-256 audit_ledger

function deliverRevocation(revocationId):
    if job.status == ACKNOWLEDGED:
        return HTTP 409 ALREADY_ACKNOWLEDGED (idempotent)
    outcome = invokeConsumerAdapter(job)
    increment attempts
    if outcome.ok:
        job.status = ACKNOWLEDGED (store adapter_event_id + receipt_digest)
        append REVOCATION_DELIVERED and REVOCATION_ACKNOWLEDGED to SHA-256 audit_ledger
    else:
        job.status = FAILED (store last_error honestly; do not fake ack)
        append REVOCATION_FAILED to SHA-256 audit_ledger
```
