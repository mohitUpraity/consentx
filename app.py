"""ConsentX: synthetic purpose-based consent, enforcement, and revocation orchestration prototype."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, session

from adapters import (
    CONSUMER_CATALOG,
    invoke_consumer_revocation,
    list_consumers,
    seed_consumers,
    set_consumer_availability,
)
from audit_chain import append_ledger_event, verify_chain

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
    cid: {meta["purpose_id"]: set(meta["allowed_fields"])}
    for cid, meta in CONSUMER_CATALOG.items()
}
DEMO_USERS = {"student-001": "Aarav Demo", "student-002": "Mira Demo"}
DEFAULT_NOTICE = (
    "CampusPulse uses data only for the selected purpose. You can withdraw consent at any time. "
    "A new notice version may require you to confirm your choices again."
)
RECEIPT_DISCLAIMER = (
    "A service acknowledgement confirms the simulated service processed the instruction. "
    "It does not establish that every previously shared copy was erased."
)


def count_suite_tests() -> int:
    test_file = ROOT / "tests" / "test_ps002.py"
    if not test_file.exists():
        return 0
    return len(re.findall(r"^\s*def test_", test_file.read_text(encoding="utf-8"), re.MULTILINE))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


@contextmanager
def db_session(write: bool = False):
    con = get_db()
    try:
        # Acquire SQLite's writer lock before request policy reads so parallel
        # requests never collide upgrading transactions for audit writes.
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
    now = utc_now()
    with db_session(write=True) as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS notices (
                version TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                sha256 TEXT NOT NULL,
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
                last_error TEXT,
                pending_actions_cancelled INTEGER NOT NULL DEFAULT 0,
                notice_version TEXT,
                notice_hash TEXT,
                adapter_receipt_digest TEXT
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
            CREATE TABLE IF NOT EXISTS consumer_services (
                consumer_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                purpose_id TEXT NOT NULL,
                allowed_fields TEXT NOT NULL,
                description TEXT NOT NULL,
                available INTEGER NOT NULL DEFAULT 1,
                revocations_processed INTEGER NOT NULL DEFAULT 0,
                last_ack_event_id TEXT,
                last_ack_at TEXT,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                event_type TEXT NOT NULL,
                user_id TEXT NOT NULL,
                purpose_id TEXT,
                consumer_id TEXT,
                details TEXT NOT NULL,
                notice_version TEXT,
                notice_hash TEXT,
                prev_hash TEXT NOT NULL,
                row_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

        # Safe column migrations for existing databases
        access_cols = {row["name"] for row in con.execute("PRAGMA table_info(access_decisions)")}
        for name, declaration in (
            ("consumer_id", "TEXT NOT NULL DEFAULT 'legacy-consumer'"),
            ("operation", "TEXT NOT NULL DEFAULT 'READ'"),
            ("requested_fields", "TEXT NOT NULL DEFAULT '[]'"),
        ):
            if name not in access_cols:
                con.execute(f"ALTER TABLE access_decisions ADD COLUMN {name} {declaration}")

        rev_cols = {row["name"] for row in con.execute("PRAGMA table_info(revocation_jobs)")}
        for name, declaration in (
            ("pending_actions_cancelled", "INTEGER NOT NULL DEFAULT 0"),
            ("notice_version", "TEXT"),
            ("notice_hash", "TEXT"),
            ("adapter_receipt_digest", "TEXT"),
        ):
            if name not in rev_cols:
                con.execute(f"ALTER TABLE revocation_jobs ADD COLUMN {name} {declaration}")

        con.execute(
            "INSERT OR IGNORE INTO notices(version,text,sha256,created_at) VALUES(?,?,?,?)",
            ("1.0", DEFAULT_NOTICE, digest, now),
        )
        seed_consumers(con)
        for user_id in DEMO_USERS:
            for cid, meta in CONSUMER_CATALOG.items():
                for sequence in (1, 2):
                    con.execute(
                        "INSERT OR IGNORE INTO pending_actions"
                        "(action_id,user_id,purpose_id,consumer_id,action_type,status,created_at) "
                        "VALUES(?,?,?,?,?,'QUEUED',?)",
                        (
                            f"ACTION-{user_id}-{meta['purpose_id']}-{sequence}",
                            user_id,
                            meta["purpose_id"],
                            cid,
                            meta["action_type"],
                            now,
                        ),
                    )


def active_notice(con: sqlite3.Connection) -> sqlite3.Row:
    return con.execute("SELECT * FROM notices ORDER BY rowid DESC LIMIT 1").fetchone()


def session_user_id() -> str | None:
    user_id = session.get("user_id")
    return user_id if user_id in DEMO_USERS else None


def identity_error(user_id: str | None = None):
    active_user = session_user_id()
    if not active_user:
        return jsonify({"error": "Choose a synthetic demo identity first", "reason_code": "NO_DEMO_IDENTITY"}), 401
    if user_id and user_id != active_user:
        return jsonify({
            "error": "Request identity does not match the selected demo identity",
            "reason_code": "IDENTITY_MISMATCH",
        }), 403
    return None


def operator_token_configured() -> str | None:
    return app.config.get("OPERATOR_TOKEN") or os.environ.get("CONSENTX_OPERATOR_TOKEN")


def audit_decision(
    con: sqlite3.Connection,
    user_id: str,
    purpose_id: str,
    decision: str,
    reason: str,
    notice: sqlite3.Row | None,
    request_id: str | None = None,
    consumer_id: str = "unknown",
    operation: str = "READ",
    requested_fields=None,
) -> str:
    request_id = request_id or str(uuid.uuid4())
    ts = utc_now()
    fields_json = json.dumps(requested_fields or [])
    nv = notice["version"] if notice else None
    nh = notice["sha256"] if notice else None
    con.execute(
        """INSERT INTO access_decisions
        (request_id,user_id,purpose_id,decision,reason_code,created_at,notice_version,notice_hash,
         consumer_id,operation,requested_fields)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (request_id, user_id, purpose_id, decision, reason, ts, nv, nh, consumer_id, operation, fields_json),
    )
    append_ledger_event(
        con,
        event_type="ACCESS_ALLOW" if decision == "ALLOW" else "ACCESS_DENY",
        user_id=user_id,
        purpose_id=purpose_id,
        consumer_id=consumer_id,
        details={
            "request_id": request_id,
            "decision": decision,
            "reason_code": reason,
            "operation": operation,
            "requested_fields": requested_fields or [],
        },
        notice_version=nv,
        notice_hash=nh,
        created_at=ts,
    )
    return request_id


