"""Independent simulated downstream consumer adapters for ConsentX."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone

CONSUMER_CATALOG = {
    "notification-service": {
        "consumer_id": "notification-service",
        "display_name": "Notification Service",
        "purpose_id": "P1",
        "allowed_fields": ["channel", "upcoming_event_ids"],
        "description": "Dispatches CampusPulse email/push reminders for saved campus events.",
        "action_type": "event_reminder",
    },
    "recommendation-service": {
        "consumer_id": "recommendation-service",
        "display_name": "Recommendation Engine",
        "purpose_id": "P2",
        "allowed_fields": ["synthetic_interests", "suggested_event_ids"],
        "description": "Computes personalized campus event suggestions from synthetic interests.",
        "action_type": "event_recommendation",
    },
    "analytics-service": {
        "consumer_id": "analytics-service",
        "display_name": "Analytics Pipeline",
        "purpose_id": "P3",
        "allowed_fields": ["aggregation", "feature_use_counts"],
        "description": "Collects aggregated synthetic usage counts without individual targeting.",
        "action_type": "analytics_export",
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def seed_consumers(con: sqlite3.Connection) -> None:
    """Ensure all three simulated consumers exist in SQLite."""
    now = utc_now()
    for cid, meta in CONSUMER_CATALOG.items():
        con.execute(
            """
            INSERT OR IGNORE INTO consumer_services
                (consumer_id, display_name, purpose_id, allowed_fields, description,
                 available, revocations_processed, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, 0, ?)
            """,
            (
                cid,
                meta["display_name"],
                meta["purpose_id"],
                json.dumps(meta["allowed_fields"]),
                meta["description"],
                now,
            ),
        )


def list_consumers(con: sqlite3.Connection) -> list[dict]:
    """Return current status of all simulated consumers."""
    rows = con.execute(
        "SELECT * FROM consumer_services ORDER BY purpose_id, consumer_id"
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["available"] = bool(item["available"])
        try:
            item["allowed_fields"] = json.loads(item["allowed_fields"] or "[]")
        except ValueError:
            item["allowed_fields"] = []
        result.append(item)
    return result


def get_consumer(con: sqlite3.Connection, consumer_id: str) -> dict | None:
    row = con.execute(
        "SELECT * FROM consumer_services WHERE consumer_id = ?", (consumer_id,)
    ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["available"] = bool(item["available"])
    return item


def set_consumer_availability(
    con: sqlite3.Connection, consumer_id: str, available: bool
) -> dict | None:
    """Persist simulated online/offline availability for failure/retry demos."""
    if consumer_id not in CONSUMER_CATALOG:
        return None
    now = utc_now()
    con.execute(
        "UPDATE consumer_services SET available = ?, updated_at = ? WHERE consumer_id = ?",
        (1 if available else 0, now, consumer_id),
    )
    return get_consumer(con, consumer_id)


def invoke_consumer_revocation(
    con: sqlite3.Connection, job: sqlite3.Row | dict
) -> dict:
    """Send a revocation instruction to the target consumer adapter.

    Returns a structured response dict:
      - ok (bool)
      - delivered_at (str)
      - acknowledged_at (str | None)
      - adapter_event_id (str | None)
      - receipt_digest (str | None)
      - error (str | None)
    """
    consumer_id = job["consumer_id"]
    consumer = get_consumer(con, consumer_id)
    now = utc_now()

    if not consumer:
        return {
            "ok": False,
            "delivered_at": now,
            "acknowledged_at": None,
            "adapter_event_id": None,
            "receipt_digest": None,
            "error": f"Unknown consumer adapter: {consumer_id}",
        }

    if not consumer["available"]:
        return {
            "ok": False,
            "delivered_at": now,
            "acknowledged_at": None,
            "adapter_event_id": None,
            "receipt_digest": None,
            "error": (
                f"{consumer['display_name']} ({consumer_id}) is currently unavailable "
                "(simulated outage). Revocation remains unresolved until retry succeeds."
            ),
        }

    # Adapter validates purpose binding and records its own acknowledgement event
    expected_purpose = CONSUMER_CATALOG[consumer_id]["purpose_id"]
    if job["purpose_id"] != expected_purpose:
        return {
            "ok": False,
            "delivered_at": now,
            "acknowledged_at": None,
            "adapter_event_id": None,
            "receipt_digest": None,
            "error": f"Adapter scope mismatch: {consumer_id} does not handle {job['purpose_id']}.",
        }

    adapter_event_id = f"ACK-{consumer_id[:4].upper()}-{uuid.uuid4().hex[:10]}"
    ack_payload = json.dumps(
        {
            "adapter_event_id": adapter_event_id,
            "consumer_id": consumer_id,
            "purpose_id": job["purpose_id"],
            "revocation_id": job["revocation_id"],
            "user_id": job["user_id"],
            "acknowledged_at": now,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    receipt_digest = hashlib.sha256(ack_payload.encode("utf-8")).hexdigest()

    con.execute(
        """
        UPDATE consumer_services
        SET revocations_processed = revocations_processed + 1,
            last_ack_event_id = ?,
            last_ack_at = ?,
            updated_at = ?
        WHERE consumer_id = ?
        """,
        (adapter_event_id, now, now, consumer_id),
    )

    return {
        "ok": True,
        "delivered_at": now,
        "acknowledged_at": now,
        "adapter_event_id": adapter_event_id,
        "receipt_digest": receipt_digest,
        "error": None,
    }
