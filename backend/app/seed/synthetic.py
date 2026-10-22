"""Synthetic demonstration data — NOT Lives Group data.

Generates (seeded, reproducible):
- canonical customer master records across five illustrative countries, with source-system aliases
  created by different business entities (the duplicate problem described in the brief);
- items, vendors and cost centres;
- 12 months (Oct 2025 – Sep 2026) of customer purchasing events: purchase orders with explicit
  statuses, purchase requests (incl. ones waiting on MDM set-up) and general enquiries, plus
  deliberate data-quality defects (double-loaded lines, country spelling variants, missing products,
  invalid quantities).

Planted patterns (so insights genuinely emerge from data, not hardcoded claims): country × family
trends, Product C under-adoption among peers, customers who stop or reduce ordering, customers
starting mid-window, and a product not registered in one country.
"""
from dataclasses import dataclass, field
from datetime import date

import numpy as np
from sqlalchemy.orm import Session

from ..models import CanonicalRecordMapping, Customer, MasterRecord, MasterRecordAlias, Product, PurchasingEvent, User
from ..services.duplicates import name_similarity, normalise
from .reference import ACCOUNT_OWNER_BY_COUNTRY

MONTHS = [(2025, m) for m in range(10, 13)] + [(2026, m) for m in range(1, 10)]  # 12 months
FAMILY_ENTITY = {"A": "SPD", "B": "QTS", "C": "QTG"}  # assumed primary entity per product family

