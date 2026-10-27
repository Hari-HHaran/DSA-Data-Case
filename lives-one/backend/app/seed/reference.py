"""Reference data: countries, entities, roles, demo personas, settings, forms, validation and approval rules.

Everything here is a PROTOTYPE ASSUMPTION unless it is a fact from the case brief:
- Brief facts: entities SPD/QTS/QTG; Products A/B/C; five SEA country locations; SAP B1; M365;
  approver groups (BU Head, Finance, Quality/Regulatory, Business Support); MDM team; personas Amy,
  Wei Jie, Priya, Marcus.
- Assumptions: which five countries, all field lists, approval routing conditions, SLAs, and the
  supporting personas Daniel, Siti, Kevin, Alex, Elaine and the country account owners.
"""
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import (
    BusinessEntity, Country, FieldDefinition, FormDefinition, Role, User, ValidationRule, WorkflowStep, WorkflowTemplate,
)
from ..services import settings_service
from ..services.roles import ROLE_DEFINITIONS
from ..services.security import hash_password

COUNTRIES = [  # Illustrative allocation — configurable; not verified Lives Group locations beyond the Singapore HQ.
    ("SG", "Singapore", "Asia/Singapore", 1), ("MY", "Malaysia", "Asia/Kuala_Lumpur", 2),
    ("ID", "Indonesia", "Asia/Jakarta", 3), ("TH", "Thailand", "Asia/Bangkok", 4), ("VN", "Vietnam", "Asia/Ho_Chi_Minh", 5),
]
ENTITIES = [(c, c, "Business entity named in the case brief. Product-line allocation in this prototype is illustrative.")
            for c in ("SPD", "QTS", "QTG")]

# username, name, title, roles, entity, country, note
USERS = [
    ("amy", "Amy", "Product Manager", ["REQUESTOR"], "SPD", "SG", "Brief persona: needs a new item code; unsure of regulatory fields."),
    ("weijie", "Wei Jie", "Finance Manager", ["FINANCE"], "SPD", "SG", "Brief persona: approves credit terms and banking details."),
    ("priya", "Priya", "MDM Analyst", ["MDM_ANALYST"], None, "SG", "Brief persona: final verification and SAP B1 creation."),
    ("marcus", "Marcus", "Regional Sales · new business unit", ["SALES", "REQUESTOR"], "QTG", "SG", "Brief persona: new BU, needs a standard process."),
    ("daniel", "Daniel", "Business Unit Head", ["BU_HEAD"], "SPD", "SG", "Fictional supporting persona (not in the brief)."),
    ("siti", "Siti", "Quality & Regulatory Affairs", ["QRA"], None, "MY", "Fictional supporting persona (not in the brief)."),
    ("kevin", "Kevin", "Business Support", ["BUSINESS_SUPPORT"], None, "SG", "Fictional supporting persona (not in the brief)."),
    ("alex", "Alex", "System Administrator", ["ADMIN"], None, "SG", "Fictional supporting persona (not in the brief)."),
    ("elaine", "Elaine", "Executive Viewer", ["EXECUTIVE"], None, "SG", "Fictional supporting persona (not in the brief)."),
    ("nurul", "Nurul", "Account Manager · Malaysia", ["SALES"], "SPD", "MY", "Fictional account owner."),
    ("putri", "Putri", "Account Manager · Indonesia", ["SALES"], "QTS", "ID", "Fictional account owner."),
    ("anan", "Anan", "Account Manager · Thailand", ["SALES"], "SPD", "TH", "Fictional account owner."),
    ("linh", "Linh", "Account Manager · Vietnam", ["SALES"], "QTS", "VN", "Fictional account owner."),
    ("ben", "Ben", "Procurement Officer", ["REQUESTOR"], "QTS", "MY", "Fictional requestor used in seeded history."),
]
ACCOUNT_OWNER_BY_COUNTRY = {"SG": "marcus", "MY": "nurul", "ID": "putri", "TH": "anan", "VN": "linh"}

