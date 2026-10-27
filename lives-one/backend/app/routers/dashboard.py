"""Executive Command Centre: one call that joins all three pillars, shaped by the viewer's role."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import (
    ApprovalTask, CommercialOpportunity, DuplicateCandidate, DuplicateReview, MasterRecord, MdmRequest, SalesFollowup,
    SapRecordMapping, SapSyncJob, User, WorkflowEvent,
)
from ..serializers import event_out, request_summary, task_out
from ..services import analytics, forecasting, roles, workflow
from ..services.clock import utcnow

router = APIRouter(prefix="/api", tags=["command-centre"])
OPEN = ("SUBMITTED", "VALIDATION_COMPLETED", "PENDING_APPROVAL", "APPROVED", "MDM_VERIFICATION", "SAP_PENDING", "SAP_FAILED", "NEEDS_CHANGES")


def operational(db: Session) -> dict:
    now = utcnow()
    pending = db.execute(select(ApprovalTask).where(ApprovalTask.status == "PENDING")).scalars().all()
    submitted = db.execute(select(func.count(MdmRequest.id)).where(MdmRequest.submitted_at.is_not(None))).scalar() or 0
    with_dupes = db.execute(select(func.count(func.distinct(DuplicateCandidate.request_id)))).scalar() or 0
    checked = db.execute(select(func.count(MdmRequest.id)).where(MdmRequest.duplicate_check_status != "NOT_RUN")).scalar() or 0
    blocked = db.execute(select(func.count(WorkflowEvent.id)).where(WorkflowEvent.event_type == "SUBMISSION_BLOCKED")).scalar() or 0
    return {
        "open_requests": db.execute(select(func.count(MdmRequest.id)).where(MdmRequest.status.in_(OPEN))).scalar(),
        "awaiting_approval": db.execute(select(func.count(MdmRequest.id)).where(MdmRequest.status == "PENDING_APPROVAL")).scalar(),
        "overdue_approvals": sum(1 for t in pending if workflow.task_sla_state(t, now) == "OVERDUE"),
        "awaiting_mdm": db.execute(select(func.count(MdmRequest.id)).where(MdmRequest.status == "MDM_VERIFICATION")).scalar(),
        "sap_success": db.execute(select(func.count(SapRecordMapping.id))).scalar(),
        "sap_failed_open": db.execute(select(func.count(MdmRequest.id)).where(MdmRequest.status == "SAP_FAILED")).scalar(),
        "duplicates_prevented": workflow.reuse_count(db),
        "duplicate_flags": with_dupes,
        "potential_duplicate_rate": round(with_dupes / checked, 3) if checked else None,
        "flagged_for_review": db.execute(select(func.count(MdmRequest.id)).where(MdmRequest.flagged_for_review.is_(True), MdmRequest.status.in_(OPEN))).scalar(),
        "submissions_blocked_by_validation": blocked,
        "submitted_requests": submitted,
        "first_pass_validation_rate": round(submitted / (submitted + blocked), 3) if submitted + blocked else None,
        "master_records": db.execute(select(func.count(MasterRecord.id))).scalar(),
        "status_counts": dict(db.execute(select(MdmRequest.status, func.count()).group_by(MdmRequest.status)).all()),
        **workflow.turnaround_metrics(db),
    }


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Personal home page data. Each block is only sent to the people it concerns."""
    oversight = user.has_role(*roles.REQUEST_OVERSIGHT_ROLES)  # MDM analyst, admin, executive
    out = {"user_roles": user.role_codes, "synthetic": True}
    # Process-wide numbers are for the people who run or oversee the process, not for every user.
    if oversight:
        out["operational"] = operational(db)
    if user.has_role(*roles.ANALYTICS_ROLES):
        ov = analytics.overview(db, {})
        run = forecasting.latest(db)
        out["regional"] = {"kpis": ov["kpis"], "ranking": ov["ranking"], "matrix": ov["matrix"], "window": ov["window"],
                           "trend": ov["trend"], "countries": ov["countries"], "forecast": forecasting.summary(db, run) if run else None}
    # Opportunities only for the roles that can open the opportunities workspace.
    if user.has_role(roles.SALES, roles.EXECUTIVE, roles.ADMIN, roles.MDM_ANALYST):
        live = (CommercialOpportunity.is_stale.is_(False),)
        scope = "all"
        if not oversight:  # a salesperson sees what they own or what sits in their own country
            scope = "mine"
            live += ((CommercialOpportunity.owner_id == user.id) | (CommercialOpportunity.country_code == user.country_code),)
        out["opportunities"] = {
            "scope": scope,
            "open": db.execute(select(func.count(CommercialOpportunity.id)).where(CommercialOpportunity.status.in_(["NEW", "UNDER_REVIEW", "ASSIGNED", "IN_PROGRESS"]), *live)).scalar(),
            "high": db.execute(select(func.count(CommercialOpportunity.id)).where(CommercialOpportunity.priority_label == "HIGH",
                                                                                 CommercialOpportunity.status == "NEW", *live)).scalar(),
            "top": [{"id": o.id, "title": o.title, "category": o.category, "priority": o.priority_label, "insight": o.insight, "country_code": o.country_code}
                    for o in db.execute(select(CommercialOpportunity).where(CommercialOpportunity.status == "NEW", *live)
                                        .order_by(CommercialOpportunity.priority_score.desc()).limit(6)).scalars()],
            "followups_open": db.execute(select(func.count(SalesFollowup.id)).where(SalesFollowup.status != "DONE")).scalar(),
        }
    mine = db.execute(select(MdmRequest).where(MdmRequest.requester_id == user.id).order_by(MdmRequest.updated_at.desc()).limit(6)).scalars().all()
    out["my_requests"] = [request_summary(r) for r in mine]
    out["my_request_counts"] = dict(db.execute(select(MdmRequest.status, func.count()).where(MdmRequest.requester_id == user.id)
                                               .group_by(MdmRequest.status)).all())
    approver_roles = [r for r in user.role_codes if r in roles.APPROVER_ROLES]
    if approver_roles:
        tasks = db.execute(select(ApprovalTask).where(ApprovalTask.role_code.in_(approver_roles), ApprovalTask.status == "PENDING")
                           .order_by(ApprovalTask.due_at)).scalars().all()
        now = utcnow()
        states = [workflow.task_sla_state(t, now) for t in tasks]
        out["my_tasks"] = [{**task_out(t), "request": request_summary(t.request)} for t in tasks[:8]]
        out["my_task_counts"] = {"pending": len(tasks), "overdue": states.count("OVERDUE"), "due_soon": states.count("DUE_SOON"),
                                 "on_track": states.count("ON_TRACK"),
                                 "decided": db.execute(select(func.count(ApprovalTask.id)).where(ApprovalTask.decided_by_id == user.id)).scalar()}
    if user.has_role(roles.MDM_ANALYST):
        q = db.execute(select(MdmRequest).where(MdmRequest.status.in_(["MDM_VERIFICATION", "SAP_PENDING", "SAP_FAILED"]))
                       .order_by(MdmRequest.updated_at)).scalars().all()
        out["mdm_queue"] = [request_summary(r) for r in q]
    feed = select(WorkflowEvent).where(WorkflowEvent.event_type.in_([
        "STATUS_SUBMITTED", "TASK_APPROVED", "TASK_REJECTED", "TASK_CHANGES_REQUESTED", "SAP_CREATION_COMPLETED", "SAP_CREATION_FAILED",
        "DUPLICATE_PREVENTED", "FOLLOWUP_ASSIGNED", "MAPPING_CONFIRMED", "ESCALATED"]))
    if not oversight:  # everyone else only sees updates on requests they raised or acted on
        own = select(MdmRequest.id).where(MdmRequest.requester_id == user.id)
        feed = feed.where((WorkflowEvent.request_id.in_(own)) | (WorkflowEvent.actor_id == user.id))
    out["activity_scope"] = "all" if oversight else "mine"
    out["activity"] = [event_out(e) for e in db.execute(feed.order_by(WorkflowEvent.created_at.desc(), WorkflowEvent.id.desc()).limit(10)).scalars()]
    return out
