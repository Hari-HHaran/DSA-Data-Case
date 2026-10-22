"""Seeded MDM workflow history, produced by driving the real services with a back-dated clock.
All requests are synthetic (is_synthetic=True) and exist to populate the tracker, inbox, SLA and
turnaround metrics. Nothing here is Lives Group data."""
import hashlib
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import ApprovalTask, MdmRequest, RequestAttachment, User
from ..services import notifications, sap_service, settings_service, workflow
from ..services.clock import add_working_days, utcnow
from ..services.errors import ValidationFailed

PDF_BYTES = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
             b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj "
             b"4 0 obj<</Length 58>>stream\nBT /F1 12 Tf 20 70 Td (SYNTHETIC DEMO DOCUMENT) Tj ET\nendstream endobj "
             b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF")

FUTURE = (date.today() + timedelta(days=700)).isoformat()


def attach(db: Session, req: MdmRequest, user: User, category: str, at: datetime):
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex}.pdf"
    (settings.upload_dir / stored).write_bytes(PDF_BYTES)
    db.add(RequestAttachment(request_id=req.id, category=category, original_filename=f"synthetic-{category.lower()}.pdf", stored_filename=stored,
                             content_type="application/pdf", size_bytes=len(PDF_BYTES), sha256=hashlib.sha256(PDF_BYTES).hexdigest(),
                             uploaded_by_id=user.id, uploaded_at=at))
    db.flush()
    db.refresh(req)


def item_data(i: int, name: str, manufacturer: str, part: str, family: str, reg: str = "Class B", stock: str = "Yes") -> dict:
    d = {"item_name": name, "item_description": f"{name} (synthetic demo item)", "product_family": family, "item_category": "Consumable",
         "unit_of_measure": "BOX", "manufacturer": manufacturer, "manufacturer_part_no": part, "supplier_name": manufacturer,
         "regulatory_class": reg, "storage_condition": "Ambient", "stock_managed": stock, "standard_cost": str(20 + i), "lead_time_days": "21"}
    if reg in ("Class B", "Class C", "Class D"):
        d.update({"licence_number": f"SYN-LIC-{1000 + i}", "licence_expiry": FUTURE})
    return d


def customer_data(name: str, reg: str, country: str, segment: str = "Hospital", terms: str = "Net 30", bu: str = "Diagnostics (IVD)") -> dict:
    d = {"legal_name": name, "business_reg_no": reg, "customer_segment": segment, "business_unit": bu,
         "registered_address": f"1 Synthetic Avenue, {country}", "contact_person": "Procurement Desk",
         "contact_email": "procurement@example-customer.test", "contact_phone": "+65 6000 0000", "payment_terms": terms}
    if terms != "Cash in advance":
        d["credit_limit"] = "50000"
    return d


def vendor_data(name: str, reg: str, category: str = "Distributor") -> dict:
    return {"legal_name": name, "vendor_reg_no": reg, "supplier_category": category, "address": "8 Synthetic Industrial Park",
            "contact_person": "Accounts Receivable", "contact_email": "ar@example-vendor.test", "contact_phone": "+60 3 0000 0000",
            "payment_terms": "Net 45", "bank_name": "Synthetic Bank Bhd", "bank_account_no": "000-111222-333", "swift_code": "SYNTMYKL"}


def cc_data(name: str, code: str) -> dict:
    return {"cost_center_name": name, "cost_center_code": code, "business_unit": "Laboratory Solutions", "responsible_manager": "Daniel",
            "manager_email": "daniel@lives-one.example", "effective_date": "2026-11-01", "cost_classification": "Operating expense"}


DOCS = {"ITEM": ["REGULATORY_LICENCE"], "CUSTOMER": ["BUSINESS_REGISTRATION"], "VENDOR": ["BANK_CONFIRMATION"], "COST_CENTER": []}


