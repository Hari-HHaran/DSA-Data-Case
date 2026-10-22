"""Explainable demand forecasting on confirmed demand (units per country × product family per month).

Models
- ROLLING_AVG   : mean of the last N months (N=6 by default) — the brief's current 6–12-month approach.
- HOLT_DAMPED   : additive-trend exponential smoothing with a damped trend (statsmodels).
- RIDGE_POOLED  : one ridge regression pooled across all 15 series on scale-free lag features
                  (lags 1–3, 3-month mean, recent slope, family indicators). Pooling gives ~45–90 training
                  rows instead of ≤11 per series, which is why a regression is defensible at all here.

Evaluation: rolling-origin backtest, horizons 1–3 months, origins from month 7 onwards. Each model only
sees data strictly before the origin (no shuffling, scales computed from training data only → no leakage).
Metrics: MAE (units), WAPE = Σ|e| / Σ actual, bias = Σ(forecast − actual) / Σ actual.
Units differ by family (boxes / kits / units), so errors are never pooled across families: the headline
WAPE and bias are the simple average of the three per-family values, and MAE is reported per family.
Selection: a champion is chosen PER PRODUCT FAMILY (lowest family WAPE; ties within 0.1 pp go to the simpler model),
because demand patterns differ — e.g. recurring Product A vs periodic Product C. The "selected" headline is the
average WAPE of the three family champions, compared like-for-like with the rolling-average baseline.

Limitations: 12 monthly points per series cannot identify seasonality; seasonal-naive is therefore not run.
"""
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ForecastEvaluation, ForecastResult, ForecastRun, User
from . import analytics, settings_service

MODELS = {
    "ROLLING_AVG": {"label": "Rolling average (baseline)", "complexity": 0,
                    "description": "Average of the last N months — the current spreadsheet approach."},
    "HOLT_DAMPED": {"label": "Damped-trend exponential smoothing", "complexity": 1,
                    "description": "Weights recent months more and follows a trend that flattens over time."},
    "RIDGE_POOLED": {"label": "Pooled ridge regression (lag features)", "complexity": 2,
                     "description": "Learns how recent momentum carries forward, sharing evidence across all country/product series."},
    "CHAMPION": {"label": "Selected model per product family", "complexity": 3,
                 "description": "For each product family, the model with the lowest backtest error."},
}
CANDIDATES = ("ROLLING_AVG", "HOLT_DAMPED", "RIDGE_POOLED")
HORIZON = 3
MIN_TRAIN = 6
LOW_VOLUME_UNITS = 30  # below this total test volume, WAPE is shown with a caveat


def series_matrix(db: Session) -> tuple[pd.DataFrame, list[str]]:
    p = analytics.prepare(db)
    inc = p.df[p.df["included"]]
    g = inc.groupby(["country_code", "family", "month"])["quantity"].sum()
    idx = pd.MultiIndex.from_product([[c["code"] for c in p.countries], list("ABC")], names=["country_code", "family"])
    mat = g.unstack("month").reindex(idx).reindex(columns=p.months).fillna(0.0)
    return mat, p.months


# ---------------------------------------------------------------- models

def f_rolling(hist: np.ndarray, h: int, window: int) -> np.ndarray:
    return np.repeat(hist[-window:].mean(), h)


def f_holt(hist: np.ndarray, h: int) -> np.ndarray:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    if len(hist) < 4 or hist.sum() == 0:
        return np.repeat(hist[-3:].mean(), h)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            fit = ExponentialSmoothing(hist.astype(float), trend="add", damped_trend=True, initialization_method="estimated").fit()
            out = np.asarray(fit.forecast(h))
        except Exception:
            out = np.repeat(hist[-3:].mean(), h)
    return np.clip(out, 0, None)


def _features(hist: np.ndarray, family: str) -> np.ndarray | None:
    if len(hist) < 4:
        return None
    scale = hist.mean() or 1.0
    l1, l2, l3 = hist[-1] / scale, hist[-2] / scale, hist[-3] / scale
    return np.array([l1, l2, l3, (l1 + l2 + l3) / 3, (l1 - l3) / 2, family == "A", family == "B"], dtype=float)


def _train_ridge(mat: pd.DataFrame, upto: int) -> Ridge | None:
    X, y = [], []
    for (cc, fam), row in mat.iterrows():
        v = row.values
        for t in range(4, upto):
            feats = _features(v[:t], fam)
            scale = v[:t].mean() or 1.0
            if feats is not None:
                X.append(feats)
                y.append(v[t] / scale)
    if len(X) < 15:
        return None
    return Ridge(alpha=1.0).fit(np.array(X), np.array(y))


