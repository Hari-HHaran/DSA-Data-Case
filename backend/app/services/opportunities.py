"""Explainable commercial opportunity engine. Every recommendation carries the numbers behind it and is a
review candidate for a human — never an assertion that a sale will happen or a customer has churned."""
from datetime import date, datetime

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CommercialOpportunity, Customer, Product, SalesFollowup, User
from . import analytics, audit, forecasting, notifications, roles
from .clock import utcnow
from .errors import Forbidden, NotFound, ValidationFailed

STATUSES = ["NEW", "UNDER_REVIEW", "ASSIGNED", "IN_PROGRESS", "COMPLETED", "DISMISSED"]
OUTCOMES = ["ORDER_PLACED", "QUOTE_SENT", "CUSTOMER_RETAINED", "NO_INTEREST", "NOT_CLINICALLY_SUITABLE", "STOCK_ADJUSTED", "NO_ACTION_NEEDED"]
CATEGORY_LABELS = {"CROSS_SELL": "Cross-selling candidate", "INACTIVITY": "Potential inactivity", "GROWTH_MARKET": "Growing product-market",
                   "DEMAND_CHANGE": "Potential demand change"}
# Clinical/commercial suitability assumption: which segments a family is relevant to (configurable in future).
SUITABLE = {"HOSPITAL": "ABC", "LABORATORY": "ABC", "RESEARCH": "ABC", "CLINIC": "AB"}
MIN_PEERS = 5
MIN_ADOPTION = 0.40


def _priority(score: float) -> str:
    return "HIGH" if score >= 65 else "MEDIUM" if score >= 45 else "LOW"


def _customer_frame(db: Session, use_mappings: bool = True):
    p = analytics.prepare(db, use_mappings)
    inc = p.df[p.df["included"]].copy()
    return p, inc


def cross_sell_candidates(db: Session, use_mappings: bool = True) -> tuple[list[dict], list[dict]]:
    p, inc = _customer_frame(db, use_mappings)
    months = p.months
    registered = {}
    for prod in db.execute(select(Product)).scalars():
        registered.setdefault(prod.family, set()).update(prod.registered_countries)
    enq = p.df[(p.df["reason"] == "ENQUIRY") & p.df["month"].isin(months[-6:])]
    enq = enq.groupby(["canonical_key", "family"]).size()
    cust = inc.groupby("canonical_key").agg(name=("canonical_name", "first"), country=("country_code", "first"), segment=("segment", "first"),
                                            master=("master_record_id", "first"), owner=("owner_id", "first"), last=("month", "max"),
                                            lines=("id", "size"))
    fams = inc.groupby("canonical_key")["family"].agg(lambda s: frozenset(s.unique()))
    cust["families"] = fams
    seg_rank = cust.groupby("segment")["lines"].rank(pct=True)
    out, suppressed = [], []
    for key, c in cust.iterrows():
        if c["last"] < months[-3]:
            continue  # not currently active — handled by retention signals instead
        for fam in "ABC":
            if fam in c["families"] or fam not in SUITABLE.get(c["segment"], "ABC"):
                continue
            peers = cust[(cust["segment"] == c["segment"]) & (cust.index != key) & cust["families"].map(lambda f: c["families"] <= f)]
            if len(peers) < MIN_PEERS:
                continue
            adopters = int(peers["families"].map(lambda f: fam in f).sum())
            rate = adopters / len(peers)
            if rate < MIN_ADOPTION:
                continue
            n_enq = int(enq.get((key, fam), 0))
            if c["country"] not in registered.get(fam, set()):
                suppressed.append({"customer": c["name"], "country": c["country"], "family": fam,
                                   "reason": f"Product {fam} is not registered in {c['country']} (synthetic product register)."})
                continue
            recency = 1.0 if c["last"] == months[-1] else 0.5
            score = round(50 * rate + 20 * min(1.0, n_enq / 2) + 20 * float(seg_rank[key]) + 10 * recency, 1)
            have = " & ".join(f"Product {x}" for x in sorted(c["families"]))
            out.append({
                "key": key, "name": c["name"], "country": c["country"], "segment": c["segment"], "family": fam,
                "master_id": None if pd.isna(c["master"]) else int(c["master"]), "owner_id": None if pd.isna(c["owner"]) else int(c["owner"]),
                "score": score, "existing": sorted(c["families"]), "peers": int(len(peers)), "adopters": adopters, "rate": rate,
                "enquiries": n_enq, "lines": int(c["lines"]), "segment_percentile": round(float(seg_rank[key]), 2), "last": c["last"],
                "insight": f"{c['name']} buys {have} but not Product {fam}.",
                "explanation": f"{adopters} of {len(peers)} comparable {c['segment'].lower()} customers that buy {have} also buy Product {fam} "
                               f"({rate:.0%}). " + (f"The customer enquired about Product {fam} {n_enq} time(s) in the last 6 months. " if n_enq else "")
                               + f"It is in the top {100 - round(100 * float(seg_rank[key])):.0f}% of {c['segment'].lower()} customers by order lines.",
            })
    return out, suppressed