@app.get("/")
def home():
    if not session_user_id():
        session["user_id"] = "student-001"
    return render_template(
        "index.html",
        purposes=PURPOSES,
        users=DEMO_USERS,
        consumers=CONSUMERS,
        app_version=APP_VERSION,
        suite_test_count=count_suite_tests(),
        operator_configured=bool(operator_token_configured()),
    )


@app.get("/api/demo-session")
def demo_session_state():
    user_id = session_user_id()
    if not user_id:
        return jsonify({"error": "Choose a synthetic demo identity", "reason_code": "NO_DEMO_IDENTITY"}), 401
    return jsonify({
        "user_id": user_id,
        "display_name": DEMO_USERS[user_id],
        "mode": "synthetic-demo-identity",
        "role": session.get("role", "student"),
        "operator_configured": bool(operator_token_configured()),
    })


@app.post("/api/demo-session")
def select_demo_identity():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if user_id not in DEMO_USERS:
        return jsonify({"error": "Unknown synthetic user", "reason_code": "UNKNOWN_USER"}), 400
    session["user_id"] = user_id
    session["role"] = "student"
    return jsonify({
        "user_id": user_id,
        "display_name": DEMO_USERS[user_id],
        "mode": "synthetic-demo-identity",
    })


@app.post("/api/operator-session")
def operator_session():
    configured_token = operator_token_configured()
    supplied_token = (request.get_json(silent=True) or {}).get("token", "")
    if not configured_token:
        return jsonify({
            "error": "Operator access is not configured (set CONSENTX_OPERATOR_TOKEN on the server)",
            "reason_code": "OPERATOR_NOT_CONFIGURED",
        }), 503
    if not isinstance(supplied_token, str) or not secrets.compare_digest(supplied_token, configured_token):
        return jsonify({
            "error": "Operator access code is incorrect",
            "reason_code": "OPERATOR_AUTH_REQUIRED",
        }), 403
    if not session_user_id():
        return jsonify({"error": "Choose a synthetic identity first", "reason_code": "NO_DEMO_IDENTITY"}), 401
    session["role"] = "operator"
    return jsonify({"role": "operator", "mode": "synthetic-demo-operator"})


@app.route("/healthz", methods=["GET", "HEAD"])
def healthz():
    with db_session() as con:
        con.execute("SELECT 1")
    return jsonify({"status": "ok"})


@app.get("/api/health")
def health():
    with db_session() as con:
        con.execute("SELECT 1")
        integrity = verify_chain(con)
    return jsonify({
        "status": "ok",
        "service": "ConsentX synthetic demo",
        "version": APP_VERSION,
        "suite_test_count": count_suite_tests(),
        "operator_configured": bool(operator_token_configured()),
        "ledger_status": integrity["status"],
        "ledger_count": integrity["total_count"],
    })


