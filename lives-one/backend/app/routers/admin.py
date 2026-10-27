from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import ApplicationSetting, FieldDefinition, FormDefinition, Role, User, ValidationRule, WorkflowStep, WorkflowTemplate
from ..schemas import FormUpdate, SettingUpdate, WorkflowUpdate
from ..serializers import iso
from ..services import audit, conditions, roles, settings_service
from ..services.errors import NotFound, ValidationFailed
from ..services.forms import HEADER_FIELDS

router = APIRouter(prefix="/api/config", tags=["configuration"])
admin = require_roles(roles.ADMIN)


def _form_out(f: FormDefinition) -> dict:
    return {"id": f.id, "domain": f.domain, "name": f.name, "description": f.description, "version": f.version, "updated_at": iso(f.updated_at),
            "fields": [{c: getattr(x, c) for c in ("id", "key", "label", "field_type", "section", "display_order", "required", "required_when",
                                                    "visible_when", "options", "pattern", "pattern_message", "help_text", "sensitivity",
                                                    "is_identifier", "is_active")} for x in f.fields]}


@router.get("/forms")
def forms(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [_form_out(f) for f in db.execute(select(FormDefinition).order_by(FormDefinition.id)).scalars()]


@router.put("/forms/{form_id}")
def update_form(form_id: int, body: FormUpdate, db: Session = Depends(get_db), user: User = Depends(admin)):
    form = db.get(FormDefinition, form_id)
    if not form:
        raise NotFound("Form not found.")
    keys = [f.key for f in body.fields]
    if len(keys) != len(set(keys)):
        raise ValidationFailed("Field keys must be unique.")
    known = set(keys) | set(HEADER_FIELDS)
    problems = []
    for f in body.fields:
        for cond_name in ("required_when", "visible_when"):
            problems += [f"{f.label} – {cond_name}: {p}" for p in conditions.validate_condition(getattr(f, cond_name), known)]
        if f.field_type == "select" and not f.options:
            problems.append(f"{f.label}: select fields need at least one option.")
    existing_identity = {x.key for x in form.fields if x.is_identifier}
    removed = existing_identity - {f.key for f in body.fields if f.is_active}
    if removed:
        problems.append(f"Identifier fields cannot be removed (used for duplicate detection): {', '.join(sorted(removed))}.")
    if problems:
        raise ValidationFailed("Form configuration is invalid.", {"problems": problems})
    by_id = {x.id: x for x in form.fields}
    before = {x.key: (x.required, x.is_active, x.label) for x in form.fields}
    for i, f in enumerate(body.fields):
        data = f.model_dump(exclude={"id"})
        data["display_order"] = i * 10
        row = by_id.get(f.id) if f.id else None
        if row is None:
            form.fields.append(FieldDefinition(**data))
        else:
            for k, v in data.items():
                setattr(row, k, v)
    # Fields omitted from the payload are deactivated, never deleted (drafts may still hold values).
    sent = {f.id for f in body.fields if f.id}
    for x in form.fields:
        if x.id and x.id not in sent:
            x.is_active = False
    if body.name:
        form.name = body.name
    if body.description is not None:
        form.description = body.description
    form.version += 1
    form.updated_by_id = user.id
    db.flush()
    after = {x.key: (x.required, x.is_active, x.label) for x in form.fields}
    diff = {k: {"from": before.get(k), "to": v} for k, v in after.items() if before.get(k) != v}
    audit.record(db, "FORM_CONFIG_CHANGED", actor_id=user.id, entity_type="FORM", entity_ref=form.domain,
                 comment=f"{form.name} form updated to v{form.version}", changes=diff)
    db.commit()
    return _form_out(form)


def _wf_out(t: WorkflowTemplate) -> dict:
    return {"id": t.id, "domain": t.domain, "name": t.name, "version": t.version, "mdm_verification_sla_days": t.mdm_verification_sla_days,
            "updated_at": iso(t.updated_at), "steps": [{"id": s.id, "step_key": s.step_key, "name": s.name, "role_code": s.role_code,
                                                         "stage_order": s.stage_order, "condition": s.condition,
                                                         "condition_text": conditions.describe(s.condition), "description": s.description,
                                                         "sla_days": s.sla_days, "is_active": s.is_active} for s in t.steps]}


@router.get("/workflows")
def workflows(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [_wf_out(t) for t in db.execute(select(WorkflowTemplate).order_by(WorkflowTemplate.id)).scalars()]


def validate_workflow(db: Session, template: WorkflowTemplate, body: WorkflowUpdate) -> list[str]:
    problems = []
    approver_roles = {r.code for r in db.execute(select(Role).where(Role.is_approver.is_(True))).scalars()}
    form = db.execute(select(FormDefinition).where(FormDefinition.domain == template.domain)).scalar_one()
    known = {f.key for f in form.fields} | set(HEADER_FIELDS)
    keys = [s.step_key for s in body.steps]
    if len(keys) != len(set(keys)):
        problems.append("Step keys must be unique.")
    active = [s for s in body.steps if s.is_active]
    if not active:
        problems.append("At least one active approval step is required.")
    if active and not any(s.condition is None for s in active):
        problems.append("At least one active step must apply to every request (no condition), so no request skips approval.")
    for s in body.steps:
        if s.role_code not in approver_roles:
            problems.append(f"{s.name}: '{s.role_code}' is not an approver role.")
        problems += [f"{s.name}: {p}" for p in conditions.validate_condition(s.condition, known)]
    seen = set()
    for s in active:
        if (s.role_code, s.stage_order) in seen:
            problems.append(f"{s.name}: the same role appears twice in stage {s.stage_order}.")
        seen.add((s.role_code, s.stage_order))
    # Stages are ordinal (1 → 2 → 3); parallel = same stage. Cycles are therefore impossible by construction.
    return problems


@router.put("/workflows/{template_id}")
def update_workflow(template_id: int, body: WorkflowUpdate, db: Session = Depends(get_db), user: User = Depends(admin)):
    t = db.get(WorkflowTemplate, template_id)
    if not t:
        raise NotFound("Workflow not found.")
    problems = validate_workflow(db, t, body)
    if problems:
        raise ValidationFailed("Workflow configuration is invalid.", {"problems": problems})
    before = [(s.name, s.role_code, s.stage_order, s.is_active) for s in t.steps]
    by_id = {s.id: s for s in t.steps}
    sent = set()
    for s in body.steps:
        data = s.model_dump(exclude={"id"})
        if s.id and s.id in by_id:
            for k, v in data.items():
                setattr(by_id[s.id], k, v)
            sent.add(s.id)
        else:
            t.steps.append(WorkflowStep(**data))
    for s in list(t.steps):
        if s.id and s.id not in sent and s.id in by_id:
            s.is_active = False  # in-flight tasks keep their history; the step simply stops applying
    if body.name:
        t.name = body.name
    if body.mdm_verification_sla_days:
        t.mdm_verification_sla_days = body.mdm_verification_sla_days
    t.version += 1
    t.updated_by_id = user.id
    db.flush()
    after = [(s.name, s.role_code, s.stage_order, s.is_active) for s in t.steps]
    audit.record(db, "WORKFLOW_CONFIG_CHANGED", actor_id=user.id, entity_type="WORKFLOW", entity_ref=t.domain,
                 comment=f"{t.name} updated to v{t.version}. Applies to new submissions; in-flight requests keep their routing.",
                 changes={"before": before, "after": after})
    db.commit()
    db.refresh(t)
    return _wf_out(t)


@router.get("/validation-rules")
def rules(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [{"id": r.id, "domain": r.domain, "rule_key": r.rule_key, "rule_type": r.rule_type, "condition": r.condition,
             "condition_text": conditions.describe(r.condition), "attachment_category": r.attachment_category, "field_key": r.field_key,
             "message": r.message, "is_active": r.is_active} for r in db.execute(select(ValidationRule).order_by(ValidationRule.id)).scalars()]


@router.get("/settings")
def get_settings_(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [{"key": s.key, "value": s.value, "description": s.description, "updated_at": iso(s.updated_at)}
            for s in db.execute(select(ApplicationSetting).order_by(ApplicationSetting.key)).scalars()]


EDITABLE_SETTINGS = {"duplicate.likely_threshold", "duplicate.review_threshold", "sla.escalate_after_overdue_days",
                     "sla.total_turnaround_target_days", "forecast.rolling_window"}


@router.put("/settings/{key}")
def put_setting(key: str, body: SettingUpdate, db: Session = Depends(get_db), user: User = Depends(admin)):
    if key not in EDITABLE_SETTINGS:
        raise ValidationFailed("This setting cannot be edited here.")
    v = body.value
    if key.startswith("duplicate."):
        v = float(v)
        other = float(settings_service.get(db, "duplicate.review_threshold" if key.endswith("likely_threshold") else "duplicate.likely_threshold"))
        if not 50 <= v <= 100 or (key.endswith("likely_threshold") and v <= other) or (key.endswith("review_threshold") and v >= other):
            raise ValidationFailed("Thresholds must be 50–100 and 'likely' must be above 'review'.")
    if key == "forecast.rolling_window" and int(v) not in (3, 6):
        raise ValidationFailed("With 12 months of data the rolling window can be 3 or 6 months (backtests start at month 7).")
    old = settings_service.get(db, key)
    settings_service.set_value(db, key, v, user.id)
    audit.record(db, "SETTING_CHANGED", actor_id=user.id, entity_type="SETTING", entity_ref=key, comment=f"{key}: {old} → {v}")
    db.commit()
    return {"key": key, "value": v}
