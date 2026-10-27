"""Smart MDM: master records, aliases, canonical mappings, requests, attachments, duplicates."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from ._common import created_at_col, updated_at_col

DOMAINS = ("CUSTOMER", "VENDOR", "ITEM", "COST_CENTER")


class MasterRecord(Base):
    """A verified master record (golden/canonical record) as it exists, or will exist, in SAP B1."""
    __tablename__ = "master_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    record_code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    domain: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(200))
    normalized_name: Mapped[str] = mapped_column(String(200), index=True)
    country_code: Mapped[str | None] = mapped_column(ForeignKey("countries.code"), nullable=True)
    entity_code: Mapped[str | None] = mapped_column(ForeignKey("business_entities.code"), nullable=True)
    identifier: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    source: Mapped[str] = mapped_column(String(40), default="SYNTHETIC_SEED")
    sap_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_from_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("mdm_requests.id", use_alter=True, name="fk_master_records_created_from_request"), nullable=True)
    created_at: Mapped[datetime] = created_at_col()

    aliases: Mapped[list["MasterRecordAlias"]] = relationship(back_populates="master_record", cascade="all, delete-orphan")


class MasterRecordAlias(Base):
    __tablename__ = "master_record_aliases"
    id: Mapped[int] = mapped_column(primary_key=True)
    master_record_id: Mapped[int] = mapped_column(ForeignKey("master_records.id", ondelete="CASCADE"), index=True)
    alias_name: Mapped[str] = mapped_column(String(200))
    source_system: Mapped[str] = mapped_column(String(40))
    source_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = created_at_col()

    master_record: Mapped[MasterRecord] = relationship(back_populates="aliases")


class CanonicalRecordMapping(Base):
    """Maps a source-system customer record onto a verified canonical master record.

    Rows are never overwritten: a remap retires the old row (is_current=False) and adds a new one,
    so mapping history is preserved and historical transactions are never rewritten.
    """
    __tablename__ = "canonical_record_mappings"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    master_record_id: Mapped[int] = mapped_column(ForeignKey("master_records.id"), index=True)
    alias_name: Mapped[str] = mapped_column(String(200))
    confidence: Mapped[float] = mapped_column(Float)
    method: Mapped[str] = mapped_column(String(40))  # EXACT_ID | FUZZY_NAME | MANUAL
    review_status: Mapped[str] = mapped_column(String(20), default="PROPOSED")  # PROPOSED | CONFIRMED | REJECTED
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = created_at_col()

    master_record: Mapped[MasterRecord] = relationship()
    source_customer: Mapped["Customer"] = relationship()  # noqa: F821


class MdmRequest(Base):
    __tablename__ = "mdm_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_number: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    domain: Mapped[str] = mapped_column(String(20), index=True)
    request_type: Mapped[str] = mapped_column(String(20), default="CREATE")
    title: Mapped[str] = mapped_column(String(200), default="")
    entity_code: Mapped[str | None] = mapped_column(ForeignKey("business_entities.code"), nullable=True)
    country_code: Mapped[str | None] = mapped_column(ForeignKey("countries.code"), nullable=True)
    department: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", index=True)
    priority: Mapped[str] = mapped_column(String(10), default="NORMAL")
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    flagged_for_review: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_check_status: Mapped[str] = mapped_column(String(20), default="NOT_RUN")  # NOT_RUN | CLEAR | REVIEW_REQUIRED | RESOLVED | BLOCKED
    form_version: Mapped[int] = mapped_column(Integer, default=1)
    workflow_template_id: Mapped[int | None] = mapped_column(ForeignKey("workflow_templates.id"), nullable=True)
    cycle: Mapped[int] = mapped_column(Integer, default=0)
    resolution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cloned_from_id: Mapped[int | None] = mapped_column(ForeignKey("mdm_requests.id"), nullable=True)
    reused_record_id: Mapped[int | None] = mapped_column(ForeignKey("master_records.id"), nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    requester: Mapped["User"] = relationship(foreign_keys=[requester_id], lazy="joined")  # noqa: F821
    fields: Mapped[list["MdmRequestField"]] = relationship(back_populates="request", cascade="all, delete-orphan", lazy="selectin")
    attachments: Mapped[list["RequestAttachment"]] = relationship(back_populates="request", cascade="all, delete-orphan", lazy="selectin")

    @property
    def data(self) -> dict:
        return {f.field_key: f.value for f in self.fields}

    def set_data(self, values: dict) -> dict:
        """Replace field values; returns {key: (old, new)} for the changed-field audit summary."""
        current = {f.field_key: f for f in self.fields}
        changes = {}
        for key, value in values.items():
            value = None if value is None else str(value).strip()
            if value == "":
                value = None
            row = current.get(key)
            old = row.value if row else None
            if old == value:
                continue
            changes[key] = (old, value)
            if row:
                row.value = value
            else:
                self.fields.append(MdmRequestField(field_key=key, value=value))
        return changes


class MdmRequestField(Base):
    __tablename__ = "mdm_request_fields"
    __table_args__ = (UniqueConstraint("request_id", "field_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("mdm_requests.id", ondelete="CASCADE"), index=True)
    field_key: Mapped[str] = mapped_column(String(60))
    value: Mapped[str | None] = mapped_column(Text, nullable=True)

    request: Mapped[MdmRequest] = relationship(back_populates="fields")


class RequestAttachment(Base):
    __tablename__ = "request_attachments"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("mdm_requests.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(40))
    original_filename: Mapped[str] = mapped_column(String(200))
    stored_filename: Mapped[str] = mapped_column(String(80))
    content_type: Mapped[str] = mapped_column(String(80))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = created_at_col()

    request: Mapped[MdmRequest] = relationship(back_populates="attachments")


class DuplicateCandidate(Base):
    __tablename__ = "duplicate_candidates"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("mdm_requests.id", ondelete="CASCADE"), index=True)
    master_record_id: Mapped[int | None] = mapped_column(ForeignKey("master_records.id"), nullable=True)
    other_request_id: Mapped[int | None] = mapped_column(ForeignKey("mdm_requests.id"), nullable=True)
    score: Mapped[float] = mapped_column(Float)
    band: Mapped[str] = mapped_column(String(20))  # LIKELY_DUPLICATE | NEEDS_REVIEW
    exact_identifier_match: Mapped[bool] = mapped_column(Boolean, default=False)
    matched_fields: Mapped[list] = mapped_column(JSON, default=list)
    explanation: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = created_at_col()

    master_record: Mapped[MasterRecord | None] = relationship(lazy="joined")


class DuplicateReview(Base):
    __tablename__ = "duplicate_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("mdm_requests.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[int | None] = mapped_column(ForeignKey("duplicate_candidates.id", ondelete="SET NULL"), nullable=True)
    decision: Mapped[str] = mapped_column(String(30))  # NOT_DUPLICATE | CONTINUE_WITH_JUSTIFICATION | REUSE_EXISTING | FLAG_FOR_REVIEW
    justification: Mapped[str] = mapped_column(Text, default="")
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_at_col()