CUSTOMER_NAMES = {
    "SG": ["National University Hospital", "Meridian General Hospital", "Lumen Diagnostic Laboratory", "Harbourview Specialist Hospital",
           "Orchid Pathology Laboratory", "Kestrel Family Clinic", "Straitsgate Biomedical Research Institute", "Vantage Medical Centre",
           "Sapphire Women's Hospital", "Northpoint Community Hospital", "Brightwell Clinical Laboratory", "Evergreen Medical Clinic",
           "Pioneer Cardiac Hospital", "Lionsgate Research Laboratory"],
    "MY": ["Selangor Meridian Hospital", "Klang Valley Diagnostic Laboratory", "Penang Harbour Medical Centre", "Johor Southern Specialist Hospital",
           "Ipoh Lumen Clinic", "Kuching River Hospital", "Melaka Heritage Laboratory", "Putra Biomedical Research Institute",
           "Sabah Coastal Hospital", "Cyberjaya Health Clinic", "Seremban Valley Pathology Laboratory", "Kedah Northern Medical Centre"],
    "ID": ["Jakarta Medika Hospital", "Surabaya Sentosa Laboratory", "Bandung Harapan Hospital", "Bali Dharma Clinic",
           "Medan Sejahtera Medical Centre", "Semarang Lumen Diagnostic Laboratory", "Yogyakarta Life Sciences Research Institute",
           "Makassar Bahari Hospital", "Palembang Sehat Clinic", "Batam Island Laboratory", "Tangerang Mitra Hospital", "Bogor Biotek Research Institute"],
    "TH": ["Bangkok Meridian Hospital", "Chiang Mai Lanna Laboratory", "Phuket Andaman Hospital", "Khon Kaen Isan Medical Centre",
           "Pattaya Coastal Clinic", "Siam Biomedical Research Institute", "Nonthaburi Lumen Diagnostic Laboratory", "Hat Yai Southern Hospital",
           "Rayong Eastern Clinic", "Udon Thani Pathology Laboratory"],
    "VN": ["Saigon Meridian Hospital", "Hanoi Capital Laboratory", "Da Nang Coastal Hospital", "Hue Imperial Medical Centre",
           "Can Tho Delta Clinic", "Mekong Biomedical Research Institute", "Hai Phong Harbour Hospital", "Nha Trang Lumen Diagnostic Laboratory",
           "Vung Tau Seaside Clinic", "Bien Hoa Pathology Laboratory"],
}
LEGAL_SUFFIX = {"SG": "Pte Ltd", "MY": "Sdn Bhd", "ID": "PT", "TH": "Co., Ltd.", "VN": "JSC"}
COUNTRY_VARIANTS = {
    "SG": [("Singapore", .86), ("SG", .08), ("SINGAPORE", .04), ("S'pore", .02)],
    "MY": [("Malaysia", .86), ("MY", .08), ("M'sia", .04), ("MALAYSIA", .02)],
    "ID": [("Indonesia", .88), ("ID", .07), ("Indonesia ", .03), ("INDO", .02)],
    "TH": [("Thailand", .88), ("TH", .08), ("Thai", .04)],
    "VN": [("Vietnam", .80), ("VN", .08), ("Viet Nam", .10), ("VIETNAM", .02)],
}
# Monthly compound trend per country × family (planted; recovered by analytics, never displayed as fact).
TRENDS = {
    "SG": {"A": 0.010, "B": 0.032, "C": 0.000},
    "MY": {"A": 0.018, "B": 0.008, "C": 0.050},
    "ID": {"A": 0.045, "B": 0.020, "C": 0.012},
    "TH": {"A": -0.028, "B": 0.000, "C": 0.015},
    "VN": {"A": 0.030, "B": 0.062, "C": 0.020},
}
ADOPTION = {  # probability a customer of this segment buys the family
    "HOSPITAL": {"A": .92, "B": .80, "C": .60}, "LABORATORY": {"A": .80, "B": .92, "C": .62},
    "CLINIC": {"A": .90, "B": .35, "C": 0.0}, "RESEARCH": {"A": .60, "B": .75, "C": .55},
}
BASE_QTY = {  # mean units per order line
    "HOSPITAL": {"A": 220, "B": 38, "C": 5}, "LABORATORY": {"A": 160, "B": 55, "C": 6},
    "CLINIC": {"A": 55, "B": 9, "C": 1}, "RESEARCH": {"A": 80, "B": 28, "C": 3},
}
PRODUCTS = [
    ("A-100", "Product A · SKU A-100", "A", "Consumable (assumed)", "RECURRING", "box", ["SG", "MY", "ID", "TH", "VN"], 42.0),
    ("A-200", "Product A · SKU A-200", "A", "Consumable (assumed)", "RECURRING", "box", ["SG", "MY", "ID", "TH", "VN"], 55.0),
    ("B-100", "Product B · SKU B-100", "B", "Reagent kit (assumed)", "RECURRING", "kit", ["SG", "MY", "ID", "TH", "VN"], 310.0),
    ("B-200", "Product B · SKU B-200", "B", "Reagent kit (assumed)", "RECURRING", "kit", ["SG", "MY", "TH", "VN"], 365.0),
    ("C-100", "Product C · SKU C-100", "C", "Laboratory solution (assumed)", "PERIODIC", "unit", ["SG", "MY", "ID", "TH"], 4200.0),
]


def segment_of(name: str) -> str:
    n = name.lower()
    if "research" in n:
        return "RESEARCH"
    if "clinic" in n:
        return "CLINIC"
    if "laboratory" in n or "pathology" in n or "diagnostic" in n:
        return "LABORATORY"
    return "HOSPITAL"


def alias_variants(name: str, country: str, rng) -> list[str]:
    abbrev = (name.replace("Hospital", "Hosp.").replace("Laboratory", "Lab").replace("Medical Centre", "Med. Ctr")
              .replace("Research Institute", "Research Inst.").replace("Diagnostic", "Diag."))
    suffix = LEGAL_SUFFIX[country]
    legal = f"PT {name}" if country == "ID" else f"{name} {suffix}"
    return [abbrev, legal, name.upper(), f"{abbrev} ({country})"]


@dataclass
class CanonicalCustomer:
    key: int
    name: str
    country: str
    segment: str
    size: float
    families: set
    start: int = 0
    stops: dict = field(default_factory=dict)      # family -> month index after which ordering stops
    declines: dict = field(default_factory=dict)   # family -> month index from which volume drops
    c_period: int = 3
    c_phase: int = 0
    master: MasterRecord | None = None
    sources: dict = field(default_factory=dict)    # entity -> Customer


