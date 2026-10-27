from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import ApprovalDecision, ApprovalTask, MdmRequest, NotificationEvent, User, WorkflowEvent
from ..schemas import DecisionIn
from ..serializers import event_out, notification_out, request_detail, request_summary, task_out, user_brief
from ..services import audit, roles, workflow
from ..services.clock import utcnow
from ..services.errors import Forbidden, NotFound
from ..services.state_machine import MAIN_PATH, STATUS_LABELS, TRANSITIONS

router = APIRouter(prefix="/api", tags=["flow-engine"])


@router.get("/approvals/inbox")
def inbox(view: str = "pending", q: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    my_roles = [r for r in user.role_codes if r in roles.APPROVER_ROLES]
    base = select(ApprovalTask).where(ApprovalTask.role_code.in_(my_roles))
    now = utcnow()
    if view == "completed":
        base = base.where(ApprovalTask.decided_by_id == user.id)
    elif view == "clarification":
        base = base.where(ApprovalTask.status == "CHANGES_REQUESTED", ApprovalTask.decided_by_id == user.id)
    else:
        base = base.where(ApprovalTask.status == "PENDING")
    tasks = db.execute(base.order_by(ApprovalTask.due_at.is_(None), ApprovalTask.due_at, ApprovalTask.id.desc())).scalars().all()
    items = []
    for t in tasks:
        r = t.request
        if q and q.lower() not in (r.title + r.request_number).lower():
            continue
        if view in ("due_soon", "overdue") and workflow.task_sla_state(t, now) != {"due_soon": "DUE_SOON", "overdue": "OVERDUE"}[view]:
            continue
        decision = db.execute(select(ApprovalDecision).where(ApprovalDecision.task_id == t.id)).scalars().first()
        items.append({**task_out(t), "request": request_summary(r),
                      "hours_pending": round(((t.decided_at or now) - t.activated_at).total_seconds() / 3600, 1) if t.activated_at else None,
                      "decision_comment": decision.comment if decision else None,
                      "parallel_tasks": [{"step_name": o.step_name, "status": o.status} for o in workflow.current_tasks(db, r)
                                         if o.stage_order == t.stage_order and o.id != t.id]})
    pending = db.execute(select(ApprovalTask).where(ApprovalTask.role_code.in_(my_roles), ApprovalTask.status == "PENDING")).scalars().all()
    states = [workflow.task_sla_state(t, now) for t in pending]
    return {"items": items, "roles": my_roles, "counts": {
        "pending": len(pending), "due_soon": states.count("DUE_SOON"), "overdue": states.count("OVERDUE"),
        "completed": db.execute(select(func.count(ApprovalTask.id)).where(ApprovalTask.decided_by_id == user.id)).scalar(),
        "clarification": db.execute(select(func.count(ApprovalTask.id)).where(ApprovalTask.decided_by_id == user.id,
                                                                            ApprovalTask.status == "CHANGES_REQUESTED")).scalar()}}


def _decide(task_id: int, decision: str, body: DecisionIn, db: Session, user: User):
    task = workflow.decide(db, user, task_id, decision, body.comment)
    db.commit()
    return {"task": task_out(task), "request": request_detail(db, user, task.request)}


@router.post("/approvals/{task_id}/approve")
def approve(task_id: int, body: DecisionIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _decide(task_id, "APPROVE", body, db, user)


@router.post("/approvals/{task_id}/reject")
def reject(task_id: int, body: DecisionIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _decide(task_id, "REJECT", body, db, user)


@router.post("/approvals/{task_id}/request-changes")
def request_changes(task_id: int, body: DecisionIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _decide(task_id, "REQUEST_CHANGES", body, db, user)


@router.get("/workflows/state-machine")
def state_machine(_: User = Depends(get_current_user)):
    return {"labels": STATUS_LABELS, "transitions": {k: sorted(v) for k, v in TRANSITIONS.items()}, "main_path": MAIN_PATH}


@router.get("/workflows/{request_id}")
def workflow_timeline(request_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    req = workflow.get_request(db, request_id)
    workflow.assert_can_view(db, user, req)
    events = db.execute(select(WorkflowEvent).where(WorkflowEvent.request_id == req.id).order_by(WorkflowEvent.created_at, WorkflowEvent.id)).scalars().all()
    reached = {}
    for e in events:
        if e.to_status and e.to_status not in reached and e.to_status != e.from_status:
            reached[e.to_status] = e.created_at
    reached.setdefault("DRAFT", req.created_at)
    tasks = workflow.current_tasks(db, req)
    stages = []
    for s in MAIN_PATH:
        st = "done" if s in reached else "upcoming"
        if s == req.status:
            st = "current"
        stages.append({"status": s, "label": STATUS_LABELS[s], "state": st, "at": reached.get(s).isoformat() + "Z" if reached.get(s) else None})
    if req.status in ("NEEDS_CHANGES", "REJECTED", "CANCELLED", "SAP_FAILED"):
        stages.append({"status": req.status, "label": STATUS_LABELS[req.status], "state": "exception",
                       "at": reached.get(req.status).isoformat() + "Z" if reached.get(req.status) else None})
    pending = [t for t in tasks if t.status == "PENDING"]
    next_action = {
        "DRAFT": "The requester finishes the form and sends it in",
        "NEEDS_CHANGES": "The requester fixes the request and sends it again",
        "PENDING_APPROVAL": "Waiting for: " + ", ".join(f"{t.step_name}" for t in pending) if pending else "Sending to the approvers",
        "MDM_VERIFICATION": "The Master Data team does a final check",
        "SAP_PENDING": "The Master Data team sends it to SAP",
        "SAP_FAILED": "The Master Data team tries again, or creates it in SAP by hand",
        "SAP_COMPLETED": "Nothing. It is ready to use in SAP",
        "REJECTED": "Nothing. The request was not approved", "CANCELLED": "Nothing. The request was cancelled",
    }.get(req.status, "")
    return {"request": request_summary(req), "stages": stages, "tasks": [task_out(t) for t in tasks], "next_action": next_action,
            "events": [event_out(e) for e in events]}


@router.get("/workflows")
def tracker(status: str | None = None, q: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
            db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = select(MdmRequest).where(MdmRequest.status != "DRAFT")
    if not user.has_role(*roles.REQUEST_OVERSIGHT_ROLES):
        mine = select(ApprovalTask.request_id).where(ApprovalTask.role_code.in_(user.role_codes))
        query = query.where(or_(MdmRequest.requester_id == user.id, MdmRequest.id.in_(mine)))
    if status:
        query = query.where(MdmRequest.status.in_(status.split(",")))
    if q:
        query = query.where(or_(MdmRequest.title.ilike(f"%{q}%"), MdmRequest.request_number.ilike(f"%{q}%")))
    total = db.execute(select(func.count()).select_from(query.subquery())).scalar()
    rows = db.execute(query.order_by(MdmRequest.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)).scalars().all()
    now = utcnow()
    items = []
    for r in rows:
        tasks = workflow.current_tasks(db, r)
        s = request_summary(r)
        s["tasks"] = [{"step_name": t.step_name, "status": t.status, "stage": t.stage_order, "sla_state": workflow.task_sla_state(t, now),
                       "due_at": t.due_at.isoformat() + "Z" if t.due_at else None, "escalated": t.escalated_at is not None} for t in tasks]
        s["age_days"] = round((now - (r.submitted_at or r.created_at)).total_seconds() / 86400, 1)
        items.append(s)
    return {"items": items, "total": total, "page": page, "page_size": page_size, "metrics": workflow.turnaround_metrics(db)}


@router.post("/workflows/sla/run")
def run_sla(db: Session = Depends(get_db), _: User = Depends(require_roles(roles.ADMIN, roles.MDM_ANALYST))):
    result = workflow.run_sla_checks(db)
    db.commit()
    return result


@router.get("/audit-events")
def audit_events(request_id: int | None = None, event_type: str | None = None, entity_type: str | None = None, q: str | None = None,
                 page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    query = select(WorkflowEvent)
    if not user.has_role(roles.ADMIN, roles.MDM_ANALYST, roles.EXECUTIVE):
        if not request_id:
            raise Forbidden("Full audit history is restricted to administrators, MDM and executives.")
        workflow.assert_can_view(db, user, workflow.get_request(db, request_id))
    if request_id:
        query = query.where(WorkflowEvent.request_id == request_id)
    if event_type:
        query = query.where(WorkflowEvent.event_type == event_type)
    if entity_type:
        query = query.where(WorkflowEvent.entity_type == entity_type)
    if q:
        query = query.where(or_(WorkflowEvent.comment.ilike(f"%{q}%"), WorkflowEvent.entity_ref.ilike(f"%{q}%")))
    total = db.execute(select(func.count()).select_from(query.subquery())).scalar()
    rows = db.execute(query.order_by(WorkflowEvent.created_at.desc(), WorkflowEvent.id.desc()).offset((page - 1) * page_size).limit(page_size)).scalars().all()
    types = sorted(x for (x,) in db.execute(select(WorkflowEvent.event_type).distinct()).all())
    return {"items": [event_out(e) for e in rows], "total": total, "page": page, "page_size": page_size, "event_types": types}


@router.get("/audit-events/verify")
def verify_audit(db: Session = Depends(get_db), _: User = Depends(require_roles(roles.ADMIN, roles.MDM_ANALYST, roles.EXECUTIVE))):
    return audit.verify_chain(db)


# ---------------------------------------------------------------- notifications

@router.get("/notifications")
def my_notifications(limit: int = Query(30, le=100), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.execute(select(NotificationEvent).where(NotificationEvent.recipient_id == user.id, NotificationEvent.channel == "IN_APP")
                      .order_by(NotificationEvent.created_at.desc(), NotificationEvent.id.desc()).limit(limit)).scalars().all()
    unread = db.execute(select(func.count(NotificationEvent.id)).where(NotificationEvent.recipient_id == user.id, NotificationEvent.channel == "IN_APP",
                                                                      NotificationEvent.read_at.is_(None))).scalar()
    return {"items": [notification_out(n) for n in rows], "unread": unread}


@router.post("/notifications/read")
def mark_read(ids: list[int] | None = Body(default=None, embed=True), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(NotificationEvent).filter(NotificationEvent.recipient_id == user.id, NotificationEvent.read_at.is_(None))
    if ids:
        q = q.filter(NotificationEvent.id.in_(ids))
    n = q.update({NotificationEvent.read_at: utcnow()}, synchronize_session=False)
    db.commit()
    return {"marked": n}


@router.get("/notifications/outbox")
def outbox(channel: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(50, le=200), db: Session = Depends(get_db),
           _: User = Depends(require_roles(roles.ADMIN, roles.MDM_ANALYST))):
    q = select(NotificationEvent).where(NotificationEvent.channel != "IN_APP")
    if channel:
        q = q.where(NotificationEvent.channel == channel)
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar()
    rows = db.execute(q.order_by(NotificationEvent.created_at.desc(), NotificationEvent.id.desc()).offset((page - 1) * page_size).limit(page_size)).scalars().all()
    by_type = dict(db.execute(select(NotificationEvent.event_type, func.count()).group_by(NotificationEvent.event_type)).all())
    return {"items": [notification_out(n) for n in rows], "total": total, "by_event_type": by_type,
            "note": "Mock outbox: these Teams/Outlook messages were NOT sent. A Microsoft Graph adapter would deliver them in production."}
