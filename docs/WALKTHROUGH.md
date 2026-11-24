# ConsentX Personal Walkthrough and Demo Guide

This is the hands-on guide for understanding, checking, and presenting every ConsentX feature. It describes the current **v1.2.0** build. The main lifecycle and audit-filter interactions have been walked through in the browser; screenshots and a recording are still needed as saved demo evidence.

## How to use this guide

For each feature, read **What it means**, perform **Try it**, check **What you should see**, then use **Say in the demo** as your concise explanation. Use synthetic demo accounts only. This prototype demonstrates technical behavior; it does not certify legal compliance.

## Start a clean demo safely

Use a separate temporary database so you can reset the demo without touching your usual local data. From the `consentx/` folder:

```bash
CONSENTX_DB=/tmp/consentx-walkthrough.sqlite3 .venv/bin/python app.py
```

Keep this terminal running. Open `http://127.0.0.1:5001` in your browser. If that port is occupied, stop the other ConsentX server first. To restart this walkthrough from a clean state, stop the server with Ctrl+C, remove only this walkthrough DB, and start it again:

```bash
rm -f /tmp/consentx-walkthrough.sqlite3
CONSENTX_DB=/tmp/consentx-walkthrough.sqlite3 .venv/bin/python app.py
```

Optional API checks can run in another terminal:

```bash
export BASE_URL=http://127.0.0.1:5001
curl -s "$BASE_URL/api/health"
```

Expected: HTTP 200 and a JSON status of `ok`. A clean database starts at notice v1.0 with no consent decisions.

## Troubleshooting — `addEventListener` reads null

If the page stays on **Loading notice…** and the browser console reports a null element at an audit-filter `addEventListener`, the server may be serving an older cached template while `app.js` is newer. Audit filters are optional in the script now, so missing filter elements won’t stop the rest of the page. Restart the server from the ConsentX project folder to load the matching template, then hard-refresh the browser:

```bash
# In the terminal running the old server, press Ctrl+C first.
cd /Users/mohitupraity/Documents/aiori/consentx
source .venv/bin/activate
python app.py
```

Restarting preserves the regular SQLite database. After reloading, check that the notice, purpose cards, and three audit filters render. If the page still stays blank, inspect the console for the next missing element and confirm the browser is on `http://localhost:5001/` from this project.

## Feature 1 — Independent purpose choices (v1.0)

**PS-002 coverage:** R-01, R-02, R-03.

**What it means:** The user decides separately whether CampusPulse may use their synthetic data for event reminders (P1), personalized suggestions (P2), and anonymous usage analytics (P3). Saying yes to one purpose does not grant the others.

**Try it:**

1. Select **Aarav Demo**.
2. Confirm all three cards show **Not granted**.
3. On P1, click **Grant consent**.
4. Confirm P1 changes to **Granted**. Confirm P2 and P3 remain **Not granted**.
5. Select P2 in **Request data** and click **Send request**.

**What you should see:** P2 request is denied with `NO_ACTIVE_CONSENT` and `payload: null`. The consent timeline should show the P1 grant and P2 denial.

**Say in the demo:** “Consent is recorded per purpose. Agreeing to reminders does not authorize personalized suggestions or analytics.”

**API equivalent:**

```bash
curl -i -X POST "$BASE_URL/api/consent" -H 'Content-Type: application/json' \
  -d '{"user_id":"student-001","purpose_id":"P1","action":"grant"}'
curl -i -X POST "$BASE_URL/api/data-access" -H 'Content-Type: application/json' \
  -d '{"user_id":"student-001","purpose_id":"P2"}'
```

Expected: grant returns 201; P2 request returns 403 with `NO_ACTIVE_CONSENT` and no payload.

## Feature 2 — A matching grant allows a mock request (v1.0)

**PS-002 coverage:** R-05, R-06.

**What it means:** The mock consumer checks consent at request time. It returns only the synthetic payload tied to the purpose when the selected user has a current grant for that purpose.

**Try it:** Grant P1 if it is not already granted. Select P1 under **Request data**, then click **Send request**.

**What you should see:** The result contains `ALLOW`, `ACTIVE_CONSENT`, and a synthetic P1 payload. The audit trail adds an access event. No real student data is used.

**Say in the demo:** “The consumer asks the consent service on every request. A matching current grant is required before the mock payload is returned.”

