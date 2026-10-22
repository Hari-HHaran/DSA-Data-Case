"""Business-impact calculator. Separates capacity released from cash savings, and revenue opportunity from
realised revenue. Every input is an editable assumption."""

DEFAULT_ASSUMPTIONS = {
    "requests_per_month": 120,          # assumption: MDM requests across all entities/countries
    "manual_minutes_per_request": 95,   # assumption: requestor + approvers + MDM chasing, re-keying, follow-ups
    "projected_saving_pct": 0.45,       # assumption: share of that effort removed by structured intake + workflow
    "loaded_hourly_cost": 55.0,         # assumption: SGD per staff hour, fully loaded
    "error_rate_before": 0.12,          # assumption: share of records needing later correction today
    "error_rate_after": 0.04,           # assumption: after validation + duplicate checks
    "cost_per_error": 180.0,            # assumption: SGD to find & fix a bad record (re-invoicing, reconciliation)
    "annual_operating_cost": 18000.0,   # assumption: hosting, support, licences
    "one_time_cost": 45000.0,           # assumption: build/configure, SAP integration, training
    "pipeline_value": 250000.0,         # assumption: value of opportunities surfaced per year (not realised revenue)
    "conversion_rate": 0.10,            # assumption: share of pipeline expected to convert
}


def calculate(a: dict) -> dict:
    x = {**DEFAULT_ASSUMPTIONS, **{k: float(v) for k, v in a.items() if k in DEFAULT_ASSUMPTIONS and v is not None}}
    for k, v in x.items():
        if v < 0:
            raise ValueError(f"{k} cannot be negative")
    if x["projected_saving_pct"] > 1 or x["conversion_rate"] > 1:
        raise ValueError("Percentages must be between 0 and 1")
    annual_requests = x["requests_per_month"] * 12
    hours_released = annual_requests * x["manual_minutes_per_request"] / 60 * x["projected_saving_pct"]
    capacity_value = hours_released * x["loaded_hourly_cost"]
    errors_avoided = annual_requests * max(0.0, x["error_rate_before"] - x["error_rate_after"])
    error_cost_avoided = errors_avoided * x["cost_per_error"]
    expected_revenue = x["pipeline_value"] * x["conversion_rate"]
    # Conservative first-year view: cash-like benefit = error-cost avoidance only; capacity is not cash unless redeployed.
    first_year_net_cash = error_cost_avoided - x["annual_operating_cost"] - x["one_time_cost"]
    first_year_net_incl_capacity = capacity_value + error_cost_avoided - x["annual_operating_cost"] - x["one_time_cost"]
    monthly_benefit = (capacity_value + error_cost_avoided - x["annual_operating_cost"]) / 12
    payback = round(x["one_time_cost"] / monthly_benefit, 1) if monthly_benefit > 0 else None
    return {
        "assumptions": x,
        "annual_requests": annual_requests,
        "staff_hours_released": round(hours_released, 0),
        "fte_equivalent": round(hours_released / 1720, 2),
        "labour_capacity_value": round(capacity_value, 0),
        "errors_avoided": round(errors_avoided, 0),
        "error_cost_avoided": round(error_cost_avoided, 0),
        "revenue_opportunity_identified": round(x["pipeline_value"], 0),
        "expected_incremental_revenue": round(expected_revenue, 0),
        "realised_incremental_revenue": None,
        "first_year_net_value_including_capacity": round(first_year_net_incl_capacity, 0),
        "first_year_net_cash_only": round(first_year_net_cash, 0),
        "payback_months_including_capacity": payback,
        "notes": [
            "Staff capacity released is not a cash saving unless the time is redeployed or hiring is avoided.",
            "Revenue opportunity is pipeline for sales review; realised revenue is only recorded from completed follow-ups.",
            "Payback uses capacity value + error-cost avoidance − operating cost; it is a projection, not an observed outcome.",
        ],
    }
