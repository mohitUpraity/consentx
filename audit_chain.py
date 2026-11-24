"""Tamper-evident SHA-256 hash-chain audit ledger for ConsentX."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone

GENESIS_HASH = "0" * 64


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def canonical_event(event_dict: dict) -> str:
    """Return deterministic canonical JSON representation for hashing."""
    return json.dumps(event_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_row_hash(prev_hash: str, event_dict: dict) -> str:
    """Compute H_i = SHA256(H_{i-1} || CanonicalEvent_i)."""
    payload = f"{prev_hash}||{canonical_event(event_dict)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def append_ledger_event(
    con: sqlite3.Connection,
    *,
    event_type: str,
    user_id: str,
    purpose_id: str | None = None,
    consumer_id: str | None = None,
    details: dict | str = "",
    notice_version: str | None = None,
    notice_hash: str | None = None,
    event_id: str | None = None,
    created_at: str | None = None,
) -> tuple[str, str]:
    """Append an event to the unified SHA-256 hash-chained audit_ledger."""
    eid = event_id or f"LED-{uuid.uuid4()}"
    ts = created_at or utc_now()
    details_str = (
        json.dumps(details, sort_keys=True, separators=(",", ":"))
        if isinstance(details, dict)
        else str(details)
    )

    last = con.execute("SELECT row_hash FROM audit_ledger ORDER BY id DESC LIMIT 1").fetchone()
    prev_hash = last["row_hash"] if last else GENESIS_HASH

    event_payload = {
        "consumer_id": consumer_id or "",
        "created_at": ts,
        "details": details_str,
        "event_id": eid,
        "event_type": event_type,
        "notice_hash": notice_hash or "",
        "notice_version": notice_version or "",
        "purpose_id": purpose_id or "",
        "user_id": user_id,
    }
    row_hash = compute_row_hash(prev_hash, event_payload)

    con.execute(
        """
        INSERT INTO audit_ledger
            (event_id, event_type, user_id, purpose_id, consumer_id, details,
             notice_version, notice_hash, prev_hash, row_hash, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            eid,
            event_type,
            user_id,
            purpose_id or "",
            consumer_id or "",
            details_str,
            notice_version,
            notice_hash,
            prev_hash,
            row_hash,
            ts,
        ),
    )
    return eid, row_hash


def verify_chain(con: sqlite3.Connection) -> dict:
    """Walk the entire audit_ledger from genesis to tip and verify hashes and links."""
    rows = [
        dict(row)
        for row in con.execute("SELECT * FROM audit_ledger ORDER BY id ASC").fetchall()
    ]
    if not rows:
        return {
            "status": "intact",
            "verified_count": 0,
            "total_count": 0,
            "tip_hash": GENESIS_HASH,
            "broken_at_id": None,
            "message": "Audit ledger is empty (genesis state verified).",
        }

    expected_prev = GENESIS_HASH
    for idx, row in enumerate(rows):
        if row["prev_hash"] != expected_prev:
            return {
                "status": "broken",
                "verified_count": idx,
                "total_count": len(rows),
                "tip_hash": rows[-1]["row_hash"],
                "broken_at_id": row["id"],
                "message": (
                    f"Integrity failure at ledger record #{row['id']} ({row['event_type']}): "
                    "prev_hash does not match predecessor row_hash (deleted, reordered, or forged link)."
                ),
            }

        event_payload = {
            "consumer_id": row["consumer_id"] or "",
            "created_at": row["created_at"],
            "details": row["details"],
            "event_id": row["event_id"],
            "event_type": row["event_type"],
            "notice_hash": row["notice_hash"] or "",
            "notice_version": row["notice_version"] or "",
            "purpose_id": row["purpose_id"] or "",
            "user_id": row["user_id"],
        }
        expected_hash = compute_row_hash(row["prev_hash"], event_payload)
        if row["row_hash"] != expected_hash:
            return {
                "status": "broken",
                "verified_count": idx,
                "total_count": len(rows),
                "tip_hash": rows[-1]["row_hash"],
                "broken_at_id": row["id"],
                "message": (
                    f"Integrity failure at ledger record #{row['id']} ({row['event_type']}): "
                    "row_hash mismatch (event content was altered)."
                ),
            }
        expected_prev = row["row_hash"]

    return {
        "status": "intact",
        "verified_count": len(rows),
        "total_count": len(rows),
        "tip_hash": rows[-1]["row_hash"],
        "broken_at_id": None,
        "message": f"Tamper-evident SHA-256 chain intact across all {len(rows)} ledger events.",
    }