def f_ridge(model: Ridge | None, hist: np.ndarray, fam: str, h: int) -> np.ndarray:
    if model is None:
        return np.repeat(hist[-3:].mean(), h)
    out, cur = [], list(hist)
    for _ in range(h):
        # Recursive multi-step: later steps use earlier predictions, never future actuals.
        arr = np.array(cur)
        feats = _features(arr, fam)
        nxt = max(0.0, float(model.predict(feats.reshape(1, -1))[0]) * (arr.mean() or 1.0))
        out.append(nxt)
        cur.append(nxt)
    return np.array(out)


def _predict_all(mat: pd.DataFrame, upto: int, h: int, window: int) -> dict:
    ridge = _train_ridge(mat, upto)
    preds = {}
    for (cc, fam), row in mat.iterrows():
        hist = row.values[:upto]
        preds[(cc, fam)] = {"ROLLING_AVG": f_rolling(hist, h, window), "HOLT_DAMPED": f_holt(hist, h), "RIDGE_POOLED": f_ridge(ridge, hist, fam, h)}
    return preds


# ---------------------------------------------------------------- evaluation

def metrics(actual: np.ndarray, pred: np.ndarray) -> dict:
    err = pred - actual
    tot = actual.sum()
    return {"mae": float(np.abs(err).mean()) if len(err) else 0.0, "wape": float(np.abs(err).sum() / tot) if tot > 0 else None,
            "bias": float(err.sum() / tot) if tot > 0 else 0.0, "n": int(len(err)), "volume": float(tot)}


def backtest(mat: pd.DataFrame, months: list[str], window: int) -> pd.DataFrame:
    rows = []
    n = len(months)
    for origin in range(MIN_TRAIN, n):
        h = min(HORIZON, n - origin)
        preds = _predict_all(mat, origin, h, window)
        for (cc, fam), by_model in preds.items():
            actual = mat.loc[(cc, fam)].values[origin:origin + h]
            for model, p in by_model.items():
                for k in range(h):
                    rows.append({"country_code": cc, "family": fam, "model": model, "origin": months[origin - 1],
                                 "period": months[origin + k], "horizon": k + 1, "actual": float(actual[k]), "predicted": float(p[k])})
    return pd.DataFrame(rows)


def run(db: Session, user: User | None = None) -> ForecastRun:
    mat, months = series_matrix(db)
    window = int(settings_service.get(db, "forecast.rolling_window"))
    bt = backtest(mat, months, window)
    fam_metrics = {(m, f): metrics(g["actual"].values, g["predicted"].values) for (m, f), g in bt.groupby(["model", "family"])}
    champions = {f: min(CANDIDATES, key=lambda m: (round(fam_metrics[(m, f)]["wape"] or 9e9, 3), MODELS[m]["complexity"])) for f in "ABC"}

    def macro(pairs):
        fm = [fam_metrics[p] for p in pairs]
        return {"mae": None, "wape": float(np.mean([x["wape"] for x in fm if x["wape"] is not None])),
                "bias": float(np.mean([x["bias"] for x in fm])), "n": int(sum(x["n"] for x in fm))}

    overall = {m: macro([(m, f) for f in "ABC"]) for m in CANDIDATES}
    overall["CHAMPION"] = macro([(champions[f], f) for f in "ABC"])
    selected = "CHAMPION"
    by_h = {m: {int(h): float(np.mean([metrics(g3["actual"].values, g3["predicted"].values)["wape"] or 0 for _, g3 in g2.groupby("family")]))
                for h, g2 in g.groupby("horizon")} for m, g in bt.groupby("model")}

    run = ForecastRun(created_by_id=user.id if user else None, params={"rolling_window": window, "horizon": HORIZON, "min_train": MIN_TRAIN},
                      window_start=months[0], window_end=months[-1], selected_model=selected,
                      notes={"by_horizon": {m: {str(h): v for h, v in hs.items()} for m, hs in by_h.items()},
                             "backtest_origins": sorted(bt["origin"].unique().tolist()), "series": len(mat),
                             "observations_per_series": len(months),
                             "data_sufficiency": f"{len(months)} monthly observations per series. Enough for level and short-term trend; "
                                                 "not enough to estimate seasonality (needs ≥24 months).",
                             "champions": champions})
    db.add(run)
    db.flush()
    for m, v in overall.items():
        db.add(ForecastEvaluation(run_id=run.id, model=m, scope="ALL", mae=v["mae"], wape=v["wape"], bias=v["bias"], n_points=v["n"], is_selected=m == selected))
    for (m, f), v in fam_metrics.items():
        db.add(ForecastEvaluation(run_id=run.id, model=m, scope=f"FAM-{f}", mae=v["mae"], wape=v["wape"], bias=v["bias"], n_points=v["n"],
                                  is_selected=m == champions[f]))
    for (cc, fam, m), g in bt.groupby(["country_code", "family", "model"]):
        v = metrics(g["actual"].values, g["predicted"].values)
        db.add(ForecastEvaluation(run_id=run.id, model=m, scope=f"{cc}-{fam}", mae=v["mae"], wape=v["wape"], bias=v["bias"],
                                  n_points=v["n"], is_selected=m == champions[fam]))
    # Store 1-step-ahead backtest predictions for the "held-out" chart layer.
    h1 = bt[bt["horizon"] == 1]
    db.bulk_insert_mappings(ForecastResult, [
        {"run_id": run.id, "country_code": r.country_code, "product_family": r.family, "model": r.model, "period": r.period,
         "kind": "BACKTEST", "actual": r.actual, "predicted": r.predicted} for r in h1.itertuples()])

    # Empirical interval: 80th percentile of relative absolute error of each family's champion, per horizon.
    rel = {}
    for f in "ABC":
        sel = bt[(bt["model"] == champions[f]) & (bt["family"] == f) & (bt["actual"] > 0)]
        rel[f] = {int(h): float(np.quantile(np.abs(g["predicted"] - g["actual"]) / g["actual"], 0.8)) for h, g in sel.groupby("horizon")}
    future_months = [str(p) for p in pd.period_range(pd.Period(months[-1], "M") + 1, periods=HORIZON, freq="M")]
    preds = _predict_all(mat, len(months), HORIZON, window)
    future = []
    for (cc, fam), by_model in preds.items():
        for m, p in by_model.items():
            champ = m == champions[fam]
            for k in range(HORIZON):
                q = rel[fam].get(k + 1, 0.3)
                future.append({"run_id": run.id, "country_code": cc, "product_family": fam, "model": m, "period": future_months[k],
                               "kind": "FUTURE", "actual": None, "predicted": float(p[k]),
                               "lower": float(max(0, p[k] * (1 - q))) if champ else None,
                               "upper": float(p[k] * (1 + q)) if champ else None})
    db.bulk_insert_mappings(ForecastResult, future)
    run.notes = {**run.notes, "interval_relative_error_q80": rel, "future_months": future_months}
    db.flush()
    return run