def inactivity_candidates(db: Session) -> list[dict]:
    p, inc = _customer_frame(db)
    months = p.months
    idx = {m: i for i, m in enumerate(months)}
    end = len(months) - 1
    out = []
    for (key, fam), sub in inc.groupby(["canonical_key", "family"]):
        order_idx = sorted({idx[m] for m in sub["month"]})
        if len(order_idx) < 3:
            continue
        gaps = np.diff(order_idx)
        typical = float(np.median(gaps))
        since = end - order_idx[-1]
        by_m = sub.groupby("month")["quantity"].sum().reindex(months, fill_value=0)
        name, country = sub["canonical_name"].iloc[0], sub["country_code"].iloc[0]
        base = {"key": key, "name": name, "country": country, "family": fam, "segment": sub["segment"].iloc[0],
                "master_id": None if pd.isna(sub["master_record_id"].iloc[0]) else int(sub["master_record_id"].iloc[0]),
                "owner_id": None if pd.isna(sub["owner_id"].iloc[0]) else int(sub["owner_id"].iloc[0]),
                "typical_interval_months": typical, "months_since_last_order": since, "last_order_month": months[order_idx[-1]],
                "orders_in_window": len(order_idx), "monthly_units": [float(x) for x in by_m.values]}
        if since >= max(2, 2 * typical) and since >= typical + 1:
            share = float(sub["quantity"].sum())
            score = round(min(100, 40 + 15 * (since / max(typical, 1)) + 10 * min(3, len(order_idx) / 4)), 1)
            out.append({**base, "kind": "GAP", "score": score, "volume": share,
                        "insight": f"No Product {fam} order from {name} for {since} months.",
                        "explanation": f"It previously ordered Product {fam} about every {typical:g} month(s) ({len(order_idx)} orders in the window); "
                                       f"the last order was in {months[order_idx[-1]]}. This interval-based test accounts for "
                                       f"customers who naturally buy infrequently."})
            continue
        if typical <= 1.5 and since <= 1:
            recent, prior = by_m.iloc[-3:].mean(), by_m.iloc[-9:-3].mean()
            if prior > 0 and recent < 0.6 * prior:
                drop = 1 - recent / prior
                out.append({**base, "kind": "DECLINE", "score": round(min(100, 35 + 60 * drop), 1), "drop": float(drop),
                            "insight": f"{name}'s Product {fam} volume is down {drop:.0%}.",
                            "explanation": f"Average {recent:,.0f} {analytics.UNIT[fam]}/month over the last 3 months vs {prior:,.0f} over the "
                                           f"preceding 6 months, while the customer is still ordering."})
    return out


def market_candidates(db: Session) -> list[dict]:
    run = forecasting.latest(db)
    if not run:
        return []
    mat, months = forecasting.series_matrix(db)
    out = []
    for (cc, fam), row in mat.iterrows():
        g = analytics.growth(pd.Series(row.values, index=months), months)
        if g is None:
            continue
        detail = forecasting.series_detail(db, run, cc, fam)
        fc = detail["explanation"]["forecast_change"]
        unit = analytics.UNIT[fam]
        if g >= 0.15 and (fc is None or fc > -0.05):
            out.append({"kind": "GROWTH_MARKET", "country": cc, "family": fam, "growth": g, "forecast_change": fc,
                        "score": round(min(100, 40 + 100 * g), 1),
                        "insight": f"Product {fam} demand in {cc} grew {g:+.0%} (3M vs prior 3M).",
                        "explanation": f"Confirmed {unit} rose from {row.values[-6:-3].sum():,.0f} to {row.values[-3:].sum():,.0f}. "
                                       + next((x + "." for x in detail["explanation"]["summary"].split(". ") if x.startswith("The selected model")), ""),
                        "action": "Review stock cover and supplier lead times for the next quarter; confirm with the regional planner."})
        elif g <= -0.12:
            out.append({"kind": "DEMAND_CHANGE", "country": cc, "family": fam, "growth": g, "forecast_change": fc,
                        "score": round(min(100, 40 + 100 * abs(g)), 1),
                        "insight": f"Product {fam} demand in {cc} fell {g:+.0%} (3M vs prior 3M).",
                        "explanation": f"Confirmed {unit} fell from {row.values[-6:-3].sum():,.0f} to {row.values[-3:].sum():,.0f}. "
                                       "The data shows the change but not its cause.",
                        "action": "Investigate with account owners (customer-specific vs market-wide) and review replenishment to avoid overstock."})
    return out