**API equivalent:**

```bash
curl -i -X POST "$BASE_URL/api/data-access" -H 'Content-Type: application/json' \
  -d '{"user_id":"student-001","purpose_id":"P1"}'
```

Expected: HTTP 200 and `decision: ALLOW` with a synthetic payload.

## Feature 3 — Withdrawal takes effect on the next request (v1.0)

**PS-002 coverage:** R-03, R-06, R-07.

**What it means:** Withdrawal is a new event in the history, not deletion of the earlier grant. The latest user-purpose event is authoritative, so a later request is denied.

**Try it:** With P1 granted, click **Withdraw consent** on P1. Then send a P1 data request again.

**What you should see:** P1 shows **Withdrawn**. The next request returns `DENY`, reason `CONSENT_WITHDRAWN`, and `payload: null`. Both the grant and withdrawal remain visible in the audit records.

**Say in the demo:** “Withdrawal is recorded as an event and enforced immediately on later access. The earlier history remains auditable.”

**API equivalent:**

```bash
curl -i -X POST "$BASE_URL/api/consent" -H 'Content-Type: application/json' \
  -d '{"user_id":"student-001","purpose_id":"P1","action":"withdraw"}'
curl -i -X POST "$BASE_URL/api/data-access" -H 'Content-Type: application/json' \
  -d '{"user_id":"student-001","purpose_id":"P1"}'
```

Expected: withdrawal returns 201; following request returns 403 with `CONSENT_WITHDRAWN` and no payload.

## Feature 4 — Notice version and SHA-256 binding (v1.0, notice update in v1.1)

**PS-002 coverage:** R-04, R-05, R-06, R-07.

**What it means:** Each consent event records the notice version and SHA-256 digest that was active when the choice was made. Publishing a new notice makes earlier grants stale until the user confirms again.

**Try it:** Start with a clean walkthrough database for this section, or use a P1 grant made under notice v1.0.

1. Grant P1 and note the version and hash shown in the notice panel.
2. Click **Publish notice v2** once.
3. Try requesting P1 before granting again.
4. Grant P1 again, then request P1 once more.
5. Check the audit trail for `NOTICE_PUBLISHED` and the consent events.

**What you should see:** The current notice becomes v2.0 with a new hash. Before re-consent, the request is denied as `NOTICE_MISMATCH` with no payload and P1 indicates re-consent is needed. After a fresh grant, the request is allowed under v2.0.

**Say in the demo:** “Consent is tied to the exact notice version and hash. A notice change does not silently carry old consent forward; the user must confirm again.”

**API equivalent:**

```bash
curl -i -X POST "$BASE_URL/api/notices" -H 'Content-Type: application/json' \
  -d '{"version":"2.0","text":"CampusPulse notice v2: revised purpose descriptions."}'
curl -i -X POST "$BASE_URL/api/data-access" -H 'Content-Type: application/json' \
  -d '{"user_id":"student-001","purpose_id":"P1"}'
```

Expected: notice publication returns 201 and a 64-character SHA-256 digest. An old grant returns 403 `NOTICE_MISMATCH`. Re-grant under v2.0, then retry: expected 200 `ALLOW`.

**Important for repeat demos:** Publishing v2.0 repeatedly adds another notice event. For the cleanest presentation, restart using the clean temporary DB instructions above.

## Feature 5 — Audit trail and JSON/CSV export (v1.0, publication event in v1.1)

**PS-002 coverage:** R-07.

**What it means:** Consent choices, downstream allow/deny decisions, and notice publication create records so the demo can show what happened and why.

**Try it:** Perform one grant, one allowed request, one withdrawal, one denied request, and (once) publish notice v2. Scroll to **Recent events**. Click **Export JSON**, then return and click **Export CSV**.

**What you should see:** The audit list and both downloaded files include event type, synthetic user, purpose where relevant, result/reason, timestamp, and notice version/hash. Notice publication appears as a system event. JSON and CSV should represent the same filtered set.

**Say in the demo:** “The trail captures both user choices and enforcement decisions, including denials and notice changes, and can be exported for review.”

**API equivalent:**

```bash
curl -s "$BASE_URL/api/audit?format=json"
curl -s "$BASE_URL/api/audit?format=csv"
```

