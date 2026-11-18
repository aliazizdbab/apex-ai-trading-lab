from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import redact_secrets
from app.db.models import AuditLog, utcnow

GENESIS_HASH = "0" * 64


def _utc_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        normalized = dt.replace(tzinfo=timezone.utc)
    else:
        normalized = dt.astimezone(timezone.utc)
    return normalized.isoformat()


def compute_audit_entry_hash(
    *,
    ts: datetime,
    actor: str,
    action: str,
    entity: str,
    payload_redacted: dict[str, Any],
    hash_prev: str,
) -> str:
    """Compute deterministic SHA-256 hash linking an audit record to the previous record."""
    canonical = json.dumps(
        {
            "ts": _utc_iso(ts),
            "actor": actor,
            "action": action,
            "entity": entity,
            "payload": payload_redacted,
            "hash_prev": hash_prev,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def append_audit_log(
    db: Session,
    *,
    actor: str,
    action: str,
    entity: str,
    payload: dict[str, Any] | None = None,
    owner_id: str | None = None,
) -> AuditLog:
    """Append a redacted, hash-chained entry to the append-only audit_logs table."""
    last = db.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).scalar_one_or_none()
    hash_prev = last.entry_hash if last else GENESIS_HASH

    ts = utcnow()
    safe_payload = redact_secrets(payload or {})
    if not isinstance(safe_payload, dict):
        safe_payload = {"value": safe_payload}

    entry_hash = compute_audit_entry_hash(
        ts=ts,
        actor=actor,
        action=action,
        entity=entity,
        payload_redacted=safe_payload,
        hash_prev=hash_prev,
    )

    row = AuditLog(
        owner_id=owner_id,
        ts=ts,
        actor=actor,
        action=action,
        entity=entity,
        payload_redacted=safe_payload,
        hash_prev=hash_prev,
        entry_hash=entry_hash,
    )
    db.add(row)
    db.flush()
    return row


def verify_audit_chain(db: Session) -> tuple[bool, int, str | None]:
    """Verify hash-chain continuity and integrity across all audit_logs entries."""
    rows = db.execute(select(AuditLog).order_by(AuditLog.id.asc())).scalars().all()
    expected_prev = GENESIS_HASH

    for row in rows:
        if row.hash_prev != expected_prev:
            return False, len(rows), f"Broken hash_prev link at audit_log id={row.id}"
        expected_hash = compute_audit_entry_hash(
            ts=row.ts,
            actor=row.actor,
            action=row.action,
            entity=row.entity,
            payload_redacted=row.payload_redacted,
            hash_prev=row.hash_prev,
        )
        if row.entry_hash != expected_hash:
            return False, len(rows), f"Entry hash mismatch at audit_log id={row.id}"
        expected_prev = row.entry_hash

    return True, len(rows), None
