"""Orchestrates SAP creation for verified requests: payload validation, idempotent submission,
persisted job status, record mapping, failure logging and safe retry."""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import IntegrationEventLog, MasterRecord, MasterRecordAlias, MdmRequest, SapRecordMapping, SapSyncJob, User
from . import audit, notifications, roles, settings_service
from .clock import utcnow
from .duplicates import normalise
from .errors import Conflict, Forbidden, ValidationFailed
from .forms import DOMAIN_KEYS
from .sap_adapter import OBJECT_TYPES, SapAdapterError, build_payload, get_adapter, validate_payload
from .state_machine import transition

RECORD_PREFIX = {"CUSTOMER": "CUST", "VENDOR": "VEND", "ITEM": "ITEM", "COST_CENTER": "CC"}


def _log(db: Session, job: SapSyncJob | None, level: str, message: str, detail: dict | None = None, at=None):
    db.add(IntegrationEventLog(job_id=job.id if job else None, system="SAP_B1", level=level, message=message,
                               detail=detail, created_at=at or utcnow()))


def _next_record_code(db: Session, domain: str) -> str:
    n = db.execute(select(func.count(MasterRecord.id)).where(MasterRecord.domain == domain)).scalar() or 0
    while True:
        n += 1
        code = f"{RECORD_PREFIX[domain]}-{n:06d}"
        if not db.execute(select(MasterRecord.id).where(MasterRecord.record_code == code)).scalar():
            return code


def sync(db: Session, user: User, req: MdmRequest, at: datetime | None = None) -> SapSyncJob:
    at = at or utcnow()
    if not user.has_role(roles.MDM_ANALYST):
        raise Forbidden("Only MDM analysts can submit records to SAP B1.")
    existing = db.execute(select(SapRecordMapping).where(SapRecordMapping.request_id == req.id)).scalar_one_or_none()
    if existing:
        # Idempotent: a repeat call never creates a second SAP record.
        return db.execute(select(SapSyncJob).where(SapSyncJob.request_id == req.id).order_by(SapSyncJob.id.desc())).scalars().first()
    if req.status not in ("SAP_PENDING", "SAP_FAILED"):
        raise Conflict("Only verified requests can be submitted to SAP B1.")

    operation, obj = OBJECT_TYPES[req.domain]
    payload = build_payload(req.domain, req.data, req.entity_code, req.country_code)
    problems = validate_payload(req.domain, payload)
    if problems:
        raise ValidationFailed("SAP payload validation failed.", {"problems": problems})

    key = f"REQ-{req.id}-CYCLE-{req.cycle}"
    job = db.execute(select(SapSyncJob).where(SapSyncJob.idempotency_key == key)).scalar_one_or_none()
    mode = get_settings().sap_adapter
    if job is None:
        job = SapSyncJob(request_id=req.id, idempotency_key=key, operation=operation, sap_object_type=obj, adapter_mode=mode,
                         status="PENDING", payload=payload, triggered_by_id=user.id, created_at=at, updated_at=at)
        db.add(job)
        db.flush()
    if req.status == "SAP_FAILED":
        transition(db, req, "SAP_PENDING", user.id, "Retrying SAP creation", event_type="SAP_RETRY", at=at)
    job.attempt_count += 1
    job.status = "PENDING"
    _log(db, job, "INFO", f"Attempt {job.attempt_count}: submitting {operation} for {req.request_number}", {"payload_keys": sorted(payload)}, at)

    fail_next = int(settings_service.get(db, "sap.mock_fail_next") or 0)
    try:
        seq = (db.execute(select(func.count(SapRecordMapping.id))).scalar() or 0) + 1001
        result = get_adapter(mode).create(req.domain, payload, key, seq, fail=fail_next > 0 and mode == "mock")
    except SapAdapterError as exc:
        if fail_next > 0:
            settings_service.set_value(db, "sap.mock_fail_next", fail_next - 1)
        job.status = "FAILED"
        job.error_message = str(exc)
        job.updated_at = at
        _log(db, job, "ERROR", str(exc), {"code": exc.code, "retryable": exc.retryable}, at)
        transition(db, req, "SAP_FAILED", user.id, str(exc), event_type="SAP_CREATION_FAILED", at=at)
        notifications.notify(db, notifications.users_with_role(db, roles.MDM_ANALYST), "SAP_FAILED",
                             f"SAP creation failed: {req.request_number}", f"{exc} Retry or resolve manually.",
                             request_id=req.id, link=f"/mdm/requests/{req.id}", at=at)
        db.flush()
        return job

    _complete(db, user, req, job, result.sap_key, result.object_type, result.raw, is_mock=True, at=at)
    return job


