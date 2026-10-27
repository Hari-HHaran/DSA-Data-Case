"""SAP B1 integration: sync jobs, persistent record mappings, integration logs."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from ._common import created_at_col, updated_at_col


class SapSyncJob(Base):
    __tablename__ = "sap_sync_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("mdm_requests.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(80), unique=True)
    operation: Mapped[str] = mapped_column(String(40))  # e.g. CREATE_BUSINESS_PARTNER
    sap_object_type: Mapped[str] = mapped_column(String(40))
    adapter_mode: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))  # PENDING | SUCCESS | FAILED
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sap_key: Mapped[str | None] = mapped_column(String(40), nullable=True)
    triggered_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class SapRecordMapping(Base):
    __tablename__ = "sap_record_mappings"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("mdm_requests.id"), unique=True)
    master_record_id: Mapped[int] = mapped_column(ForeignKey("master_records.id"))
    sap_object_type: Mapped[str] = mapped_column(String(40))
    sap_key: Mapped[str] = mapped_column(String(40), unique=True)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = created_at_col()


class IntegrationEventLog(Base):
    __tablename__ = "integration_event_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("sap_sync_jobs.id"), nullable=True, index=True)
    system: Mapped[str] = mapped_column(String(20))  # SAP_B1 | M365
    level: Mapped[str] = mapped_column(String(10))  # INFO | WARN | ERROR
    message: Mapped[str] = mapped_column(Text)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = created_at_col()
