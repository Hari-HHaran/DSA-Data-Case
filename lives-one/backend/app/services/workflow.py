"""Flow Engine: request lifecycle, approval routing (parallel + sequential), decisions, MDM verification, SLA."""
from datetime import datetime, timedelta
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from ..models import (
    ApprovalDecision, ApprovalTask, Country, DuplicateCandidate, DuplicateReview, MasterRecord, MdmRequest,
    RequestAttachment, User, WorkflowStep, WorkflowTemplate,
)
from . import audit, conditions, duplicates, notifications, roles, settings_service, validation
from .clock import add_working_days, utcnow, working_days_between
from .errors import Conflict, Forbidden, NotFound, ValidationFailed
from .forms import DOMAIN_LABELS, field_labels, get_form, request_title
from .state_machine import EDITABLE, transition

OPEN_TASK = ("PENDING", "WAITING")


# ---------------------------------------------------------------- access helpers

def get_request(db: Session, request_id: int) -> MdmRequest:
    req = db.get(MdmRequest, request_id)
    if not req:
        raise NotFound("Request not found.")
    return req


def can_view(db: Session, user: User, req: MdmRequest) -> bool:
    if req.requester_id == user.id or user.has_role(*roles.REQUEST_OVERSIGHT_ROLES):
        return True
    task_roles = set(db.execute(select(ApprovalTask.role_code).where(ApprovalTask.request_id == req.id)).scalars())
    return any(user.has_role(r) for r in task_roles)


def assert_can_view(db: Session, user: User, req: MdmRequest) -> None:
    if not can_view(db, user, req):
        raise Forbidden("You do not have access to this request.")


def sensitive_keys(db: Session, domain: str) -> set[str]:
    return {f.key for f in get_form(db, domain).fields if f.sensitivity == "FINANCIAL"}


def can_see_financial(user: User, req: MdmRequest) -> bool:
    return req.requester_id == user.id or user.has_role(*roles.FINANCIAL_FIELD_ROLES)


def mask(value: str | None) -> str | None:
    if not value:
        return value
    tail = value[-4:] if len(value) > 6 else ""
    return f"•••• {tail}".strip() + " (restricted)"


def visible_data(db: Session, user: User, req: MdmRequest) -> tuple[dict, list[str]]:
    data = dict(req.data)
    masked = []
    if not can_see_financial(user, req):
        for k in sensitive_keys(db, req.domain):
            if data.get(k):
                data[k] = mask(data[k])
                masked.append(k)
    return data, masked


# ---------------------------------------------------------------- drafts

def _next_number(db: Session, req: MdmRequest, at: datetime) -> str:
    return f"MDM-{at.year}-{req.id:04d}"


def create_draft(db: Session, user: User, payload: dict, at: datetime | None = None) -> MdmRequest:
    at = at or utcnow()
    domain = payload["domain"]
    if domain not in DOMAIN_LABELS:
        raise ValidationFailed(f"Unknown record category '{domain}'.")
    if not user.has_role(roles.REQUESTOR, roles.SALES, roles.ADMIN):
        raise Forbidden("Your role cannot raise master-data requests.")
    form = get_form(db, domain)
    data = payload.get("data") or {}
    req = MdmRequest(
        request_number=f"TMP-{at.timestamp()}", domain=domain, request_type=payload.get("request_type") or "CREATE",
        entity_code=payload.get("entity_code") or user.entity_code, country_code=payload.get("country_code") or user.country_code,
        department=payload.get("department") or "", priority=payload.get("priority") or "NORMAL",
        requester_id=user.id, form_version=form.version, status="DRAFT", created_at=at, updated_at=at,
        cloned_from_id=payload.get("cloned_from_id"), is_synthetic=bool(payload.get("is_synthetic")),
    )
    db.add(req)
    db.flush()
    req.request_number = _next_number(db, req, at)
    req.set_data(data)
    req.title = request_title(domain, req.data)
    audit.record(db, "DRAFT_CREATED", request_id=req.id, actor_id=user.id, to_status="DRAFT",
                 comment=f"{DOMAIN_LABELS[domain]} request drafted", entity_ref=req.request_number, at=at)
    db.flush()
    return req