def build_customers(rng) -> list[CanonicalCustomer]:
    out = []
    k = 0
    for country, names in CUSTOMER_NAMES.items():
        for name in names:
            seg = segment_of(name)
            fams = {f for f in "ABC" if rng.random() < ADOPTION[seg][f]}
            if not fams:
                fams = {"A"}
            c = CanonicalCustomer(k, name, country, seg, float(rng.lognormal(0, 0.45)), fams,
                                  c_period=int(rng.choice([2, 3, 3, 4])), c_phase=int(rng.integers(0, 3)))
            if rng.random() < 0.08:
                c.start = int(rng.integers(3, 7))  # new customer ramping up mid-window
            out.append(c)
            k += 1
    # The NUH naming scenario: guarantee it buys all three families through three entities.
    out[0].families = {"A", "B", "C"}
    out[0].size = 2.2
    # Planted retention signals: customers who stop ordering a recurring family, or reduce sharply.
    recurring = [(c, f) for c in out[1:] for f in sorted(c.families) if f in "AB" and c.start == 0]
    idx = rng.choice(len(recurring), size=11, replace=False)
    for j, i in enumerate(idx):
        c, f = recurring[i]
        if j < 6:
            c.stops[f] = int(rng.integers(7, 10))
        else:
            c.declines[f] = 9
    return out


def seed_master_and_purchasing(db: Session, rng, users: dict[str, User]) -> dict:
    customers = build_customers(rng)
    reviewer = users["priya"]

    # Canonical customer master records (verified "golden" records).
    for c in customers:
        reg = f"{c.country}{rng.integers(10**7, 10**8)}{'ABCDEFGHJK'[c.key % 10]}"
        mr = MasterRecord(record_code=f"CUST-{c.key + 1:06d}", domain="CUSTOMER", name=c.name, normalized_name=normalise(c.name),
                          country_code=c.country, entity_code=FAMILY_ENTITY[sorted(c.families)[0]], identifier=reg,
                          attributes={"customer_segment": c.segment.title(), "address": f"{int(rng.integers(1, 400))} {c.name.split()[0]} Road, {c.country}"},
                          sap_code=f"C{c.key + 20001}", source="SYNTHETIC_SEED")
        db.add(mr)
        c.master = mr
    db.flush()

    # Source customer records: each entity that sells to the customer keyed its own BP, sometimes under a variant name.
    src_n = 0
    mappings = []
    for c in customers:
        for fam in sorted(c.families):
            ent = FAMILY_ENTITY[fam]
            if ent in c.sources:
                continue
            first = not c.sources
            variants = alias_variants(c.name, c.country, rng)
            if c.key == 0:
                name = {"SPD": "National University Hospital", "QTS": "NUH", "QTG": "Natl Univ. Hospital (S)"}[ent]
            elif first or rng.random() < 0.45:
                name = c.name
            else:
                name = variants[int(rng.integers(0, len(variants)))]
            src_n += 1
            cust = Customer(source_code=f"{ent}-{src_n:05d}", source_entity=ent, name=name, country_code=c.country,
                            segment=c.segment, account_owner_id=users[ACCOUNT_OWNER_BY_COUNTRY[c.country]].id)
            db.add(cust)
            c.sources[ent] = cust
            if name != c.name:
                db.add(MasterRecordAlias(master_record=c.master, alias_name=name, source_system=ent, source_code=cust.source_code))
            mappings.append((c, cust, name))
    db.flush()

    # Canonical mappings. Exact names auto-confirm; fuzzy aliases mostly confirmed, a few left PROPOSED for review.
    proposed_left = 0
    for c, cust, name in mappings:
        if name == c.name:
            conf, method, status = 1.0, "EXACT_NAME", "CONFIRMED"
        else:
            score, _ = name_similarity(name, c.name)
            conf, method = round(score / 100, 2), "FUZZY_NAME"
            leave = (c.key == 0 and cust.source_entity == "QTG") or (proposed_left < 5 and rng.random() < 0.25)
            status = "PROPOSED" if leave else "CONFIRMED"
            proposed_left += leave
        db.add(CanonicalRecordMapping(source_customer_id=cust.id, master_record_id=c.master.id, alias_name=name, confidence=conf,
                                      method=method, review_status=status, reviewer_id=reviewer.id if status == "CONFIRMED" else None,
                                      reviewed_at=date(2025, 9, 15) if status == "CONFIRMED" else None))
    db.flush()

    # Products.
    products = {}
    for code, name, fam, cat, pattern, unit, reg, price in PRODUCTS:
        p = Product(code=code, name=name, family=fam, category=cat, purchase_pattern=pattern, unit=unit, registered_countries=reg)
        db.add(p)
        products[code] = (p, price)
    db.flush()

    events = _generate_events(rng, customers, products)
    db.bulk_insert_mappings(PurchasingEvent, events)
    db.flush()
    return {"customers": customers, "events": len(events)}


