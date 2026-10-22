"""MDM request state machine. Every status change goes through `transition`, which also audits it."""
from sqlalchemy.orm import Session

from ..models import MdmRequest
from . import audit
from .errors import Conflict

TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"SUBMITTED", "CANCELLED"},
    "SUBMITTED": {"VALIDATION_COMPLETED"},
    "VALIDATION_COMPLETED": {"PENDING_APPROVAL", "MDM_VERIFICATION"},
    "PENDING_APPROVAL": {"APPROVED", "REJECTED", "NEEDS_CHANGES"},
    "APPROVED": {"MDM_VERIFICATION"},
    "MDM_VERIFICATION": {"SAP_PENDING", "NEEDS_CHANGES", "REJECTED"},
    "NEEDS_CHANGES": {"SUBMITTED", "CANCELLED"},
    "SAP_PENDING": {"SAP_COMPLETED", "SAP_FAILED"},
    "SAP_FAILED": {"SAP_PENDING", "SAP_COMPLETED"},  # retry, or manual resolution with a recorded SAP key
    "SAP_COMPLETED": set(),
    "REJECTED": set(),
    "CANCELLED": set(),
}

STATUS_LABELS = {
    "DRAFT": "Draft", "SUBMITTED": "Submitted", "VALIDATION_COMPLETED": "Validation completed",
    "PENDING_APPROVAL": "Pending approval", "NEEDS_CHANGES": "Needs changes", "REJECTED": "Rejected",
    "APPROVED": "Approved", "MDM_VERIFICATION": "MDM verification", "SAP_PENDING": "SAP creation pending",
    "SAP_COMPLETED": "SAP creation completed", "SAP_FAILED": "SAP creation failed", "CANCELLED": "Cancelled",
}

# The "happy path" used by the tracker timeline.
MAIN_PATH = ["DRAFT", "SUBMITTED", "VALIDATION_COMPLETED", "PENDING_APPROVAL", "APPROVED",
             "MDM_VERIFICATION", "SAP_PENDING", "SAP_COMPLETED"]
TERMINAL = {"SAP_COMPLETED", "REJECTED", "CANCELLED"}
EDITABLE = {"DRAFT", "NEEDS_CHANGES"}


def can_transition(src: str, dst: str) -> bool:
    return dst in TRANSITIONS.get(src, set())


def transition(db: Session, req: MdmRequest, dst: str, actor_id: int | None, comment: str = "",
               event_type: str | None = None, changes: dict | None = None, at=None) -> None:
    src = req.status
    if not can_transition(src, dst):
        raise Conflict(f"Request {req.request_number} cannot move from {STATUS_LABELS[src]} to {STATUS_LABELS[dst]}.")
    req.status = dst
    audit.record(db, event_type or f"STATUS_{dst}", request_id=req.id, actor_id=actor_id, from_status=src,
                 to_status=dst, comment=comment, changes=changes, entity_ref=req.request_number, at=at)