def update_draft(db: Session, user: User, req: MdmRequest, payload: dict, at: datetime | None = None) -> MdmRequest:
    if req.requester_id != user.id:
        raise Forbidden("Only the requestor can edit this request.")
    if req.status not in EDITABLE:
        raise Conflict("Only drafts and requests returned for changes can be edited.")
    changes = {}
    for key in ("entity_code", "country_code", "department", "request_type", "priority"):
        if key in payload and payload[key] is not None and getattr(req, key) != payload[key]:
            changes[key] = (getattr(req, key), payload[key])
            setattr(req, key, payload[key])
    if "data" in payload and payload["data"] is not None:
        changes.update(req.set_data(payload["data"]))
    if not changes:
        return req
    req.title = request_title(req.domain, req.data)
    if set(changes) & (duplicates.identity_keys(req.domain) | {"country_code"}):
        req.duplicate_check_status = "NOT_RUN"
    secret = sensitive_keys(db, req.domain)
    summary = {k: ("[sensitive value changed]" if k in secret else {"from": v[0], "to": v[1]}) for k, v in changes.items()}
    audit.record(db, "DRAFT_UPDATED", request_id=req.id, actor_id=user.id, from_status=req.status, to_status=req.status,
                 comment=f"{len(changes)} field(s) changed", changes=summary, entity_ref=req.request_number, at=at)
    db.flush()
    return req


def clone_request(db: Session, user: User, source: MdmRequest) -> MdmRequest:
    assert_can_view(db, user, source)
    payload = {"domain": source.domain, "entity_code": source.entity_code, "country_code": source.country_code,
               "department": source.department, "request_type": source.request_type, "data": source.data,
               "cloned_from_id": source.id}
    if not can_see_financial(user, source):
        payload["data"] = {k: v for k, v in source.data.items() if k not in sensitive_keys(db, source.domain)}
    return create_draft(db, user, payload)


def cancel_request(db: Session, user: User, req: MdmRequest, reason: str = "") -> MdmRequest:
    if req.requester_id != user.id and not user.has_role(roles.ADMIN):
        raise Forbidden("Only the requestor can cancel this request.")
    transition(db, req, "CANCELLED", user.id, reason or "Cancelled by requestor", event_type="REQUEST_CANCELLED")
    return req


# ---------------------------------------------------------------- duplicate review

def review_duplicates(db: Session, user: User, req: MdmRequest, decision: str, justification: str,
                      candidate_id: int | None = None, at: datetime | None = None) -> MdmRequest:
    if req.requester_id != user.id and not user.has_role(roles.MDM_ANALYST):
        raise Forbidden("Only the requestor or MDM can record a duplicate review.")
    if req.status not in EDITABLE:
        raise Conflict("Duplicate review is only possible before submission.")
    cands = list(db.execute(select(DuplicateCandidate).where(DuplicateCandidate.request_id == req.id)).scalars())
    if req.duplicate_check_status == "NOT_RUN":
        raise Conflict("Run the duplicate check first.")
    exact = any(c.exact_identifier_match for c in cands)
    likely = any(c.band == "LIKELY_DUPLICATE" for c in cands)
    justification = (justification or "").strip()
    allowed = {"REUSE_EXISTING", "FLAG_FOR_REVIEW"}
    if not exact:
        allowed |= {"CONTINUE_WITH_JUSTIFICATION"} if likely else {"NOT_DUPLICATE", "CONTINUE_WITH_JUSTIFICATION"}
    if decision not in allowed:
        raise ValidationFailed(f"'{decision}' is not permitted for these matches. Allowed: {', '.join(sorted(allowed))}.")
    if decision in ("CONTINUE_WITH_JUSTIFICATION", "FLAG_FOR_REVIEW") and len(justification) < 15:
        raise ValidationFailed("Please explain why this is not a duplicate (at least 15 characters).")
    db.add(DuplicateReview(request_id=req.id, candidate_id=candidate_id, decision=decision, justification=justification,
                           reviewer_id=user.id, created_at=at or utcnow()))
    if decision == "REUSE_EXISTING":
        cand = db.get(DuplicateCandidate, candidate_id) if candidate_id else next((c for c in cands if c.master_record_id), None)
        if not cand or not cand.master_record_id:
            raise ValidationFailed("Choose an existing master record to reuse.")
        req.reused_record_id = cand.master_record_id
        req.resolution = f"Reused existing record {cand.master_record.record_code}"
        req.duplicate_check_status = "RESOLVED"
        transition(db, req, "CANCELLED", user.id, f"Duplicate prevented: requestor reused {cand.master_record.record_code}",
                   event_type="DUPLICATE_PREVENTED", at=at)
        return req
    req.flagged_for_review = decision in ("CONTINUE_WITH_JUSTIFICATION", "FLAG_FOR_REVIEW")
    req.duplicate_check_status = "RESOLVED"
    audit.record(db, "DUPLICATE_REVIEWED", request_id=req.id, actor_id=user.id, from_status=req.status, to_status=req.status,
                 comment=f"{decision.replace('_', ' ').title()}: {justification}".strip(": "), entity_ref=req.request_number, at=at)
    return req