class History:
    def __init__(self, db: Session, users: dict[str, User], rng):
        self.db, self.u, self.rng = db, users, rng
        self.now = utcnow().replace(second=0, microsecond=0)

    def wd(self, start: datetime, lo: float, hi: float) -> datetime:
        return add_working_days(start, round(float(self.rng.uniform(lo, hi)), 2))

    def draft(self, user: str, domain: str, data: dict, country: str, entity: str, at: datetime, docs: bool = True, dept: str = "") -> MdmRequest:
        u = self.u[user]
        req = workflow.create_draft(self.db, u, {"domain": domain, "entity_code": entity, "country_code": country, "department": dept,
                                                 "data": data, "is_synthetic": True}, at=at)
        if docs:
            for cat in DOCS[domain]:
                attach(self.db, req, u, cat, at)
        return req

    def check_and_submit(self, req: MdmRequest, at: datetime):
        u = req.requester
        workflow.run_duplicate_check(self.db, u, req, at=at)
        if req.duplicate_check_status in ("REVIEW_REQUIRED", "BLOCKED"):
            workflow.review_duplicates(self.db, u, req, "CONTINUE_WITH_JUSTIFICATION",
                                       "Different legal entity / product variant confirmed with the customer.", at=at)
        workflow.submit(self.db, u, req, at=at)

    def approver(self, role: str, req: MdmRequest) -> User:
        return next(x for x in notifications.users_with_role(self.db, role) if x.id != req.requester_id)

    def approve(self, req: MdmRequest, at: datetime, lo=0.3, hi=2.2, stop_after: int | None = None) -> datetime:
        """Approves pending tasks in time order. Returns the time of the last decision."""
        done = 0
        while req.status == "PENDING_APPROVAL":
            pending = [t for t in workflow.current_tasks(self.db, req) if t.status == "PENDING"]
            if not pending or (stop_after is not None and done >= stop_after):
                break
            plan = sorted((self.wd(t.activated_at, lo, hi), t) for t in pending)
            for when, t in plan:
                if stop_after is not None and done >= stop_after:
                    break
                workflow.decide(self.db, self.approver(t.role_code, req), t.id, "APPROVE", "Checked — OK", at=when)
                at = when
                done += 1
        return at

    def finish(self, req: MdmRequest, at: datetime) -> datetime:
        v = self.wd(at, 0.1, 0.9)
        workflow.mdm_verify(self.db, self.u["priya"], req, "VERIFY", "Fields verified against supporting documents", at=v)
        s = v + timedelta(minutes=4)
        sap_service.sync(self.db, self.u["priya"], req, at=s)
        return s

    def complete(self, user, domain, data, country, entity, start, dept="", blocked_first=False):
        req = self.draft(user, domain, data, country, entity, start, dept=dept, docs=not blocked_first)
        sub = start + timedelta(hours=float(self.rng.uniform(0.5, 6)))
        if blocked_first and DOCS[domain]:
            # Requestor tries to submit without the mandatory document: blocked before any approver sees it.
            try:
                workflow.submit(self.db, req.requester, req, at=start + timedelta(minutes=20))
            except ValidationFailed:
                pass
            for cat in DOCS[domain]:
                attach(self.db, req, req.requester, cat, sub - timedelta(minutes=10))
        if req.status == "DRAFT":
            self.check_and_submit(req, sub)
        last = self.approve(req, sub)
        if req.status == "MDM_VERIFICATION":
            self.finish(req, last)
        return req