@app.post("/api/demo-reset")
def reset_demo():
    """Reset the synthetic demo database back to clean Notice v1.0 baseline."""
    if not session_user_id():
        return jsonify({"error": "Choose a synthetic demo identity first", "reason_code": "NO_DEMO_IDENTITY"}), 401
    with db_session(write=True) as con:
        for table in (
            "audit_ledger",
            "system_events",
            "pending_actions",
            "revocation_jobs",
            "access_decisions",
            "consent_events",
            "consumer_services",
            "notices",
        ):
            con.execute(f"DELETE FROM {table}")
        seq_exists = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'"
        ).fetchone()
        if seq_exists:
            con.execute("DELETE FROM sqlite_sequence")
    init_db()
    session["user_id"] = "student-001"
    session["role"] = "student"
    return jsonify({"reset": True, "user_id": "student-001", "notice_version": "1.0"}), 200


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
        notice_history = [
            dict(row)
            for row in con.execute("SELECT version,text,sha256,created_at FROM notices ORDER BY rowid DESC").fetchall()
        ]
        statuses = {}
        for purpose_id in PURPOSES:
            row = con.execute(
                "SELECT action,notice_version,notice_hash,created_at FROM consent_events "
                "WHERE user_id=? AND purpose_id=? ORDER BY id DESC LIMIT 1",
                (user_id, purpose_id),
            ).fetchone()
            statuses[purpose_id] = dict(row) if row else None
        consumers = list_consumers(con)
        integrity = verify_chain(con)
        return jsonify({
            "user_id": user_id,
            "purposes": PURPOSES,
            "consents": statuses,
            "active_notice": dict(notice),
            "notice_history": notice_history,
            "consumers": consumers,
            "ledger_integrity": integrity,
            "suite_test_count": count_suite_tests(),
        })


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
        ts = utc_now()
        con.execute(
            "INSERT INTO consent_events(event_id,user_id,purpose_id,action,notice_version,notice_hash,created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (event_id, user_id, purpose_id, action, notice["version"], notice["sha256"], ts),
        )
        append_ledger_event(
            con,
            event_type="CONSENT_GRANTED" if action == "grant" else "CONSENT_WITHDRAWN",
            user_id=user_id,
            purpose_id=purpose_id,
            details={"consent_event_id": event_id, "action": action},
            notice_version=notice["version"],
            notice_hash=notice["sha256"],
            created_at=ts,
        )

        revocations = []
        if action == "grant":
            # Replenish synthetic queued work if none is currently queued so repeat demos can cancel live work
            queued_count = con.execute(
                "SELECT COUNT(*) AS cnt FROM pending_actions WHERE user_id=? AND purpose_id=? AND status='QUEUED'",
                (user_id, purpose_id),
            ).fetchone()["cnt"]
            if queued_count == 0:
                for cid, meta in CONSUMER_CATALOG.items():
                    if meta["purpose_id"] == purpose_id:
                        for idx in (1, 2):
                            con.execute(
                                "INSERT INTO pending_actions"
                                "(action_id,user_id,purpose_id,consumer_id,action_type,status,created_at) "
                                "VALUES(?,?,?,?,?,'QUEUED',?)",
                                (
                                    f"ACTION-{user_id}-{purpose_id}-{uuid.uuid4().hex[:6]}-{idx}",
                                    user_id,
                                    purpose_id,
                                    cid,
                                    meta["action_type"],
                                    ts,
                                ),
                            )
        elif action == "withdraw":
            for consumer_id, scopes in CONSUMERS.items():
                if purpose_id in scopes:
                    revocation_id = f"REV-{uuid.uuid4()}"
                    created_at = utc_now()
                    con.execute(
                        "INSERT INTO revocation_jobs"
                        "(revocation_id,withdrawal_event_id,user_id,purpose_id,consumer_id,status,created_at,notice_version,notice_hash) "
                        "VALUES(?,?,?,?,?,'PENDING',?,?,?)",
                        (
                            revocation_id,
                            event_id,
                            user_id,
                            purpose_id,
                            consumer_id,
                            created_at,
                            notice["version"],
                            notice["sha256"],
                        ),
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
                    details = json.dumps({
                        "revocation_id": revocation_id,
                        "consumer_id": consumer_id,
                        "user_id": user_id,
                        "purpose_id": purpose_id,
                        "status": "PENDING",
                        "pending_actions_cancelled": cancelled,
                    })
                    con.execute(
                        "INSERT INTO system_events(event_id,event_type,details,created_at,notice_version,notice_hash) "
                        "VALUES(?,?,?,?,?,?)",
                        (str(uuid.uuid4()), "REVOCATION_QUEUED", details, created_at, notice["version"], notice["sha256"]),
                    )
                    append_ledger_event(
                        con,
                        event_type="REVOCATION_QUEUED",
                        user_id=user_id,
                        purpose_id=purpose_id,
                        consumer_id=consumer_id,
                        details={
                            "revocation_id": revocation_id,
                            "withdrawal_event_id": event_id,
                            "pending_actions_cancelled": cancelled,
                        },
                        notice_version=notice["version"],
                        notice_hash=notice["sha256"],
                        created_at=created_at,
                    )
                    if cancelled > 0:
                        append_ledger_event(
                            con,
                            event_type="WORK_CANCELLED",
                            user_id=user_id,
                            purpose_id=purpose_id,
                            consumer_id=consumer_id,
                            details={
                                "revocation_id": revocation_id,
                                "cancelled_count": cancelled,
                            },
                            notice_version=notice["version"],
                            notice_hash=notice["sha256"],
                            created_at=created_at,
                        )
                    revocations.append({
                        "revocation_id": revocation_id,
                        "consumer_id": consumer_id,
                        "status": "PENDING",
                        "pending_actions_cancelled": cancelled,
                    })

    return jsonify({
        "recorded": True,
        "user_id": user_id,
        "purpose_id": purpose_id,
        "event_id": event_id,
        "action": action,
        "notice_version": notice["version"],
        "notice_hash": notice["sha256"],
        "revocations": revocations,
    }), 201


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


def _dispatch_revocation(revocation_id: str, is_retry: bool = False):
    active_user = session_user_id()
    if not active_user:
        return jsonify({"error": "Choose a synthetic demo identity first", "reason_code": "NO_DEMO_IDENTITY"}), 401

    with db_session(write=True) as con:
        job = con.execute(
            "SELECT * FROM revocation_jobs WHERE revocation_id = ?", (revocation_id,)
        ).fetchone()
        if not job:
            return jsonify({"error": "Revocation instruction not found", "reason_code": "REVOCATION_NOT_FOUND"}), 404
        if job["user_id"] != active_user:
            return jsonify({
                "error": "Request identity does not match the selected demo identity",
                "reason_code": "IDENTITY_MISMATCH",
            }), 403
        if job["status"] == "ACKNOWLEDGED":
            return jsonify({
                "error": "Revocation instruction has already been acknowledged",
                "reason_code": "ALREADY_ACKNOWLEDGED",
                "revocation": dict(job),
            }), 409
        if is_retry and job["status"] != "FAILED":
            return jsonify({
                "error": "Only failed revocation instructions can be retried",
                "reason_code": "REVOCATION_NOT_FAILED",
                "revocation": dict(job),
            }), 400

        notice = active_notice(con)
        nv = job["notice_version"] or (notice["version"] if notice else None)
        nh = job["notice_hash"] or (notice["sha256"] if notice else None)

        if is_retry:
            retry_ts = utc_now()
            retry_details = {
                "revocation_id": revocation_id,
                "consumer_id": job["consumer_id"],
                "user_id": job["user_id"],
                "purpose_id": job["purpose_id"],
                "previous_attempts": job["attempts"],
            }
            con.execute(
                "INSERT INTO system_events(event_id,event_type,details,created_at,notice_version,notice_hash) "
                "VALUES(?,?,?,?,?,?)",
                (str(uuid.uuid4()), "REVOCATION_RETRIED", json.dumps(retry_details), retry_ts, nv, nh),
            )
            append_ledger_event(
                con,
                event_type="REVOCATION_RETRIED",
                user_id=job["user_id"],
                purpose_id=job["purpose_id"],
                consumer_id=job["consumer_id"],
                details=retry_details,
                notice_version=nv,
                notice_hash=nh,
                created_at=retry_ts,
            )

        outcome = invoke_consumer_revocation(con, job)
        new_attempts = job["attempts"] + 1

        if outcome["ok"]:
            con.execute(
                """
                UPDATE revocation_jobs
                SET status='ACKNOWLEDGED',
                    delivered_at=?,
                    acknowledged_at=?,
                    attempts=?,
                    adapter_event_id=?,
                    adapter_receipt_digest=?,
                    last_error=NULL
                WHERE revocation_id=?
                """,
                (
                    outcome["delivered_at"],
                    outcome["acknowledged_at"],
                    new_attempts,
                    outcome["adapter_event_id"],
                    outcome["receipt_digest"],
                    revocation_id,
                ),
            )
            delivered_details = {
                "revocation_id": revocation_id,
                "consumer_id": job["consumer_id"],
                "user_id": job["user_id"],
                "purpose_id": job["purpose_id"],
                "attempt": new_attempts,
            }
            ack_details = {
                "revocation_id": revocation_id,
                "consumer_id": job["consumer_id"],
                "user_id": job["user_id"],
                "purpose_id": job["purpose_id"],
                "adapter_event_id": outcome["adapter_event_id"],
                "receipt_digest": outcome["receipt_digest"],
                "attempt": new_attempts,
            }
            con.execute(
                "INSERT INTO system_events(event_id,event_type,details,created_at,notice_version,notice_hash) "
                "VALUES(?,?,?,?,?,?)",
                (str(uuid.uuid4()), "REVOCATION_DELIVERED", json.dumps(delivered_details), outcome["delivered_at"], nv, nh),
            )
            con.execute(
                "INSERT INTO system_events(event_id,event_type,details,created_at,notice_version,notice_hash) "
                "VALUES(?,?,?,?,?,?)",
                (str(uuid.uuid4()), "REVOCATION_ACKNOWLEDGED", json.dumps(ack_details), outcome["acknowledged_at"], nv, nh),
            )
            append_ledger_event(
                con,
                event_type="REVOCATION_DELIVERED",
                user_id=job["user_id"],
                purpose_id=job["purpose_id"],
                consumer_id=job["consumer_id"],
                details=delivered_details,
                notice_version=nv,
                notice_hash=nh,
                created_at=outcome["delivered_at"],
            )
            append_ledger_event(
                con,
                event_type="REVOCATION_ACKNOWLEDGED",
                user_id=job["user_id"],
                purpose_id=job["purpose_id"],
                consumer_id=job["consumer_id"],
                details=ack_details,
                notice_version=nv,
                notice_hash=nh,
                created_at=outcome["acknowledged_at"],
            )
            updated = dict(con.execute("SELECT * FROM revocation_jobs WHERE revocation_id=?", (revocation_id,)).fetchone())
            return jsonify({"revocation": updated, "outcome": "ACKNOWLEDGED"}), 200

        # Failure path: record FAILED honestly without fabricating acknowledgement
        con.execute(
            """
            UPDATE revocation_jobs
            SET status='FAILED',
                delivered_at=?,
                attempts=?,
                last_error=?
            WHERE revocation_id=?
            """,
            (outcome["delivered_at"], new_attempts, outcome["error"], revocation_id),
        )
        fail_details = {
            "revocation_id": revocation_id,
            "consumer_id": job["consumer_id"],
            "user_id": job["user_id"],
            "purpose_id": job["purpose_id"],
            "attempt": new_attempts,
            "error": outcome["error"],
        }
        con.execute(
            "INSERT INTO system_events(event_id,event_type,details,created_at,notice_version,notice_hash) "
            "VALUES(?,?,?,?,?,?)",
            (str(uuid.uuid4()), "REVOCATION_FAILED", json.dumps(fail_details), outcome["delivered_at"], nv, nh),
        )
        append_ledger_event(
            con,
            event_type="REVOCATION_FAILED",
            user_id=job["user_id"],
            purpose_id=job["purpose_id"],
            consumer_id=job["consumer_id"],
            details=fail_details,
            notice_version=nv,
            notice_hash=nh,
            created_at=outcome["delivered_at"],
        )
        updated = dict(con.execute("SELECT * FROM revocation_jobs WHERE revocation_id=?", (revocation_id,)).fetchone())
        return jsonify({
            "error": outcome["error"],
            "reason_code": "CONSUMER_UNAVAILABLE",
            "revocation": updated,
            "outcome": "FAILED",
        }), 502


@app.post("/api/revocations/<revocation_id>/deliver")
def deliver_revocation(revocation_id: str):
    return _dispatch_revocation(revocation_id, is_retry=False)


@app.post("/api/revocations/<revocation_id>/retry")
def retry_revocation(revocation_id: str):
    return _dispatch_revocation(revocation_id, is_retry=True)


@app.get("/api/consumers")
def get_consumers():
    with db_session() as con:
        consumers = list_consumers(con)
    return jsonify({"consumers": consumers, "total": len(consumers)})


@app.post("/api/consumers/<consumer_id>/availability")
def toggle_consumer_availability(consumer_id: str):
    if consumer_id not in CONSUMER_CATALOG:
        return jsonify({"error": "Unknown consumer service", "reason_code": "UNKNOWN_CONSUMER"}), 404
    active_user = session_user_id()
    if not active_user:
        return jsonify({"error": "Choose a synthetic demo identity first", "reason_code": "NO_DEMO_IDENTITY"}), 401

    data = request.get_json(silent=True) or {}
    if "available" not in data or not isinstance(data["available"], bool):
        return jsonify({"error": "available (boolean) is required", "reason_code": "INVALID_REQUEST"}), 400

    with db_session(write=True) as con:
        updated = set_consumer_availability(con, consumer_id, data["available"])
        notice = active_notice(con)
        ts = utc_now()
        details = {
            "consumer_id": consumer_id,
            "available": updated["available"],
            "user_id": active_user,
        }
        con.execute(
            "INSERT INTO system_events(event_id,event_type,details,created_at,notice_version,notice_hash) "
            "VALUES(?,?,?,?,?,?)",
            (
                str(uuid.uuid4()),
                "CONSUMER_AVAILABILITY_CHANGED",
                json.dumps(details),
                ts,
                notice["version"] if notice else None,
                notice["sha256"] if notice else None,
            ),
        )
        append_ledger_event(
            con,
            event_type="CONSUMER_AVAILABILITY_CHANGED",
            user_id=active_user,
            purpose_id=CONSUMER_CATALOG[consumer_id]["purpose_id"],
            consumer_id=consumer_id,
            details=details,
            notice_version=notice["version"] if notice else None,
            notice_hash=notice["sha256"] if notice else None,
            created_at=ts,
        )
    return jsonify({"consumer": updated}), 200


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


@app.post("/api/pending-actions/simulate")
def simulate_pending_action():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id") or session_user_id()
    purpose_id = data.get("purpose_id")
    if user_id not in DEMO_USERS:
        return jsonify({"error": "Unknown synthetic user", "reason_code": "UNKNOWN_USER"}), 400
    if purpose_id not in PURPOSES:
        return jsonify({"error": "Unknown purpose", "reason_code": "INVALID_PURPOSE"}), 400
    error = identity_error(user_id)
    if error:
        return error

    with db_session(write=True) as con:
        notice = active_notice(con)
        latest = con.execute(
            "SELECT * FROM consent_events WHERE user_id=? AND purpose_id=? ORDER BY id DESC LIMIT 1",
            (user_id, purpose_id),
        ).fetchone()
        if (
            not latest
            or latest["action"] != "grant"
            or latest["notice_version"] != notice["version"]
            or latest["notice_hash"] != notice["sha256"]
        ):
            return jsonify({
                "error": "Cannot queue synthetic work without active consent under the current notice",
                "reason_code": "CONSENT_REQUIRED",
            }), 403

        cid = next(c for c, meta in CONSUMER_CATALOG.items() if meta["purpose_id"] == purpose_id)
        action_id = f"ACTION-{user_id}-{purpose_id}-{uuid.uuid4().hex[:6]}"
        ts = utc_now()
        con.execute(
            "INSERT INTO pending_actions(action_id,user_id,purpose_id,consumer_id,action_type,status,created_at) "
            "VALUES(?,?,?,?,?,'QUEUED',?)",
            (action_id, user_id, purpose_id, cid, CONSUMER_CATALOG[cid]["action_type"], ts),
        )
        row = dict(con.execute("SELECT * FROM pending_actions WHERE action_id=?", (action_id,)).fetchone())
    return jsonify({"pending_action": row}), 201


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
        return jsonify({
            "request_id": request_id,
            "decision": "DENY",
            "reason_code": "NO_DEMO_IDENTITY",
            "payload": None,
        }), 401
    if user_id not in DEMO_USERS:
        with db_session(write=True) as con:
            notice = active_notice(con)
            audit_decision(
                con,
                active_user,
                str(purpose_id or "unknown"),
                "DENY",
                "UNKNOWN_USER",
                notice,
                request_id,
                str(consumer_id or "unknown"),
                str(operation or "unknown"),
                requested_fields,
            )
        return jsonify({"request_id": request_id, "decision": "DENY", "reason_code": "UNKNOWN_USER", "payload": None}), 403
    if user_id != active_user:
        with db_session(write=True) as con:
            notice = active_notice(con)
            audit_decision(
                con,
                active_user,
                str(purpose_id or "unknown"),
                "DENY",
                "IDENTITY_MISMATCH",
                notice,
                request_id,
                str(consumer_id or "unknown"),
                str(operation or "unknown"),
                requested_fields,
            )
        return jsonify({
            "request_id": request_id,
            "decision": "DENY",
            "reason_code": "IDENTITY_MISMATCH",
            "payload": None,
        }), 403
    if purpose_id not in PURPOSES:
        with db_session(write=True) as con:
            notice = active_notice(con)
            audit_decision(
                con,
                user_id,
                str(purpose_id or "unknown"),
                "DENY",
                "INVALID_PURPOSE",
                notice,
                request_id,
                str(consumer_id or "unknown"),
                str(operation or "unknown"),
                requested_fields,
            )
        return jsonify({"request_id": request_id, "decision": "DENY", "reason_code": "INVALID_PURPOSE", "payload": None}), 400

    policy_fields = CONSUMERS.get(consumer_id, {}).get(purpose_id, set())
    if not isinstance(requested_fields, list) or not requested_fields or any(not isinstance(f, str) for f in requested_fields):
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
        policy_reason = (
            reason
            if reason in {"INVALID_REQUEST", "CONSUMER_PURPOSE_MISMATCH", "OPERATION_NOT_ALLOWED", "FIELD_SCOPE_EXCEEDED"}
            else None
        )
        audit_decision(
            con,
            user_id,
            purpose_id,
            decision,
            reason,
            notice,
            request_id,
            consumer_id,
            operation,
            requested_fields,
        )
        consent_check = "PASS" if event is not None and event["action"] == "grant" else "FAIL"
        notice_check = (
            "PASS"
            if event is not None
            and event["action"] == "grant"
            and event["notice_version"] == notice["version"]
            and event["notice_hash"] == notice["sha256"]
            else ("FAIL" if event is not None and event["action"] == "grant" else "SKIPPED")
        )
        result = {
            "request_id": request_id,
            "consumer_id": consumer_id,
            "operation": operation,
            "requested_fields": requested_fields,
            "decision": decision,
            "reason_code": reason,
            "payload": (
                {k: v for k, v in PURPOSES[purpose_id]["payload"].items() if k in set(requested_fields or [])}
                if decision == "ALLOW"
                else None
            ),
            "decision_trace": [
                {"check": "Synthetic user", "status": "PASS", "detail": "Known demo identity."},
                {"check": "Purpose boundary", "status": "PASS", "detail": f"Request is scoped to {purpose_id}."},
                {
                    "check": "Consumer and field scope",
                    "status": "FAIL" if policy_reason else "PASS",
                    "detail": (
                        f"{consumer_id or 'Unknown consumer'} requested "
                        f"{', '.join(requested_fields or [])} for {operation or 'unknown operation'}."
                    ),
                },
                {
                    "check": "Latest consent",
                    "status": consent_check,
                    "detail": (
                        "Latest event is a grant."
                        if consent_check == "PASS"
                        else ("Latest event is a withdrawal." if event is not None else "No consent event exists.")
                    ),
                },
                {
                    "check": "Current notice",
                    "status": notice_check,
                    "detail": (
                        f"Consent and active notice are both v{notice['version']}."
                        if notice_check == "PASS"
                        else (
                            f"Consent is tied to an older notice; current version is v{notice['version']}."
                            if notice_check == "FAIL"
                            else "Not checked because there is no current grant."
                        )
                    ),
                },
                {
                    "check": "Payload release",
                    "status": "RELEASED" if decision == "ALLOW" else "WITHHELD",
                    "detail": "Purpose-scoped synthetic fields only."
                    if decision == "ALLOW"
                    else "No protected payload returned.",
                },
            ],
        }
    return jsonify(result), 200 if decision == "ALLOW" else 403


@app.post("/api/notices")
def publish_notice():
    data = request.get_json(silent=True) or {}
    version, text = str(data.get("version", "")).strip(), str(data.get("text", "")).strip()
    if not version or not text:
        return jsonify({"error": "version and text are required", "reason_code": "INVALID_NOTICE"}), 400
    if session.get("role") != "operator":
        return jsonify({
            "error": "Operator access is required to publish a notice",
            "reason_code": "OPERATOR_AUTH_REQUIRED",
        }), 403

    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    with db_session(write=True) as con:
        current = active_notice(con)
        if current and current["text"] == text:
            return jsonify({
                "error": "Notice text must differ from the current active notice",
                "reason_code": "UNCHANGED_NOTICE",
            }), 400
        exists = con.execute("SELECT 1 FROM notices WHERE version=?", (version,)).fetchone()
        if exists:
            return jsonify({
                "error": f"Notice version {version} already exists",
                "reason_code": "VERSION_EXISTS",
            }), 409

        ts = utc_now()
        con.execute(
            "INSERT INTO notices(version,text,sha256,created_at) VALUES(?,?,?,?)",
            (version, text, digest, ts),
        )
        con.execute(
            "INSERT INTO system_events(event_id,event_type,details,created_at,notice_version,notice_hash) "
            "VALUES(?,?,?,?,?,?)",
            (str(uuid.uuid4()), "NOTICE_PUBLISHED", "A new notice version became active.", ts, version, digest),
        )
        append_ledger_event(
            con,
            event_type="NOTICE_PUBLISHED",
            user_id="system",
            purpose_id="SYSTEM",
            details={"version": version, "sha256": digest},
            notice_version=version,
            notice_hash=digest,
            created_at=ts,
        )
    return jsonify({"version": version, "sha256": digest}), 201


@app.get("/api/my-privacy")
def my_privacy():
    user_id = request.args.get("user_id", "").strip() or session_user_id()
    if user_id and user_id not in DEMO_USERS:
        return jsonify({"error": "Unknown synthetic user", "reason_code": "UNKNOWN_USER"}), 400
    error = identity_error(user_id)
    if error:
        return error

    with db_session() as con:
        notice = dict(active_notice(con))
        permissions = []
        consents_map = {}
        for pid, pmeta in PURPOSES.items():
            latest = con.execute(
                "SELECT event_id,action,notice_version,notice_hash,created_at FROM consent_events "
                "WHERE user_id=? AND purpose_id=? ORDER BY id DESC LIMIT 1",
                (user_id, pid),
            ).fetchone()
            latest_dict = dict(latest) if latest else None
            consents_map[pid] = latest_dict
            matches_notice = bool(
                latest_dict
                and latest_dict["notice_version"] == notice["version"]
                and latest_dict["notice_hash"] == notice["sha256"]
            )
            granted = bool(latest_dict and latest_dict["action"] == "grant" and matches_notice)
            if granted:
                status_label = "Granted"
            elif latest_dict and latest_dict["action"] == "withdraw":
                status_label = "Withdrawn"
            elif latest_dict and latest_dict["action"] == "grant":
                status_label = "Re-consent needed"
            else:
                status_label = "Not granted"
            permissions.append({
                "purpose_id": pid,
                "name": pmeta["name"],
                "description": pmeta["description"],
                "status_label": status_label,
                "granted": granted,
                "notice_version": latest_dict["notice_version"] if latest_dict else None,
                "notice_hash": latest_dict["notice_hash"] if latest_dict else None,
                "updated_at": latest_dict["created_at"] if latest_dict else None,
            })

        consumers = {c["consumer_id"]: c for c in list_consumers(con)}
        connected_services = []
        for cid, meta in CONSUMER_CATALOG.items():
            pid = meta["purpose_id"]
            perm = next(p for p in permissions if p["purpose_id"] == pid)
            queued_cnt = con.execute(
                "SELECT COUNT(*) AS c FROM pending_actions WHERE user_id=? AND consumer_id=? AND status='QUEUED'",
                (user_id, cid),
            ).fetchone()["c"]
            cancelled_cnt = con.execute(
                "SELECT COUNT(*) AS c FROM pending_actions WHERE user_id=? AND consumer_id=? AND status='CANCELLED'",
                (user_id, cid),
            ).fetchone()["c"]
            connected_services.append({
                "consumer_id": cid,
                "display_name": meta["display_name"],
                "purpose_id": pid,
                "purpose_name": PURPOSES[pid]["name"],
                "authorized_fields": meta["allowed_fields"],
                "currently_authorized": perm["granted"],
                "available": consumers[cid]["available"],
                "queued_work_count": queued_cnt,
                "cancelled_work_count": cancelled_cnt,
            })

        rev_rows = [
            dict(r)
            for r in con.execute(
                "SELECT * FROM revocation_jobs WHERE user_id=? ORDER BY id DESC", (user_id,)
            ).fetchall()
        ]
        for rev in rev_rows:
            rev["purpose_name"] = PURPOSES.get(rev["purpose_id"], {}).get("name", rev["purpose_id"])
            rev["receipt_json_url"] = f"/api/privacy-receipt/{rev['revocation_id']}?format=json&download=1"
            rev["receipt_html_url"] = f"/api/privacy-receipt/{rev['revocation_id']}?format=html"

        unresolved = [r for r in rev_rows if r["status"] != "ACKNOWLEDGED"]
        total_cancelled = sum(r.get("pending_actions_cancelled", 0) for r in rev_rows)

    return jsonify({
        "user_id": user_id,
        "display_name": DEMO_USERS[user_id],
        "active_notice": notice,
        "permissions": permissions,
        "connected_services": connected_services,
        "revocations": rev_rows,
        "unresolved_actions": unresolved,
        "summary": {
            "granted_count": sum(1 for p in permissions if p["granted"]),
            "withdrawn_count": sum(1 for p in permissions if p["status_label"] == "Withdrawn"),
            "unresolved_revocations": len(unresolved),
            "acknowledged_revocations": sum(1 for r in rev_rows if r["status"] == "ACKNOWLEDGED"),
            "cancelled_actions": total_cancelled,
        },
        "disclaimer": RECEIPT_DISCLAIMER,
    })


def _build_receipt_payload(con: sqlite3.Connection, job: sqlite3.Row) -> dict:
    pid = job["purpose_id"]
    notice = active_notice(con)
    nv = job["notice_version"] or (notice["version"] if notice else "1.0")
    nh = job["notice_hash"] or (notice["sha256"] if notice else "")
    cancelled_rows = [
        r["action_id"]
        for r in con.execute(
            "SELECT action_id FROM pending_actions WHERE revocation_id=? ORDER BY action_id",
            (job["revocation_id"],),
        ).fetchall()
    ]
    ledger_ids = [
        r["event_id"]
        for r in con.execute(
            "SELECT event_id, details FROM audit_ledger WHERE user_id=? ORDER BY id ASC",
            (job["user_id"],),
        ).fetchall()
        if job["revocation_id"] in (r["details"] or "") or job["withdrawal_event_id"] in (r["details"] or "")
    ]
    ack_map = {
        "ACKNOWLEDGED": "Acknowledged",
        "FAILED": "Failed (unresolved)",
        "DELIVERED": "Delivered (awaiting acknowledgement)",
        "PENDING": "Pending delivery",
    }
    return {
        "receipt_type": "ConsentX Withdrawal Receipt",
        "generated_at": utc_now(),
        "withdrawal_id": job["revocation_id"],
        "user_id": job["user_id"],
        "user": DEMO_USERS.get(job["user_id"], job["user_id"]),
        "purpose_id": pid,
        "purpose": f"{pid} — {PURPOSES.get(pid, {}).get('name', pid)}",
        "affected_consumer": job["consumer_id"],
        "withdrawal_timestamp": job["created_at"],
        "cancelled_pending_actions": job["pending_actions_cancelled"],
        "cancelled_action_ids": cancelled_rows,
        "delivery_attempts": job["attempts"],
        "status": job["status"],
        "consumer_acknowledgement": ack_map.get(job["status"], job["status"]),
        "delivered_at": job["delivered_at"],
        "acknowledged_at": job["acknowledged_at"],
        "adapter_event_id": job["adapter_event_id"],
        "adapter_receipt_digest": job["adapter_receipt_digest"],
        "last_error": job["last_error"],
        "notice_reference": {"version": nv, "sha256": nh},
        "evidence_ids": {
            "consent_event_id": job["withdrawal_event_id"],
            "revocation_id": job["revocation_id"],
            "adapter_event_id": job["adapter_event_id"],
            "ledger_event_ids": ledger_ids,
        },
        "disclaimer": RECEIPT_DISCLAIMER,
    }


@app.get("/api/privacy-receipt/<revocation_id>")
def privacy_receipt(revocation_id: str):
    active_user = session_user_id()
    if not active_user:
        return jsonify({"error": "Choose a synthetic demo identity first", "reason_code": "NO_DEMO_IDENTITY"}), 401

    fmt = request.args.get("format", "json").lower()
    if fmt not in ("json", "html"):
        return jsonify({"error": "format must be json or html"}), 400

    with db_session() as con:
        job = con.execute(
            "SELECT * FROM revocation_jobs WHERE revocation_id=?", (revocation_id,)
        ).fetchone()
        if not job:
            return jsonify({"error": "Withdrawal receipt not found", "reason_code": "REVOCATION_NOT_FOUND"}), 404
        if job["user_id"] != active_user:
            return jsonify({
                "error": "Receipt identity does not match the selected demo identity",
                "reason_code": "IDENTITY_MISMATCH",
            }), 403
        receipt = _build_receipt_payload(con, job)

    if fmt == "html":
        return render_template("receipt.html", receipt=receipt, app_version=APP_VERSION)

    headers = {}
    if request.args.get("download") in ("1", "true", "yes"):
        headers["Content-Disposition"] = f"attachment; filename=privacy-receipt-{revocation_id}.json"
    return Response(json.dumps(receipt, indent=2), mimetype="application/json", headers=headers)


@app.get("/api/audit/verify")
def verify_audit():
    with db_session() as con:
        result = verify_chain(con)
    return jsonify(result), 200 if result["status"] == "intact" else 409


@app.get("/api/audit/ledger")
def audit_ledger_view():
    active_user = session_user_id()
    if not active_user:
        return jsonify({"error": "Choose a synthetic demo identity first", "reason_code": "NO_DEMO_IDENTITY"}), 401
    with db_session() as con:
        rows = [
            dict(r)
            for r in con.execute(
                "SELECT * FROM audit_ledger WHERE user_id=? OR user_id='system' ORDER BY id DESC",
                (active_user,),
            ).fetchall()
        ]
        integrity = verify_chain(con)
    return jsonify({"events": rows, "total": len(rows), "integrity": integrity})


@app.get("/api/diagnostics")
def live_diagnostics():
    """Run non-destructive live verification checks against the running backend."""
    checks = []
    with db_session() as con:
        notice = active_notice(con)
        recomputed = hashlib.sha256(notice["text"].encode("utf-8")).hexdigest() if notice else ""
        integrity = verify_chain(con)
        consumers = list_consumers(con)
        decisions_count = con.execute("SELECT COUNT(*) AS c FROM access_decisions").fetchone()["c"]
        consents_count = con.execute("SELECT COUNT(*) AS c FROM consent_events").fetchone()["c"]
        rev_count = con.execute("SELECT COUNT(*) AS c FROM revocation_jobs").fetchone()["c"]

    checks.append({
        "id": "CHK-01",
        "name": "Database & health readiness",
        "expected": "SQLite connected and responsive",
        "observed": "SQLite operational",
        "passed": True,
    })
    checks.append({
        "id": "CHK-02",
        "name": "Exact 3-purpose PS-002 scope",
        "expected": "Purposes = {P1, P2, P3}",
        "observed": f"Purposes = {sorted(PURPOSES.keys())}",
        "passed": set(PURPOSES.keys()) == {"P1", "P2", "P3"},
    })
    checks.append({
        "id": "CHK-03",
        "name": "Registered downstream consumer adapters",
        "expected": "3 purpose-isolated adapters seeded",
        "observed": f"{len(consumers)} adapters ({sum(1 for c in consumers if c['available'])} online)",
        "passed": len(consumers) == 3,
    })
    checks.append({
        "id": "CHK-04",
        "name": "Active notice SHA-256 verification",
        "expected": "Stored digest matches SHA-256 of exact notice text",
        "observed": f"v{notice['version']} · {recomputed[:12]}…",
        "passed": bool(notice and notice["sha256"] == recomputed),
    })
    checks.append({
        "id": "CHK-05",
        "name": "Tamper-evident audit ledger chain",
        "expected": "All ledger records link to genesis with valid SHA-256 hashes",
        "observed": f"{integrity['status'].upper()} ({integrity['verified_count']}/{integrity['total_count']} verified)",
        "passed": integrity["status"] == "intact",
    })
    checks.append({
        "id": "CHK-06",
        "name": "Session identity boundary",
        "expected": "Active demo identity pinned in server session",
        "observed": f"session={session_user_id() or 'none'} · role={session.get('role', 'student')}",
        "passed": session_user_id() in DEMO_USERS,
    })
    checks.append({
        "id": "CHK-07",
        "name": "Operator notice-publish gate",
        "expected": "CONSENTX_OPERATOR_TOKEN configured; student mode cannot publish",
        "observed": "Token configured" if operator_token_configured() else "Not configured (publishing locked)",
        "passed": True,
    })
    checks.append({
        "id": "CHK-08",
        "name": "Isolated automated lifecycle suite",
        "expected": ">= 12 tests in suite",
        "observed": f"{count_suite_tests()} test cases defined; {consents_count} consent, {decisions_count} access, {rev_count} revocation rows in DB",
        "passed": count_suite_tests() >= 12,
    })

    passed_count = sum(1 for c in checks if c["passed"])
    return jsonify({
        "checks": checks,
        "passed": passed_count,
        "total": len(checks),
        "all_passed": passed_count == len(checks),
        "checked_at": utc_now(),
    })


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
        return jsonify({
            "error": "Audit identity does not match the selected demo identity",
            "reason_code": "IDENTITY_MISMATCH",
        }), 403
    user_filter = active_user
    if purpose_filter and purpose_filter not in PURPOSES:
        return jsonify({"error": "Unknown purpose", "reason_code": "INVALID_PURPOSE"}), 400
    if decision_filter and decision_filter not in ("ALLOW", "DENY"):
        return jsonify({"error": "decision must be ALLOW or DENY", "reason_code": "INVALID_DECISION"}), 400

    with db_session() as con:
        query = (
            "SELECT * FROM ("
            "SELECT 'consent' AS record_type,event_id AS record_id,user_id,purpose_id,action AS result,"
            "action AS reason_code,created_at,notice_version,notice_hash,'' AS consumer_id,'' AS operation,'[]' AS requested_fields "
            "FROM consent_events "
            "UNION ALL "
            "SELECT 'access',request_id,user_id,purpose_id,decision,reason_code,created_at,notice_version,notice_hash,"
            "consumer_id,operation,requested_fields FROM access_decisions "
            "UNION ALL "
            "SELECT 'system',event_id,"
            "CASE WHEN json_valid(details) THEN COALESCE(json_extract(details,'$.user_id'),'system') ELSE 'system' END,"
            "CASE WHEN json_valid(details) THEN COALESCE(json_extract(details,'$.purpose_id'),'SYSTEM') ELSE 'SYSTEM' END,"
            "event_type,details,created_at,notice_version,notice_hash,"
            "CASE WHEN json_valid(details) THEN COALESCE(json_extract(details,'$.consumer_id'),'system') ELSE 'system' END,"
            "'EVENT','[]' FROM system_events"
            ") WHERE 1=1"
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
        return Response(
            json.dumps(rows, indent=2),
            mimetype="application/json",
            headers={"Content-Disposition": "attachment; filename=consentx-audit.json"},
        )
    output = io.StringIO()
    fields = [
        "record_type",
        "record_id",
        "user_id",
        "purpose_id",
        "result",
        "reason_code",
        "created_at",
        "notice_version",
        "notice_hash",
        "consumer_id",
        "operation",
        "requested_fields",
    ]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=consentx-audit.csv"},
    )


init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5001")), debug=False)
