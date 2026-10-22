"""Context-aware validation and submission readiness. The backend is the source of truth:
the UI calls the same function (POST /api/mdm/validate) for live feedback, and submit re-runs it."""
import re
from datetime import date

from sqlalchemy.orm import Session

from ..models import BusinessEntity, Country, MdmRequest
from . import conditions
from .forms import active_fields, get_form, rules_for

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9 ()\-]{6,19}$")

ATTACHMENT_LABELS = {
    "REGULATORY_LICENCE": "Product registration / licence evidence",
    "BUSINESS_REGISTRATION": "Business registration certificate",
    "BANK_CONFIRMATION": "Bank account confirmation letter",
    "QUALITY_CERTIFICATE": "Quality certificate (e.g. ISO 13485)",
    "OTHER": "Other supporting document",
}


def build_context(domain: str, header: dict, data: dict) -> dict:
    ctx = {k: v for k, v in data.items()}
    ctx.update({"domain": domain, **{k: header.get(k) for k in ("entity_code", "country_code", "request_type", "department")}})
    return ctx


def _check_value(field, value: str) -> str | None:
    t = field.field_type
    if t == "email" and not EMAIL_RE.match(value):
        return "Enter a valid email address (e.g. name@hospital.org)."
    if t == "phone" and not PHONE_RE.match(value):
        return "Enter a valid phone number, including country code (e.g. +65 6123 4567)."
    if t == "number":
        try:
            if float(value) < 0:
                return "Value cannot be negative."
        except ValueError:
            return "Enter a number."
    if t == "date":
        try:
            date.fromisoformat(value)
        except ValueError:
            return "Enter a date in YYYY-MM-DD format."
    if t == "select" and field.options and value not in field.options:
        return f"Choose one of: {', '.join(field.options)}."
    if field.pattern and not re.fullmatch(field.pattern, value):
        return field.pattern_message or "Value is not in the expected format."
    return None


def evaluate(db: Session, domain: str, header: dict, data: dict, attachments: list[str],
             duplicate_status: str = "NOT_RUN") -> dict:
    form = get_form(db, domain)
    ctx = build_context(domain, header, data)
    errors: dict[str, str] = {}
    required_total = required_done = 0
    format_problems = 0
    visible = []

    for key, label in (("entity_code", "Business entity"), ("country_code", "Country")):
        required_total += 1
        val = header.get(key)
        model = BusinessEntity if key == "entity_code" else Country
        if not val:
            errors[key] = f"{label} is required."
        elif db.get(model, val) is None:
            errors[key] = f"Unknown {label.lower()} '{val}'."
        else:
            required_done += 1

    for field in active_fields(form):
        if not conditions.evaluate(field.visible_when, ctx):
            continue
        visible.append(field.key)
        value = (data.get(field.key) or "").strip() if data.get(field.key) is not None else ""
        required = field.required or (field.required_when is not None and conditions.evaluate(field.required_when, ctx))
        if required:
            required_total += 1
            if not value:
                reason = ""
                if not field.required and field.required_when:
                    reason = " " + conditions.describe(field.required_when, {f.key: f.label for f in form.fields}).replace("When", "because", 1) + "."
                errors[field.key] = f"{field.label} is required{reason}"
                continue
            required_done += 1
        if value:
            problem = _check_value(field, value)
            if problem:
                errors[field.key] = problem
                format_problems += 1
                if required:
                    required_done -= 1

    attachments_required = []
    domain_checks = []
    for rule in rules_for(db, domain):
        if not conditions.evaluate(rule.condition, ctx):
            continue
        if rule.rule_type == "REQUIRED_ATTACHMENT":
            provided = rule.attachment_category in attachments
            attachments_required.append({
                "category": rule.attachment_category, "label": ATTACHMENT_LABELS.get(rule.attachment_category, rule.attachment_category),
                "provided": provided, "message": rule.message,
            })
            if not provided:
                errors[f"attachment:{rule.attachment_category}"] = rule.message
        elif rule.rule_type == "FUTURE_DATE" and rule.field_key:
            raw = data.get(rule.field_key)
            ok = True
            if raw:
                try:
                    ok = date.fromisoformat(raw) > date.today()
                except ValueError:
                    ok = True  # format error already reported on the field
                if not ok:
                    errors.setdefault(rule.field_key, rule.message)
            domain_checks.append({"key": rule.rule_key, "label": rule.message, "passed": ok})

    field_errors = {k: v for k, v in errors.items() if not k.startswith("attachment:")}
    dup_ok = duplicate_status in ("CLEAR", "RESOLVED")
    if errors:
        state = "INCOMPLETE"
    elif not dup_ok:
        state = "REQUIRES_REVIEW"
    else:
        state = "COMPLETE"

    checks = [
        {"key": "fields", "label": "Required fields completed", "passed": required_done == required_total and not field_errors,
         "detail": f"{required_done} of {required_total} required fields complete"},
        {"key": "attachments", "label": "Supporting documents provided", "passed": all(a["provided"] for a in attachments_required),
         "detail": f"{sum(a['provided'] for a in attachments_required)} of {len(attachments_required)} required documents"},
        {"key": "duplicates", "label": "Duplicate review completed", "passed": dup_ok,
         "detail": {"NOT_RUN": "Duplicate check not yet run", "CLEAR": "No significant matches",
                    "REVIEW_REQUIRED": "Possible duplicates need your review", "RESOLVED": "Reviewed and documented",
                    "BLOCKED": "Exact identifier match — reuse or correct"}.get(duplicate_status, duplicate_status)},
        {"key": "domain", "label": "Domain-specific checks passed",
         "passed": all(c["passed"] for c in domain_checks) and format_problems == 0,
         "detail": (f"{format_problems} value(s) in the wrong format" if format_problems else
                    f"{sum(c['passed'] for c in domain_checks)} of {len(domain_checks)} rule checks passed" if domain_checks else "Entered values are in the expected format")},
    ]
    return {
        "state": state, "errors": errors, "field_errors": field_errors, "visible_fields": visible,
        "required_total": required_total, "required_complete": required_done,
        "attachments_required": attachments_required, "domain_checks": domain_checks,
        "duplicate_status": duplicate_status, "checks": checks,
        "completion_pct": round(100 * required_done / required_total) if required_total else 100,
    }


def evaluate_request(db: Session, req: MdmRequest) -> dict:
    header = {"entity_code": req.entity_code, "country_code": req.country_code,
              "request_type": req.request_type, "department": req.department}
    return evaluate(db, req.domain, header, req.data, [a.category for a in req.attachments], req.duplicate_check_status)
