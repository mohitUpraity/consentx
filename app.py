"""ConsentX: small synthetic consent and downstream-enforcement prototype."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

ROOT = Path(__file__).resolve().parent
INSTANCE = ROOT / "instance"
DB_PATH = Path(os.environ.get("CONSENTX_DB", INSTANCE / "consentx.sqlite3"))
app = Flask(__name__)

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


def init_db() -> None:
    digest = hashlib.sha256(DEFAULT_NOTICE.encode("utf-8")).hexdigest()
    with get_db() as con:
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
                notice_hash TEXT
            );
            """
        )
        con.execute(
            "INSERT OR IGNORE INTO notices(version,text,sha256,created_at) VALUES(?,?,?,?)",
            ("1.0", DEFAULT_NOTICE, digest, utc_now()),
        )


def active_notice(con: sqlite3.Connection) -> sqlite3.Row:
    return con.execute("SELECT * FROM notices ORDER BY created_at DESC, rowid DESC LIMIT 1").fetchone()


def audit_decision(con, user_id, purpose_id, decision, reason, notice):
    con.execute(
        """INSERT INTO access_decisions
        (request_id,user_id,purpose_id,decision,reason_code,created_at,notice_version,notice_hash)
        VALUES(?,?,?,?,?,?,?,?)""",
        (str(uuid.uuid4()), user_id, purpose_id, decision, reason, utc_now(),
         notice["version"] if notice else None, notice["sha256"] if notice else None),
    )


@app.get("/")
def home():
    return render_template("index.html", purposes=PURPOSES, users=DEMO_USERS)


@app.get("/api/health")
def health():
    with get_db() as con:
        con.execute("SELECT 1")
    return jsonify({"status": "ok", "service": "ConsentX synthetic demo"})


@app.get("/api/state")
def state():
    user_id = request.args.get("user_id", "student-001")
    if user_id not in DEMO_USERS:
        return jsonify({"error": "Unknown synthetic user", "reason_code": "UNKNOWN_USER"}), 400
    with get_db() as con:
        notice = active_notice(con)
        statuses = {}
        for purpose_id in PURPOSES:
            row = con.execute(
                "SELECT action,notice_version,notice_hash,created_at FROM consent_events "
                "WHERE user_id=? AND purpose_id=? ORDER BY id DESC LIMIT 1",
                (user_id, purpose_id),
            ).fetchone()
            statuses[purpose_id] = dict(row) if row else None
        return jsonify({"user_id": user_id, "purposes": PURPOSES, "consents": statuses,
                        "active_notice": dict(notice)})


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
    with get_db() as con:
        notice = active_notice(con)
        con.execute(
            "INSERT INTO consent_events(event_id,user_id,purpose_id,action,notice_version,notice_hash,created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), user_id, purpose_id, action, notice["version"], notice["sha256"], utc_now()),
        )
    return jsonify({"recorded": True, "user_id": user_id, "purpose_id": purpose_id,
                    "action": action, "notice_version": notice["version"], "notice_hash": notice["sha256"]}), 201


@app.post("/api/data-access")
def data_access():
    data = request.get_json(silent=True) or {}
    user_id, purpose_id = data.get("user_id"), data.get("purpose_id")
    if user_id not in DEMO_USERS:
        return jsonify({"decision": "DENY", "reason_code": "UNKNOWN_USER", "payload": None}), 403
    if purpose_id not in PURPOSES:
        return jsonify({"decision": "DENY", "reason_code": "INVALID_PURPOSE", "payload": None}), 400
    with get_db() as con:
        notice = active_notice(con)
        event = con.execute(
            "SELECT * FROM consent_events WHERE user_id=? AND purpose_id=? ORDER BY id DESC LIMIT 1",
            (user_id, purpose_id),
        ).fetchone()
        if event is None:
            reason = "NO_ACTIVE_CONSENT"
        elif event["action"] != "grant":
            reason = "CONSENT_WITHDRAWN"
        elif event["notice_version"] != notice["version"] or event["notice_hash"] != notice["sha256"]:
            reason = "NOTICE_MISMATCH"
        else:
            reason = "ACTIVE_CONSENT"
        decision = "ALLOW" if reason == "ACTIVE_CONSENT" else "DENY"
        audit_decision(con, user_id, purpose_id, decision, reason, notice)
        result = {"request_id": con.execute("SELECT request_id FROM access_decisions ORDER BY id DESC LIMIT 1").fetchone()[0],
                  "decision": decision, "reason_code": reason,
                  "payload": PURPOSES[purpose_id]["payload"] if decision == "ALLOW" else None}
    return jsonify(result), 200 if decision == "ALLOW" else 403


@app.post("/api/notices")
def publish_notice():
    data = request.get_json(silent=True) or {}
    version, text = str(data.get("version", "")).strip(), str(data.get("text", "")).strip()
    if not version or not text:
        return jsonify({"error": "version and text are required", "reason_code": "INVALID_NOTICE"}), 400
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    with get_db() as con:
        con.execute("INSERT INTO notices(version,text,sha256,created_at) VALUES(?,?,?,?)",
                    (version, text, digest, utc_now()))
    return jsonify({"version": version, "sha256": digest}), 201


@app.get("/api/audit")
def audit_export():
    fmt = request.args.get("format", "json").lower()
    if fmt not in ("json", "csv"):
        return jsonify({"error": "format must be json or csv"}), 400
    with get_db() as con:
        rows = [dict(r) for r in con.execute(
            "SELECT * FROM (SELECT 'consent' AS record_type,event_id AS record_id,user_id,purpose_id,action AS result,"
            "action AS reason_code,created_at,notice_version,notice_hash FROM consent_events "
            "UNION ALL SELECT 'access',request_id,user_id,purpose_id,decision,reason_code,created_at,notice_version,notice_hash "
            "FROM access_decisions) ORDER BY created_at"
        ).fetchall()]
    if fmt == "json":
        return Response(json.dumps(rows, indent=2), mimetype="application/json",
                        headers={"Content-Disposition": "attachment; filename=consentx-audit.json"})
    output = io.StringIO()
    fields = ["record_type", "record_id", "user_id", "purpose_id", "result", "reason_code",
              "created_at", "notice_version", "notice_hash"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=consentx-audit.csv"})


init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5001")), debug=False)
