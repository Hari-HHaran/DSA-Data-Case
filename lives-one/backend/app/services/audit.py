"""Append-only, hash-chained application audit log.

Each event stores the SHA-256 of its content plus the previous event's hash. Editing or deleting
any historical row breaks the chain, which verify_chain() detects. This is tamper-evident at the
application level; it is not a legally certified immutable ledger.
"""
import hashlib
import json
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import WorkflowEvent
from .clock import utcnow

GENESIS = "0" * 64


def _digest(prev_hash: str, ev: WorkflowEvent) -> str:
    body = json.dumps(
        {
            "uid": ev.event_uid, "request_id": ev.request_id, "entity_type": ev.entity_type, "entity_ref": ev.entity_ref,
            "type": ev.event_type, "from": ev.from_status, "to": ev.to_status, "actor": ev.actor_id,
            "comment": ev.comment, "changes": ev.changes, "at": ev.created_at.isoformat(timespec="seconds"),
        },
        sort_keys=True, default=str,
    )
    return hashlib.sha256((prev_hash + body).encode()).hexdigest()


def record(
    db: Session, event_type: str, *, request_id: int | None = None, actor_id: int | None = None,
    from_status: str | None = None, to_status: str | None = None, comment: str = "",
    changes: dict | None = None, entity_type: str = "MDM_REQUEST", entity_ref: str | None = None,
    at: datetime | None = None,
) -> WorkflowEvent:
    last = db.execute(select(WorkflowEvent.hash).order_by(WorkflowEvent.id.desc()).limit(1)).scalar()
    prev = last or GENESIS
    ev = WorkflowEvent(
        event_uid=str(uuid.uuid4()), request_id=request_id, entity_type=entity_type, entity_ref=entity_ref,
        event_type=event_type, from_status=from_status, to_status=to_status, actor_id=actor_id,
        comment=comment or "", changes=changes, created_at=(at or utcnow()).replace(microsecond=0), prev_hash=prev,
    )
    ev.hash = _digest(prev, ev)
    db.add(ev)
    db.flush()
    return ev


def verify_chain(db: Session) -> dict:
    prev = GENESIS
    count = 0
    for ev in db.execute(select(WorkflowEvent).order_by(WorkflowEvent.id)).scalars():
        count += 1
        if ev.prev_hash != prev or _digest(prev, ev) != ev.hash:
            return {"valid": False, "events_checked": count, "broken_at_event_id": ev.id}
        prev = ev.hash
    return {"valid": True, "events_checked": count, "broken_at_event_id": None, "head_hash": prev}
