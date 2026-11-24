# Feature Test Plan

This plan turns each PS-002 requirement into reproducible checks. It is **not** itself a test result. The 24-case automated suite passed on 2026-11-24; see `evidence/test-results.txt`. The main lifecycle and audit filters have also been exercised in the browser on an isolated database; saved screenshots/video and a few remaining UI checks are pending. See [WALKTHROUGH.md](WALKTHROUGH.md) for plain-language explanations and presenter notes.

## What PS-002 failure each feature addresses

| PS-002 failure/risk | ConsentX feature | How we prove it |
|---|---|---|
| Consent is recorded but downstream services keep processing | Mock data-access API checks the latest consent on every request | T-04, T-05, T-08, T-10, T-11 |
| One purpose's consent is reused for another | Separate state and payload per P1/P2/P3 | T-02, T-06, T-07 |
| Withdrawal does not stop later sharing | Append withdrawal; immediately deny the next same-purpose request | T-08, T-09 |
| Notice changes cannot be tied to the decision | Store version/hash on each consent event and deny stale grants | T-03, T-10, T-11, T-16 |
| Missing/unknown consent is handled permissively | Fail closed with no payload and a reason code | T-03, T-06, T-12, T-13 |
| No evidence of access decision | Log consent and allow/deny events; export JSON and CSV | T-14, T-15, T-17 |
| Demo cannot prove the whole lifecycle | One scripted end-to-end walkthrough | Manual Demo M-01 |

## Start with an isolated database

From the `consentx/` project root, use a new temporary DB path so existing demo state cannot affect results:

```bash
CONSENTX_DB=/tmp/consentx-test-run.sqlite3 .venv/bin/python app.py
```

In another terminal:

```bash
export BASE_URL=http://127.0.0.1:5001
curl -s "$BASE_URL/api/health"
```

Expected: HTTP 200 and `{"status":"ok",...}`. A fresh DB starts with notice v1.0 and no consent events. If port 5001 is in use, stop the existing ConsentX server or choose another `PORT` and update `BASE_URL`.

### Standard request examples

Grant P1:

```bash
curl -i -X POST "$BASE_URL/api/consent" -H 'Content-Type: application/json' \
  -d '{"user_id":"student-001","purpose_id":"P1","action":"grant"}'
```

Check P1 access:

```bash
curl -i -X POST "$BASE_URL/api/data-access" -H 'Content-Type: application/json' \
  -d '{"user_id":"student-001","purpose_id":"P1"}'
```

Withdraw P1:

```bash
curl -i -X POST "$BASE_URL/api/consent" -H 'Content-Type: application/json' \
  -d '{"user_id":"student-001","purpose_id":"P1","action":"withdraw"}'
```

Publish notice v2 in a clean test run:

```bash
curl -i -X POST "$BASE_URL/api/notices" -H 'Content-Type: application/json' \
  -d '{"version":"2.0","text":"CampusPulse notice v2: revised purpose descriptions."}'
```

Do not run a case against a database already used by a previous run unless the case explicitly depends on prior steps. Prefer a fresh `CONSENTX_DB` path for each isolated case or give each test its own temporary database.

## Automated lifecycle/enforcement cases

The current suite contains 24 independent automated cases. Tests call the Flask test client against a temporary database and assert HTTP status and response fields. Keep them repeatable without relying on order.

