import csv
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import re
import threading
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as consentx


class PS002LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "consentx-test.sqlite3"
        self.original_testing = consentx.app.config.get("TESTING", False)
        self.db_patch = patch.object(consentx, "DB_PATH", self.db_path)
        self.db_patch.start()
        consentx.init_db()
        self.original_operator_token = consentx.app.config.get("OPERATOR_TOKEN")
        consentx.app.config["OPERATOR_TOKEN"] = "test-operator-token"
        consentx.app.config.update(TESTING=True)
        self.client = consentx.app.test_client()
        self.select_user("student-001")

    def tearDown(self):
        self.db_patch.stop()
        consentx.app.config.update(TESTING=self.original_testing)
        if self.original_operator_token is None:
            consentx.app.config.pop("OPERATOR_TOKEN", None)
        else:
            consentx.app.config["OPERATOR_TOKEN"] = self.original_operator_token
        self.temp.cleanup()

    def select_user(self, user):
        response = self.client.post("/api/demo-session", json={"user_id": user})
        self.assertEqual(response.status_code, 200)

    def consent(self, purpose="P1", action="grant", user="student-001"):
        self.select_user(user)
        return self.client.post("/api/consent", json={"user_id": user, "purpose_id": purpose, "action": action})

    def access(self, purpose="P1", user="student-001"):
        if user in consentx.DEMO_USERS:
            self.select_user(user)
        consumer, fields = {
            "P1": ("notification-service", ["channel", "upcoming_event_ids"]),
            "P2": ("recommendation-service", ["synthetic_interests", "suggested_event_ids"]),
            "P3": ("analytics-service", ["aggregation", "feature_use_counts"]),
        }.get(purpose, ("notification-service", ["channel"]))
        return self.client.post("/api/data-access", json={"user_id": user, "purpose_id": purpose,
            "consumer_id": consumer, "operation": "READ", "requested_fields": fields})

    def publish_v2(self):
        authorized = self.client.post("/api/operator-session", json={"token": "test-operator-token"})
        self.assertEqual(authorized.status_code, 200)
        return self.client.post("/api/notices", json={"version": "2.0", "text": "Updated CampusPulse purposes."})

    def audit(self):
        return self.client.get("/api/audit?format=json").get_json()

    def test_01_health_and_version(self):
        healthz = self.client.get("/healthz")
        self.assertEqual(healthz.status_code, 200)
        self.assertEqual(healthz.get_json(), {"status": "ok"})
        healthz_head = self.client.head("/healthz")
        self.assertEqual(healthz_head.status_code, 200)

        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")
        self.assertEqual(response.get_json()["version"], consentx.APP_VERSION)

    def test_02_exactly_three_purposes_and_demo_users(self):
        response = self.client.get("/api/state?user_id=student-001")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.get_json()["purposes"]), {"P1", "P2", "P3"})
        self.assertEqual(set(response.get_json()["consents"]), {"P1", "P2", "P3"})

    def test_03_missing_consent_denied_without_payload(self):
        response = self.access()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["reason_code"], "NO_ACTIVE_CONSENT")
        self.assertIsNone(response.get_json()["payload"])

    def test_04_grant_records_notice_evidence(self):
        response = self.consent()
        body = response.get_json()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(body["action"], "grant")
        self.assertEqual(body["notice_version"], "1.0")
        self.assertEqual(len(body["notice_hash"]), 64)

    def test_05_matching_grant_allows_payload(self):
        self.consent()
        response = self.access()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["decision"], "ALLOW")
        self.assertTrue(response.get_json()["payload"])

    def test_06_grant_does_not_authorize_other_purpose(self):
        self.consent("P1")
        response = self.access("P2")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["reason_code"], "NO_ACTIVE_CONSENT")
        self.assertIsNone(response.get_json()["payload"])

    def test_07_purposes_can_be_granted_independently(self):
        self.consent("P2")
        self.assertEqual(self.access("P2").status_code, 200)
        self.assertEqual(self.access("P1").status_code, 403)

    def test_08_withdrawal_blocks_next_request(self):
        self.consent()
        self.assertEqual(self.access().status_code, 200)
        self.assertEqual(self.consent(action="withdraw").status_code, 201)
        response = self.access()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["reason_code"], "CONSENT_WITHDRAWN")
        self.assertIsNone(response.get_json()["payload"])

    def test_09_withdrawal_does_not_change_other_purpose(self):
        self.consent("P1")
        self.consent("P2")
        self.consent("P1", "withdraw")
        self.assertEqual(self.access("P1").status_code, 403)
        self.assertEqual(self.access("P2").status_code, 200)

    def test_10_notice_change_denies_old_grant_and_is_audited(self):
        self.consent()
        response = self.publish_v2()
        self.assertEqual(response.status_code, 201)
        access = self.access()
        self.assertEqual(access.status_code, 403)
        self.assertEqual(access.get_json()["reason_code"], "NOTICE_MISMATCH")
        self.assertTrue(any(r["result"] == "NOTICE_PUBLISHED" for r in self.audit()))

    def test_11_reconsent_under_new_notice_restores_access(self):
        self.consent()
        self.publish_v2()
        grant = self.consent()
        self.assertEqual(grant.get_json()["notice_version"], "2.0")
        self.assertEqual(self.access().status_code, 200)

    def test_12_unknown_purpose_denied_and_logged(self):
        response = self.access("P9")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["reason_code"], "INVALID_PURPOSE")
        with consentx.db_session() as con:
            rows = [dict(r) for r in con.execute("SELECT * FROM access_decisions").fetchall()]
        self.assertTrue(any(r["reason_code"] == "INVALID_PURPOSE" and r["decision"] == "DENY" for r in rows))

    def test_13_unknown_user_denied_and_logged(self):
        response = self.access(user="unknown-user")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["reason_code"], "UNKNOWN_USER")
        rows = self.audit()
        self.assertTrue(any(r["reason_code"] == "UNKNOWN_USER" and r["result"] == "DENY" for r in rows))

    def test_14_audit_contains_consent_access_and_notice_events(self):
        self.consent()
        self.access()
        self.consent(action="withdraw")
        self.access()
        self.publish_v2()
        rows = self.audit()
        self.assertIn("consent", {r["record_type"] for r in rows})
        self.assertIn("access", {r["record_type"] for r in rows})
        self.assertTrue(any(r["result"] == "NOTICE_PUBLISHED" for r in rows))

    def test_15_json_export_shape(self):
        self.consent()
        self.access()
        response = self.client.get("/api/audit?format=json")
        self.assertEqual(response.status_code, 200)
        rows = response.get_json()
        self.assertTrue({"record_type", "record_id", "user_id", "purpose_id", "result",
                         "reason_code", "created_at", "notice_version", "notice_hash"}.issubset(rows[0]))

    def test_16_csv_export_matches_json_row_count(self):
        self.consent()
        self.access()
        self.publish_v2()
        json_rows = self.audit()
        response = self.client.get("/api/audit?format=csv")
        self.assertEqual(response.status_code, 200)
        csv_rows = list(csv.DictReader(io.StringIO(response.get_data(as_text=True))))
        self.assertEqual(len(csv_rows), len(json_rows))
        self.assertIn("notice_hash", csv_rows[0])

    def test_17_notice_hash_recomputes_from_exact_text(self):
        state = self.client.get("/api/state").get_json()
        notice = state["active_notice"]
        self.assertEqual(notice["sha256"], hashlib.sha256(notice["text"].encode("utf-8")).hexdigest())

    def test_18_invalid_consent_action_rejected_without_event(self):
        response = self.consent(action="approve")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["reason_code"], "INVALID_ACTION")

    def test_19_ui_renders_version_and_three_purposes(self):
        response = self.client.get("/")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(f"ConsentX v{consentx.APP_VERSION}", body)
        self.assertIn('id="purpose-list"', body)
        catalog = self.client.get("/api/state").get_json()["purposes"]
        for purpose in ("Event reminders", "Personalized event suggestions", "Anonymous usage analytics"):
            self.assertIn(purpose, [entry["name"] for entry in catalog.values()])

    def test_20_audit_filters_by_synthetic_user(self):
        self.consent(user="student-001")
        self.access(user="student-001")
        self.consent(user="student-002")
        self.select_user("student-001")
        rows = self.client.get("/api/audit?format=json&user_id=student-001").get_json()
        self.assertTrue(rows)
        self.assertEqual({row["user_id"] for row in rows}, {"student-001"})

    def test_21_audit_filters_by_purpose(self):
        self.consent("P1")
        self.consent("P2")
        rows = self.client.get("/api/audit?format=json&purpose_id=P2").get_json()
        self.assertTrue(rows)
        self.assertEqual({row["purpose_id"] for row in rows}, {"P2"})

    def test_22_decision_filter_returns_access_decisions_only(self):
        self.consent("P1")
        self.access("P1")
        self.access("P2")
        rows = self.client.get("/api/audit?format=json&decision=ALLOW").get_json()
        self.assertTrue(rows)
        self.assertTrue(all(row["record_type"] == "access" and row["result"] == "ALLOW" for row in rows))

    def test_23_invalid_audit_filters_return_400(self):
        for query, reason in (("user_id=unknown", "UNKNOWN_USER"),
                              ("purpose_id=P9", "INVALID_PURPOSE"),
                              ("decision=MAYBE", "INVALID_DECISION")):
            with self.subTest(query=query):
                response = self.client.get(f"/api/audit?format=json&{query}")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["reason_code"], reason)

    def test_24_filtered_csv_matches_filtered_json(self):
        self.consent("P1")
        self.access("P1")
        self.consent("P2")
        query = "purpose_id=P1"
        json_rows = self.client.get(f"/api/audit?format=json&{query}").get_json()
        csv_response = self.client.get(f"/api/audit?format=csv&{query}")
        csv_rows = list(csv.DictReader(io.StringIO(csv_response.get_data(as_text=True))))
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(len(csv_rows), len(json_rows))
        self.assertEqual({row["purpose_id"] for row in csv_rows}, {"P1"})

    def test_25_test_fixture_isolated_from_demo_database(self):
        self.assertTrue(consentx.app.testing)
        self.assertEqual(consentx.DB_PATH, self.db_path)
        self.assertNotEqual(consentx.DB_PATH, consentx.INSTANCE / "consentx.sqlite3")

    def test_26_allow_response_explains_every_policy_check(self):
        self.consent("P1")
        response = self.access("P1")
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["decision"], "ALLOW")
        self.assertEqual([step["status"] for step in body["decision_trace"]],
                         ["PASS", "PASS", "PASS", "PASS", "PASS", "RELEASED"])
        self.assertTrue(body["payload"])

    def test_27_withdrawal_trace_shows_why_payload_was_withheld(self):
        self.consent("P1")
        self.consent("P1", "withdraw")
        response = self.access("P1")
        body = response.get_json()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(body["decision"], "DENY")
        self.assertIsNone(body["payload"])
        self.assertEqual(body["decision_trace"][3]["status"], "FAIL")
        self.assertEqual(body["decision_trace"][-1]["status"], "WITHHELD")

    def test_29_out_of_scope_field_is_denied_without_payload(self):
        self.consent("P1")
        response = self.client.post("/api/data-access", json={"user_id":"student-001","purpose_id":"P1",
            "consumer_id":"notification-service","operation":"READ",
            "requested_fields":["channel","student_email"]})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["reason_code"], "FIELD_SCOPE_EXCEEDED")
        self.assertIsNone(response.get_json()["payload"])

    def test_30_consumer_cannot_request_another_purposes_fields(self):
        self.consent("P1")
        response = self.client.post("/api/data-access", json={"user_id":"student-001","purpose_id":"P1",
            "consumer_id":"analytics-service","operation":"READ","requested_fields":["feature_use_counts"]})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["reason_code"], "CONSUMER_PURPOSE_MISMATCH")

    def test_31_non_read_operation_is_denied(self):
        self.consent("P1")
        response = self.client.post("/api/data-access", json={"user_id":"student-001","purpose_id":"P1",
            "consumer_id":"notification-service","operation":"WRITE","requested_fields":["channel"]})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["reason_code"], "OPERATION_NOT_ALLOWED")

    def test_32_concurrent_access_requests_keep_unique_audit_ids(self):
        self.consent("P1")
        request_count = 16
        barrier = threading.Barrier(request_count)

        def send_request(_):
            with consentx.app.test_client() as client:
                client.post("/api/demo-session", json={"user_id": "student-001"})
                barrier.wait(timeout=5)
                return client.post("/api/data-access", json={"user_id": "student-001", "purpose_id": "P1",
                    "consumer_id": "notification-service", "operation": "READ",
                    "requested_fields": ["channel"]})

        with ThreadPoolExecutor(max_workers=request_count) as pool:
            responses = list(pool.map(send_request, range(request_count)))

        self.assertTrue(all(response.status_code == 200 for response in responses))
        request_ids = [response.get_json()["request_id"] for response in responses]
        self.assertEqual(len(set(request_ids)), request_count)
        with consentx.db_session() as con:
            rows = con.execute("SELECT request_id FROM access_decisions").fetchall()
        self.assertEqual(len(rows), request_count)
        self.assertEqual({row["request_id"] for row in rows}, set(request_ids))

    def test_33_withdrawal_creates_pending_consumer_revocation(self):
        self.consent("P3")
        response = self.consent("P3", "withdraw")
        body = response.get_json()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(body["revocations"]), 1)
        queued = body["revocations"][0]
        self.assertEqual(queued["consumer_id"], "analytics-service")
        self.assertEqual(queued["status"], "PENDING")
        self.assertTrue(queued["revocation_id"].startswith("REV-"))
        jobs = self.client.get("/api/revocations?user_id=student-001").get_json()["revocations"]
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["withdrawal_event_id"], body["event_id"])
        self.assertEqual(jobs[0]["attempts"], 0)
        self.assertIsNone(jobs[0]["acknowledged_at"])
        audit = self.audit()
        self.assertTrue(any(row["result"] == "REVOCATION_QUEUED" for row in audit))

    def test_34_revocation_queue_is_user_scoped_and_grants_do_not_queue(self):
        self.consent("P1", user="student-001")
        self.consent("P1", "withdraw", user="student-001")
        self.consent("P2", "withdraw", user="student-002")
        self.consent("P3", user="student-002")
        self.select_user("student-001")
        aarav_jobs = self.client.get("/api/revocations?user_id=student-001").get_json()["revocations"]
        all_jobs = self.client.get("/api/revocations").get_json()
        mira_client = consentx.app.test_client()
        mira_client.post("/api/demo-session", json={"user_id": "student-002"})
        mira_jobs = mira_client.get("/api/revocations?user_id=student-002").get_json()["revocations"]
        self.assertEqual({job["purpose_id"] for job in aarav_jobs}, {"P1"})
        self.assertEqual({job["purpose_id"] for job in mira_jobs}, {"P2"})
        self.assertEqual(all_jobs["total"], 1)
        invalid = self.client.get("/api/revocations?user_id=unknown")
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.get_json()["reason_code"], "UNKNOWN_USER")

    def test_35_withdrawal_cancels_only_matching_users_purpose_actions(self):
        before = self.client.get("/api/pending-actions?user_id=student-001").get_json()["pending_actions"]
        self.assertEqual(len(before), 6)
        self.consent("P1")
        withdrawal = self.consent("P1", "withdraw").get_json()
        self.assertEqual(withdrawal["revocations"][0]["pending_actions_cancelled"], 2)
        actions = self.client.get("/api/pending-actions?user_id=student-001").get_json()["pending_actions"]
        p1_actions = [row for row in actions if row["purpose_id"] == "P1"]
        other_purposes = [row for row in actions if row["purpose_id"] != "P1"]
        mira_client = consentx.app.test_client()
        mira_client.post("/api/demo-session", json={"user_id": "student-002"})
        mira_actions = mira_client.get("/api/pending-actions?user_id=student-002").get_json()["pending_actions"]
        self.assertEqual({row["status"] for row in p1_actions}, {"CANCELLED"})
        self.assertEqual({row["revocation_id"] for row in p1_actions},
                         {withdrawal["revocations"][0]["revocation_id"]})
        self.assertTrue(all(row["status"] == "QUEUED" for row in other_purposes))
        self.assertTrue(all(row["status"] == "QUEUED" for row in mira_actions))

    def test_36_demo_identity_cannot_be_overridden_by_request_field(self):
        self.consent("P1", user="student-001")
        response = self.client.post("/api/data-access", json={"user_id": "student-002", "purpose_id": "P1",
            "consumer_id": "notification-service", "operation": "READ", "requested_fields": ["channel"]})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["reason_code"], "IDENTITY_MISMATCH")
        self.assertIsNone(response.get_json()["payload"])
        state_response = self.client.get("/api/state?user_id=student-002")
        self.assertEqual(state_response.status_code, 403)
        audit_response = self.client.get("/api/audit?format=json&user_id=student-002")
        self.assertEqual(audit_response.status_code, 403)
        consent_response = self.client.post("/api/consent", json={"user_id": "student-002", "purpose_id": "P1", "action": "grant"})
        self.assertEqual(consent_response.status_code, 403)
        self.assertEqual(consent_response.get_json()["reason_code"], "IDENTITY_MISMATCH")

    def test_37_notice_publication_requires_operator_session(self):
        payload = {"version": "2.0", "text": "Updated notice for operator authorization test."}
        denied = self.client.post("/api/notices", json=payload)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.get_json()["reason_code"], "OPERATOR_AUTH_REQUIRED")
        wrong = self.client.post("/api/operator-session", json={"token": "wrong"})
        self.assertEqual(wrong.status_code, 403)
        self.assertEqual(wrong.get_json()["reason_code"], "OPERATOR_AUTH_REQUIRED")
        allowed = self.client.post("/api/operator-session", json={"token": "test-operator-token"})
        self.assertEqual(allowed.status_code, 200)
        published = self.client.post("/api/notices", json=payload)
        self.assertEqual(published.status_code, 201)

    def test_28_notice_history_is_newest_first_and_hash_linked(self):
        self.publish_v2()
        state = self.client.get("/api/state").get_json()
        versions = state["notice_history"]
        self.assertEqual([item["version"] for item in versions], ["2.0", "1.0"])
        self.assertEqual(versions[0]["sha256"], state["active_notice"]["sha256"])

    def test_38_ui_test_count_matches_actual_suite(self):
        body = self.client.get("/").get_data(as_text=True)
        match = re.search(r"(\d+) passing tests", body)
        self.assertIsNotNone(match, "UI template must display passing test count")
        displayed = int(match.group(1))
        actual_tests = [name for name in dir(self) if name.startswith("test_")]
        self.assertEqual(displayed, len(actual_tests))

    def test_39_audit_ledger_verifies_when_intact(self):
        self.consent("P1")
        self.access("P1")
        self.consent("P1", "withdraw")
        self.publish_v2()
        verify = self.client.get("/api/audit/verify")
        self.assertEqual(verify.status_code, 200)
        body = verify.get_json()
        self.assertEqual(body["status"], "intact")
        self.assertGreaterEqual(body["verified_count"], 5)
        self.assertEqual(body["verified_count"], body["total_count"])

    def test_40_tampered_ledger_record_fails_verification(self):
        self.consent("P1")
        self.access("P1")
        self.consent("P1", "withdraw")
        with consentx.db_session(write=True) as con:
            con.execute("UPDATE audit_ledger SET event_type='ACCESS_DENY' WHERE id=2")
        verify = self.client.get("/api/audit/verify")
        self.assertEqual(verify.status_code, 409)
        body = verify.get_json()
        self.assertEqual(body["status"], "broken")
        self.assertEqual(body["broken_at_id"], 2)
        self.assertIn("row_hash mismatch", body["message"])

    def test_41_deleted_ledger_record_fails_verification(self):
        self.consent("P1")
        self.access("P1")
        self.consent("P1", "withdraw")
        with consentx.db_session(write=True) as con:
            con.execute("DELETE FROM audit_ledger WHERE id=2")
        verify = self.client.get("/api/audit/verify")
        self.assertEqual(verify.status_code, 409)
        body = verify.get_json()
        self.assertEqual(body["status"], "broken")
        self.assertEqual(body["broken_at_id"], 3)
        self.assertIn("prev_hash", body["message"])

    def test_42_new_ledger_event_links_to_previous_hash(self):
        self.consent("P1")
        self.access("P1")
        ledger = self.client.get("/api/audit/ledger").get_json()["events"]
        ordered = list(reversed(ledger))
        self.assertGreaterEqual(len(ordered), 2)
        self.assertEqual(ordered[0]["prev_hash"], "0" * 64)
        for i in range(1, len(ordered)):
            self.assertEqual(ordered[i]["prev_hash"], ordered[i - 1]["row_hash"])

    def test_43_revocation_delivery_creates_acknowledged_instruction(self):
        self.consent("P1")
        withdrawal = self.consent("P1", "withdraw").get_json()
        rev_id = withdrawal["revocations"][0]["revocation_id"]
        deliver = self.client.post(f"/api/revocations/{rev_id}/deliver", json={})
        self.assertEqual(deliver.status_code, 200)
        job = deliver.get_json()["revocation"]
        self.assertEqual(job["status"], "ACKNOWLEDGED")
        self.assertEqual(job["attempts"], 1)
        self.assertIsNotNone(job["delivered_at"])
        self.assertIsNotNone(job["acknowledged_at"])
        self.assertTrue(job["adapter_event_id"].startswith("ACK-"))
        self.assertEqual(len(job["adapter_receipt_digest"]), 64)
        ledger_types = {e["event_type"] for e in self.client.get("/api/audit/ledger").get_json()["events"]}
        self.assertTrue({"REVOCATION_QUEUED", "WORK_CANCELLED", "REVOCATION_DELIVERED", "REVOCATION_ACKNOWLEDGED"}.issubset(ledger_types))

    def test_44_p3_withdrawal_cancels_p3_and_leaves_p1_usable(self):
        self.consent("P1")
        self.consent("P3")
        withdrawal = self.consent("P3", "withdraw").get_json()
        rev_id = withdrawal["revocations"][0]["revocation_id"]
        self.assertEqual(withdrawal["revocations"][0]["consumer_id"], "analytics-service")
        self.assertEqual(self.access("P3").status_code, 403)
        self.assertEqual(self.access("P1").status_code, 200)
        actions = self.client.get("/api/pending-actions?user_id=student-001").get_json()["pending_actions"]
        self.assertTrue(all(a["status"] == "CANCELLED" for a in actions if a["purpose_id"] == "P3"))
        self.assertTrue(all(a["status"] == "QUEUED" for a in actions if a["purpose_id"] == "P1"))
        deliver = self.client.post(f"/api/revocations/{rev_id}/deliver", json={})
        self.assertEqual(deliver.status_code, 200)
        self.assertEqual(deliver.get_json()["revocation"]["status"], "ACKNOWLEDGED")

    def test_45_unavailable_consumer_records_failure_honestly(self):
        self.consent("P1")
        rev_id = self.consent("P1", "withdraw").get_json()["revocations"][0]["revocation_id"]
        toggle = self.client.post("/api/consumers/notification-service/availability", json={"available": False})
        self.assertEqual(toggle.status_code, 200)
        self.assertFalse(toggle.get_json()["consumer"]["available"])
        deliver = self.client.post(f"/api/revocations/{rev_id}/deliver", json={})
        self.assertEqual(deliver.status_code, 502)
        body = deliver.get_json()
        self.assertEqual(body["reason_code"], "CONSUMER_UNAVAILABLE")
        job = body["revocation"]
        self.assertEqual(job["status"], "FAILED")
        self.assertEqual(job["attempts"], 1)
        self.assertIsNone(job["acknowledged_at"])
        self.assertIn("unavailable", job["last_error"])

    def test_46_retry_succeeds_after_consumer_becomes_available(self):
        self.consent("P1")
        rev_id = self.consent("P1", "withdraw").get_json()["revocations"][0]["revocation_id"]
        self.client.post("/api/consumers/notification-service/availability", json={"available": False})
        self.assertEqual(self.client.post(f"/api/revocations/{rev_id}/deliver", json={}).status_code, 502)
        self.client.post("/api/consumers/notification-service/availability", json={"available": True})
        retry = self.client.post(f"/api/revocations/{rev_id}/retry", json={})
        self.assertEqual(retry.status_code, 200)
        job = retry.get_json()["revocation"]
        self.assertEqual(job["status"], "ACKNOWLEDGED")
        self.assertEqual(job["attempts"], 2)
        self.assertIsNone(job["last_error"])
        ledger_types = {e["event_type"] for e in self.client.get("/api/audit/ledger").get_json()["events"]}
        self.assertIn("REVOCATION_FAILED", ledger_types)
        self.assertIn("REVOCATION_RETRIED", ledger_types)
        self.assertIn("REVOCATION_ACKNOWLEDGED", ledger_types)

    def test_47_duplicate_delivery_and_retry_are_idempotent(self):
        self.consent("P1")
        rev_id = self.consent("P1", "withdraw").get_json()["revocations"][0]["revocation_id"]
        first = self.client.post(f"/api/revocations/{rev_id}/deliver", json={})
        self.assertEqual(first.status_code, 200)
        ack_id = first.get_json()["revocation"]["adapter_event_id"]
        dup_deliver = self.client.post(f"/api/revocations/{rev_id}/deliver", json={})
        self.assertEqual(dup_deliver.status_code, 409)
        self.assertEqual(dup_deliver.get_json()["reason_code"], "ALREADY_ACKNOWLEDGED")
        self.assertEqual(dup_deliver.get_json()["revocation"]["attempts"], 1)
        self.assertEqual(dup_deliver.get_json()["revocation"]["adapter_event_id"], ack_id)
        dup_retry = self.client.post(f"/api/revocations/{rev_id}/retry", json={})
        self.assertEqual(dup_retry.status_code, 409)
        self.assertEqual(dup_retry.get_json()["revocation"]["attempts"], 1)

    def test_48_my_privacy_returns_permissions_services_and_unresolved(self):
        self.consent("P1")
        self.consent("P2")
        self.consent("P1", "withdraw")
        privacy = self.client.get("/api/my-privacy?user_id=student-001")
        self.assertEqual(privacy.status_code, 200)
        body = privacy.get_json()
        self.assertEqual(body["summary"]["granted_count"], 1)
        self.assertEqual(body["summary"]["withdrawn_count"], 1)
        self.assertEqual(body["summary"]["unresolved_revocations"], 1)
        self.assertEqual(len(body["permissions"]), 3)
        self.assertEqual(len(body["connected_services"]), 3)
        rev_id = body["revocations"][0]["revocation_id"]
        self.client.post(f"/api/revocations/{rev_id}/deliver", json={})
        after = self.client.get("/api/my-privacy?user_id=student-001").get_json()
        self.assertEqual(after["summary"]["unresolved_revocations"], 0)
        self.assertEqual(after["summary"]["acknowledged_revocations"], 1)

    def test_49_privacy_receipt_json_html_and_isolation(self):
        self.consent("P1")
        rev_id = self.consent("P1", "withdraw").get_json()["revocations"][0]["revocation_id"]
        self.client.post(f"/api/revocations/{rev_id}/deliver", json={})
        json_res = self.client.get(f"/api/privacy-receipt/{rev_id}?format=json")
        self.assertEqual(json_res.status_code, 200)
        receipt = json_res.get_json()
        self.assertEqual(receipt["withdrawal_id"], rev_id)
        self.assertEqual(receipt["affected_consumer"], "notification-service")
        self.assertEqual(receipt["cancelled_pending_actions"], 2)
        self.assertEqual(receipt["consumer_acknowledgement"], "Acknowledged")
        self.assertIn("not establish that every previously shared copy was erased", receipt["disclaimer"])
        self.assertTrue(receipt["evidence_ids"]["ledger_event_ids"])
        html_res = self.client.get(f"/api/privacy-receipt/{rev_id}?format=html")
        self.assertEqual(html_res.status_code, 200)
        self.assertIn(rev_id, html_res.get_data(as_text=True))
        # Another synthetic user cannot view Aarav's receipt
        self.select_user("student-002")
        forbidden = self.client.get(f"/api/privacy-receipt/{rev_id}?format=json")
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(forbidden.get_json()["reason_code"], "IDENTITY_MISMATCH")

    def test_50_diagnostics_and_simulate_pending_work_guard(self):
        diag = self.client.get("/api/diagnostics")
        self.assertEqual(diag.status_code, 200)
        self.assertTrue(diag.get_json()["all_passed"])
        denied = self.client.post("/api/pending-actions/simulate", json={"user_id": "student-001", "purpose_id": "P1"})
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.get_json()["reason_code"], "CONSENT_REQUIRED")
        self.consent("P1")
        allowed = self.client.post("/api/pending-actions/simulate", json={"user_id": "student-001", "purpose_id": "P1"})
        self.assertEqual(allowed.status_code, 201)
        self.assertEqual(allowed.get_json()["pending_action"]["status"], "QUEUED")

    def test_51_demo_md_and_self_guided_judge_ui(self):
        demo_md = (consentx.ROOT / "DEMO.md").read_text(encoding="utf-8")
        for heading in ("PS-002 Requirements Checklist", "Why ConsentX Is More Than a Static Checkbox", "Technical Architecture", "Tough Judge Q&A"):
            self.assertIn(heading, demo_md)
        html = self.client.get("/").get_data(as_text=True)
        for marker in ('id="judge-tour"', 'id="view-guide"', 'class="feature-guide"', 'id="sim-live-status"', 'id="tour-toggle"', 'id="tour-restart-btn"', 'id="tour-reset-btn"'):
            self.assertIn(marker, html)

    def test_52_demo_reset_restores_clean_v1_state(self):
        self.consent("P1")
        self.access("P1")
        self.consent("P1", "withdraw")
        self.publish_v2()
        reset = self.client.post("/api/demo-reset", json={})
        self.assertEqual(reset.status_code, 200)
        self.assertTrue(reset.get_json()["reset"])
        state = self.client.get("/api/state?user_id=student-001").get_json()
        self.assertEqual(state["active_notice"]["version"], "1.0")
        self.assertEqual(len(state["notice_history"]), 1)
        self.assertEqual(state["consents"], {"P1": None, "P2": None, "P3": None})
        self.assertEqual(state["ledger_integrity"]["total_count"], 0)
        self.assertEqual(len(self.client.get("/api/revocations").get_json()["revocations"]), 0)
        self.assertEqual(len(self.client.get("/api/pending-actions").get_json()["pending_actions"]), 6)


if __name__ == "__main__":
    unittest.main()