def refresh(db: Session) -> dict:
    owners_by_country = {}
    for c in db.execute(select(Customer)).scalars():
        owners_by_country.setdefault(c.country_code, c.account_owner_id)
    generated = {}
    xs, suppressed = cross_sell_candidates(db)
    for c in xs:
        generated[f"XSELL:{c['key']}:{c['family']}"] = dict(
            category="CROSS_SELL", title=f"Cross-sell Product {c['family']} · {c['name']}", insight=c["insight"],
            evidence={k: c[k] for k in ("existing", "peers", "adopters", "rate", "enquiries", "lines", "segment_percentile", "last", "segment")},
            explanation=c["explanation"], suggested_action=f"Account owner to review clinical fit and registration, then arrange a Product {c['family']} "
            "discussion. This is a review candidate, not a guaranteed sale.", priority_score=c["score"],
            priority_reason=f"Peer adoption {c['rate']:.0%} (50%), enquiries {c['enquiries']} (20%), size percentile {c['segment_percentile']:.0%} (20%), recency (10%).",
            customer_master_id=c["master_id"], country_code=c["country"], product_family=c["family"], owner_id=c["owner_id"])
    for c in inactivity_candidates(db):
        generated[f"INACT:{c['key']}:{c['family']}"] = dict(
            category="INACTIVITY", title=f"{'Ordering gap' if c['kind'] == 'GAP' else 'Volume decline'} · {c['name']}", insight=c["insight"],
            evidence={k: c[k] for k in ("typical_interval_months", "months_since_last_order", "last_order_month", "orders_in_window", "monthly_units", "kind", "segment")},
            explanation=c["explanation"], suggested_action="Account owner to contact the customer and check for service, supply or competitive issues. "
            "Label: potential inactivity — not confirmed churn.", priority_score=c["score"],
            priority_reason="Weighted by gap length relative to the customer's own buying interval." if c["kind"] == "GAP" else "Weighted by size of the volume drop.",
            customer_master_id=c["master_id"], country_code=c["country"], product_family=c["family"], owner_id=c["owner_id"])
    for c in market_candidates(db):
        generated[f"{c['kind']}:{c['country']}:{c['family']}"] = dict(
            category=c["kind"], title=f"{'Growing' if c['kind'] == 'GROWTH_MARKET' else 'Declining'} demand · Product {c['family']} in {c['country']}",
            insight=c["insight"], evidence={"growth": c["growth"], "forecast_change": c["forecast_change"]}, explanation=c["explanation"],
            suggested_action=c["action"], priority_score=c["score"], priority_reason="Weighted by size of the 3-month change.",
            customer_master_id=None, country_code=c["country"], product_family=c["family"], owner_id=owners_by_country.get(c["country"]))

    existing = {o.opp_key: o for o in db.execute(select(CommercialOpportunity)).scalars()}
    created = updated = stale = 0
    for key, g in generated.items():
        g["priority_label"] = _priority(g["priority_score"])
        o = existing.get(key)
        if o is None:
            db.add(CommercialOpportunity(opp_key=key, status="NEW", **g))
            created += 1
        else:
            for k, v in g.items():
                if k != "owner_id" or o.owner_id is None:
                    setattr(o, k, v)
            o.is_stale = False
            updated += 1
    for key, o in existing.items():
        if key not in generated and o.status in ("NEW", "UNDER_REVIEW"):
            o.is_stale = True
            stale += 1
    db.flush()
    return {"created": created, "updated": updated, "marked_stale": stale, "suppressed_by_regulation": suppressed}


def mapping_effect_on_cross_sell(db: Session) -> dict:
    """What a gap analysis looks like without canonical mapping: each entity's customer record looks like a
    separate customer that buys only 'its' product family, so most apparent product gaps are false."""
    with_map, _ = cross_sell_candidates(db, True)
    without, _ = cross_sell_candidates(db, False)
    lookup = analytics.canonical_lookup(db, True)
    src_to_can = {f"SRC-{int(r.customer_id)}": r.canonical_key for r in lookup.itertuples()}
    seg = {f"SRC-{int(r.customer_id)}": r.segment for r in lookup.itertuples()}
    p = analytics.prepare(db, True)
    inc = p.df[p.df["included"]]
    fam_by_can = inc.groupby("canonical_key")["family"].agg(lambda s: set(s.unique())).to_dict()
    raw = analytics.prepare(db, False).df
    raw_inc = raw[raw["included"]]
    apparent, false_gaps, examples = 0, 0, []
    for key, fams in raw_inc.groupby("canonical_key")["family"].agg(lambda s: set(s.unique())).items():
        for fam in SUITABLE.get(seg.get(key, ""), "ABC"):
            if fam in fams:
                continue
            apparent += 1
            if fam in fam_by_can.get(src_to_can.get(key, key), set()):
                false_gaps += 1
                if len(examples) < 5:
                    name = raw_inc.loc[raw_inc["canonical_key"] == key, "raw_customer_name"].iloc[0]
                    examples.append({"customer": name, "family": fam})
    return {"apparent_gaps_without_mapping": apparent, "false_gaps_avoided": false_gaps,
            "false_gap_share": round(false_gaps / apparent, 3) if apparent else None,
            "recommendations_with_mapping": len(with_map), "recommendations_without_mapping": len(without), "examples": examples}