def seed_history(db: Session, users: dict[str, User], rng) -> dict:
    h = History(db, users, rng)
    now = h.now
    created = []
    countries = ["SG", "MY", "ID", "TH", "VN"]
    # Completed requests across ~3 months — feeds turnaround metrics and the audit trail.
    items = [("Blood Collection Tube, EDTA 4 mL", "Vaculine Medical", "VCL-EDTA-4"), ("Urine Specimen Container 60 mL", "Specimate", "SPM-U60"),
             ("Rapid Antigen Test Cassette", "Quantadx Labs", "QDX-RAT-25"), ("Microplate, 96-well, sterile", "Lumenis Scientific", "LNS-MP96"),
             ("Glucose Reagent, 4 x 50 mL", "Quantadx Labs", "QDX-GLU-200"), ("Pipette Tips 200 µL, filtered", "Lumenis Scientific", "LNS-PT200F"),
             ("Calibrator Set, Lipid Panel", "Quantadx Labs", "QDX-CAL-LIP"), ("Swab, Flocked Nasopharyngeal", "Meditrans Biologics", "MTB-FNP-50")]
    custs = [("Lakeview Diagnostics Centre", "SG", "Laboratory"), ("Riverside Medical Group", "MY", "Hospital"), ("Garuda Health Laboratory", "ID", "Laboratory"),
             ("Chao Phraya Specialist Clinic", "TH", "Clinic"), ("Red River Diagnostics", "VN", "Laboratory"), ("Bayfront Children's Clinic", "SG", "Clinic"),
             ("Penang Hillside Hospital", "MY", "Hospital"), ("Surabaya Delta Laboratory", "ID", "Laboratory")]
    vendors = [("Northwind Labware Sdn Bhd", "MY20180011223"), ("Andaman Cold Chain Co., Ltd.", "TH0105559998887"), ("Pacific Reagent Trading Pte Ltd", "SG2016554433A")]
    ccs = [("Laboratory Solutions Vietnam", "LS-501"), ("Diagnostics Sales Indonesia", "DX-301"), ("Equipment Service Thailand", "ME-411")]
    plan = []
    for i, (n, m, part) in enumerate(items):
        plan.append(("amy" if i % 2 == 0 else "ben", "ITEM", item_data(i, n, m, part, f"Product {'ABC'[i % 3]}", reg=["Class B", "Class A", "Not regulated", "Class C"][i % 4],
                                                                         stock="Yes" if i % 3 else "No"), "SG", "SPD"))
    for i, (n, c, seg) in enumerate(custs):
        plan.append(("marcus" if i % 2 else "ben", "CUSTOMER", customer_data(n, f"{c}{20240000 + i * 37}X", c, seg,
                                                                                terms=["Net 30", "Cash in advance", "Net 60"][i % 3]), c, "QTS"))
    for i, (n, r) in enumerate(vendors):
        plan.append(("ben", "VENDOR", vendor_data(n, r), countries[i], "QTS"))
    for i, (n, code) in enumerate(ccs):
        plan.append(("ben", "COST_CENTER", cc_data(n, code), countries[2 + i], "QTG"))
    for i, (user, domain, data, country, entity) in enumerate(plan):
        start = now - timedelta(days=int(10 + (i * 83 / len(plan))), hours=int(rng.integers(0, 8)))
        start = start.replace(hour=int(rng.integers(1, 9)))  # 09:00–17:00 SGT ≈ 01:00–09:00 UTC
        created.append(h.complete(user, domain, data, country, entity, start, blocked_first=i % 5 == 1))

    # Rejected vendor (Finance found a mismatch).
    r = h.draft("ben", "VENDOR", vendor_data("Eastgate Medical Trading", "SG2020771122B"), "SG", "QTS", now - timedelta(days=24))
    h.check_and_submit(r, now - timedelta(days=24))
    h.approve(r, now - timedelta(days=24), stop_after=1)
    t = next(t for t in workflow.current_tasks(db, r) if t.status == "PENDING" and t.role_code == "FINANCE")
    workflow.decide(db, users["weijie"], t.id, "REJECT", "Bank confirmation letter is in a different company name than the vendor registration.",
                    at=add_working_days(t.activated_at, 0.7))

    # Returned for changes, corrected and resubmitted, then completed (cycle 2).
    r = h.draft("amy", "ITEM", item_data(31, "Sample Transport Bag, Biohazard", "Specimate", "SPM-BAG-01", "Product A"), "SG", "SPD", now - timedelta(days=17))
    h.check_and_submit(r, now - timedelta(days=17))
    t = next(t for t in workflow.current_tasks(db, r) if t.role_code == "QRA")
    workflow.decide(db, users["siti"], t.id, "REQUEST_CHANGES", "Licence evidence covers the 10-pack only; please upload the certificate for the 50-pack.",
                    at=add_working_days(t.activated_at, 0.6))
    fix_at = add_working_days(now - timedelta(days=17), 1.4)
    workflow.update_draft(db, users["amy"], r, {"data": {"item_description": "Biohazard sample transport bag, 50-pack (synthetic)"}}, at=fix_at)
    attach(db, r, users["amy"], "REGULATORY_LICENCE", fix_at)
    h.check_and_submit(r, fix_at)
    h.finish(r, h.approve(r, fix_at))

    # Amy: currently returned for changes (to demo correction).
    r = h.draft("amy", "ITEM", item_data(41, "Specimen Rack, 50-position", "Lumenis Scientific", "LNS-RK50", "Product C", reg="Class B"), "SG", "SPD",
                now - timedelta(days=4))
    h.check_and_submit(r, now - timedelta(days=4))
    t = next(t for t in workflow.current_tasks(db, r) if t.role_code == "QRA")
    workflow.decide(db, users["siti"], t.id, "REQUEST_CHANGES", "Regulatory class looks wrong: racks are usually Class A. Please confirm with the manufacturer's declaration.",
                    at=add_working_days(t.activated_at, 0.5))

    # In-flight approvals for the inbox: Wei Jie overdue / due soon, parallel item, sequential vendor, cost centre.
    pr_links = {}
    r = h.draft("marcus", "CUSTOMER", customer_data("Raffles Lakeside Clinic", "SG20250099R", "SG", "Clinic", "Net 30", "Life Science Tools (new BU)"), "SG", "QTG",
                add_working_days(now, -6))
    h.check_and_submit(r, add_working_days(now, -6))
    h.approve(r, add_working_days(now, -6), stop_after=1)  # BU Head approved; Finance overdue → reminder + escalation
    pr_links["Raffles Lakeside Clinic"] = r.id
    r = h.draft("marcus", "CUSTOMER", customer_data("Klang Riverside Laboratory", "MY20250123K", "MY", "Laboratory", "Net 45", "Life Science Tools (new BU)"), "MY",
                "QTG", add_working_days(now, -1.4))
    h.check_and_submit(r, add_working_days(now, -1.4))
    pr_links["Klang Riverside Laboratory"] = r.id
    r = h.draft("ben", "CUSTOMER", customer_data("Sentosa Wellness Clinic", "SG20250777S", "SG", "Clinic", "Net 30"), "SG", "SPD", add_working_days(now, -0.6))
    h.check_and_submit(r, add_working_days(now, -0.6))
    r = h.draft("ben", "ITEM", item_data(51, "Haematology Reagent Pack, 5-part diff", "Quantadx Labs", "QDX-HRP-5D", "Product B", reg="Class C"), "MY", "QTS",
                add_working_days(now, -1.2))
    h.check_and_submit(r, add_working_days(now, -1.2))
    h.approve(r, add_working_days(now, -1.2), stop_after=1)  # one parallel approval done, one pending
    r = h.draft("ben", "VENDOR", vendor_data("Mekong Medical Logistics JSC", "VN0312345678", "Logistics / service provider"), "VN", "QTS", add_working_days(now, -3.5))
    h.check_and_submit(r, add_working_days(now, -3.5))
    h.approve(r, add_working_days(now, -3.5), stop_after=1)
    r = h.draft("ben", "COST_CENTER", cc_data("Life Science Tools Singapore", "LT-101"), "SG", "QTG", add_working_days(now, -2.2))
    h.check_and_submit(r, add_working_days(now, -2.2))

    # Priya's queue: approved and awaiting verification (one of them a Marcus prospect).
    r = h.draft("marcus", "CUSTOMER", customer_data("Chonburi Bayside Laboratory", "TH0105567890", "TH", "Laboratory", "Cash in advance", "Life Science Tools (new BU)"),
                "TH", "QTG", add_working_days(now, -2.5))
    h.check_and_submit(r, add_working_days(now, -2.5))
    h.approve(r, add_working_days(now, -2.5), lo=0.2, hi=0.8)
    pr_links["Chonburi Bayside Laboratory"] = r.id
    r = h.draft("amy", "ITEM", item_data(61, "Cryo Storage Box, 81-place", "Lumenis Scientific", "LNS-CB81", "Product C", reg="Not regulated", stock="Yes"),
                "SG", "SPD", add_working_days(now, -1.8))
    h.check_and_submit(r, add_working_days(now, -1.8))
    h.approve(r, add_working_days(now, -1.8), lo=0.1, hi=0.6)

    # A failed SAP creation awaiting retry.
    r = h.draft("ben", "VENDOR", vendor_data("Borneo Scientific Supplies Sdn Bhd", "MY20199988776"), "MY", "QTS", add_working_days(now, -3))
    h.check_and_submit(r, add_working_days(now, -3))
    last = h.approve(r, add_working_days(now, -3), lo=0.1, hi=0.7)
    settings_service.set_value(db, "sap.mock_fail_next", 1)
    h.finish(r, last)
    settings_service.set_value(db, "sap.mock_fail_next", 0)

    # Drafts.
    h.draft("marcus", "CUSTOMER", {"legal_name": "Quang Ninh Coastal Hospital", "customer_segment": "Hospital"}, "VN", "QTG",
            add_working_days(now, -0.3), docs=False)
    # Marcus tried to create NUH again — duplicate detected and the existing record reused.
    r = h.draft("marcus", "CUSTOMER", customer_data("Natl University Hosp.", "SG19850001N", "SG", "Hospital"), "SG", "QTG", now - timedelta(days=9))
    workflow.run_duplicate_check(db, users["marcus"], r, at=now - timedelta(days=9))
    if r.duplicate_check_status in ("REVIEW_REQUIRED", "BLOCKED"):
        workflow.review_duplicates(db, users["marcus"], r, "REUSE_EXISTING", "Existing NUH record found — no new record needed.",
                                   at=now - timedelta(days=9) + timedelta(minutes=3))
    db.flush()
    return {"requests": db.query(MdmRequest).count(), "pr_links": pr_links}
