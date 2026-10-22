import hashlib
import mimetypes
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select, true
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import (
    ApprovalTask, CanonicalRecordMapping, Customer, MasterRecord, MdmRequest, RequestAttachment, User,
)
from ..schemas import DuplicateCheckIn, DuplicateReviewIn, RequestCreate, RequestUpdate, ValidateIn, VerifyIn, MappingReviewIn
from ..serializers import iso, request_detail, request_summary, user_brief
from ..services import analytics, audit, duplicates, roles, validation, workflow
from ..services.clock import utcnow
from ..services.errors import Conflict, Forbidden, ValidationFailed
from ..services.forms import DOMAIN_LABELS, get_form
from ..services.validation import ATTACHMENT_LABELS

router = APIRouter(prefix="/api", tags=["smart-mdm"])
ALLOWED_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".docx", ".xlsx", ".txt"}


def _clean(data: dict | None) -> dict:
    return {k: (None if v is None else str(v)) for k, v in (data or {}).items()}


@router.get("/mdm/forms/{domain}")
def form(domain: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    f = get_form(db, domain)
    return {"domain": f.domain, "name": f.name, "description": f.description, "version": f.version,
            "attachment_categories": ATTACHMENT_LABELS,
            "fields": [{"key": x.key, "label": x.label, "field_type": x.field_type, "section": x.section, "required": x.required,
                        "required_when": x.required_when, "visible_when": x.visible_when, "options": x.options, "pattern": x.pattern,
                        "pattern_message": x.pattern_message, "help_text": x.help_text, "sensitivity": x.sensitivity,
                        "is_identifier": x.is_identifier} for x in f.fields if x.is_active]}


@router.post("/mdm/validate")
def validate(body: ValidateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    dup_status = "NOT_RUN"
    attachments = body.attachments
    if body.request_id:
        req = workflow.get_request(db, body.request_id)
        workflow.assert_can_view(db, user, req)
        dup_status = req.duplicate_check_status
        attachments = [a.category for a in req.attachments]
    header = {"entity_code": body.entity_code, "country_code": body.country_code, "request_type": body.request_type, "department": body.department}
    data = _clean(body.data)
    result = validation.evaluate(db, body.domain, header, data, attachments, dup_status)
    result["route"] = workflow.preview_route(db, body.domain, header, data)
    return result


@router.post("/mdm/duplicate-check")
def duplicate_check(body: DuplicateCheckIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if body.request_id:
        req = workflow.get_request(db, body.request_id)
        rows = workflow.run_duplicate_check(db, user, req)
        db.commit()
        from ..serializers import candidate_out
        return {"status": req.duplicate_check_status, "candidates": [candidate_out(db, c) for c in rows]}
    if not body.domain:
        raise ValidationFailed("domain or request_id is required")
    values = _clean(body.data)
    values["country_code"] = body.country_code
    found = duplicates.find_candidates(db, body.domain, values)
    return {"status": "CLEAR" if not found else "REVIEW_REQUIRED", "candidates": [
        {**c, "suggested_action": duplicates.suggested_action(c)} for c in found]}


@router.get("/mdm/requests")
def list_requests(scope: str = "mine", status: str | None = None, domain: str | None = None, q: str | None = None,
                  page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = select(MdmRequest)
    if scope == "all":
        if not user.has_role(*roles.REQUEST_OVERSIGHT_ROLES, *roles.APPROVER_ROLES):
            raise Forbidden("You can only list your own requests.")
        if not user.has_role(*roles.REQUEST_OVERSIGHT_ROLES):
            mine = select(ApprovalTask.request_id).where(ApprovalTask.role_code.in_(user.role_codes))
            query = query.where(or_(MdmRequest.id.in_(mine), MdmRequest.requester_id == user.id))
    else:
        query = query.where(MdmRequest.requester_id == user.id)
    if status:
        query = query.where(MdmRequest.status.in_(status.split(",")))
    if domain:
        query = query.where(MdmRequest.domain == domain)
    if q:
        like = f"%{q.strip()}%"
        query = query.where(or_(MdmRequest.title.ilike(like), MdmRequest.request_number.ilike(like)))
    total = db.execute(select(func.count()).select_from(query.subquery())).scalar()
    rows = db.execute(query.order_by(MdmRequest.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)).scalars().all()
    items = []
    for r in rows:
        s = request_summary(r)
        tasks = workflow.current_tasks(db, r) if r.status == "PENDING_APPROVAL" else []
        s["pending_with"] = [{"step": t.step_name, "role": t.role_code, "sla_state": workflow.task_sla_state(t)} for t in tasks if t.status == "PENDING"]
        items.append(s)
    counts = dict(db.execute(select(MdmRequest.status, func.count()).where(
        MdmRequest.requester_id == user.id if scope != "all" else true()).group_by(MdmRequest.status)).all())
    return {"items": items, "total": total, "page": page, "page_size": page_size, "status_counts": counts}


@router.post("/mdm/requests", status_code=201)
def create_request(body: RequestCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    payload = body.model_dump()
    payload["data"] = _clean(body.data)
    req = workflow.create_draft(db, user, payload)
    db.commit()
    return request_detail(db, user, req)


@router.get("/mdm/requests/{request_id}")
def get_request(request_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    req = workflow.get_request(db, request_id)
    workflow.assert_can_view(db, user, req)
    out = request_detail(db, user, req)
    out["readiness"] = validation.evaluate_request(db, req) if req.status in ("DRAFT", "NEEDS_CHANGES") else None
    out["route_preview"] = workflow.preview_route(db, req.domain, {"entity_code": req.entity_code, "country_code": req.country_code,
                                                                  "request_type": req.request_type, "department": req.department}, req.data)
    return out


@router.patch("/mdm/requests/{request_id}")
def update_request(request_id: int, body: RequestUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    req = workflow.get_request(db, request_id)
    payload = body.model_dump(exclude_unset=True)
    if "data" in payload:
        payload["data"] = _clean(payload["data"])
    workflow.update_draft(db, user, req, payload)
    db.commit()
    out = request_detail(db, user, req)
    out["readiness"] = validation.evaluate_request(db, req)
    return out


@router.post("/mdm/requests/{request_id}/duplicate-review")
def duplicate_review(request_id: int, body: DuplicateReviewIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    req = workflow.get_request(db, request_id)
    workflow.review_duplicates(db, user, req, body.decision, body.justification, body.candidate_id)
    db.commit()
    return request_detail(db, user, req)


@router.post("/mdm/requests/{request_id}/submit")
def submit(request_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    req = workflow.get_request(db, request_id)
    result = workflow.submit(db, user, req)
    db.commit()
    return {"request": request_detail(db, user, req), "route": result["route"]}


@router.post("/mdm/requests/{request_id}/clone", status_code=201)
def clone(request_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    req = workflow.clone_request(db, user, workflow.get_request(db, request_id))
    db.commit()
    return request_detail(db, user, req)


@router.post("/mdm/requests/{request_id}/cancel")
def cancel(request_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    req = workflow.cancel_request(db, user, workflow.get_request(db, request_id))
    db.commit()
    return request_detail(db, user, req)


@router.post("/mdm/requests/{request_id}/verify")
def verify(request_id: int, body: VerifyIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    req = workflow.mdm_verify(db, user, workflow.get_request(db, request_id), body.action, body.comment)
    db.commit()
    return request_detail(db, user, req)


@router.get("/mdm/route-preview")
def route_preview(request_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    req = workflow.get_request(db, request_id)
    workflow.assert_can_view(db, user, req)
    return workflow.preview_route(db, req.domain, {"entity_code": req.entity_code, "country_code": req.country_code}, req.data)


# ---------------------------------------------------------------- attachments

@router.post("/mdm/requests/{request_id}/attachments", status_code=201)
async def upload(request_id: int, category: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    req = workflow.get_request(db, request_id)
    if req.requester_id != user.id or req.status not in ("DRAFT", "NEEDS_CHANGES"):
        raise Forbidden("Only the requestor can add documents before submission.")
    if category not in ATTACHMENT_LABELS:
        raise ValidationFailed("Unknown document category.")
    name = (file.filename or "document").replace("\\", "/").split("/")[-1][:200]
    ext = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
    if ext not in ALLOWED_EXT:
        raise ValidationFailed(f"File type not allowed. Allowed: {', '.join(sorted(ALLOWED_EXT))}.")
    settings = get_settings()
    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise ValidationFailed("File is larger than 5 MB.")
    if not content:
        raise ValidationFailed("File is empty.")
    stored = f"{uuid.uuid4().hex}{ext}"
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    (settings.upload_dir / stored).write_bytes(content)
    att = RequestAttachment(request_id=req.id, category=category, original_filename=name, stored_filename=stored,
                            content_type=mimetypes.guess_type(name)[0] or "application/octet-stream", size_bytes=len(content),
                            sha256=hashlib.sha256(content).hexdigest(), uploaded_by_id=user.id)
    db.add(att)
    audit.record(db, "ATTACHMENT_ADDED", request_id=req.id, actor_id=user.id, from_status=req.status, to_status=req.status,
                 comment=f"{ATTACHMENT_LABELS[category]}: {name}", changes={"sha256": att.sha256}, entity_ref=req.request_number)
    db.commit()
    db.refresh(req)
    return {"id": att.id, "category": category, "filename": name, "size": len(content), "readiness": validation.evaluate_request(db, req)}


@router.delete("/mdm/requests/{request_id}/attachments/{att_id}")
def delete_attachment(request_id: int, att_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    req = workflow.get_request(db, request_id)
    att = db.get(RequestAttachment, att_id)
    if not att or att.request_id != req.id:
        raise HTTPException(404, "Attachment not found")
    if req.requester_id != user.id or req.status not in ("DRAFT", "NEEDS_CHANGES"):
        raise Forbidden("Documents can only be removed by the requestor before submission.")
    audit.record(db, "ATTACHMENT_REMOVED", request_id=req.id, actor_id=user.id, from_status=req.status, to_status=req.status,
                 comment=att.original_filename, entity_ref=req.request_number)
    db.delete(att)
    db.commit()
    db.refresh(req)
    return {"readiness": validation.evaluate_request(db, req)}


@router.get("/mdm/requests/{request_id}/attachments/{att_id}")
def download(request_id: int, att_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    req = workflow.get_request(db, request_id)
    workflow.assert_can_view(db, user, req)
    att = db.get(RequestAttachment, att_id)
    if not att or att.request_id != req.id:
        raise HTTPException(404, "Attachment not found")
    path = get_settings().upload_dir / att.stored_filename
    if not path.exists():
        raise HTTPException(404, "File missing from storage")
    return FileResponse(path, media_type=att.content_type, filename=att.original_filename)


# ---------------------------------------------------------------- master records & canonical mapping

@router.get("/master-records")
def master_records(domain: str | None = None, q: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
                   db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    query = select(MasterRecord)
    if domain:
        query = query.where(MasterRecord.domain == domain)
    if q:
        like = f"%{q.strip()}%"
        query = query.where(or_(MasterRecord.name.ilike(like), MasterRecord.record_code.ilike(like), MasterRecord.identifier.ilike(like)))
    total = db.execute(select(func.count()).select_from(query.subquery())).scalar()
    rows = db.execute(query.order_by(MasterRecord.record_code).offset((page - 1) * page_size).limit(page_size)).scalars().all()
    counts = dict(db.execute(select(MasterRecord.domain, func.count()).group_by(MasterRecord.domain)).all())
    return {"total": total, "page": page, "page_size": page_size, "domain_counts": counts, "items": [
        {"id": m.id, "code": m.record_code, "domain": m.domain, "domain_label": DOMAIN_LABELS[m.domain], "name": m.name,
         "country_code": m.country_code, "entity_code": m.entity_code, "identifier": m.identifier, "sap_code": m.sap_code,
         "source": m.source, "status": m.status, "aliases": [a.alias_name for a in m.aliases], "created_at": iso(m.created_at)} for m in rows]}


@router.get("/master-records/{record_id}")
def master_record(record_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    m = workflow.master_record(db, record_id)
    maps = db.execute(select(CanonicalRecordMapping).where(CanonicalRecordMapping.master_record_id == m.id)
                      .order_by(CanonicalRecordMapping.id)).scalars().all()
    return {"id": m.id, "code": m.record_code, "domain": m.domain, "name": m.name, "country_code": m.country_code,
            "entity_code": m.entity_code, "identifier": m.identifier, "sap_code": m.sap_code, "source": m.source,
            "attributes": m.attributes, "created_from_request_id": m.created_from_request_id,
            "aliases": [{"name": a.alias_name, "source_system": a.source_system, "source_code": a.source_code} for a in m.aliases],
            "mappings": [_mapping_out(x) for x in maps]}


def _mapping_out(x: CanonicalRecordMapping) -> dict:
    return {"id": x.id, "source_customer": {"id": x.source_customer.id, "code": x.source_customer.source_code, "name": x.source_customer.name,
                                            "entity": x.source_customer.source_entity, "country": x.source_customer.country_code},
            "master_record": {"id": x.master_record.id, "code": x.master_record.record_code, "name": x.master_record.name},
            "alias_name": x.alias_name, "confidence": x.confidence, "method": x.method, "review_status": x.review_status,
            "reviewed_at": iso(x.reviewed_at), "is_current": x.is_current, "created_at": iso(x.created_at)}


@router.get("/canonical-mappings")
def mappings(status: str | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    q = select(CanonicalRecordMapping).where(CanonicalRecordMapping.is_current.is_(True))
    if status:
        q = q.where(CanonicalRecordMapping.review_status == status)
    rows = db.execute(q.order_by(CanonicalRecordMapping.review_status.desc(), CanonicalRecordMapping.confidence)).scalars().all()
    counts = dict(db.execute(select(CanonicalRecordMapping.review_status, func.count()).where(CanonicalRecordMapping.is_current.is_(True))
                             .group_by(CanonicalRecordMapping.review_status)).all())
    return {"counts": counts, "items": [_mapping_out(x) for x in rows]}


@router.post("/canonical-mappings/{mapping_id}/review")
def review_mapping(mapping_id: int, body: MappingReviewIn, db: Session = Depends(get_db),
                   user: User = Depends(require_roles(roles.MDM_ANALYST, roles.ADMIN))):
    m = db.get(CanonicalRecordMapping, mapping_id)
    if not m or not m.is_current:
        raise HTTPException(404, "Mapping not found")
    if body.decision not in ("CONFIRM", "REJECT"):
        raise ValidationFailed("Decision must be CONFIRM or REJECT.")
    if m.review_status != "PROPOSED":
        raise Conflict("Only proposed mappings can be reviewed.")
    # History is preserved: retire the proposal and add the reviewed mapping as a new current row.
    m.is_current = False
    new = CanonicalRecordMapping(source_customer_id=m.source_customer_id, master_record_id=m.master_record_id, alias_name=m.alias_name,
                                 confidence=m.confidence, method=m.method, review_status="CONFIRMED" if body.decision == "CONFIRM" else "REJECTED",
                                 reviewer_id=user.id, reviewed_at=utcnow(), is_current=True)
    db.add(new)
    audit.record(db, f"MAPPING_{new.review_status}", actor_id=user.id, entity_type="CANONICAL_MAPPING", entity_ref=m.source_customer.source_code,
                 from_status="PROPOSED", to_status=new.review_status,
                 comment=f"'{m.alias_name}' ({m.source_customer.source_entity}) → {m.master_record.record_code} {m.master_record.name}. {body.comment}".strip())
    db.commit()
    return _mapping_out(new)


@router.get("/canonical-mappings/consolidation")
def consolidation(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return analytics.customer_consolidation(db)
