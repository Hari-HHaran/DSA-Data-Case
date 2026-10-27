"""Response shaping, including sensitive-field masking based on the viewer."""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    ApprovalTask, DuplicateCandidate, DuplicateReview, MdmRequest, NotificationEvent, SapRecordMapping, SapSyncJob, User, WorkflowEvent,
)
from .services import workflow
from .services.forms import DOMAIN_LABELS
from .services.state_machine import STATUS_LABELS


def iso(dt):
    """Timestamps are stored as naive UTC; emit them with a Z so clients render local time correctly."""
    if dt is None:
        return None
    return dt.isoformat() + "Z" if isinstance(dt, datetime) else dt.isoformat()


def user_brief(u: User | None) -> dict | None:
    if not u:
        return None
    return {"id": u.id, "username": u.username, "name": u.full_name, "title": u.title}


def user_out(u: User) -> dict:
    return {**user_brief(u), "email": u.email, "roles": u.role_codes, "entity_code": u.entity_code, "country_code": u.country_code,
            "persona_note": u.persona_note, "is_demo": u.is_demo}


def task_out(t: ApprovalTask) -> dict:
    return {"id": t.id, "request_id": t.request_id, "step_name": t.step_name, "role_code": t.role_code, "stage": t.stage_order,
            "cycle": t.cycle, "status": t.status, "sla_days": t.sla_days, "activated_at": iso(t.activated_at), "due_at": iso(t.due_at),
            "decided_at": iso(t.decided_at), "decided_by": user_brief(t.decided_by), "sla_state": workflow.task_sla_state(t),
            "reminder_sent_at": iso(t.reminder_sent_at), "escalated_at": iso(t.escalated_at)}


def request_summary(r: MdmRequest) -> dict:
    return {"id": r.id, "request_number": r.request_number, "domain": r.domain, "domain_label": DOMAIN_LABELS[r.domain], "title": r.title,
            "request_type": r.request_type, "entity_code": r.entity_code, "country_code": r.country_code, "department": r.department,
            "status": r.status, "status_label": STATUS_LABELS[r.status], "priority": r.priority, "requester": user_brief(r.requester),
            "flagged_for_review": r.flagged_for_review, "duplicate_check_status": r.duplicate_check_status, "cycle": r.cycle,
            "submitted_at": iso(r.submitted_at), "completed_at": iso(r.completed_at), "created_at": iso(r.created_at),
            "updated_at": iso(r.updated_at), "resolution": r.resolution, "is_synthetic": r.is_synthetic}


def candidate_out(db: Session, c: DuplicateCandidate) -> dict:
    existing = None
    if c.master_record:
        mr = c.master_record
        existing = {"type": "MASTER_RECORD", "id": mr.id, "code": mr.record_code, "name": mr.name, "country_code": mr.country_code,
                    "identifier": mr.identifier, "sap_code": mr.sap_code, "aliases": [a.alias_name for a in mr.aliases]}
    elif c.other_request_id:
        o = db.get(MdmRequest, c.other_request_id)
        existing = {"type": "OPEN_REQUEST", "id": o.id, "code": o.request_number, "name": o.title, "country_code": o.country_code, "status": o.status}
    from .services.duplicates import suggested_action
    return {"id": c.id, "score": c.score, "band": c.band, "exact_identifier_match": c.exact_identifier_match,
            "matched_fields": c.matched_fields, "explanation": c.explanation, "existing": existing,
            "suggested_action": suggested_action({"exact_identifier_match": c.exact_identifier_match, "band": c.band})}


def event_out(e: WorkflowEvent) -> dict:
    return {"id": e.id, "event_uid": e.event_uid, "request_id": e.request_id, "entity_type": e.entity_type, "entity_ref": e.entity_ref,
            "event_type": e.event_type, "from_status": e.from_status, "to_status": e.to_status, "actor": user_brief(e.actor),
            "comment": e.comment, "changes": e.changes, "created_at": iso(e.created_at), "hash": e.hash, "prev_hash": e.prev_hash}


def request_detail(db: Session, viewer: User, r: MdmRequest) -> dict:
    data, masked = workflow.visible_data(db, viewer, r)
    tasks = list(db.execute(select(ApprovalTask).where(ApprovalTask.request_id == r.id).order_by(ApprovalTask.cycle, ApprovalTask.stage_order, ApprovalTask.id)).scalars())
    cands = list(db.execute(select(DuplicateCandidate).where(DuplicateCandidate.request_id == r.id).order_by(DuplicateCandidate.score.desc())).scalars())
    reviews = list(db.execute(select(DuplicateReview).where(DuplicateReview.request_id == r.id).order_by(DuplicateReview.id)).scalars())
    events = list(db.execute(select(WorkflowEvent).where(WorkflowEvent.request_id == r.id).order_by(WorkflowEvent.created_at, WorkflowEvent.id)).scalars())
    jobs = list(db.execute(select(SapSyncJob).where(SapSyncJob.request_id == r.id).order_by(SapSyncJob.id)).scalars())
    mapping = db.execute(select(SapRecordMapping).where(SapRecordMapping.request_id == r.id)).scalar_one_or_none()
    can_fin = workflow.can_see_financial(viewer, r)
    return {
        **request_summary(r), "data": data, "masked_fields": masked,
        "attachments": [{"id": a.id, "category": a.category, "filename": a.original_filename, "size": a.size_bytes,
                         "uploaded_at": iso(a.uploaded_at)} for a in r.attachments],
        "tasks": [task_out(t) for t in tasks], "current_cycle": r.cycle,
        "duplicate_candidates": [candidate_out(db, c) for c in cands],
        "duplicate_reviews": [{"decision": d.decision, "justification": d.justification, "created_at": iso(d.created_at)} for d in reviews],
        "events": [event_out(e) for e in events],
        "sap": {"jobs": [{"id": j.id, "status": j.status, "attempts": j.attempt_count, "operation": j.operation, "object_type": j.sap_object_type,
                          "adapter_mode": j.adapter_mode, "sap_key": j.sap_key, "error": j.error_message,
                          "payload": j.payload if can_fin else {k: v for k, v in j.payload.items() if k not in ("BPBankAccounts", "CreditLimit")},
                          "response": j.response, "updated_at": iso(j.updated_at)} for j in jobs],
                "mapping": {"sap_key": mapping.sap_key, "object_type": mapping.sap_object_type, "is_mock": mapping.is_mock,
                            "master_record_id": mapping.master_record_id} if mapping else None},
        "permissions": {
            "can_edit": r.requester_id == viewer.id and r.status in ("DRAFT", "NEEDS_CHANGES"),
            "can_verify": viewer.has_role("MDM_ANALYST") and r.status == "MDM_VERIFICATION" and r.requester_id != viewer.id,
            "can_sync": viewer.has_role("MDM_ANALYST") and r.status in ("SAP_PENDING", "SAP_FAILED"),
            "can_cancel": r.requester_id == viewer.id and r.status in ("DRAFT", "NEEDS_CHANGES"),
            "can_see_financial": can_fin,
        },
    }


def notification_out(n: NotificationEvent) -> dict:
    return {"id": n.id, "channel": n.channel, "event_type": n.event_type, "title": n.title, "body": n.body, "link": n.link,
            "request_id": n.request_id, "delivery_status": n.delivery_status, "read": n.read_at is not None,
            "created_at": iso(n.created_at), "recipient": user_brief(n.recipient)}
