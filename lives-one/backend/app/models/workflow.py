"""Flow Engine: templates, steps (approval rules), tasks, decisions, audit events, notifications."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from ._common import created_at_col, updated_at_col


class WorkflowTemplate(Base):
    __tablename__ = "workflow_templates"
    id: Mapped[int] = mapped_column(primary_key=True)
    domain: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer, default=1)
    mdm_verification_sla_days: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = updated_at_col()

    steps: Mapped[list["WorkflowStep"]] = relationship(
        back_populates="template", cascade="all, delete-orphan", order_by="WorkflowStep.stage_order", lazy="selectin"
    )


class WorkflowStep(Base):
    """An approval rule: which role must approve, at which stage, under which condition.

    Steps sharing a stage_order run in parallel; stages run in ascending order (sequential).
    Ordinal stages make circular dependencies impossible by construction.
    """
    __tablename__ = "workflow_steps"
    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("workflow_templates.id", ondelete="CASCADE"), index=True)
    step_key: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    role_code: Mapped[str] = mapped_column(String(40))
    stage_order: Mapped[int] = mapped_column(Integer)
    condition: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    description: Mapped[str] = mapped_column(String(255), default="")
    sla_days: Mapped[int] = mapped_column(Integer, default=2)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    template: Mapped[WorkflowTemplate] = relationship(back_populates="steps")


class ApprovalTask(Base):
    __tablename__ = "approval_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("mdm_requests.id", ondelete="CASCADE"), index=True)
    step_id: Mapped[int | None] = mapped_column(ForeignKey("workflow_steps.id", ondelete="SET NULL"), nullable=True)
    step_name: Mapped[str] = mapped_column(String(120))
    role_code: Mapped[str] = mapped_column(String(40), index=True)
    stage_order: Mapped[int] = mapped_column(Integer)
    cycle: Mapped[int] = mapped_column(Integer, default=1)
    # WAITING (earlier stage open) | PENDING | APPROVED | REJECTED | CHANGES_REQUESTED | CANCELLED
    status: Mapped[str] = mapped_column(String(20), index=True)
    assigned_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    sla_days: Mapped[int] = mapped_column(Integer, default=2)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = created_at_col()

    __mapper_args__ = {"version_id_col": version}

    request: Mapped["MdmRequest"] = relationship(lazy="joined")  # noqa: F821
    assigned_user: Mapped["User | None"] = relationship(foreign_keys=[assigned_user_id], lazy="joined")  # noqa: F821
    decided_by: Mapped["User | None"] = relationship(foreign_keys=[decided_by_id], lazy="joined")  # noqa: F821


class ApprovalDecision(Base):
    __tablename__ = "approval_decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("approval_tasks.id", ondelete="CASCADE"), index=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("mdm_requests.id", ondelete="CASCADE"), index=True)
    decision: Mapped[str] = mapped_column(String(20))  # APPROVE | REJECT | REQUEST_CHANGES
    comment: Mapped[str] = mapped_column(Text, default="")
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_at_col()


class WorkflowEvent(Base):
    """Append-only, hash-chained application audit log (tamper-evident, not legally certified)."""
    __tablename__ = "workflow_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_uid: Mapped[str] = mapped_column(String(36), unique=True)
    request_id: Mapped[int | None] = mapped_column(ForeignKey("mdm_requests.id"), nullable=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(40), default="MDM_REQUEST")
    entity_ref: Mapped[str | None] = mapped_column(String(60), nullable=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    comment: Mapped[str] = mapped_column(Text, default="")
    changes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = created_at_col()
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))

    actor: Mapped["User | None"] = relationship(lazy="joined")  # noqa: F821


@event.listens_for(WorkflowEvent, "before_update")
def _block_audit_update(mapper, connection, target):
    raise PermissionError("Audit events are append-only and cannot be modified.")


@event.listens_for(WorkflowEvent, "before_delete")
def _block_audit_delete(mapper, connection, target):
    raise PermissionError("Audit events are append-only and cannot be deleted.")


class NotificationEvent(Base):
    __tablename__ = "notification_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20))  # IN_APP | MOCK_TEAMS | MOCK_OUTLOOK
    event_type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str | None] = mapped_column(String(200), nullable=True)
    request_id: Mapped[int | None] = mapped_column(ForeignKey("mdm_requests.id"), nullable=True)
    # IN_APP: DELIVERED. Mock channels: MOCK_QUEUED (never actually sent).
    delivery_status: Mapped[str] = mapped_column(String(20))
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = created_at_col()

    recipient: Mapped["User"] = relationship(lazy="joined")  # noqa: F821
