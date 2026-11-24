"""ConsentX: small synthetic consent and downstream-enforcement prototype."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, session

ROOT = Path(__file__).resolve().parent
INSTANCE = ROOT / "instance"
DB_PATH = Path(os.environ.get("CONSENTX_DB", INSTANCE / "consentx.sqlite3"))
APP_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
app = Flask(__name__)
app.secret_key = os.environ.get("CONSENTX_SECRET_KEY") or os.urandom(32)

PURPOSES = {
    "P1": {
        "name": "Event reminders",
        "description": "Send reminders for events the user saved.",
        "payload": {"channel": "email", "upcoming_event_ids": ["EVT-104", "EVT-208"]},
    },
    "P2": {
        "name": "Personalized event suggestions",
        "description": "Use synthetic interests to suggest campus events.",
        "payload": {"synthetic_interests": ["design", "robotics"], "suggested_event_ids": ["EVT-311"]},
    },
    "P3": {
        "name": "Anonymous usage analytics",
        "description": "Use aggregated synthetic feature-use counts to improve CampusPulse.",
        "payload": {"aggregation": "synthetic-demo", "feature_use_counts": {"search": 18, "calendar": 9}},
    },
}
CONSUMERS = {
    "notification-service": {"P1": {"channel", "upcoming_event_ids"}},
    "recommendation-service": {"P2": {"synthetic_interests", "suggested_event_ids"}},
    "analytics-service": {"P3": {"aggregation", "feature_use_counts"}},
}
DEMO_USERS = {"student-001": "Aarav Demo", "student-002": "Mira Demo"}
DEFAULT_NOTICE = (
    "CampusPulse uses data only for the selected purpose. You can withdraw consent at any time. "
    "A new notice version may require you to confirm your choices again."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def get_db() -> sqlite3.Connection:
    INSTANCE.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


@contextmanager
def db_session(write=False):
    con = get_db()
    try:
        # Acquire SQLite's writer lock before request policy reads. Without this,
        # parallel requests can all read first and then collide while upgrading
        # their transactions to write the corresponding audit decision.
        if write:
            con.execute("BEGIN IMMEDIATE")
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db() -> None:
    digest = hashlib.sha256(DEFAULT_NOTICE.encode("utf-8")).hexdigest()
    with db_session() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS notices (
                version TEXT PRIMARY KEY, text TEXT NOT NULL, sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS consent_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                user_id TEXT NOT NULL,
                purpose_id TEXT NOT NULL,
                action TEXT NOT NULL CHECK(action IN ('grant','withdraw')),
                notice_version TEXT NOT NULL,
                notice_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS access_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL UNIQUE,
                user_id TEXT NOT NULL,
                purpose_id TEXT NOT NULL,
                decision TEXT NOT NULL CHECK(decision IN ('ALLOW','DENY')),
                reason_code TEXT NOT NULL,
                created_at TEXT NOT NULL,
                notice_version TEXT,
                notice_hash TEXT,
                consumer_id TEXT NOT NULL DEFAULT 'legacy-consumer',
                operation TEXT NOT NULL DEFAULT 'READ',
                requested_fields TEXT NOT NULL DEFAULT '[]'
            );
            CREATE TABLE IF NOT EXISTS system_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                event_type TEXT NOT NULL,
                details TEXT NOT NULL,
                created_at TEXT NOT NULL,
                notice_version TEXT,
                notice_hash TEXT
            );
            CREATE TABLE IF NOT EXISTS revocation_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                revocation_id TEXT NOT NULL UNIQUE,
                withdrawal_event_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                purpose_id TEXT NOT NULL,
                consumer_id TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('PENDING','DELIVERED','ACKNOWLEDGED','FAILED')),
                created_at TEXT NOT NULL,
                delivered_at TEXT,
                acknowledged_at TEXT,
                attempts INTEGER NOT NULL DEFAULT 0,
                adapter_event_id TEXT,
                last_error TEXT
            );
            CREATE TABLE IF NOT EXISTS pending_actions (
                action_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                purpose_id TEXT NOT NULL,
                consumer_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('QUEUED','CANCELLED','COMPLETED')),
                created_at TEXT NOT NULL,
                cancelled_at TEXT,
                revocation_id TEXT
            );
            """
        )
        columns = {row["name"] for row in con.execute("PRAGMA table_info(access_decisions)")}
        for name, declaration in (("consumer_id", "TEXT NOT NULL DEFAULT 'legacy-consumer'"),
                                  ("operation", "TEXT NOT NULL DEFAULT 'READ'"),
                                  ("requested_fields", "TEXT NOT NULL DEFAULT '[]'")):
            if name not in columns:
                con.execute(f"ALTER TABLE access_decisions ADD COLUMN {name} {declaration}")
        revocation_columns = {row["name"] for row in con.execute("PRAGMA table_info(revocation_jobs)")}
        if "pending_actions_cancelled" not in revocation_columns:
            con.execute("ALTER TABLE revocation_jobs ADD COLUMN pending_actions_cancelled INTEGER NOT NULL DEFAULT 0")
        con.execute(
            "INSERT OR IGNORE INTO notices(version,text,sha256,created_at) VALUES(?,?,?,?)",
            ("1.0", DEFAULT_NOTICE, digest, utc_now()),
        )
        for user_id in DEMO_USERS:
            for purpose_id, consumer_id, action_type in (
                ("P1", "notification-service", "event_reminder"),
                ("P2", "recommendation-service", "event_recommendation"),
                ("P3", "analytics-service", "analytics_export"),
            ):
                for sequence in (1, 2):
                    con.execute(
                        "INSERT OR IGNORE INTO pending_actions(action_id,user_id,purpose_id,consumer_id,action_type,status,created_at) "
                        "VALUES(?,?,?,?,?,'QUEUED',?)",
                        (f"ACTION-{user_id}-{purpose_id}-{sequence}", user_id, purpose_id,
                         consumer_id, action_type, utc_now()),
                    )