# ---------------------------------------------------------------- workflow on opportunities

def serialize(o: CommercialOpportunity, followups: list[SalesFollowup] | None = None) -> dict:
    return {
        "id": o.id, "category": o.category, "category_label": CATEGORY_LABELS.get(o.category, o.category), "title": o.title,
        "insight": o.insight, "evidence": o.evidence, "explanation": o.explanation, "suggested_action": o.suggested_action,
        "priority_score": o.priority_score, "priority": o.priority_label, "priority_reason": o.priority_reason,
        "customer": {"id": o.customer.id, "code": o.customer.record_code, "name": o.customer.name} if o.customer else None,
        "country": o.country_code, "family": o.product_family,
        "owner": {"id": o.owner.id, "name": o.owner.full_name, "title": o.owner.title} if o.owner else None,
        "status": o.status, "outcome": o.outcome, "outcome_note": o.outcome_note, "is_stale": o.is_stale,
        "created_at": o.created_at.isoformat(), "updated_at": o.updated_at.isoformat(),
        "followups": [{"id": f.id, "assigned_to": f.assigned_to.full_name, "due_date": f.due_date.isoformat() if f.due_date else None,
                       "note": f.note, "status": f.status, "outcome": f.outcome, "created_at": f.created_at.isoformat()} for f in (followups or [])],
    }


def _get(db: Session, opp_id: int) -> CommercialOpportunity:
    o = db.get(CommercialOpportunity, opp_id)
    if not o:
        raise NotFound("Opportunity not found.")
    return o


def _assert_commercial(user: User):
    if not user.has_role(roles.SALES, roles.ADMIN):
        raise Forbidden("Only sales users can act on commercial opportunities.")


def update(db: Session, user: User, opp_id: int, status: str | None, outcome: str | None, note: str | None) -> CommercialOpportunity:
    _assert_commercial(user)
    o = _get(db, opp_id)
    before = o.status
    if status:
        if status not in STATUSES:
            raise ValidationFailed(f"Unknown status {status}.")
        if status == "COMPLETED" and not (outcome or o.outcome):
            raise ValidationFailed("Record an outcome when completing an opportunity.")
        if status == "DISMISSED" and not (note or "").strip():
            raise ValidationFailed("Give a reason when dismissing an opportunity.")
        o.status = status
    if outcome:
        if outcome not in OUTCOMES:
            raise ValidationFailed(f"Unknown outcome {outcome}.")
        o.outcome = outcome
    if note is not None:
        o.outcome_note = note
    audit.record(db, "OPPORTUNITY_UPDATED", actor_id=user.id, entity_type="OPPORTUNITY", entity_ref=f"OPP-{o.id}",
                 from_status=before, to_status=o.status, comment=note or "", changes={"outcome": o.outcome})
    return o


def create_followup(db: Session, user: User, opp_id: int, assignee_id: int, due: date | None, note: str) -> SalesFollowup:
    _assert_commercial(user)
    o = _get(db, opp_id)
    assignee = db.get(User, assignee_id)
    if not assignee or not assignee.has_role(roles.SALES):
        raise ValidationFailed("Follow-ups can only be assigned to sales users.")
    f = SalesFollowup(opportunity_id=o.id, assigned_to_id=assignee.id, assigned_by_id=user.id, due_date=due, note=note or "", status="OPEN")
    db.add(f)
    before = o.status
    o.owner_id = assignee.id
    if o.status in ("NEW", "UNDER_REVIEW"):
        o.status = "ASSIGNED"
    db.flush()
    notifications.notify(db, [assignee], "FOLLOWUP_ASSIGNED", f"Sales follow-up: {o.title}",
                         f"Assigned by {user.full_name}{f' · due {due:%d %b}' if due else ''}. {note or ''}".strip(), link=f"/growth/opportunities?id={o.id}")
    audit.record(db, "FOLLOWUP_ASSIGNED", actor_id=user.id, entity_type="OPPORTUNITY", entity_ref=f"OPP-{o.id}", from_status=before,
                 to_status=o.status, comment=f"Assigned to {assignee.full_name}. {note or ''}".strip())
    return f