def _country_text(rng, country: str) -> str:
    vals, probs = zip(*COUNTRY_VARIANTS[country])
    return str(rng.choice(vals, p=np.array(probs) / sum(probs)))


def _day(rng, y, m, lo=1, hi=28) -> date:
    return date(y, m, int(rng.integers(lo, hi + 1)))


def _generate_events(rng, customers, products) -> list[dict]:
    rows = []
    po_n = pr_n = enq_n = 0
    skus = {f: [code for code, (p, _) in products.items() if p.family == f] for f in "ABC"}
    for c in customers:
        pref = {f: skus[f][int(rng.integers(0, len(skus[f])))] for f in "ABC"}
        # Respect registration: never sell an unregistered SKU in a country.
        for f in "ABC":
            ok = [s for s in skus[f] if c.country in products[s][0].registered_countries]
            if pref[f] not in ok and ok:
                pref[f] = ok[0]
        fams = {f for f in c.families if any(c.country in products[s][0].registered_countries for s in skus[f])}
        for t, (y, m) in enumerate(MONTHS):
            if t < c.start:
                continue
            lines = []
            for f in sorted(fams):
                if f in c.stops and t > c.stops[f]:
                    continue
                if f == "C" and (t + c.c_phase) % c.c_period != 0:
                    continue
                if f in "AB" and rng.random() < 0.03:
                    continue  # occasional skipped month
                ramp = min(1.0, 0.4 + 0.2 * (t - c.start)) if c.start else 1.0
                mean = BASE_QTY[c.segment][f] * c.size * ((1 + TRENDS[c.country][f]) ** t) * ramp
                if f in c.declines and t >= c.declines[f]:
                    mean *= 0.4
                qty = max(1, int(round(rng.gamma(20, mean / 20))))  # cv ≈ 0.22 per customer line
                lines.append((f, qty))
            if not lines:
                continue
            ent_lines: dict[str, list] = {}
            for f, q in lines:
                ent_lines.setdefault(FAMILY_ENTITY[f], []).append((f, q))
            for ent, items in ent_lines.items():
                cust = c.sources.get(ent)
                po_n += 1
                txn = f"PO-{ent}-{y % 100:02d}{m:02d}-{po_n:05d}"
                d = _day(rng, y, m)
                recent = t >= len(MONTHS) - 2
                po_status = "CONFIRMED" if recent else "FULFILLED"
                cancelled = rng.random() < 0.05
                country_txt = _country_text(rng, c.country)
                for ln, (f, q) in enumerate(items, 1):
                    code = pref[f]
                    status = "CANCELLED" if cancelled else po_status
                    product_code, quantity = code, float(q)
                    r = rng.random()
                    if not cancelled and r < 0.015:
                        status = "RETURNED"
                    elif not cancelled and r < 0.03:
                        status, quantity = "INCOMPLETE", None
                    elif not cancelled and r < 0.037:
                        product_code = None  # missing product code in source extract
                    elif not cancelled and r < 0.042:
                        quantity = 0.0  # invalid quantity
                    row = dict(source_txn_id=txn, line_no=ln, event_type="PURCHASE_ORDER", status=status, event_date=d,
                               customer_id=cust.id, raw_customer_name=cust.name, product_code=product_code, raw_country=country_txt,
                               entity_code=ent, quantity=quantity, unit_price=products[code][1])
                    rows.append(row)
                    if rng.random() < 0.02:
                        rows.append(dict(row))  # double-loaded line from a second spreadsheet extract
                if cancelled:  # customer re-places the order: true demand is unchanged
                    po_n += 1
                    for ln, (f, q) in enumerate(items, 1):
                        rows.append(dict(source_txn_id=f"PO-{ent}-{y % 100:02d}{m:02d}-{po_n:05d}", line_no=ln, event_type="PURCHASE_ORDER",
                                         status=po_status, event_date=_day(rng, y, m, min(d.day + 1, 28), 28), customer_id=cust.id,
                                         raw_customer_name=cust.name, product_code=pref[f], raw_country=country_txt, entity_code=ent,
                                         quantity=float(q), unit_price=products[pref[f]][1]))
            # Purchase requests (need processing/confirmation) and general enquiries — demand signals, not orders.
            any_cust = next(iter(c.sources.values()))
            for _ in range(int(rng.poisson(0.25))):
                pr_n += 1
                f = str(rng.choice(sorted(c.families)))
                rows.append(dict(source_txn_id=f"PR-{pr_n:05d}", line_no=1, event_type="PURCHASE_REQUEST",
                                 status=str(rng.choice(["CONVERTED", "OPEN", "LAPSED"], p=[.6, .25, .15])), event_date=_day(rng, y, m),
                                 customer_id=any_cust.id, raw_customer_name=any_cust.name, product_code=pref[f], raw_country=_country_text(rng, c.country),
                                 entity_code=FAMILY_ENTITY[f], quantity=float(max(1, int(rng.gamma(4, BASE_QTY[c.segment][f] / 4 + 1)))), unit_price=None))
            for _ in range(int(rng.poisson(0.45))):
                enq_n += 1
                missing = [f for f in "ABC" if f not in c.families and ADOPTION[c.segment][f] > 0]
                f = str(rng.choice(missing)) if missing and rng.random() < 0.55 else str(rng.choice(list("ABC")))
                rows.append(dict(source_txn_id=f"ENQ-{enq_n:05d}", line_no=1, event_type="ENQUIRY", status=str(rng.choice(["OPEN", "CLOSED"], p=[.3, .7])),
                                 event_date=_day(rng, y, m), customer_id=any_cust.id, raw_customer_name=any_cust.name, product_code=skus[f][0],
                                 raw_country=_country_text(rng, c.country), entity_code=FAMILY_ENTITY[f], quantity=None, unit_price=None))
    return rows


