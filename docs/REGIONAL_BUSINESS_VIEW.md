# Regional business view — Products A, B, C across five locations

> **Synthetic data.** Generated with a fixed seed (20261028) across five *illustrative* locations. Figures below are copied from
> the running prototype (Growth Intelligence → Regional Overview / Data Quality / Forecasting) after `python -m app.seed`.
> They demonstrate the method; they are not Lives Group results.

## Scope and definitions

* **Period:** October 2025 – September 2026 (12 months).
* **Measure:** confirmed customer purchase orders — PO lines with status *Confirmed* or *Fulfilled*, a known customer and product,
  quantity > 0, each (PO, line) counted once. Orders are counted once each; quantities stay in each family's unit
  (A = boxes, B = kits, C = units) and are **never summed across families**.
* **Growth:** (sum of the last 3 months − sum of the preceding 3 months) ÷ preceding 3 months.
* **Not demand:** 277 general enquiries, 163 purchase requests, 10 purchase requests waiting on customer MDM set-up, and the
  MDM set-up requests themselves (a separate object in the Flow Engine), plus cancelled, returned and incomplete orders.

## Clean data first

| Step | Records |
|---|---|
| Raw purchasing records | 1,697 |
| Data-quality issues flagged (double-loaded lines, missing product codes, zero quantities) | 29 |
| Excluded by policy (enquiries, requests, cancelled, returned, incomplete) | 545 |
| **Confirmed demand lines** | **1,123** |
| Customer records across SPD/QTS/QTG → distinct customers after confirmed mapping | 125 → 63 |

A naive spreadsheet roll-up of all PO lines overstates demand by **+10.5% (A), +8.4% (B), +7.0% (C)**. Without canonical
mapping, **67% of apparent "customer does not buy product X" gaps are false** (160 of 238) — the customer buys it under another
entity's record — and peer-based cross-sell analysis finds nothing (0 vs 30 candidates).

## Country × product view (confirmed quantity, 3M growth)

| Country | Product A (boxes) | Product B (kits) | Product C (units) | Confirmed POs | PO growth | Active customers |
|---|---|---|---|---|---|---|
| Singapore | 26,284 · **+18.6%** | 6,262 · +8.3% | 182 · −22.8% | 294 | −5.1% | 19 |
| Malaysia | 25,336 · −0.2% | 4,907 · −11.2% | 164 · +4.3% | 237 | −6.3% | 12 |
| Indonesia | 26,103 · +9.8% | 4,191 · **+30.0%** | 83 · +60.0% *(small base)* | 208 | **+7.7%** | 12 |
| Thailand | 11,492 · +3.7% | 3,398 · −21.7% | 181 · −10.9% | 193 | −15.8% | 10 |
| Vietnam | 21,736 · −14.8% | 6,092 · −16.9% | — *(not registered)* | 191 | −6.3% | 10 |
| **Region** | 110,951 · +4.0% | 24,850 · −3.9% | 610 · −5.0% | **1,123** | −5.3% | 63 |

Product C penetration (share of active customers buying it): SG 47%, MY 50%, ID 42%, TH 80%, VN 0%.

## How data science improves forecasting and productivity

* **Rolling-origin backtest** (train only on earlier months, predict 1–3 months ahead, 225 held-out points per model).
* **Product A** (recurring, high volume): pooled ridge regression WAPE **12.6% vs 16.9%** for the rolling average (−25%);
  bias +5% vs −13%.
* **Products B and C:** the rolling average stays best on WAPE (19.0%, 54.2%), so it is kept — but it under-forecasts by 14% and
  24%, which planners should know. Product C is periodic, so quarterly planning may suit it better.
* **Headline (average of families):** WAPE 28.6% vs 30.0% (−4.8%); bias −11% vs −17%. Ranges shown are empirical 80% bands.
* **Productivity:** the same pipeline replaces manual spreadsheet consolidation; enquiries and pending MDM requests are
  separated automatically; forecasts and opportunities refresh on demand.

## Implications and recommended actions

1. **Singapore Product A (+18.6%) and Indonesia Product B (+30%) are growing** — review stock cover and supplier lead times
   for the next quarter; the selected Product A model projects continued growth in Singapore (+5% vs the recent average).
2. **Thailand is the main concern (−15.8% POs; Product B −21.7%) and Vietnam Products A/B are down 15–17%.** The
   opportunity workspace shows these are largely customer-specific ordering gaps (11 high/medium inactivity alerts) — account
   owners should contact those customers before purchasing is cut.
3. **Cross-sell:** 30 evidence-backed candidates (6 high priority), e.g. "11 of 13 comparable hospitals that buy Products A & C
   also buy Product B (85%) and the customer enquired 3 times" — route to account owners, subject to clinical fit and registration.
4. **Vietnam Product C:** zero penetration because the product is not registered there; recommendations are suppressed —
   registration, not sales effort, is the lever.
5. **Unblock revenue:** 10 purchase requests are waiting on customer MDM set-up; faster MDM approval (median 2.45 working days in
   the simulated workflow vs "two to three weeks" in the brief) converts them sooner.
