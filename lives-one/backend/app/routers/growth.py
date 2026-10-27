from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import CommercialOpportunity, ForecastEvaluation, Product, SalesFollowup, User
from ..schemas import FollowupIn, OpportunityUpdate
from ..services import analytics, forecasting, opportunities, roles
from ..services.errors import NotFound

router = APIRouter(prefix="/api", tags=["growth-intelligence"])
analyst = require_roles(*roles.ANALYTICS_ROLES)


def _filters(countries: str | None, families: str | None, entities: str | None, start: str | None, end: str | None,
             customer: str | None, status: str | None) -> dict:
    split = lambda s: [x for x in s.split(",") if x] if s else None  # noqa: E731
    return {"countries": split(countries), "families": split(families), "entities": split(entities), "start": start, "end": end,
            "customer": customer, "status": status}


@router.get("/analytics/overview")
def overview(countries: str | None = None, families: str | None = None, entities: str | None = None, start: str | None = None,
             end: str | None = None, customer: str | None = None, status: str | None = None, db: Session = Depends(get_db), _: User = Depends(analyst)):
    out = analytics.overview(db, _filters(countries, families, entities, start, end, customer, status))
    run = forecasting.latest(db)
    out["forecast"] = forecasting.summary(db, run) if run else None
    out["open_opportunities"] = db.execute(select(func.count(CommercialOpportunity.id)).where(
        CommercialOpportunity.status.in_(["NEW", "UNDER_REVIEW", "ASSIGNED", "IN_PROGRESS"]),
        CommercialOpportunity.priority_label.in_(["HIGH", "MEDIUM"]), CommercialOpportunity.is_stale.is_(False))).scalar()
    return out


@router.get("/analytics/countries")
def countries(db: Session = Depends(get_db), _: User = Depends(analyst)):
    o = analytics.overview(db, {})
    return {"ranking": o["ranking"], "matrix": o["matrix"], "penetration": o["penetration"], "countries": o["countries"]}


@router.get("/analytics/products")
def products(db: Session = Depends(get_db), _: User = Depends(analyst)):
    return [{"code": p.code, "name": p.name, "family": p.family, "category": p.category, "pattern": p.purchase_pattern, "unit": p.unit,
             "registered_countries": p.registered_countries} for p in db.execute(select(Product).order_by(Product.code)).scalars()]


@router.get("/analytics/customers")
def customers(db: Session = Depends(get_db), _: User = Depends(analyst)):
    return analytics.customers_list(db)


@router.get("/analytics/purchasing")
def purchasing(reason: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(25, le=100), db: Session = Depends(get_db),
               _: User = Depends(analyst)):
    p = analytics.prepare(db)
    df = p.df
    if reason:
        df = df[df["reason"] == reason]
    total = len(df)
    sub = df.iloc[(page - 1) * page_size: page * page_size]
    cols = ["id", "source_txn_id", "line_no", "event_type", "status", "event_date", "raw_customer_name", "canonical_name", "product_code",
            "family", "raw_country", "country_code", "entity_code", "quantity", "reason", "included"]
    rows = sub[cols].astype(object).where(sub[cols].notna(), None).to_dict("records")
    for r in rows:
        r["event_date"] = str(r["event_date"])
        r["reason_label"] = analytics.REASONS.get(r["reason"], ("", "Included in confirmed demand"))[1]
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


@router.get("/analytics/data-quality")
def data_quality(db: Session = Depends(get_db), _: User = Depends(analyst)):
    dq = analytics.data_quality(db)
    dq["cross_sell_mapping_effect"] = opportunities.mapping_effect_on_cross_sell(db)
    dq["consolidation_examples"] = analytics.customer_consolidation(db, limit=5)
    return dq


# ---------------------------------------------------------------- forecasting

@router.get("/forecasts")
def forecast_latest(country: str = "SG", family: str = "B", db: Session = Depends(get_db), _: User = Depends(analyst)):
    run = forecasting.latest(db)
    if not run:
        raise NotFound("No forecast has been run yet.")
    return {"summary": forecasting.summary(db, run), "series": forecasting.series_detail(db, run, country, family)}