| Test | Setup/action | Expected result |
|---|---|---|
| T-01 Health | `GET /api/health` | 200; status is `ok`. |
| T-02 Exact purpose catalog | `GET /api/state?user_id=student-001` | 200; purpose keys are exactly P1, P2, P3; each has separate consent status. |
| T-03 No consent fails closed | Fresh DB; request P1 from `/api/data-access` | 403; `DENY`, `NO_ACTIVE_CONSENT`, `payload: null`. |
| T-04 Grant records evidence | POST grant for student-001/P1 | 201; action is grant; notice version is active; hash is 64 hexadecimal characters. |
| T-05 Grant allows only that purpose | After T-04, request P1 | 200; `ALLOW`, `ACTIVE_CONSENT`; P1 payload present. |
| T-06 Purpose isolation | Grant P1, then request P2 | P1 may be allowed; P2 is 403 `NO_ACTIVE_CONSENT`, payload null. |
| T-07 Independent purpose grant | Grant P2 while P1 is not granted | P2 is allowed; P1 remains denied. |
| T-08 Withdrawal blocks next request | Grant P1, request P1, withdraw P1, request P1 again | First request 200; withdrawal 201; next request 403 `CONSENT_WITHDRAWN`, payload null. |
| T-09 Withdrawal is scoped | Grant P1 and P2; withdraw P1; request both | P1 denied; P2 remains allowed. |
| T-10 Notice change invalidates stale consent | Grant P1 under v1; publish v2; request P1 | 403 `NOTICE_MISMATCH`, payload null; old consent event remains unchanged. |
| T-11 Re-consent restores access | After T-10, grant P1 again and request | New event references v2/hash; request 200 `ACTIVE_CONSENT`. |
| T-12 Unknown purpose fails closed | Request purpose `P9` | 400 `INVALID_PURPOSE`; no data payload; an `INVALID_PURPOSE` DENY audit row exists. Verify code with T-046. |
| T-13 Unknown user fails closed | Request `unknown-user` for P1 | 403 `UNKNOWN_USER`; no payload; an `UNKNOWN_USER` DENY audit row exists. Verify code with T-046. |
| T-14 Audit records lifecycle | Grant, allow, withdraw, deny P1, publish v2 | Audit has consent, access and `NOTICE_PUBLISHED` system rows with purpose/result/reason, timestamp and notice reference. |
| T-15 JSON export shape | `GET /api/audit?format=json` after T-14 | 200 JSON array; required event fields exist; consent, access and notice publication rows match the actions just performed. |
| T-16 Notice hash is reproducible | Read active notice; independently SHA-256 its exact UTF-8 text | Recomputed digest equals `sha256` returned by state/consent API. |
| T-17 CSV export shape | `GET /api/audit?format=csv` after T-14 | 200 `text/csv`; header and row count match JSON export, including notice publication. |
| T-18 Input validation | Try invalid action, missing version/text for notice, and malformed JSON | 4xx response; no consent grant or payload is created. Record each exact observed result. |
| T-19 UI baseline | `GET /` | 200; HTML contains app version and three purpose identifiers. |
| T-20 User audit filter | Create events for both demo users; request `user_id=student-001` | Every returned row belongs to student-001. |
| T-21 Purpose audit filter | Create P1 and P2 events; request `purpose_id=P2` | Every returned row is for P2. |
| T-22 Decision audit filter | Create allowed and denied requests; request `decision=ALLOW` | Only ALLOW access-decision rows are returned. |
| T-23 Invalid audit filters | Try unknown user, purpose and decision values | Each returns 400 with a stable reason code. |
| T-24 Filtered CSV consistency | Filter by P1 and fetch JSON and CSV | Same row count and purpose in both exports. |

**Verification note:** T-046 writes audit rows for unknown users and purposes; T-12/T-13 assert those rows. Full and filtered JSON/CSV outputs from the current manual run are saved under `evidence/`. Keep R-07 complete only while those artifacts and automated checks remain valid.

**v1.2.0 verification:** Automated cases T-20–T-24 cover API filters and filtered exports. Browser interaction for user, purpose, and ALLOW/DENY filters was exercised on 2026-11-24; the run log and filtered export outputs are under `evidence/`. A saved filtered-screen screenshot and clicking the UI download links remain pending.

## Manual UI checks

For click-by-click steps and what to say while demonstrating each feature, use [WALKTHROUGH.md](WALKTHROUGH.md).

| Manual ID | Steps | Expected visible behavior |
|---|---|---|
| M-01 | Open `http://127.0.0.1:5001`; select Aarav; grant P1; request P1; withdraw P1; request P1 again; publish v2; re-grant P1; request again. | v1 notice/hash visible; grant changes status; first request shows ALLOW and payload; withdrawal changes status; next request shows DENY/no payload; v2 makes old grants stale; re-grant under v2 allows again. |
| M-02 | Grant P1 only; try P2 and P3 in consumer panel; then grant P2 and retry. | P2/P3 denied before their own grants; P2 allowed after grant; P1 state is unchanged. |
| M-03 | Refresh browser after grant/withdraw. | UI reloads state from database and shows the latest event, not a client-only toggle. |
| M-04 | Use JSON and CSV export links after M-01. | Both contain the same consent/access sequence and notice references. |
| M-05 | Filter audit by user, purpose and ALLOW/DENY; export each filtered view as JSON and CSV. | Displayed rows and both exports match the selected filters; invalid filter values return a clear 4xx response. |

M-01 lifecycle was exercised on 2026-11-24 and its API/audit outputs are saved in `evidence/`; a screenshot/video is still needed. M-02 P1 authorization isolation from P2 and P3 was exercised; see `evidence/manual-p3-deny.json`. M-03 persistence after refresh was observed. M-05 user/purpose/decision filters were exercised and filtered JSON/CSV responses were saved; screenshot remains. For M-04, clicking the export links in connected Chrome was blocked with `ERR_BLOCKED_BY_CLIENT`; the live endpoints were fetched directly and both returned HTTP 200 with matching row counts (`evidence/live-export-ui-check.*`). Repeat the click in the user's regular browser if download behavior needs separate confirmation. Use synthetic evidence only; never put real personal data or secrets in captures.

## Pseudocode/manual API review

For every request, inspect that identity and purpose validation happen before payload construction, the latest user-purpose event and active notice are checked, and the payload is built only on ALLOW. A DENY must have a reason code, no payload, and an audit record. Review `docs/DEMO_PSEUDOCODE.md` against actual code whenever enforcement changes.

## Test output and completion rule

Run the suite with `.venv/bin/python -m unittest discover -s tests -v`. Each test creates an isolated temporary DB. Save the exact command, date, Python version, passed/failed count and output at `evidence/test-results.txt`. Keep the case list mapped to R-01–R-11. R-08 requires at least 12 distinct lifecycle/enforcement tests to pass; writing this plan alone does not satisfy it.