def run_duplicate_check(db: Session, user: User, req: MdmRequest, at: datetime | None = None):
    if req.requester_id != user.id and not user.has_role(roles.MDM_ANALYST):
        raise Forbidden("You cannot run checks on this request.")
    rows = duplicates.run_check(db, req)
    audit.record(db, "DUPLICATE_CHECK_RUN", request_id=req.id, actor_id=user.id, from_status=req.status, to_status=req.status,
                 comment=f"{len(rows)} potential match(es); result {req.duplicate_check_status}",
                 changes={"candidates": [{"score": r.score, "band": r.band} for r in rows]}, entity_ref=req.request_number, at=at)
    return rows


# ---------------------------------------------------------------- routing

def template_for(db: Session, domain: str) -> WorkflowTemplate:
    t = db.execute(select(WorkflowTemplate).where(WorkflowTemplate.domain == domain, WorkflowTemplate.is_active.is_(True))).scalar_one_or_none()
    if not t:
        raise NotFound(f"No active workflow template for {domain}.")
    return t


def route(db: Session, domain: str, ctx: dict) -> list[dict]:
    """Returns the approval steps that apply, with the reason each one applies."""
    template = template_for(db, domain)
    labels = field_labels(db, domain)
    out = []
    for step in template.steps:
        if step.is_active and conditions.evaluate(step.condition, ctx):
            out.append({"step_id": step.id, "name": step.name, "role_code": step.role_code, "stage_order": step.stage_order,
                        "sla_days": step.sla_days, "reason": conditions.describe(step.condition, labels)
                        if step.condition else "Required for every request of this type", "description": step.description})
    # Normalise stage numbers to 1..n so the UI reads naturally.
    stages = sorted({s["stage_order"] for s in out})
    for s in out:
        s["stage"] = stages.index(s["stage_order"]) + 1
    return out


def preview_route(db: Session, domain: str, header: dict, data: dict) -> list[dict]:
    return route(db, domain, validation.build_context(domain, header, data))


def _country_tz(db: Session, code: str | None) -> str:
    c = db.get(Country, code) if code else None
    return c.timezone if c else "Asia/Singapore"


def _activate(db: Session, req: MdmRequest, tasks: list[ApprovalTask], at: datetime) -> None:
    tz = _country_tz(db, req.country_code)
    for t in tasks:
        t.status = "PENDING"
        t.activated_at = at
        t.due_at = add_working_days(at, t.sla_days, tz)
    for role in sorted({t.role_code for t in tasks}):
        names = ", ".join(t.step_name for t in tasks if t.role_code == role)
        notifications.notify(db, notifications.users_with_role(db, role), "APPROVAL_ASSIGNED",
                             f"Please approve: {req.request_number} · {req.title}",
                             f"{names}. Asked for by {req.requester.full_name}. Please decide by {tasks[0].due_at:%d %b %Y}.",
                             request_id=req.id, link=f"/flow/inbox?request={req.id}", at=at)


