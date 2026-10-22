from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import IntegrationEventLog, MdmRequest, SapRecordMapping, SapSyncJob, User
from ..schemas import ManualResolveIn, SettingUpdate
from ..serializers import iso, request_detail
from ..services import roles, sap_service, settings_service, workflow

router = APIRouter(prefix="/api/sap", tags=["sap"])


@router.post("/sync/{request_id}")
def sync(request_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    req = workflow.get_request(db, request_id)
    job = sap_service.sync(db, user, req)
    db.commit()
    return {"job_status": job.status if job else None, "request": request_detail(db, user, req)}


@router.get("/sync/{request_id}")
def sync_status(request_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    req = workflow.get_request(db, request_id)
    workflow.assert_can_view(db, user, req)
    return request_detail(db, user, req)["sap"]


@router.post("/sync/{request_id}/manual-resolve")
def manual(request_id: int, body: ManualResolveIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    req = workflow.get_request(db, request_id)
    sap_service.manual_resolve(db, user, req, body.sap_key, body.comment)
    db.commit()
    return request_detail(db, user, req)


@router.get("/status")
def status(db: Session = Depends(get_db), _: User = Depends(require_roles(roles.ADMIN, roles.MDM_ANALYST, roles.EXECUTIVE))):
    by_status = dict(db.execute(select(SapSyncJob.status, func.count()).group_by(SapSyncJob.status)).all())
    jobs = db.execute(select(SapSyncJob).order_by(SapSyncJob.updated_at.desc()).limit(25)).scalars().all()
    logs = db.execute(select(IntegrationEventLog).order_by(IntegrationEventLog.id.desc()).limit(40)).scalars().all()
    reqs = {r.id: r for r in db.execute(select(MdmRequest).where(MdmRequest.id.in_([j.request_id for j in jobs]))).scalars()}
    return {
        "adapter_mode": get_settings().sap_adapter,
        "adapter_note": "Mock adapter: confirmations are simulated and keys are prefixed MOCK-. No SAP B1 system is called.",
        "mock_fail_next": settings_service.get(db, "sap.mock_fail_next"),
        "counts": by_status, "mapped_records": db.execute(select(func.count(SapRecordMapping.id))).scalar(),
        "awaiting_sync": db.execute(select(func.count(MdmRequest.id)).where(MdmRequest.status.in_(["SAP_PENDING", "SAP_FAILED"]))).scalar(),
        "jobs": [{"id": j.id, "request_id": j.request_id, "request_number": reqs[j.request_id].request_number if j.request_id in reqs else None,
                  "operation": j.operation, "object_type": j.sap_object_type, "status": j.status, "attempts": j.attempt_count,
                  "sap_key": j.sap_key, "error": j.error_message, "adapter_mode": j.adapter_mode, "idempotency_key": j.idempotency_key,
                  "updated_at": iso(j.updated_at)} for j in jobs],
        "logs": [{"id": l.id, "job_id": l.job_id, "level": l.level, "message": l.message, "created_at": iso(l.created_at)} for l in logs],
        "future_integration": [
            "Confirm SAP B1 version, deployment (on-premise/cloud) and Service Layer availability",
            "Company database, authentication (service account) and object permissions",
            "Field mapping per domain (BusinessPartners, Items, ProfitCenters) and user-defined fields",
            "Idempotency: write the LIVES ONE request number to a UDF and check it before create",
            "Error handling and reconciliation reports for records created outside LIVES ONE",
        ],
    }


@router.put("/mock-failure")
def set_mock_failure(body: SettingUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles(roles.ADMIN, roles.MDM_ANALYST))):
    settings_service.set_value(db, "sap.mock_fail_next", max(0, int(body.value)), user.id)
    db.commit()
    return {"mock_fail_next": int(body.value)}