def active_notice(con: sqlite3.Connection) -> sqlite3.Row:
    return con.execute("SELECT * FROM notices ORDER BY created_at DESC, rowid DESC LIMIT 1").fetchone()


def session_user_id():
    user_id = session.get("user_id")
    return user_id if user_id in DEMO_USERS else None


def identity_error(user_id=None):
    active_user = session_user_id()
    if not active_user:
        return jsonify({"error": "Choose a synthetic demo identity first", "reason_code": "NO_DEMO_IDENTITY"}), 401
    if user_id and user_id != active_user:
        return jsonify({"error": "Request identity does not match the selected demo identity",
                        "reason_code": "IDENTITY_MISMATCH"}), 403
    return None


def audit_decision(con, user_id, purpose_id, decision, reason, notice, request_id=None,
                   consumer_id="unknown", operation="READ", requested_fields=None):
    request_id = request_id or str(uuid.uuid4())
    con.execute(
        """INSERT INTO access_decisions
        (request_id,user_id,purpose_id,decision,reason_code,created_at,notice_version,notice_hash,
         consumer_id,operation,requested_fields)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (request_id, user_id, purpose_id, decision, reason, utc_now(),
         notice["version"] if notice else None, notice["sha256"] if notice else None,
         consumer_id, operation, json.dumps(requested_fields or [])),
    )
    return request_id


@app.get("/")
def home():
    if not session_user_id():
        session["user_id"] = "student-001"
    return render_template("index.html", purposes=PURPOSES, users=DEMO_USERS,
                           consumers=CONSUMERS, app_version=APP_VERSION)


@app.get("/api/demo-session")
def demo_session_state():
    user_id = session_user_id()
    if not user_id:
        return jsonify({"error": "Choose a synthetic demo identity", "reason_code": "NO_DEMO_IDENTITY"}), 401
    return jsonify({"user_id": user_id, "display_name": DEMO_USERS[user_id],
                    "mode": "synthetic-demo-identity", "role": session.get("role", "student")})


@app.post("/api/demo-session")
def select_demo_identity():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if user_id not in DEMO_USERS:
        return jsonify({"error": "Unknown synthetic user", "reason_code": "UNKNOWN_USER"}), 400
    session["user_id"] = user_id
    session["role"] = "student"
    return jsonify({"user_id": user_id, "display_name": DEMO_USERS[user_id],
                    "mode": "synthetic-demo-identity"})


@app.post("/api/operator-session")
def operator_session():
    configured_token = app.config.get("OPERATOR_TOKEN") or os.environ.get("CONSENTX_OPERATOR_TOKEN")
    supplied_token = (request.get_json(silent=True) or {}).get("token", "")
    if not configured_token:
        return jsonify({"error": "Operator access is not configured", "reason_code": "OPERATOR_NOT_CONFIGURED"}), 503
    if not isinstance(supplied_token, str) or not secrets.compare_digest(supplied_token, configured_token):
        return jsonify({"error": "Operator access code is incorrect", "reason_code": "OPERATOR_AUTH_REQUIRED"}), 403
    if not session_user_id():
        return jsonify({"error": "Choose a synthetic identity first", "reason_code": "NO_DEMO_IDENTITY"}), 401
    session["role"] = "operator"
    return jsonify({"role": "operator", "mode": "synthetic-demo-operator"})


@app.get("/api/health")
def health():
    with db_session() as con:
        con.execute("SELECT 1")
    return jsonify({"status": "ok", "service": "ConsentX synthetic demo", "version": APP_VERSION})


@app.get("/api/state")
def state():
    user_id = request.args.get("user_id") or session_user_id()
    if user_id not in DEMO_USERS:
        return jsonify({"error": "Unknown synthetic user", "reason_code": "UNKNOWN_USER"}), 400
    error = identity_error(user_id)
    if error:
        return error
    with db_session() as con:
        notice = active_notice(con)
        notice_history = [dict(row) for row in con.execute(
            "SELECT version,text,sha256,created_at FROM notices ORDER BY rowid DESC"
        ).fetchall()]
        statuses = {}
        for purpose_id in PURPOSES:
            row = con.execute(
                "SELECT action,notice_version,notice_hash,created_at FROM consent_events "
                "WHERE user_id=? AND purpose_id=? ORDER BY id DESC LIMIT 1",
                (user_id, purpose_id),
            ).fetchone()
            statuses[purpose_id] = dict(row) if row else None
        return jsonify({"user_id": user_id, "purposes": PURPOSES, "consents": statuses,
                        "active_notice": dict(notice), "notice_history": notice_history})


@app.post("/api/consent")
def consent():
    data = request.get_json(silent=True) or {}
    user_id, purpose_id, action = data.get("user_id"), data.get("purpose_id"), data.get("action")
    if user_id not in DEMO_USERS:
        return jsonify({"error": "Unknown synthetic user", "reason_code": "UNKNOWN_USER"}), 400
    if purpose_id not in PURPOSES:
        return jsonify({"error": "Unknown purpose", "reason_code": "INVALID_PURPOSE"}), 400
    if action not in ("grant", "withdraw"):
        return jsonify({"error": "Action must be grant or withdraw", "reason_code": "INVALID_ACTION"}), 400
    error = identity_error(user_id)
    if error:
        return error
    with db_session(write=True) as con:
        notice = active_notice(con)
        event_id = str(uuid.uuid4())
        con.execute(
            "INSERT INTO consent_events(event_id,user_id,purpose_id,action,notice_version,notice_hash,created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (event_id, user_id, purpose_id, action, notice["version"], notice["sha256"], utc_now()),
        )
        revocations = []
        if action == "withdraw":
            for consumer_id, scopes in CONSUMERS.items():
                if purpose_id in scopes:
                    revocation_id = f"REV-{uuid.uuid4()}"
                    created_at = utc_now()
                    con.execute(
                        "INSERT INTO revocation_jobs(revocation_id,withdrawal_event_id,user_id,purpose_id,consumer_id,status,created_at) "
                        "VALUES(?,?,?,?,?,'PENDING',?)",
                        (revocation_id, event_id, user_id, purpose_id, consumer_id, created_at),
                    )
                    cancelled = con.execute(
                        "UPDATE pending_actions SET status='CANCELLED',cancelled_at=?,revocation_id=? "
                        "WHERE user_id=? AND purpose_id=? AND consumer_id=? AND status='QUEUED'",
                        (created_at, revocation_id, user_id, purpose_id, consumer_id),
                    ).rowcount
                    con.execute(
                        "UPDATE revocation_jobs SET pending_actions_cancelled=? WHERE revocation_id=?",
                        (cancelled, revocation_id),
                    )
                    details = json.dumps({"revocation_id": revocation_id, "consumer_id": consumer_id,
                                          "user_id": user_id, "purpose_id": purpose_id, "status": "PENDING",
                                          "pending_actions_cancelled": cancelled})
                    con.execute(
                        "INSERT INTO system_events(event_id,event_type,details,created_at,notice_version,notice_hash) "
                        "VALUES(?,?,?,?,?,?)",
                        (str(uuid.uuid4()), "REVOCATION_QUEUED", details, created_at,
                         notice["version"], notice["sha256"]),
                    )
                    revocations.append({"revocation_id": revocation_id, "consumer_id": consumer_id,
                                        "status": "PENDING", "pending_actions_cancelled": cancelled})
    return jsonify({"recorded": True, "user_id": user_id, "purpose_id": purpose_id,
                    "event_id": event_id, "action": action, "notice_version": notice["version"],
                    "notice_hash": notice["sha256"], "revocations": revocations}), 201


@app.get("/api/revocations")
def revocations():
    user_id = request.args.get("user_id", "").strip() or session_user_id()
    if user_id and user_id not in DEMO_USERS:
        return jsonify({"error": "Unknown synthetic user", "reason_code": "UNKNOWN_USER"}), 400
    error = identity_error(user_id)
    if error:
        return error
    with db_session() as con:
        query = "SELECT * FROM revocation_jobs"
        params = []
        if user_id:
            query += " WHERE user_id=?"
            params.append(user_id)
        query += " ORDER BY id DESC"
        rows = [dict(row) for row in con.execute(query, params).fetchall()]
    return jsonify({"revocations": rows, "total": len(rows)})


@app.get("/api/pending-actions")
def pending_actions():
    user_id = request.args.get("user_id", "").strip() or session_user_id()
    if user_id and user_id not in DEMO_USERS:
        return jsonify({"error": "Unknown synthetic user", "reason_code": "UNKNOWN_USER"}), 400
    error = identity_error(user_id)
    if error:
        return error
    status = request.args.get("status", "").strip().upper()
    if status and status not in {"QUEUED", "CANCELLED", "COMPLETED"}:
        return jsonify({"error": "Unknown pending action status", "reason_code": "INVALID_STATUS"}), 400
    clauses, params = [], []
    if user_id:
        clauses.append("user_id=?")
        params.append(user_id)
    if status:
        clauses.append("status=?")
        params.append(status)
    query = "SELECT * FROM pending_actions"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at, action_id"
    with db_session() as con:
        rows = [dict(row) for row in con.execute(query, params).fetchall()]
    return jsonify({"pending_actions": rows, "total": len(rows)})


@app.post("/api/data-access")
def data_access():
    data = request.get_json(silent=True) or {}
    user_id, purpose_id = data.get("user_id"), data.get("purpose_id")
    consumer_id = data.get("consumer_id")
    operation = data.get("operation")
    requested_fields = data.get("requested_fields")
    request_id = str(uuid.uuid4())
    active_user = session_user_id()
    if not active_user:
        return jsonify({"request_id": request_id, "decision": "DENY", "reason_code": "NO_DEMO_IDENTITY",
                        "payload": None}), 401
    if user_id not in DEMO_USERS:
        with db_session(write=True) as con:
            notice = active_notice(con)
            audit_decision(con, active_user, str(purpose_id or "unknown"),
                           "DENY", "UNKNOWN_USER", notice, request_id, str(consumer_id or "unknown"),
                           str(operation or "unknown"), requested_fields)
        return jsonify({"request_id": request_id, "decision": "DENY", "reason_code": "UNKNOWN_USER", "payload": None}), 403
    if user_id != active_user:
        with db_session(write=True) as con:
            notice = active_notice(con)
            audit_decision(con, active_user, str(purpose_id or "unknown"), "DENY", "IDENTITY_MISMATCH",
                           notice, request_id, str(consumer_id or "unknown"),
                           str(operation or "unknown"), requested_fields)
        return jsonify({"request_id": request_id, "decision": "DENY", "reason_code": "IDENTITY_MISMATCH",
                        "payload": None}), 403
    if purpose_id not in PURPOSES:
        with db_session(write=True) as con:
            notice = active_notice(con)
            audit_decision(con, user_id, str(purpose_id or "unknown"),
                           "DENY", "INVALID_PURPOSE", notice, request_id, str(consumer_id or "unknown"),
                           str(operation or "unknown"), requested_fields)
        return jsonify({"request_id": request_id, "decision": "DENY", "reason_code": "INVALID_PURPOSE", "payload": None}), 400
    policy_fields = CONSUMERS.get(consumer_id, {}).get(purpose_id, set())
    if not isinstance(requested_fields, list) or not requested_fields or any(not isinstance(field, str) for field in requested_fields):
        reason = "INVALID_REQUEST"
    elif not policy_fields:
        reason = "CONSUMER_PURPOSE_MISMATCH"
    elif operation != "READ":
        reason = "OPERATION_NOT_ALLOWED"
    elif not set(requested_fields).issubset(policy_fields):
        reason = "FIELD_SCOPE_EXCEEDED"
    else:
        reason = None
    with db_session(write=True) as con:
        notice = active_notice(con)
        event = con.execute(
            "SELECT * FROM consent_events WHERE user_id=? AND purpose_id=? ORDER BY id DESC LIMIT 1",
            (user_id, purpose_id),
        ).fetchone()
        if reason:
            pass
        elif event is None:
            reason = "NO_ACTIVE_CONSENT"
        elif event["action"] != "grant":
            reason = "CONSENT_WITHDRAWN"
        elif event["notice_version"] != notice["version"] or event["notice_hash"] != notice["sha256"]:
            reason = "NOTICE_MISMATCH"
        else:
            reason = "ACTIVE_CONSENT"
        decision = "ALLOW" if reason == "ACTIVE_CONSENT" else "DENY"
        policy_reason = reason if reason in {"INVALID_REQUEST", "CONSUMER_PURPOSE_MISMATCH", "OPERATION_NOT_ALLOWED", "FIELD_SCOPE_EXCEEDED"} else None
        audit_decision(con, user_id, purpose_id, decision, reason, notice, request_id,
                       consumer_id, operation, requested_fields)
        consent_check = "PASS" if event is not None and event["action"] == "grant" else "FAIL"
        notice_check = (
            "PASS" if event is not None
            and event["action"] == "grant"
            and event["notice_version"] == notice["version"]
            and event["notice_hash"] == notice["sha256"]
            else ("FAIL" if event is not None and event["action"] == "grant" else "SKIPPED")
        )
        result = {"request_id": request_id, "consumer_id": consumer_id, "operation": operation,
                  "requested_fields": requested_fields,
                  "decision": decision, "reason_code": reason,
                  "payload": {key: value for key, value in PURPOSES[purpose_id]["payload"].items()
                              if key in set(requested_fields or [])} if decision == "ALLOW" else None,
                  "decision_trace": [
                      {"check": "Synthetic user", "status": "PASS", "detail": "Known demo identity."},
                      {"check": "Purpose boundary", "status": "PASS", "detail": f"Request is scoped to {purpose_id}."},
                      {"check": "Consumer and field scope", "status": "FAIL" if policy_reason else "PASS",
                       "detail": f"{consumer_id or 'Unknown consumer'} requested {', '.join(requested_fields or [])} for {operation or 'unknown operation'}."},
                      {"check": "Latest consent", "status": consent_check,
                       "detail": "Latest event is a grant." if consent_check == "PASS" else
                                 ("Latest event is a withdrawal." if event is not None else "No consent event exists." )},
                      {"check": "Current notice", "status": notice_check,
                       "detail": f"Consent and active notice are both v{notice['version']}." if notice_check == "PASS" else
                                 (f"Consent is tied to an older notice; current version is v{notice['version']}." if notice_check == "FAIL" else "Not checked because there is no current grant.")},
                      {"check": "Payload release", "status": "RELEASED" if decision == "ALLOW" else "WITHHELD",
                       "detail": "Purpose-scoped synthetic fields only." if decision == "ALLOW" else "No protected payload returned."},
                  ]}
    return jsonify(result), 200 if decision == "ALLOW" else 403


@app.post("/api/notices")
def publish_notice():
    data = request.get_json(silent=True) or {}
    version, text = str(data.get("version", "")).strip(), str(data.get("text", "")).strip()
    if not version or not text:
        return jsonify({"error": "version and text are required", "reason_code": "INVALID_NOTICE"}), 400
    if session.get("role") != "operator":
        return jsonify({"error": "Operator access is required to publish a notice",
                        "reason_code": "OPERATOR_AUTH_REQUIRED"}), 403
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    with db_session(write=True) as con:
        con.execute("INSERT INTO notices(version,text,sha256,created_at) VALUES(?,?,?,?)",
                    (version, text, digest, utc_now()))
        con.execute(
            "INSERT INTO system_events(event_id,event_type,details,created_at,notice_version,notice_hash) "
            "VALUES(?,?,?,?,?,?)",
            (str(uuid.uuid4()), "NOTICE_PUBLISHED", "A new notice version became active.",
             utc_now(), version, digest),
        )
    return jsonify({"version": version, "sha256": digest}), 201


@app.get("/api/audit")
def audit_export():
    fmt = request.args.get("format", "json").lower()
    if fmt not in ("json", "csv"):
        return jsonify({"error": "format must be json or csv"}), 400
    user_filter = request.args.get("user_id", "").strip()
    purpose_filter = request.args.get("purpose_id", "").strip()
    decision_filter = request.args.get("decision", "").strip().upper()
    active_user = session_user_id()
    if not active_user:
        return jsonify({"error": "Choose a synthetic demo identity first", "reason_code": "NO_DEMO_IDENTITY"}), 401
    if user_filter and user_filter not in DEMO_USERS:
        return jsonify({"error": "Unknown synthetic user", "reason_code": "UNKNOWN_USER"}), 400
    if user_filter and user_filter != active_user:
        return jsonify({"error": "Audit identity does not match the selected demo identity",
                        "reason_code": "IDENTITY_MISMATCH"}), 403
    user_filter = active_user
    if purpose_filter and purpose_filter not in PURPOSES:
        return jsonify({"error": "Unknown purpose", "reason_code": "INVALID_PURPOSE"}), 400
    if decision_filter and decision_filter not in ("ALLOW", "DENY"):
        return jsonify({"error": "decision must be ALLOW or DENY", "reason_code": "INVALID_DECISION"}), 400
    with db_session() as con:
        query = (
            "SELECT * FROM (SELECT 'consent' AS record_type,event_id AS record_id,user_id,purpose_id,action AS result,"
            "action AS reason_code,created_at,notice_version,notice_hash,'' AS consumer_id,'' AS operation,'[]' AS requested_fields FROM consent_events "
            "UNION ALL SELECT 'access',request_id,user_id,purpose_id,decision,reason_code,created_at,notice_version,notice_hash,consumer_id,operation,requested_fields "
            "FROM access_decisions UNION ALL SELECT 'system',event_id,CASE WHEN json_valid(details) THEN COALESCE(json_extract(details,'$.user_id'),'system') ELSE 'system' END,'SYSTEM',event_type,details,created_at,"
            "notice_version,notice_hash,'system','EVENT','[]' FROM system_events) WHERE 1=1"
        )
        params = []
        if user_filter:
            query += " AND (user_id=? OR user_id='system')"
            params.append(user_filter)
        if purpose_filter:
            query += " AND purpose_id=?"
            params.append(purpose_filter)
        if decision_filter:
            query += " AND record_type='access' AND result=?"
            params.append(decision_filter)
        query += " ORDER BY created_at, record_id"
        rows = [dict(r) for r in con.execute(query, params).fetchall()]
    if fmt == "json":
        return Response(json.dumps(rows, indent=2), mimetype="application/json",
                        headers={"Content-Disposition": "attachment; filename=consentx-audit.json"})
    output = io.StringIO()
    fields = ["record_type", "record_id", "user_id", "purpose_id", "result", "reason_code",
              "created_at", "notice_version", "notice_hash", "consumer_id", "operation", "requested_fields"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=consentx-audit.csv"})


init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5001")), debug=False)