def submit(db: Session, user: User, req: MdmRequest, at: datetime | None = None) -> dict:
    at = at or utcnow()
    if req.requester_id != user.id:
        raise Forbidden("Only the requestor can submit this request.")
    if req.status not in EDITABLE:
        raise Conflict(f"Request is already {req.status.replace('_', ' ').lower()}.")
    if req.duplicate_check_status == "NOT_RUN":
        duplicates.run_check(db, req)
    readiness = validation.evaluate_request(db, req)
    if readiness["state"] != "COMPLETE":
        audit.record(db, "SUBMISSION_BLOCKED", request_id=req.id, actor_id=user.id, from_status=req.status, to_status=req.status,
                     comment="Submission blocked by validation: " + "; ".join(list(readiness["errors"].values())[:5])
                     if readiness["errors"] else "Submission blocked: duplicate review outstanding",
                     changes={"errors": readiness["errors"], "duplicate_status": readiness["duplicate_status"]},
                     entity_ref=req.request_number, at=at)
        db.commit()
        raise ValidationFailed("The request is not ready to submit.", {"readiness": readiness})

    resubmission = req.status == "NEEDS_CHANGES"
    req.cycle += 1
    req.submitted_at = req.submitted_at or at
    transition(db, req, "SUBMITTED", user.id, "Resubmitted after changes" if resubmission else "Submitted", at=at)
    transition(db, req, "VALIDATION_COMPLETED", None, "All required fields, documents and duplicate checks passed",
               changes={"required_fields": readiness["required_total"], "documents": len(readiness["attachments_required"]),
                        "duplicate_status": req.duplicate_check_status}, at=at)
    steps = route(db, req.domain, validation.build_context(req.domain, {"entity_code": req.entity_code, "country_code": req.country_code,
                                                                       "request_type": req.request_type, "department": req.department}, req.data))
    req.workflow_template_id = template_for(db, req.domain).id
    notifications.notify(db, [req.requester], "REQUEST_SUBMITTED", f"{req.request_number} submitted",
                         f"It has gone to {len(steps)} approval step(s). We will let you know at each stage.", request_id=req.id,
                         link=f"/mdm/requests/{req.id}", at=at)
    if not steps:
        transition(db, req, "MDM_VERIFICATION", None, "No approvals required by current rules", at=at)
        _notify_mdm(db, req, at)
        return {"request": req, "route": steps}
    tasks = []
    for s in steps:
        t = ApprovalTask(request_id=req.id, step_id=s["step_id"], step_name=s["name"], role_code=s["role_code"],
                         stage_order=s["stage"], cycle=req.cycle, status="WAITING", sla_days=s["sla_days"], created_at=at)
        db.add(t)
        tasks.append(t)
    db.flush()
    transition(db, req, "PENDING_APPROVAL", None, "Routed: " + "; ".join(f"Stage {s['stage']} – {s['name']}" for s in steps),
               event_type="ROUTED", changes={"steps": [{k: s[k] for k in ("name", "role_code", "stage", "reason")} for s in steps]}, at=at)
    first = min(t.stage_order for t in tasks)
    _activate(db, req, [t for t in tasks if t.stage_order == first], at)
    db.flush()
    return {"request": req, "route": steps}


def _notify_mdm(db: Session, req: MdmRequest, at: datetime) -> None:
    notifications.notify(db, notifications.users_with_role(db, roles.MDM_ANALYST), "MDM_VERIFICATION_READY",
                         f"Ready for final check: {req.request_number}", f"{req.title} has been approved by everyone needed.",
                         request_id=req.id, link=f"/mdm/requests/{req.id}", at=at)


def current_tasks(db: Session, req: MdmRequest) -> list[ApprovalTask]:
    return list(db.execute(select(ApprovalTask).where(ApprovalTask.request_id == req.id, ApprovalTask.cycle == req.cycle)
                           .order_by(ApprovalTask.stage_order, ApprovalTask.id)).scalars())