BUSINESS_UNITS = ["Diagnostics (IVD)", "Medical Equipment", "Laboratory Solutions", "Life Science Tools (new BU)"]
PAYMENT_TERMS = ["Cash in advance", "Net 30", "Net 45", "Net 60"]
REGULATED = ["Class B", "Class C", "Class D"]
MANUFACTURER_CATEGORIES = ["Medical device manufacturer", "Reagent manufacturer"]


def F(key, label, type_="text", section="Details", required=False, **kw):
    return {"key": key, "label": label, "field_type": type_, "section": section, "required": required, **kw}


FORMS = {
    "ITEM": ("Item / Material", "New product or material code for SAP B1 inventory master data.", [
        F("item_name", "Item name", section="Item basics", required=True, help_text="Name as it should appear on quotations and invoices."),
        F("item_description", "Item description", "textarea", "Item basics", True),
        F("product_family", "Product family", "select", "Item basics", True, options=["Product A", "Product B", "Product C", "Other"]),
        F("item_category", "Item category", "select", "Item basics", True, options=["Consumable", "Reagent", "Instrument / equipment", "Spare part", "Service"]),
        F("unit_of_measure", "Unit of measure", "select", "Item basics", True, options=["EA", "BOX", "KIT", "PACK", "L", "mL"]),
        F("manufacturer", "Manufacturer", section="Sourcing", required=True),
        F("manufacturer_part_no", "Manufacturer part number", section="Sourcing", required=True, is_identifier=True,
          pattern=r"[A-Za-z0-9][A-Za-z0-9\-./]{2,39}", pattern_message="3–40 letters, digits, dashes, dots or slashes.",
          help_text="Used to detect duplicate item codes across entities."),
        F("supplier_name", "Supplier", section="Sourcing"),
        F("regulatory_class", "Regulatory classification", "select", "Regulatory", True, options=["Not regulated", "Class A", *REGULATED],
          help_text="Medical device / IVD risk class in the destination country. Unsure? Use the manufacturer's declaration — Quality/Regulatory will verify. Class B–D items need licence details and evidence."),
        F("licence_number", "Product registration / licence number", section="Regulatory",
          visible_when={"all": [{"field": "regulatory_class", "op": "in", "value": REGULATED}]},
          required_when={"all": [{"field": "regulatory_class", "op": "in", "value": REGULATED}]}),
        F("licence_expiry", "Licence expiry date", "date", "Regulatory",
          visible_when={"all": [{"field": "regulatory_class", "op": "in", "value": REGULATED}]},
          required_when={"all": [{"field": "regulatory_class", "op": "in", "value": REGULATED}]}),
        F("storage_condition", "Storage condition", "select", "Regulatory", True, options=["Ambient", "Refrigerated (2–8°C)", "Frozen (−20°C)"]),
        F("stock_managed", "Stock-managed item?", "select", "Commercial", True, options=["Yes", "No"],
          help_text="Stock-managed items need warehouse and pricing set-up by Business Support."),
        F("standard_cost", "Standard cost (SGD)", "number", "Commercial"),
        F("lead_time_days", "Supplier lead time (days)", "number", "Commercial"),
    ]),
    "CUSTOMER": ("Customer / Business Partner", "New customer account (SAP B1 Business Partner, customer type).", [
        F("legal_name", "Legal business name", section="Organisation", required=True, help_text="Exactly as on the business registration certificate."),
        F("trading_name", "Trading name / common abbreviation", section="Organisation", help_text="e.g. the short name your team uses. Helps detect duplicates."),
        F("business_reg_no", "Business registration number", section="Organisation", required=True, is_identifier=True,
          pattern=r"[A-Za-z0-9\-]{6,20}", pattern_message="6–20 letters, digits or dashes."),
        F("customer_segment", "Customer segment", "select", "Organisation", True, options=["Hospital", "Laboratory", "Clinic", "Research institute", "Distributor"]),
        F("business_unit", "Business unit", "select", "Organisation", True, options=BUSINESS_UNITS),
        F("registered_address", "Registered address", "textarea", "Address & contact", True),
        F("contact_person", "Contact person", section="Address & contact", required=True),
        F("contact_email", "Contact email", "email", "Address & contact", True),
        F("contact_phone", "Contact number", "phone", "Address & contact", True),
        F("payment_terms", "Payment terms", "select", "Credit (Finance)", True, options=PAYMENT_TERMS),
        F("credit_limit", "Requested credit limit (SGD)", "number", "Credit (Finance)", sensitivity="FINANCIAL",
          visible_when={"all": [{"field": "payment_terms", "op": "neq", "value": "Cash in advance"}]},
          required_when={"all": [{"field": "payment_terms", "op": "in", "value": ["Net 30", "Net 45", "Net 60"]}]},
          help_text="Visible only to you, Finance and MDM."),
    ]),
    "VENDOR": ("Vendor / Business Partner", "New supplier (SAP B1 Business Partner, supplier type).", [
        F("legal_name", "Legal vendor name", section="Organisation", required=True),
        F("vendor_reg_no", "Vendor registration number", section="Organisation", required=True, is_identifier=True,
          pattern=r"[A-Za-z0-9\-]{6,20}", pattern_message="6–20 letters, digits or dashes."),
        F("supplier_category", "Supplier category", "select", "Organisation", True,
          options=[*MANUFACTURER_CATEGORIES, "Distributor", "Logistics / service provider", "Other"]),
        F("address", "Address", "textarea", "Address & contact", True),
        F("contact_person", "Contact person", section="Address & contact", required=True),
        F("contact_email", "Contact email", "email", "Address & contact", True),
        F("contact_phone", "Contact number", "phone", "Address & contact"),
        F("payment_terms", "Payment terms", "select", "Banking (Finance)", True, options=PAYMENT_TERMS),
        F("bank_name", "Bank name", section="Banking (Finance)", required=True, sensitivity="FINANCIAL"),
        F("bank_account_no", "Bank account number", section="Banking (Finance)", required=True, sensitivity="FINANCIAL",
          pattern=r"[0-9\-]{6,24}", pattern_message="6–24 digits (dashes allowed).", help_text="Visible only to you, Finance and MDM. Never send by email."),
        F("swift_code", "SWIFT / BIC", section="Banking (Finance)", sensitivity="FINANCIAL",
          pattern=r"[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?", pattern_message="8 or 11 characters, e.g. DBSSSGSG."),
    ]),
    "COST_CENTER": ("Finance / Cost Center", "New financial reporting unit (SAP B1 profit/cost centre).", [
        F("cost_center_name", "Cost centre name", section="Cost centre", required=True),
        F("cost_center_code", "Cost centre code", section="Cost centre", required=True, is_identifier=True,
          pattern=r"[A-Z]{2,3}-[0-9]{3,5}", pattern_message="Format AA-123 (2–3 capitals, dash, 3–5 digits)."),
        F("business_unit", "Business unit", "select", "Cost centre", True, options=BUSINESS_UNITS),
        F("responsible_manager", "Responsible manager", section="Ownership", required=True),
        F("manager_email", "Manager email", "email", "Ownership", True),
        F("effective_date", "Effective date", "date", "Ownership", True),
        F("cost_classification", "Cost classification", "select", "Ownership", True, options=["Revenue", "Operating expense", "Overhead", "Project"]),
    ]),
}