def _complete(db: Session, user: User, req: MdmRequest, job: SapSyncJob, sap_key: str, obj: str, raw: dict, is_mock: bool, at: datetime,
              comment: str | None = None):
    data = req.data
    keys = DOMAIN_KEYS[req.domain]
    mr = MasterRecord(
        record_code=_next_record_code(db, req.domain), domain=req.domain, name=data.get(keys["name"]) or req.title,
        normalized_name=normalise(data.get(keys["name"])), country_code=req.country_code, entity_code=req.entity_code,
        identifier=data.get(keys["identifier"]), status="ACTIVE", source="LIVES_ONE", sap_code=sap_key, created_from_request_id=req.id,
        attributes={k: v for k, v in data.items() if k in ("manufacturer", "unit_of_measure", "product_family", "regulatory_class",
                                                          "customer_segment", "supplier_category", "department")}
        | {"address": data.get(keys.get("address", "")) if keys.get("address") else None}, created_at=at,
    )
    db.add(mr)
    db.flush()
    if keys.get("alt_name") and data.get(keys["alt_name"]):
        db.add(MasterRecordAlias(master_record_id=mr.id, alias_name=data[keys["alt_name"]], source_system="TRADING_NAME"))
    db.add(SapRecordMapping(request_id=req.id, master_record_id=mr.id, sap_object_type=obj, sap_key=sap_key, is_mock=is_mock, created_at=at))
    job.status = "SUCCESS"
    job.sap_key = sap_key
    job.response = raw
    job.error_message = None
    job.updated_at = at
    _log(db, job, "INFO", f"{'Simulated ' if is_mock else ''}SAP B1 {obj} created: {sap_key}", raw, at)
    req.completed_at = at
    transition(db, req, "SAP_COMPLETED", user.id, comment or f"{'Mock ' if is_mock else ''}SAP B1 {obj} key {sap_key}; master record {mr.record_code}",
               event_type="SAP_CREATION_COMPLETED", changes={"sap_key": sap_key, "master_record": mr.record_code, "mock": is_mock}, at=at)
    notifications.notify(db, [req.requester], "SAP_CREATED", f"{req.request_number} is live: {sap_key}",
                         f"{req.title} was created in SAP B1 ({'simulated' if is_mock else 'manual entry'}). You can now transact on it.",
                         request_id=req.id, link=f"/mdm/requests/{req.id}", at=at)
    db.flush()


def manual_resolve(db: Session, user: User, req: MdmRequest, sap_key: str, comment: str) -> SapSyncJob:
    if not user.has_role(roles.MDM_ANALYST):
        raise Forbidden("Only MDM analysts can resolve SAP failures.")
    if req.status != "SAP_FAILED":
        raise Conflict("Manual resolution is only available after a failed SAP creation.")
    sap_key = (sap_key or "").strip()
    if not sap_key or len((comment or "").strip()) < 5:
        raise ValidationFailed("Provide the SAP key keyed manually and a short note.")
    if db.execute(select(SapRecordMapping).where(SapRecordMapping.sap_key == sap_key)).scalar():
        raise Conflict("That SAP key is already mapped to another request.")
    job = db.execute(select(SapSyncJob).where(SapSyncJob.request_id == req.id).order_by(SapSyncJob.id.desc())).scalars().first()
    at = utcnow()
    _complete(db, user, req, job, sap_key, job.sap_object_type, {"manual": True, "note": comment}, is_mock=False, at=at,
              comment=f"Manually resolved by MDM: SAP key {sap_key}. {comment}")
    return job