def decide(db: Session, user: User, task_id: int, decision: str, comment: str = "", at: datetime | None = None) -> ApprovalTask:
    at = at or utcnow()
    task = db.get(ApprovalTask, task_id)
    if not task:
        raise NotFound("Approval task not found.")
    req = task.request
    if not user.has_role(task.role_code):
        raise Forbidden(f"This task requires the {task.role_code.replace('_', ' ').title()} role.")
    if req.requester_id == user.id:
        raise Forbidden("Segregation of duties: you cannot approve your own request.")
    if task.status != "PENDING" or req.status != "PENDING_APPROVAL" or task.cycle != req.cycle:
        raise Conflict("This task has already been decided or is not yet active.")
    comment = (comment or "").strip()
    if decision in ("REJECT", "REQUEST_CHANGES") and len(comment) < 5:
        raise ValidationFailed("A reason is required to reject or request changes.")

    task.status = {"APPROVE": "APPROVED", "REJECT": "REJECTED", "REQUEST_CHANGES": "CHANGES_REQUESTED"}[decision]
    task.decided_at = at
    task.decided_by_id = user.id
    try:
        db.flush()  # optimistic version check guards against double submission
    except StaleDataError:
        db.rollback()
        raise Conflict("This task was updated by someone else. Refresh and try again.")
    db.add(ApprovalDecision(task_id=task.id, request_id=req.id, decision=decision, comment=comment, actor_id=user.id, created_at=at))
    audit.record(db, f"TASK_{task.status}", request_id=req.id, actor_id=user.id, from_status=req.status, to_status=req.status,
                 comment=f"{task.step_name}: {comment}" if comment else task.step_name, entity_ref=req.request_number, at=at)

    tasks = current_tasks(db, req)
    if decision in ("REJECT", "REQUEST_CHANGES"):
        for t in tasks:
            if t.status in OPEN_TASK:
                t.status = "CANCELLED"
        if decision == "REJECT":
            transition(db, req, "REJECTED", user.id, comment, event_type="REQUEST_REJECTED", at=at)
            notifications.notify(db, [req.requester], "REQUEST_REJECTED", f"{req.request_number} was not approved",
                                 f"{user.full_name} ({task.step_name}): {comment}", request_id=req.id, link=f"/mdm/requests/{req.id}", at=at)
        else:
            transition(db, req, "NEEDS_CHANGES", user.id, comment, event_type="RETURNED_FOR_CHANGES", at=at)
            notifications.notify(db, [req.requester], "RETURNED_FOR_CHANGES", f"Please update {req.request_number}",
                                 f"{user.full_name} ({task.step_name}): {comment}", request_id=req.id, link=f"/mdm/new?edit={req.id}", at=at)
        return task

    stage_open = [t for t in tasks if t.stage_order == task.stage_order and t.status != "APPROVED"]
    if stage_open:
        return task  # parallel stage still waiting on other approvers
    later = sorted({t.stage_order for t in tasks if t.status == "WAITING"})
    if later:
        _activate(db, req, [t for t in tasks if t.stage_order == later[0]], at)
        audit.record(db, "STAGE_ADVANCED", request_id=req.id, from_status=req.status, to_status=req.status,
                     comment=f"Stage {task.stage_order} complete; stage {later[0]} activated", entity_ref=req.request_number, at=at)
        return task
    req.approved_at = at
    transition(db, req, "APPROVED", None, "All mandatory approvals received", at=at)
    transition(db, req, "MDM_VERIFICATION", None, "Queued for MDM final verification", at=at)
    notifications.notify(db, [req.requester], "APPROVAL_COMPLETED", f"{req.request_number} is approved",
                         "Everyone has approved it. The Master Data team will do a final check and set it up in SAP.", request_id=req.id,
                         link=f"/mdm/requests/{req.id}", at=at)
    _notify_mdm(db, req, at)
    return task


def mdm_verify(db: Session, user: User, req: MdmRequest, action: str, comment: str = "", at: datetime | None = None) -> MdmRequest:
    at = at or utcnow()
    if not user.has_role(roles.MDM_ANALYST):
        raise Forbidden("Only MDM analysts can perform final verification.")
    if req.status != "MDM_VERIFICATION":
        raise Conflict("Request is not awaiting MDM verification.")
    if req.requester_id == user.id:
        raise Forbidden("Segregation of duties: you cannot verify your own request.")
    if action == "VERIFY":
        transition(db, req, "SAP_PENDING", user.id, comment or "Final verification passed", event_type="MDM_VERIFIED", at=at)
    elif action == "RETURN":
        if len((comment or "").strip()) < 5:
            raise ValidationFailed("Explain what the requestor needs to change.")
        transition(db, req, "NEEDS_CHANGES", user.id, comment, event_type="RETURNED_FOR_CHANGES", at=at)
        notifications.notify(db, [req.requester], "RETURNED_FOR_CHANGES", f"Please update {req.request_number}", comment,
                             request_id=req.id, link=f"/mdm/new?edit={req.id}", at=at)
    else:
        raise ValidationFailed("Unknown verification action.")
    return req


# ---------------------------------------------------------------- SLA monitoring & escalation

