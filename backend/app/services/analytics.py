"""Regional purchasing analytics.

Pipeline (raw purchasing_events are never modified):
 1 load raw events                      5 apply reviewed (CONFIRMED) canonical customer mappings
 2 normalise country & product codes    6 drop double-loaded source lines (keep first)
 3 validate required fields             7 classify each line under the inclusion policy
 4 restrict to the stated window        8 aggregate by month × country × product family

INCLUSION POLICY — the main demand measure counts only purchase-order lines with status CONFIRMED or
FULFILLED, a known customer, a known product and a positive quantity. Cancelled, returned and
incomplete orders, enquiries, purchase requests (incl. ones awaiting MDM set-up) and MDM set-up
requests are reported separately and never inflate confirmed demand. Returned lines are excluded
in full (conservative; no partial-return data exists in the synthetic set).
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CanonicalRecordMapping, Country, Customer, MdmRequest, Product, PurchasingEvent
from . import settings_service

INCLUDED = "CONFIRMED_DEMAND"
REASONS = {
    "DUPLICATE_LINE": ("Data quality", "Duplicate source line (same PO and line loaded twice)"),
    "UNKNOWN_COUNTRY": ("Data quality", "Country could not be normalised"),
    "UNKNOWN_PRODUCT": ("Data quality", "Missing or unknown product code"),
    "UNKNOWN_CUSTOMER": ("Data quality", "Customer not in master data"),
    "INVALID_QUANTITY": ("Data quality", "Quantity missing, zero or negative"),
    "OUT_OF_WINDOW": ("Policy", "Outside the stated analysis window"),
    "CANCELLED": ("Policy", "Cancelled purchase order"),
    "RETURNED": ("Policy", "Returned purchase order line"),
    "INCOMPLETE": ("Policy", "Incomplete purchase order (not confirmed)"),
    "ENQUIRY": ("Policy", "General enquiry — not committed demand"),
    "PURCHASE_REQUEST": ("Policy", "Purchase request — not yet a confirmed order"),
    "PENDING_MDM_SETUP": ("Policy", "Purchase request waiting on customer MDM set-up"),
}
COUNTRY_EXTRA_ALIASES = {"S'PORE": "SG", "M'SIA": "MY", "VIET NAM": "VN", "INDO": "ID", "THAI": "TH"}
FAMILY_LABEL = {"A": "Product A", "B": "Product B", "C": "Product C"}


@dataclass
class Prepared:
    df: pd.DataFrame          # every raw row with classification columns
    months: list[str]         # stated window, YYYY-MM
    countries: list[dict]


def window(db: Session) -> tuple[str, str]:
    return settings_service.get(db, "analytics.window_start"), settings_service.get(db, "analytics.window_end")


def month_range(start: str, end: str) -> list[str]:
    return [str(p) for p in pd.period_range(start, end, freq="M")]


def _country_map(db: Session) -> tuple[dict, list[dict]]:
    countries = db.execute(select(Country).order_by(Country.display_order)).scalars().all()
    m = {}
    for c in countries:
        m[c.code.upper()] = c.code
        m[c.name.upper()] = c.code
    m.update(COUNTRY_EXTRA_ALIASES)
    return m, [{"code": c.code, "name": c.name, "illustrative": c.is_illustrative} for c in countries]


def canonical_lookup(db: Session, use_mappings: bool = True) -> pd.DataFrame:
    custs = pd.DataFrame([{"customer_id": c.id, "source_name": c.name, "segment": c.segment, "source_entity": c.source_entity,
                           "owner_id": c.account_owner_id, "cust_country": c.country_code}
                          for c in db.execute(select(Customer)).scalars()])
    if custs.empty:
        return custs
    custs["canonical_key"] = "SRC-" + custs["customer_id"].astype(str)
    custs["canonical_name"] = custs["source_name"]
    custs["master_record_id"] = np.nan
    if use_mappings:
        maps = db.execute(select(CanonicalRecordMapping).where(CanonicalRecordMapping.is_current.is_(True),
                                                               CanonicalRecordMapping.review_status == "CONFIRMED")).scalars().all()
        by_src = {m.source_customer_id: m for m in maps}
        for i, row in custs.iterrows():
            m = by_src.get(row["customer_id"])
            if m:
                custs.at[i, "canonical_key"] = f"MR-{m.master_record_id}"
                custs.at[i, "canonical_name"] = m.master_record.name
                custs.at[i, "master_record_id"] = m.master_record_id
    return custs


def prepare(db: Session, use_mappings: bool = True) -> Prepared:
    start, end = window(db)
    months = month_range(start, end)
    cmap, countries = _country_map(db)
    products = {p.code: p.family for p in db.execute(select(Product)).scalars()}
    rows = db.execute(select(
        PurchasingEvent.id, PurchasingEvent.source_txn_id, PurchasingEvent.line_no, PurchasingEvent.event_type, PurchasingEvent.status,
        PurchasingEvent.event_date, PurchasingEvent.customer_id, PurchasingEvent.raw_customer_name, PurchasingEvent.product_code,
        PurchasingEvent.raw_country, PurchasingEvent.entity_code, PurchasingEvent.quantity, PurchasingEvent.unit_price,
        PurchasingEvent.linked_mdm_request_id,
    ).order_by(PurchasingEvent.id)).mappings().all()
    df = pd.DataFrame(rows)
    if df.empty:
        return Prepared(df, months, countries)
    df["country_code"] = df["raw_country"].fillna("").str.strip().str.upper().map(cmap)
    df["family"] = df["product_code"].map(products)
    df["month"] = pd.to_datetime(df["event_date"]).dt.strftime("%Y-%m")
    lookup = canonical_lookup(db, use_mappings)
    df = df.merge(lookup[["customer_id", "canonical_key", "canonical_name", "segment", "master_record_id", "owner_id"]],
                  on="customer_id", how="left")

    dup = df.duplicated(subset=["event_type", "source_txn_id", "line_no"], keep="first")
    reason = pd.Series(INCLUDED, index=df.index, dtype=object)

    def put(mask, code):
        nonlocal reason
        reason = reason.where(~(mask & (reason == INCLUDED)), code)

    is_po = df["event_type"] == "PURCHASE_ORDER"
    put(dup, "DUPLICATE_LINE")
    put(df["country_code"].isna(), "UNKNOWN_COUNTRY")
    put(~df["month"].isin(months), "OUT_OF_WINDOW")
    put(df["event_type"] == "ENQUIRY", "ENQUIRY")
    put((df["event_type"] == "PURCHASE_REQUEST") & (df["status"] == "PENDING_MDM_SETUP"), "PENDING_MDM_SETUP")
    put(df["event_type"] == "PURCHASE_REQUEST", "PURCHASE_REQUEST")
    put(is_po & (df["status"] == "CANCELLED"), "CANCELLED")
    put(is_po & (df["status"] == "RETURNED"), "RETURNED")
    put(is_po & (df["status"] == "INCOMPLETE"), "INCOMPLETE")
    put(is_po & df["family"].isna(), "UNKNOWN_PRODUCT")
    put(is_po & df["canonical_key"].isna(), "UNKNOWN_CUSTOMER")
    put(is_po & ~(df["quantity"].fillna(0) > 0), "INVALID_QUANTITY")
    put(is_po & ~df["status"].isin(["CONFIRMED", "FULFILLED"]), "INCOMPLETE")
    df["reason"] = reason
    df["included"] = df["reason"] == INCLUDED
    return Prepared(df, months, countries)


# ---------------------------------------------------------------- filters & metrics

def apply_filters(p: Prepared, f: dict) -> tuple[pd.DataFrame, list[str]]:
    df = p.df[p.df["included"]]
    months = [m for m in p.months if (not f.get("start") or m >= f["start"]) and (not f.get("end") or m <= f["end"])]
    df = df[df["month"].isin(months)]
    if f.get("countries"):
        df = df[df["country_code"].isin(f["countries"])]
    if f.get("families"):
        df = df[df["family"].isin(f["families"])]
    if f.get("entities"):
        df = df[df["entity_code"].isin(f["entities"])]
    if f.get("customer"):
        df = df[df["canonical_key"] == f["customer"]]
    if f.get("status") in ("CONFIRMED", "FULFILLED"):
        df = df[df["status"] == f["status"]]
    return df, months


def growth(values_by_month: pd.Series, months: list[str]) -> float | None:
    """Growth = (sum of last 3 months − sum of preceding 3 months) / sum of preceding 3 months."""
    if len(months) < 6:
        return None
    v = values_by_month.reindex(months, fill_value=0)
    last, prev = v.iloc[-3:].sum(), v.iloc[-6:-3].sum()
    if prev <= 0:
        return None
    return round(float((last - prev) / prev), 4)


def _po_count(df: pd.DataFrame) -> int:
    return int(df.drop_duplicates(["source_txn_id"]).shape[0])


def overview(db: Session, f: dict) -> dict:
    p = prepare(db)
    df, months = apply_filters(p, f)
    country_codes = [c["code"] for c in p.countries if not f.get("countries") or c["code"] in f["countries"]]
    families = [x for x in "ABC" if not f.get("families") or x in f["families"]]

    po_by_month = df.drop_duplicates("source_txn_id").groupby("month").size()
    units_fam_month = df.groupby(["family", "month"])["quantity"].sum()

    kpis = {
        "confirmed_pos": {"value": _po_count(df), "unit": "purchase orders", "definition": "Distinct confirmed/fulfilled purchase orders"},
        "confirmed_lines": {"value": int(len(df)), "unit": "order lines"},
        "po_growth": {"value": growth(po_by_month, months), "unit": "ratio",
                      "definition": "Last 3 months vs preceding 3 months, confirmed purchase orders"},
        "units_by_family": [{"family": fam, "label": FAMILY_LABEL[fam], "unit": UNIT[fam],
                             "units": float(units_fam_month.get(fam, pd.Series(dtype=float)).sum()),
                             "growth": growth(units_fam_month.get(fam, pd.Series(dtype=float)), months)} for fam in families],
        "active_customers": {"value": int(df["canonical_key"].nunique()), "unit": "customers",
                             "definition": "Distinct canonical customers with ≥1 confirmed order in the period"},
        "avg_monthly_pos": {"value": round(_po_count(df) / max(1, len(months)), 1), "unit": "purchase orders / month"},
    }

    trend = []
    for cc in country_codes:
        s = df[df["country_code"] == cc].drop_duplicates("source_txn_id").groupby("month").size().reindex(months, fill_value=0)
        trend.append({"country": cc, "values": [int(x) for x in s]})
    family_trend = [{"family": fam, "values": [float(units_fam_month.get((fam, m), 0)) for m in months]} for fam in families]

    matrix = []
    for cc in country_codes:
        for fam in families:
            sub = df[(df["country_code"] == cc) & (df["family"] == fam)]
            by_m = sub.groupby("month")["quantity"].sum()
            matrix.append({"country": cc, "family": fam, "units": float(sub["quantity"].sum()), "growth": growth(by_m, months),
                           "customers": int(sub["canonical_key"].nunique()), "lines": int(len(sub))})

    mix = []
    for cc in country_codes:
        sub = df[df["country_code"] == cc]
        total = len(sub)
        mix.append({"country": cc, "shares": {fam: round(len(sub[sub["family"] == fam]) / total, 4) if total else 0 for fam in families},
                    "lines": total})

    ranking = []
    for cc in country_codes:
        sub = df[df["country_code"] == cc]
        ranking.append({"country": cc, "confirmed_pos": _po_count(sub),
                        "po_growth": growth(sub.drop_duplicates("source_txn_id").groupby("month").size(), months),
                        "active_customers": int(sub["canonical_key"].nunique())})
    ranking.sort(key=lambda r: -r["confirmed_pos"])

    penetration = []
    all_customers = p.df[p.df["included"] & p.df["country_code"].isin(country_codes)]
    for cc in country_codes:
        base = all_customers[all_customers["country_code"] == cc]["canonical_key"].nunique()
        row = {"country": cc, "customers": int(base)}
        for fam in families:
            n = df[(df["country_code"] == cc) & (df["family"] == fam)]["canonical_key"].nunique()
            row[fam] = round(n / base, 4) if base else 0
        penetration.append(row)

    signals = p.df[p.df["month"].isin(months) & p.df["reason"].isin(["ENQUIRY", "PURCHASE_REQUEST", "PENDING_MDM_SETUP"])]
    if f.get("countries"):
        signals = signals[signals["country_code"].isin(f["countries"])]
    signal_summary = signals.groupby("reason").size().to_dict()

    return {
        "window": {"start": p.months[0], "end": p.months[-1], "selected_start": months[0] if months else None,
                   "selected_end": months[-1] if months else None, "months": months},
        "countries": [c for c in p.countries if c["code"] in country_codes],
        "kpis": kpis, "trend": trend, "family_trend": family_trend, "matrix": matrix, "mix": mix, "ranking": ranking,
        "penetration": penetration, "segments": segmentation(df, months), "signals": {k: int(v) for k, v in signal_summary.items()},
        "definitions": DEFINITIONS,
        "synthetic": True,
    }


UNIT = {"A": "boxes", "B": "kits", "C": "units"}
DEFINITIONS = {
    "confirmed_demand": "Purchase-order lines with status Confirmed or Fulfilled, known customer and product, quantity > 0.",
    "growth": "3-month-over-3-month growth: (last 3 months − preceding 3 months) ÷ preceding 3 months, within the selected range.",
    "units": "Physical units in each family's own unit of measure (A: boxes, B: kits, C: units). Units are never summed across families.",
    "active_customers": "Distinct canonical customers (after reviewed alias mapping) with at least one confirmed order.",
    "orders": "Purchase orders are counted once each, regardless of how many lines they contain.",
}


def segmentation(df: pd.DataFrame, months: list[str]) -> dict:
    if df.empty:
        return {"buckets": [], "by_type": []}
    g = df.groupby("canonical_key").agg(lines=("id", "size"), months_active=("month", "nunique"), last=("month", "max"),
                                        segment=("segment", "first"))
    thresh = g["lines"].quantile(0.8)
    recent = months[-2:] if len(months) >= 2 else months

    def bucket(r):
        if r["last"] not in recent:
            return "Lapsing (no order in last 2 months)"
        if r["lines"] >= thresh:
            return "Key accounts (top 20% by order lines)"
        if r["months_active"] >= 0.75 * len(months):
            return "Regular buyers"
        return "Occasional buyers"

    g["bucket"] = g.apply(bucket, axis=1)
    order = ["Key accounts (top 20% by order lines)", "Regular buyers", "Occasional buyers", "Lapsing (no order in last 2 months)"]
    buckets = [{"bucket": b, "customers": int((g["bucket"] == b).sum()), "lines": int(g.loc[g["bucket"] == b, "lines"].sum())} for b in order]
    by_type = (g.groupby("segment").agg(customers=("lines", "size"), lines=("lines", "sum")).reset_index()
               .rename(columns={"segment": "segment"}).to_dict("records"))
    return {"buckets": buckets, "by_type": [{k: (int(v) if isinstance(v, (np.integer,)) else v) for k, v in r.items()} for r in by_type]}


def customers_list(db: Session) -> list[dict]:
    p = prepare(db)
    df = p.df[p.df["included"]]
    g = df.groupby(["canonical_key", "canonical_name", "country_code"]).size().reset_index(name="lines")
    return [{"key": r.canonical_key, "name": r.canonical_name, "country": r.country_code} for r in g.sort_values("canonical_name").itertuples()]


# ---------------------------------------------------------------- data quality & before/after

def data_quality(db: Session) -> dict:
    p = prepare(db)
    df = p.df
    raw = len(df)
    flagged = df["reason"].map(lambda r: REASONS.get(r, ("", ""))[0] == "Data quality")
    policy = df["reason"].map(lambda r: REASONS.get(r, ("", ""))[0] == "Policy")
    reasons = []
    for code, (kind, label) in REASONS.items():
        sub = df[df["reason"] == code]
        if len(sub):
            reasons.append({"code": code, "kind": kind, "label": label, "records": int(len(sub)),
                            "quantity": float(sub["quantity"].fillna(0).sum())})
    by_type = df.groupby("event_type").size().to_dict()
    mdm_open = db.query(MdmRequest).filter(MdmRequest.domain == "CUSTOMER").count()

    # Before/after: naive spreadsheet consolidation vs governed pipeline.
    naive_po = df[(df["event_type"] == "PURCHASE_ORDER") & df["month"].isin(p.months)]
    unmapped = prepare(db, use_mappings=False).df
    unmapped_inc = unmapped[unmapped["included"]]
    inc = df[df["included"]]
    maps_applied = int(db.query(CanonicalRecordMapping).filter(CanonicalRecordMapping.is_current.is_(True),
                                                               CanonicalRecordMapping.review_status == "CONFIRMED").count())

    return {
        "raw_records": raw, "valid_records": int(df["included"].sum()), "flagged_records": int(flagged.sum()),
        "excluded_by_policy": int(policy.sum()), "excluded_records": int((~df["included"]).sum()),
        "by_event_type": {k: int(v) for k, v in by_type.items()}, "reasons": reasons, "canonical_mappings_applied": maps_applied,
        "mdm_setup_requests_separate": mdm_open,
        "before_after": {
            "naive_po_lines": int(len(naive_po)), "naive_units": {fam: float(naive_po[naive_po["family"] == fam]["quantity"].fillna(0).sum()) for fam in "ABC"},
            "clean_po_lines": int(len(inc)), "clean_units": {fam: float(inc[inc["family"] == fam]["quantity"].sum()) for fam in "ABC"},
            "customers_without_mapping": int(unmapped_inc["canonical_key"].nunique()),
            "customers_with_mapping": int(inc["canonical_key"].nunique()),
            "raw_name_variants": int(naive_po["raw_customer_name"].nunique()),
        },
        "inclusion_policy": _policy_text(),
        "synthetic": True,
    }


def _policy_text() -> str:
    text = " ".join(__doc__.split("INCLUSION POLICY — ")[1].split())
    return text[0].upper() + text[1:]


def customer_consolidation(db: Session, limit: int = 12) -> list[dict]:
    """Customers whose orders were split across several source records/aliases, with consolidated totals."""
    p = prepare(db)
    inc = p.df[p.df["included"]]
    out = []
    for key, sub in inc.groupby("canonical_key"):
        names = sub.groupby(["raw_customer_name", "entity_code"]).agg(lines=("id", "size"), orders=("source_txn_id", "nunique")).reset_index()
        if len(names) < 2:
            continue
        out.append({"canonical_key": key, "canonical_name": sub["canonical_name"].iloc[0], "country": sub["country_code"].iloc[0],
                    "total_orders": int(sub["source_txn_id"].nunique()), "families": sorted(sub["family"].unique().tolist()),
                    "sources": [{"name": r.raw_customer_name, "entity": r.entity_code, "orders": int(r.orders), "lines": int(r.lines)}
                                for r in names.itertuples()]})
    out.sort(key=lambda r: (not r["canonical_name"].startswith("National University"), -len(r["sources"]), -r["total_orders"]))
    return out[:limit]