@router.post("/forecasts/run")
def forecast_run(db: Session = Depends(get_db), user: User = Depends(analyst)):
    run = forecasting.run(db, user)
    db.commit()
    return forecasting.summary(db, run)


@router.get("/forecasts/evaluations")
def forecast_evaluations(db: Session = Depends(get_db), _: User = Depends(analyst)):
    run = forecasting.latest(db)
    if not run:
        raise NotFound("No forecast has been run yet.")
    rows = db.execute(select(ForecastEvaluation).where(ForecastEvaluation.run_id == run.id, ForecastEvaluation.scope.not_in(["ALL"]), ForecastEvaluation.scope.not_like("FAM-%"))).scalars().all()
    grid = {}
    for e in rows:
        g = grid.setdefault(e.scope, {"scope": e.scope, "country": e.scope.split("-")[0], "family": e.scope.split("-")[1]})
        g[e.model] = {"mae": round(e.mae, 1), "wape": None if e.wape is None else round(e.wape, 4), "bias": round(e.bias, 4)}
    out = sorted(grid.values(), key=lambda g: g["scope"])
    for g in out:
        w = {m: g[m]["wape"] for m in forecasting.MODELS if m in g and g[m]["wape"] is not None}
        g["best_model"] = min(w, key=w.get) if w else None
    return {"run_id": run.id, "selected_model": run.selected_model, "series": out, "models": forecasting.MODELS}


# ---------------------------------------------------------------- opportunities

@router.get("/opportunities")
def list_opps(category: str | None = None, status: str | None = None, country: str | None = None, include_stale: bool = False,
              db: Session = Depends(get_db), user: User = Depends(require_roles(*roles.COMMERCIAL_ROLES, roles.MDM_ANALYST))):
    q = select(CommercialOpportunity)
    if category:
        q = q.where(CommercialOpportunity.category == category)
    if status:
        q = q.where(CommercialOpportunity.status.in_(status.split(",")))
    if country:
        q = q.where(CommercialOpportunity.country_code == country)
    if not include_stale:
        q = q.where(CommercialOpportunity.is_stale.is_(False))
    rows = db.execute(q.order_by(CommercialOpportunity.priority_score.desc())).scalars().all()
    fus = {}
    for f in db.execute(select(SalesFollowup).where(SalesFollowup.opportunity_id.in_([o.id for o in rows]))).scalars():
        fus.setdefault(f.opportunity_id, []).append(f)
    counts = dict(db.execute(select(CommercialOpportunity.category, func.count()).where(CommercialOpportunity.is_stale.is_(False))
                             .group_by(CommercialOpportunity.category)).all())
    by_status = dict(db.execute(select(CommercialOpportunity.status, func.count()).where(CommercialOpportunity.is_stale.is_(False))
                                .group_by(CommercialOpportunity.status)).all())
    return {"items": [opportunities.serialize(o, fus.get(o.id)) for o in rows], "counts": counts, "by_status": by_status,
            "statuses": opportunities.STATUSES, "outcomes": opportunities.OUTCOMES, "categories": opportunities.CATEGORY_LABELS}


@router.post("/opportunities/refresh")
def refresh(db: Session = Depends(get_db), _: User = Depends(require_roles(roles.SALES, roles.ADMIN))):
    out = opportunities.refresh(db)
    db.commit()
    return out


@router.patch("/opportunities/{opp_id}")
def update_opp(opp_id: int, body: OpportunityUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    o = opportunities.update(db, user, opp_id, body.status, body.outcome, body.note)
    db.commit()
    return opportunities.serialize(o, db.execute(select(SalesFollowup).where(SalesFollowup.opportunity_id == o.id)).scalars().all())


@router.post("/opportunities/{opp_id}/assign")
@router.post("/opportunities/{opp_id}/followup")
def followup(opp_id: int, body: FollowupIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    opportunities.create_followup(db, user, opp_id, body.assignee_id, body.due_date, body.note)
    db.commit()
    o = db.get(CommercialOpportunity, opp_id)
    return opportunities.serialize(o, db.execute(select(SalesFollowup).where(SalesFollowup.opportunity_id == o.id)).scalars().all())