def run_sla_checks(db: Session, now: datetime | None = None) -> dict:
    """Deterministic and idempotent: each task gets at most one reminder and one escalation."""
    now = now or utcnow()
    grace = float(settings_service.get(db, "sla.escalate_after_overdue_days"))
    reminded = escalated = 0
    tasks = db.execute(select(ApprovalTask).where(ApprovalTask.status == "PENDING", ApprovalTask.due_at.is_not(None))).scalars().all()
    for t in tasks:
        req = t.request
        if t.due_at <= now and t.reminder_sent_at is None:
            t.reminder_sent_at = now
            reminded += 1
            notifications.notify(db, notifications.users_with_role(db, t.role_code), "SLA_REMINDER",
                                 f"Late: {req.request_number} · {t.step_name}",
                                 f"This was due on {t.due_at:%d %b}. {req.requester.full_name} is waiting.", request_id=req.id,
                                 link=f"/flow/inbox?request={req.id}", at=now)
            audit.record(db, "SLA_REMINDER", request_id=req.id, from_status=req.status, to_status=req.status,
                         comment=f"Reminder sent for {t.step_name}", entity_ref=req.request_number, at=now)
        escalate_at = add_working_days(t.due_at, grace, _country_tz(db, req.country_code))
        if escalate_at <= now and t.escalated_at is None:
            t.escalated_at = now
            escalated += 1
            target = roles.ADMIN if t.role_code == roles.BU_HEAD else roles.BU_HEAD
            notifications.notify(db, notifications.users_with_role(db, target), "ESCALATION",
                                 f"Needs attention: {req.request_number} is late at {t.step_name}",
                                 f"Waiting since {t.activated_at:%d %b}. Please follow up or pass it to someone else.", request_id=req.id,
                                 link=f"/flow/tracker?request={req.id}", at=now)
            audit.record(db, "ESCALATED", request_id=req.id, from_status=req.status, to_status=req.status,
                         comment=f"{t.step_name} escalated to {target.replace('_', ' ').title()}", entity_ref=req.request_number, at=now)
    db.flush()
    return {"reminders_sent": reminded, "escalations": escalated, "checked": len(tasks), "run_at": now.isoformat()}


def task_sla_state(t: ApprovalTask, now: datetime | None = None) -> str:
    now = now or utcnow()
    if t.status != "PENDING" or not t.due_at:
        return "N/A"
    if t.due_at < now:
        return "OVERDUE"
    if t.due_at - now < timedelta(hours=24):
        return "DUE_SOON"
    return "ON_TRACK"


def turnaround_metrics(db: Session) -> dict:
    done = db.execute(select(MdmRequest).where(MdmRequest.status == "SAP_COMPLETED", MdmRequest.submitted_at.is_not(None))).scalars().all()
    tat = sorted(working_days_between(r.submitted_at, r.completed_at) for r in done if r.completed_at)
    tasks = db.execute(select(ApprovalTask).where(ApprovalTask.decided_at.is_not(None), ApprovalTask.activated_at.is_not(None))).scalars().all()
    handling = sorted(working_days_between(t.activated_at, t.decided_at) for t in tasks)

    def pct(xs, p):
        if not xs:
            return None
        k = (len(xs) - 1) * p
        lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
        return round(xs[lo] + (xs[hi] - xs[lo]) * (k - lo), 2)

    return {
        "completed_requests": len(tat),
        "median_turnaround_days": round(median(tat), 2) if tat else None,
        "p90_turnaround_days": pct(tat, 0.9),
        "median_approval_handling_days": round(median(handling), 2) if handling else None,
        "p90_approval_handling_days": pct(handling, 0.9),
        "decided_tasks": len(handling),
        "unit": "working days (Mon–Fri, country-local; public holidays not modelled)",
    }


def attachment_count(db: Session, req: MdmRequest) -> int:
    return db.query(RequestAttachment).filter(RequestAttachment.request_id == req.id).count()


def reuse_count(db: Session) -> int:
    return db.query(DuplicateReview).filter(DuplicateReview.decision == "REUSE_EXISTING").count()


def master_record(db: Session, record_id: int) -> MasterRecord:
    mr = db.get(MasterRecord, record_id)
    if not mr:
        raise NotFound("Master record not found.")
    return mr