VALIDATION_RULES = [
    ("ITEM", "item_licence_evidence", "REQUIRED_ATTACHMENT", {"all": [{"field": "regulatory_class", "op": "in", "value": REGULATED}]},
     "REGULATORY_LICENCE", None, "Upload product registration / licence evidence (required for Class B–D items)."),
    ("ITEM", "item_licence_not_expired", "FUTURE_DATE", {"all": [{"field": "regulatory_class", "op": "in", "value": REGULATED}]},
     None, "licence_expiry", "Licence must not be expired."),
    ("CUSTOMER", "customer_business_registration", "REQUIRED_ATTACHMENT", None, "BUSINESS_REGISTRATION", None,
     "Upload the customer's business registration certificate."),
    ("VENDOR", "vendor_bank_confirmation", "REQUIRED_ATTACHMENT", None, "BANK_CONFIRMATION", None,
     "Upload a bank confirmation letter (banking details are verified by Finance)."),
    ("VENDOR", "vendor_quality_cert", "REQUIRED_ATTACHMENT", {"all": [{"field": "supplier_category", "op": "in", "value": MANUFACTURER_CATEGORIES}]},
     "QUALITY_CERTIFICATE", None, "Upload the manufacturer's quality certificate (e.g. ISO 13485)."),
]

# (domain, step_key, name, role, stage, condition, sla_days, description)
WORKFLOWS = {
    "ITEM": ("Item / Material approval", 1, [
        ("bu_head", "Business Unit Head approval", "BU_HEAD", 1, None, 2, "Confirms the commercial need for the item."),
        ("regulatory", "Quality / Regulatory sign-off", "QRA", 1,
         {"all": [{"field": "regulatory_class", "op": "in", "value": REGULATED}]}, 2, "Confirms product licence for regulated items."),
        ("business_support", "Business Support set-up check", "BUSINESS_SUPPORT", 2,
         {"all": [{"field": "stock_managed", "op": "eq", "value": "Yes"}]}, 1, "Confirms warehouse, UoM and pricing set-up."),
    ]),
    "CUSTOMER": ("Customer approval", 1, [
        ("bu_head", "Business Unit Head approval", "BU_HEAD", 1, None, 2, "Confirms the customer relationship."),
        ("finance_credit", "Finance credit review", "FINANCE", 1,
         {"all": [{"field": "payment_terms", "op": "neq", "value": "Cash in advance"}]}, 2, "Approves credit terms and limit."),
    ]),
    "VENDOR": ("Vendor approval", 1, [
        ("bu_head", "Business Unit Head approval", "BU_HEAD", 1, None, 2, "Confirms the sourcing need."),
        ("finance_bank", "Finance banking verification", "FINANCE", 2, None, 2, "Verifies bank details against the confirmation letter."),
        ("quality_supplier", "Quality supplier qualification", "QRA", 2,
         {"all": [{"field": "supplier_category", "op": "in", "value": MANUFACTURER_CATEGORIES}]}, 3, "Checks quality certification."),
    ]),
    "COST_CENTER": ("Cost centre approval", 1, [
        ("bu_head", "Business Unit Head approval", "BU_HEAD", 1, None, 2, "Confirms ownership."),
        ("finance", "Finance structure approval", "FINANCE", 2, None, 2, "Confirms reporting structure."),
    ]),
}


