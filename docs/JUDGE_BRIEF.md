# Judge brief: why the mock is the point

## 30-second explanation

“The risk PS-002 asks us to prototype is not whether a service can generate data. It is whether a downstream service can keep using data after consent is missing, withdrawn, for the wrong purpose, or tied to an old notice. CampusPulse uses fictional accounts and deterministic synthetic payloads so we can test that authorization boundary safely. On every request, the server checks the exact user-purpose event and active notice before releasing anything. The response trace and audit export make the result inspectable.”

## If a judge says “isn't this just rule-based mock data?”

“Yes, the payload and decision policy are intentionally small and deterministic. That is how this prototype isolates the PS-002 question: did the policy enforcement point stop the request? The evidence is the sequence of consent events, the current notice reference, the HTTP allow/deny result, and the presence or absence of the payload. The mock is a controlled boundary test, not a claim that synthetic records are production data.”

## Show the mechanism, not a feature list

1. Grant P1 for one synthetic account. Point out its own notice version and digest.
2. Request P1 and show the server's four policy checks followed by `RELEASED`.
3. Request P2 without granting it. Show the purpose-specific denial and no payload.
4. Withdraw P1 and request it again. Show `CONSENT_WITHDRAWN`, `WITHHELD`, and the audit row.
5. Publish a changed notice. Show the previous grant become stale, re-confirm P1, and request again.
6. Export the matching JSON/CSV and tie the request IDs back to the screen.

## Be precise about the boundary

- The user identities and payloads are synthetic. The app does not authenticate real users or call a real downstream service.
- The policy check is a prototype PEP implemented inside this Flask app. It demonstrates request-time enforcement but does not prove that every real service in an organization is wired through it.
- A SHA-256 digest identifies exact notice text; it does not prove that a person read or understood that text.
- This is technical evidence for the specified lifecycle, not legal certification or universal DPDP/GDPR compliance.

## A credible next step after PS-002

Only after the required prototype demo is complete, choose one real but low-risk workflow such as campus event reminders. Add one authenticated identity source and one downstream adapter that accepts a narrowly scoped request, while keeping an explicit deny path and event-level evidence. Measure a concrete outcome such as whether a withdrawn reminder request is stopped before a message is queued. Do not widen into multiple services or real sensitive records until the identity, revocation, retention, and audit boundaries are designed and tested.
