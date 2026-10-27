"""Form definitions drive both the dynamic UI and server-side validation."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import FieldDefinition, FormDefinition, ValidationRule
from .errors import NotFound

HEADER_FIELDS = {
    "entity_code": "Business entity", "country_code": "Country", "request_type": "Request type",
    "department": "Department", "domain": "Record category",
}

# Per-domain semantics used by duplicate detection and SAP payload building.
DOMAIN_KEYS = {
    "CUSTOMER": {"name": "legal_name", "alt_name": "trading_name", "identifier": "business_reg_no", "address": "registered_address"},
    "VENDOR": {"name": "legal_name", "identifier": "vendor_reg_no", "address": "address"},
    "ITEM": {"name": "item_name", "identifier": "manufacturer_part_no", "manufacturer": "manufacturer"},
    "COST_CENTER": {"name": "cost_center_name", "identifier": "cost_center_code"},
}

DOMAIN_LABELS = {"CUSTOMER": "Customer", "VENDOR": "Vendor", "ITEM": "Item / Material", "COST_CENTER": "Cost Center"}


def get_form(db: Session, domain: str) -> FormDefinition:
    form = db.execute(select(FormDefinition).where(FormDefinition.domain == domain)).scalar_one_or_none()
    if not form:
        raise NotFound(f"No form is configured for domain {domain}.")
    return form


def active_fields(form: FormDefinition) -> list[FieldDefinition]:
    return [f for f in form.fields if f.is_active]


def rules_for(db: Session, domain: str) -> list[ValidationRule]:
    return list(db.execute(select(ValidationRule).where(ValidationRule.domain == domain, ValidationRule.is_active.is_(True))).scalars())


def field_labels(db: Session, domain: str) -> dict[str, str]:
    labels = dict(HEADER_FIELDS)
    labels.update({f.key: f.label for f in get_form(db, domain).fields})
    return labels


def request_title(domain: str, data: dict) -> str:
    key = DOMAIN_KEYS[domain]["name"]
    return (data.get(key) or "").strip() or f"Untitled {DOMAIN_LABELS[domain].lower()} request"