def latest(db: Session) -> ForecastRun | None:
    return db.execute(select(ForecastRun).order_by(ForecastRun.id.desc()).limit(1)).scalar()


def summary(db: Session, run: ForecastRun) -> dict:
    evals = db.execute(select(ForecastEvaluation).where(ForecastEvaluation.run_id == run.id, ForecastEvaluation.scope == "ALL")).scalars().all()
    base = next((e for e in evals if e.model == "ROLLING_AVG"), None)
    sel = next((e for e in evals if e.is_selected), None)
    improvement = None
    if base and sel and base.wape and sel.wape is not None:
        improvement = round((base.wape - sel.wape) / base.wape, 4)
    return {
        "run_id": run.id, "created_at": run.created_at.isoformat(), "window": [run.window_start, run.window_end],
        "selected_model": run.selected_model, "champions": run.notes.get("champions", {}), "models": MODELS, "params": run.params,
        "notes": run.notes,
        "family_evaluations": _family_evals(db, run),
        "evaluations": [{"model": e.model, "label": MODELS[e.model]["label"], "mae": None if e.mae is None else round(e.mae, 2),
                         "wape": round(e.wape, 4) if e.wape is not None else None, "bias": round(e.bias, 4), "n_points": e.n_points,
                         "is_selected": e.is_selected} for e in sorted(evals, key=lambda e: MODELS[e.model]["complexity"])],
        "accuracy": round(1 - sel.wape, 4) if sel and sel.wape is not None else None,
        "baseline_accuracy": round(1 - base.wape, 4) if base and base.wape is not None else None,
        "wape_reduction_vs_baseline": improvement,
        "accuracy_definition": "Forecast accuracy = 1 − WAPE on rolling-origin backtests (horizons 1–3 months), averaged across "
                               "Products A, B and C so that different units are never pooled.",
    }


def _family_evals(db: Session, run: ForecastRun) -> list[dict]:
    rows = db.execute(select(ForecastEvaluation).where(ForecastEvaluation.run_id == run.id, ForecastEvaluation.scope.like("FAM-%"))).scalars().all()
    out = {}
    for e in rows:
        fam = e.scope[-1]
        out.setdefault(fam, {"family": fam, "unit": analytics.UNIT[fam]})[e.model] = {
            "mae": round(e.mae, 1), "wape": None if e.wape is None else round(e.wape, 4), "bias": round(e.bias, 4), "n": e.n_points}
    return [out[f] for f in sorted(out)]


