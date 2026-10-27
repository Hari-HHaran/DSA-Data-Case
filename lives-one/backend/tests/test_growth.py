import numpy as np
import pandas as pd

from app.database import SessionLocal
from app.services import analytics, forecasting, opportunities
from app.services.clock import add_working_days


def test_five_locations_three_families_and_stated_window(client, login):
    o = client.get("/api/analytics/overview", headers=login("marcus")).json()
    assert len(o["countries"]) == 5
    assert {m["family"] for m in o["matrix"]} == {"A", "B", "C"}
    assert o["window"]["start"] == "2025-10" and o["window"]["end"] == "2026-09" and len(o["window"]["months"]) == 12


def test_growth_definition():
    months = [f"2026-{m:02d}" for m in range(1, 7)]
    s = pd.Series([10, 10, 10, 12, 12, 12], index=months)
    assert analytics.growth(s, months) == 0.2
    assert analytics.growth(pd.Series([0, 0, 0, 5, 5, 5], index=months), months) is None  # no base → undefined, not infinite


def test_cancelled_orders_enquiries_and_mdm_requests_do_not_inflate_demand():
    with SessionLocal() as db:
        p = analytics.prepare(db)
        inc = p.df[p.df["included"]]
        assert set(inc["event_type"]) == {"PURCHASE_ORDER"}
        assert set(inc["status"]) <= {"CONFIRMED", "FULFILLED"}
        assert not inc.duplicated(["source_txn_id", "line_no"]).any()
        raw = p.df[(p.df["event_type"] == "PURCHASE_ORDER")]
        assert raw["quantity"].fillna(0).sum() > inc["quantity"].sum()
        assert p.df[p.df["reason"] == "PENDING_MDM_SETUP"].shape[0] > 0
        ov = analytics.overview(db, {})
        assert sum(r["units"] for r in ov["matrix"]) == inc["quantity"].sum()


def test_filters_update_every_view(client, login):
    h = login("marcus")
    all_ = client.get("/api/analytics/overview", headers=h).json()
    sg = client.get("/api/analytics/overview", params={"countries": "SG", "families": "A"}, headers=h).json()
    assert [t["country"] for t in sg["trend"]] == ["SG"]
    assert {m["country"] for m in sg["matrix"]} == {"SG"} and {m["family"] for m in sg["matrix"]} == {"A"}
    assert [r["country"] for r in sg["ranking"]] == ["SG"]
    assert sg["kpis"]["confirmed_pos"]["value"] < all_["kpis"]["confirmed_pos"]["value"]
    q = client.get("/api/analytics/overview", params={"start": "2026-04", "end": "2026-09"}, headers=h).json()
    assert len(q["window"]["months"]) == 6


def test_backtest_has_no_future_leakage():
    months = [f"2025-{m:02d}" for m in range(1, 13)]
    idx = pd.MultiIndex.from_product([["SG", "MY"], list("ABC")], names=["country_code", "family"])
    rng = np.random.default_rng(1)
    mat = pd.DataFrame(rng.uniform(50, 100, size=(6, 12)), index=idx, columns=months)
    base = forecasting._predict_all(mat, 8, 1, 6)
    changed = mat.copy()
    changed.iloc[:, 8:] *= 100  # wildly change everything at/after the origin
    after = forecasting._predict_all(changed, 8, 1, 6)
    for key in base:
        for model in base[key]:
            assert np.allclose(base[key][model], after[key][model])


def test_forecast_distinguishes_history_backtest_and_future(client, login):
    r = client.get("/api/forecasts", params={"country": "SG", "family": "A"}, headers=login("marcus")).json()
    s = r["series"]
    assert len(s["history"]) == 12 and len(s["future_months"]) == 3
    assert set(s["future_months"]).isdisjoint(s["months"])
    sel = s["models"][s["selected_model"]]
    assert set(sel["future"]) == set(s["future_months"]) and sel["future"][s["future_months"][0]]["lower"] is not None
    assert r["summary"]["evaluations"] and r["summary"]["family_evaluations"]


def test_cross_sell_insights_are_supported_by_data():
    with SessionLocal() as db:
        p = analytics.prepare(db)
        inc = p.df[p.df["included"]]
        fams = inc.groupby("canonical_key")["family"].agg(set)
        cands, _ = opportunities.cross_sell_candidates(db)
        assert cands
        for c in cands:
            assert c["family"] not in fams[c["key"]]
            assert c["rate"] >= opportunities.MIN_ADOPTION and c["peers"] >= opportunities.MIN_PEERS
            assert c["adopters"] == round(c["rate"] * c["peers"])


def test_canonical_mapping_reduces_false_cross_sell(client, login):
    eff = client.get("/api/analytics/data-quality", headers=login("marcus")).json()["cross_sell_mapping_effect"]
    assert eff["apparent_gaps_without_mapping"] > eff["false_gaps_avoided"] >= 1
    assert eff["recommendations_with_mapping"] != eff["recommendations_without_mapping"]


def test_opportunity_followup_flow(client, login):
    h = login("marcus")
    opps = client.get("/api/opportunities", params={"category": "CROSS_SELL", "status": "NEW"}, headers=h).json()["items"]
    o = opps[0]
    nurul = next(u for u in client.get("/api/users", params={"role": "SALES"}, headers=h).json() if u["name"] == "Nurul")
    r = client.post(f"/api/opportunities/{o['id']}/followup", json={"assignee_id": nurul["id"], "note": "Please review"}, headers=h).json()
    assert r["status"] == "ASSIGNED" and r["owner"]["name"] == "Nurul" and r["followups"]
    assert client.patch(f"/api/opportunities/{o['id']}", json={"status": "COMPLETED"}, headers=h).status_code == 422
    done = client.patch(f"/api/opportunities/{o['id']}", json={"status": "COMPLETED", "outcome": "QUOTE_SENT"}, headers=h).json()
    assert done["outcome"] == "QUOTE_SENT"
    assert client.patch(f"/api/opportunities/{o['id']}", json={"status": "IN_PROGRESS"}, headers=login("weijie")).status_code == 403


def test_mapping_review_changes_consolidated_view(client, login):
    priya = login("priya")
    proposed = client.get("/api/canonical-mappings", params={"status": "PROPOSED"}, headers=priya).json()["items"]
    nuh = next(m for m in proposed if m["master_record"]["name"] == "National University Hospital")
    before = client.get("/api/analytics/data-quality", headers=priya).json()["before_after"]["customers_with_mapping"]
    r = client.post(f"/api/canonical-mappings/{nuh['id']}/review", json={"decision": "CONFIRM"}, headers=priya)
    assert r.status_code == 200 and r.json()["review_status"] == "CONFIRMED"
    after = client.get("/api/analytics/data-quality", headers=priya).json()["before_after"]["customers_with_mapping"]
    assert after == before - 1


def test_working_days_skip_weekends():
    from datetime import datetime
    fri = datetime(2026, 10, 23, 2, 0)  # Friday 10:00 SGT
    assert add_working_days(fri, 1).weekday() == 0  # Monday
    assert add_working_days(add_working_days(fri, 3), -3) == fri


def test_analytics_requires_authorised_role(client, login):
    assert client.get("/api/analytics/overview", headers=login("amy")).status_code == 403
    assert client.get("/api/analytics/overview").status_code == 401