def seed_reference(db: Session) -> dict[str, User]:
    for code, name, tz, order in COUNTRIES:
        db.add(Country(code=code, name=name, timezone=tz, display_order=order, is_illustrative=True))
    for code, name, desc in ENTITIES:
        db.add(BusinessEntity(code=code, name=name, description=desc))
    role_by_code = {}
    for code, name, desc, approver in ROLE_DEFINITIONS:
        role_by_code[code] = Role(code=code, name=name, description=desc, is_approver=approver)
        db.add(role_by_code[code])
    db.flush()
    pw = hash_password(get_settings().demo_password)
    users = {}
    for username, name, title, role_codes, entity, country, note in USERS:
        u = User(username=username, full_name=name, title=title, email=f"{username}@lives-one.example", password_hash=pw,
                 entity_code=entity, country_code=country, persona_note=note, roles=[role_by_code[r] for r in role_codes])
        db.add(u)
        users[username] = u
    db.flush()
    settings_service.ensure_defaults(db)

    for domain, (name, desc, fields) in FORMS.items():
        form = FormDefinition(domain=domain, name=name, description=desc, version=1)
        for i, f in enumerate(fields):
            form.fields.append(FieldDefinition(display_order=i * 10, **f))
        db.add(form)
    for domain, key, rtype, cond, cat, field_key, msg in VALIDATION_RULES:
        db.add(ValidationRule(domain=domain, rule_key=key, rule_type=rtype, condition=cond, attachment_category=cat, field_key=field_key, message=msg))
    for domain, (name, mdm_sla, steps) in WORKFLOWS.items():
        t = WorkflowTemplate(domain=domain, name=name, mdm_verification_sla_days=mdm_sla)
        for key, sname, role, stage, cond, sla, desc in steps:
            t.steps.append(WorkflowStep(step_key=key, name=sname, role_code=role, stage_order=stage, condition=cond, sla_days=sla, description=desc))
        db.add(t)
    db.flush()
    return users