def series_detail(db: Session, run: ForecastRun, country: str, family: str) -> dict:
    mat, months = series_matrix(db)
    hist = mat.loc[(country, family)]
    results = db.execute(select(ForecastResult).where(ForecastResult.run_id == run.id, ForecastResult.country_code == country,
                                                      ForecastResult.product_family == family)).scalars().all()
    evals = db.execute(select(ForecastEvaluation).where(ForecastEvaluation.run_id == run.id,
                                                        ForecastEvaluation.scope == f"{country}-{family}")).scalars().all()
    by_model = {}
    for r in results:
        d = by_model.setdefault(r.model, {"backtest": {}, "future": {}})
        d["backtest" if r.kind == "BACKTEST" else "future"][r.period] = {"predicted": round(r.predicted, 1),
                                                                         "lower": None if r.lower is None else round(r.lower, 1),
                                                                         "upper": None if r.upper is None else round(r.upper, 1)}
    ev = {e.model: {"mae": round(e.mae, 2), "wape": None if e.wape is None else round(e.wape, 4), "bias": round(e.bias, 4), "n": e.n_points}
          for e in evals}
    volume = float(hist.values[MIN_TRAIN:].sum())
    return {
        "country": country, "family": family, "unit": analytics.UNIT[family], "months": months,
        "history": [round(float(x), 1) for x in hist.values], "future_months": run.notes.get("future_months", []),
        "models": by_model, "evaluations": ev, "selected_model": run.notes["champions"][family],
        "low_volume": volume < LOW_VOLUME_UNITS,
        "explanation": explain(country, family, hist.values, by_model, ev, run.notes["champions"][family], analytics.UNIT[family],
                               run.notes.get("future_months", [])),
    }


def explain(country, family, hist, by_model, ev, selected, unit, future_months) -> dict:
    """Business-language explanation built only from computed numbers — no causal claims."""
    last3, prev3 = hist[-3:].sum(), hist[-6:-3].sum()
    change = (last3 - prev3) / prev3 if prev3 else None
    fut = [by_model.get(selected, {}).get("future", {}).get(m, {}).get("predicted", 0) for m in future_months]
    fut_avg = float(np.mean(fut)) if fut else 0.0
    recent_avg = float(last3 / 3)
    fc_change = (fut_avg - recent_avg) / recent_avg if recent_avg else None
    cv = float(np.std(hist) / np.mean(hist)) if np.mean(hist) else None
    label = f"Product {family} in {country}"
    lines = []
    if change is None:
        lines.append(f"{label} has too little recent volume to measure a trend.")
    else:
        direction = "increased" if change > 0.05 else "decreased" if change < -0.05 else "been broadly stable"
        lines.append(f"{label} confirmed demand has {direction} over the last 3 months ({change:+.0%} vs the preceding 3 months).")
    if fc_change is not None:
        lines.append(f"The selected model ({MODELS[selected]['label'].lower()}) projects an average of {fut_avg:,.0f} {unit}/month "
                     f"for {future_months[0]}–{future_months[-1]}, {fc_change:+.0%} vs the recent 3-month average.")
    b, s = ev.get("ROLLING_AVG"), ev.get(selected)
    if b and s and b["wape"] is not None and s["wape"] is not None and selected != "ROLLING_AVG":
        lines.append(f"In backtests for this series its error (WAPE) was {s['wape']:.0%} vs {b['wape']:.0%} for the rolling average.")
    elif selected == "ROLLING_AVG":
        lines.append(f"For Product {family}, the rolling average had the lowest backtest error across all countries, so it is kept; "
                     "the more complex models did not earn their place here.")
    lines.append("Only 12 months of history are available, so seasonality is not modelled and the range shown is approximate.")
    recs = []
    if fc_change is not None and fc_change > 0.10:
        recs += ["Review stock availability against the higher projected demand.", "Check supplier lead times and replenishment plans."]
    elif fc_change is not None and fc_change < -0.10:
        recs += ["Review replenishment plans to avoid excess stock.", "Ask account owners whether the decline is customer-specific."]
    else:
        recs.append("Maintain the current replenishment plan; re-run the forecast after the next month closes.")
    if cv is not None and cv > 0.35:
        recs.append("Demand is volatile — investigate unusual months before relying on the point forecast.")
    return {"summary": " ".join(lines), "recent_change": change, "forecast_change": fc_change, "volatility_cv": cv,
            "recommendations": recs, "note": "Recommendations are prompts for human review; nothing is changed automatically."}
