# Business assumptions register

Every number or rule below is a **prototype assumption** unless marked *Brief*. Change them in configuration, seed data or the
ROI calculator; none is presented as Lives Group fact.

| # | Area | Assumption | Why / how to validate | Where configured |
|---|---|---|---|---|
| A1 | Countries | The five locations are SG (HQ, *Brief*), MY, ID, TH, VN | Brief states "five country locations in SEA" without naming them | `countries` table (`seed/reference.py`) |
| A2 | Entities × products | Product A sold via SPD, B via QTS, C via QTG | Brief: entities serve different product lines; allocation unknown | `seed/synthetic.py` |
| A3 | Product behaviour | A recurring consumable (boxes), B recurring reagent (kits), C periodic laboratory solution (units) | Illustrates why one forecast model does not fit all | `products` |
| A4 | Product register | Product C not registered in VN; SKU B-200 not in ID | Shows regulatory suppression of recommendations | `products.registered_countries` |
| A5 | Forms | Field lists per domain (Customer, Vendor, Item, Cost Center) | Not a verified SAP B1 schema; confirm with MDM team | Admin → Form Configuration |
| A6 | Regulated items | Class B–D need licence number, expiry and evidence | Typical medical-device/IVD practice; confirm per country | Validation rules |
| A7 | Routing | Item: BU Head ‖ QRA (if regulated) → Business Support (if stocked). Customer: BU Head ‖ Finance (if credit). Vendor: BU Head → Finance ‖ QRA (if manufacturer). Cost centre: BU Head → Finance | Mirrors approver groups in the brief; parallelises independent checks | Admin → Approval Rules |
| A8 | SLAs | 1–3 working days per step; escalation 1 working day after due; turnaround target 5 working days | Illustrative; public holidays not modelled | Approval Rules, Settings |
| A9 | Duplicate thresholds | ≥ 85 likely, 70–85 review | Calibrated on synthetic variants; tune on real history | Settings |
| A10 | Sensitive fields | Bank details and credit limit visible only to requestor, Finance, MDM | Brief: who sees/edits sensitive fields matters | Field sensitivity |
| A11 | Demand measure | Confirmed + fulfilled PO lines; returns excluded in full | Conservative; partial-return data not available | `services/analytics.py` |
| A12 | Growth measure | 3 months vs preceding 3 months | Robust to single-month noise; works within 12 months | Analytics |
| A13 | Forecast window | 12 months (Oct 2025 – Sep 2026), baseline rolling 6 months | Brief: 6–12 months; 6 leaves room for backtests | Settings |
| A14 | Cross-sell | ≥ 5 peers, ≥ 40% peer adoption, clinic segment not suited to Product C | Evidence threshold for a *review* candidate | `services/opportunities.py` |
| A15 | Simulated workflow | Seeded approvers respond in 0.3–2.2 working days | Shows the mechanism; the brief's "2–3 weeks" is the reference, not a measured baseline | `seed/history.py` |
| A16 | ROI inputs | 120 requests/month; 95 min manual effort; 45% saved; S$55/h; error rate 12% → 4%; S$180/error; S$45k one-time; S$18k/yr | Placeholders to be replaced with a 4-week time study during the pilot | Business Impact page |
| A17 | Build effort | 2-person lean team 6–8 weeks + SAP B1 partner 3–4 weeks + M365 admin 1 week | Brief: no dedicated IT team | Executive summary |
| A18 | Data source | Production would read SAP B1 purchase orders on a schedule | Requires SAP B1 query/Service Layer access | — |