Expected: JSON array and CSV file with corresponding rows. Open the downloaded files to inspect them; a link appearing is not proof that the export contents are correct.

## Feature 6 — Filter audit records (v1.2)

**PS-002 coverage:** R-07.

**What it means:** The reviewer can narrow the audit view by synthetic user, purpose, and access decision. The export links carry the same selected filters.

**Try it:** Create a mix of events for both users and at least two purposes. In **Audit trail**, choose **Mira Demo** (or another user), choose P1, and choose **Allowed** or **Denied**. Change one filter at a time and watch the list update. Then export both JSON and CSV while the filters are selected.

**What you should see:** Each returned row matches the selected user and purpose. When ALLOW or DENY is selected, only access-decision rows with that outcome appear. Both downloads use the same filters as the screen.

**Say in the demo:** “Reviewers can isolate a user's history, a purpose, or allow/deny outcomes, then export that exact view.”

**API equivalent:**

```bash
curl -s "$BASE_URL/api/audit?format=json&user_id=student-001&purpose_id=P1&decision=ALLOW"
curl -s "$BASE_URL/api/audit?format=csv&user_id=student-001&purpose_id=P1&decision=ALLOW"
```

Expected: only matching rows. Try an invalid purpose such as `purpose_id=P9`; expect HTTP 400 with `INVALID_PURPOSE`.

**Verification status:** API filter behavior and filtered JSON/CSV consistency are covered by the 24 passing automated tests. Browser filtering by user, purpose, and decision was exercised on 2026-11-24 against an isolated DB. The matching filtered JSON/CSV responses are saved under `evidence/`; a screenshot and clicking the UI download links remain pending.

## Suggested 3-minute PS-002 demo

1. **Frame the problem (20 sec):** “A consent record alone is not enough if a downstream service keeps using data. This demo checks permission at the point of access.”
2. **Show separate purposes (25 sec):** Select Aarav. Grant P1 only. Try P2 and point out the denial/no payload.
3. **Show enforcement (25 sec):** Request P1 and show `ALLOW` plus the synthetic payload.
4. **Show withdrawal (25 sec):** Withdraw P1 and retry. Show `CONSENT_WITHDRAWN` and `payload: null`.
5. **Show notice change (45 sec):** Reset to a clean DB before the demo, grant P1 under v1.0, publish v2 once, show stale denial, re-consent, and show allow under v2.0.
6. **Show evidence (30 sec):** Point to the audit events, filter them, and export JSON/CSV.
7. **Close accurately (10 sec):** “This is a synthetic technical prototype. It demonstrates purpose-level enforcement and evidence; it is not legal certification.”

If time is short, skip API commands during the live demo and keep them for verification. Avoid publishing notice v2 until the notice-change segment; it invalidates the earlier grants.

## What has and has not been verified

- **Automated:** 24 tests passed on 2026-11-24; see `evidence/test-results.txt`.
- **Browser:** The main lifecycle, user/purpose/decision filters, and persistence after refresh were exercised on an isolated database on 2026-11-24. The current run log is `evidence/manual-walkthrough-2026-11-24.md`.
- **Still to capture:** Browser screenshots or recording. P3-specific UI denial is now captured. Chrome blocked export-link clicks with `ERR_BLOCKED_BY_CLIENT`, but the live JSON and CSV endpoints returned HTTP 200 with matching row counts; see `evidence/live-export-ui-check.*`. Filtered API responses and full exports are saved under `evidence/`.

## Reusable guide for every future update

For every new feature/update, add a dated/versioned section here before calling its walkthrough complete. Keep this checklist with the task in `docs/TASKS.md`:

- **Feature and PS-002 requirement:** What user problem does it solve?
- **Plain-language explanation:** What does it do and what does it not do?
- **Preconditions:** Clean DB, account, consent, notice version, or other setup needed.
- **Exact steps:** Click-by-click browser steps, plus API/CLI steps when useful.
- **Expected result:** Visible status, response code, reason code, payload/no-payload, and audit effect.
- **Failure check:** One realistic negative case and the expected safe outcome.
- **Demo line:** A short, honest explanation to say while presenting it.
- **Proof:** Automated test output and/or screenshot, recording, JSON/CSV output; label each as passed, pending, or not run.
- **Update record:** Link the task, test-plan cases, release note, and evidence path. Do not mark the task Done until its stated proof exists.