PROSPECTS = [  # Purchase requests from customers who do not yet exist in master data (linked to MDM set-up requests).
    ("Raffles Lakeside Clinic", "SG", "A"), ("Klang Riverside Laboratory", "MY", "B"), ("Lombok Harapan Clinic", "ID", "A"),
    ("Chonburi Bayside Laboratory", "TH", "B"), ("Quang Ninh Coastal Hospital", "VN", "A"),
]


def prospect_events(rng, mdm_links: dict[str, int]) -> list[dict]:
    rows = []
    for i, (name, country, fam) in enumerate(PROSPECTS, 1):
        for j in range(2):
            rows.append(dict(source_txn_id=f"PR-NEW-{i:03d}-{j + 1}", line_no=1, event_type="PURCHASE_REQUEST", status="PENDING_MDM_SETUP",
                             event_date=date(2026, 8 + j, int(rng.integers(3, 27))), customer_id=None, raw_customer_name=name,
                             product_code=f"{fam}-100", raw_country=_country_text(rng, country), entity_code=FAMILY_ENTITY[fam],
                             quantity=float(int(rng.integers(20, 120))), unit_price=None, linked_mdm_request_id=mdm_links.get(name)))
    return rows


def seed_other_master_data(db: Session) -> None:
    items = [
        ("ITEM-000001", "Viral Transport Medium Kit, 3 mL", "MTB-VTM-3ML", {"manufacturer": "Meditrans Biologics", "unit_of_measure": "KIT", "product_family": "Product A", "regulatory_class": "Class A"}),
        ("ITEM-000002", "Sterile Specimen Collection Swab", "MTB-SW-100", {"manufacturer": "Meditrans Biologics", "unit_of_measure": "BOX", "product_family": "Product A", "regulatory_class": "Class A"}),
        ("ITEM-000003", "Immunoassay Reagent Pack (100 tests)", "QDX-IRP-100", {"manufacturer": "Quantadx Labs", "unit_of_measure": "KIT", "product_family": "Product B", "regulatory_class": "Class B"}),
        ("ITEM-000004", "Haematology Control Set, Level 1-3", "QDX-HCS-3", {"manufacturer": "Quantadx Labs", "unit_of_measure": "KIT", "product_family": "Product B", "regulatory_class": "Class B"}),
        ("ITEM-000005", "Benchtop Analyser Service Module", "LNS-BAS-01", {"manufacturer": "Lumenis Scientific", "unit_of_measure": "EA", "product_family": "Product C", "regulatory_class": "Class C"}),
        ("ITEM-000006", "Nitrile Examination Gloves, Medium", "SFG-NIT-M", {"manufacturer": "Safeguard Medical", "unit_of_measure": "BOX", "product_family": "Other", "regulatory_class": "Class A"}),
        ("ITEM-000007", "PCR Master Mix, 2x (500 reactions)", "QDX-PCR-500", {"manufacturer": "Quantadx Labs", "unit_of_measure": "KIT", "product_family": "Product B", "regulatory_class": "Class B"}),
        ("ITEM-000008", "Cryogenic Storage Vials, 2 mL", "LNS-CRV-2", {"manufacturer": "Lumenis Scientific", "unit_of_measure": "PACK", "product_family": "Product A", "regulatory_class": "Not regulated"}),
    ]
    for code, name, ident, attrs in items:
        db.add(MasterRecord(record_code=code, domain="ITEM", name=name, normalized_name=normalise(name), country_code="SG", entity_code="SPD",
                            identifier=ident, attributes=attrs, sap_code=f"I{code[-4:]}", source="SYNTHETIC_SEED"))
    vendors = [
        ("VEND-000001", "Meditrans Biologics Pte Ltd", "SG2015123456M", "SG"), ("VEND-000002", "Quantadx Labs Sdn Bhd", "MY201901023456", "MY"),
        ("VEND-000003", "Lumenis Scientific Co., Ltd.", "TH0105551234567", "TH"), ("VEND-000004", "Safeguard Medical Supplies Pte Ltd", "SG2009876543K", "SG"),
        ("VEND-000005", "Coldchain Express Logistics", "SG2018765432C", "SG"),
    ]
    for code, name, ident, cc in vendors:
        db.add(MasterRecord(record_code=code, domain="VENDOR", name=name, normalized_name=normalise(name), country_code=cc, entity_code="QTS",
                            identifier=ident, attributes={"address": f"Synthetic address, {cc}"}, sap_code=f"V{code[-4:]}", source="SYNTHETIC_SEED"))
    centres = [("CC-000001", "Diagnostics Sales Singapore", "DX-101"), ("CC-000002", "Laboratory Solutions Malaysia", "LS-201"),
               ("CC-000003", "Regional Marketing", "MK-300"), ("CC-000004", "Medical Equipment Service", "ME-410")]
    for code, name, ident in centres:
        db.add(MasterRecord(record_code=code, domain="COST_CENTER", name=name, normalized_name=normalise(name), country_code="SG",
                            entity_code="SPD", identifier=ident, attributes={}, sap_code=ident.replace("-", ""), source="SYNTHETIC_SEED"))
    db.flush()
