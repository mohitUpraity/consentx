import csv
import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as consentx


class PS002LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "consentx-test.sqlite3"
        self.db_patch = patch.object(consentx, "DB_PATH", self.db_path)
        self.db_patch.start()
        consentx.init_db()
        consentx.app.config.update(TESTING=True)
        self.client = consentx.app.test_client()

    def tearDown(self):
        self.db_patch.stop()
        self.temp.cleanup()

    def consent(self, purpose="P1", action="grant", user="student-001"):
        return self.client.post("/api/consent", json={"user_id": user, "purpose_id": purpose, "action": action})

    def access(self, purpose="P1", user="student-001"):
        return self.client.post("/api/data-access", json={"user_id": user, "purpose_id": purpose})

    def publish_v2(self):
        return self.client.post("/api/notices", json={"version": "2.0", "text": "Updated CampusPulse purposes."})

    def audit(self):
        return self.client.get("/api/audit?format=json").get_json()

    def test_01_health_and_version(self):
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
        self.assertIn(f"CONSENTX v{consentx.APP_VERSION}", body)
        self.assertIn('id="purpose-list"', body)
        catalog = self.client.get("/api/state").get_json()["purposes"]
        for purpose in ("Event reminders", "Personalized event suggestions", "Anonymous usage analytics"):
            self.assertIn(purpose, [entry["name"] for entry in catalog.values()])

    def test_20_audit_filters_by_synthetic_user(self):
        self.consent(user="student-001")
        self.access(user="student-001")
        self.consent(user="student-002")
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


if __name__ == "__main__":
    unittest.main()
