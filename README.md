# LIVES ONE

**One Record. One Workflow. One Regional Intelligence Layer.**

A working prototype for the **SMU DSA Society 2026 Data Case Competition**: *Modernizing Master Data Management at Lives Group*.
LIVES ONE turns master-data management from an email-driven admin chore into a governed workflow, and connects it to
clean five-country purchasing intelligence.

> **Prototype disclosure.** All master data, purchasing records and workflow history are **synthetic** (fixed random seed).
> The five country locations are **illustrative and configurable**. SAP Business One and Microsoft Teams/Outlook run as
> **clearly-labelled mock adapters**. Nothing here is Lives Group data or a claim about Lives Group operations.

| Deliverable | Where |
|---|---|
| A. Working prototype | this repository (`backend/`, `frontend/`) |
| B. Demo video script (2–3 min) | [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) |
| C. Regional business view | in-app **Growth Intelligence → Regional Overview**, write-up in [`docs/REGIONAL_BUSINESS_VIEW.md`](docs/REGIONAL_BUSINESS_VIEW.md) |
| D. Two-page executive summary | [`docs/EXECUTIVE_SUMMARY.md`](docs/EXECUTIVE_SUMMARY.md) |
| Architecture, ERD, state diagram, API, traceability | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| Business assumptions register | [`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md) |

---

## 1. Project overview

Three pillars on one shared data model, plus an executive Command Centre:

| Pillar | What it does |
|---|---|
| **Smart MDM** | Guided, configurable request form for Customer, Vendor, Item and Cost Center records; context-aware validation (backend is the source of truth); explainable duplicate detection against master records *and* in-flight requests; drafts, cloning, corrections; canonical customer mapping. |
| **Flow Engine** | Rule-based routing with parallel and sequential stages; approval inbox; per-approver status timeline; SLA reminders and escalation in country-local working days; append-only, hash-chained audit log; role-based access and sensitive-field masking; no-code form and approval configuration; idempotent SAP B1 adapter with failure, retry and manual resolution. |
| **Growth Intelligence** | Purchasing-event classification (enquiry ≠ purchase request ≠ purchase order ≠ MDM request); cleaning and alias consolidation; five-country × Products A/B/C dashboard with filters; rolling-average baseline vs improved models on rolling-origin backtests; explainable cross-sell, inactivity and demand-change opportunities with owners, status and outcomes; ROI calculator. |

## 2. Problem statement (from the brief)

Requests arrive as free-text email; required fields vary; duplicates (e.g. "National University Hospital" under another name) slip
through; approvals depend on people noticing email, so a five-approval request can take two to three weeks; there is no reliable
record of who approved what; banking and credit details travel by email; any change to forms or approvers needs IT. Separately,
regional forecasts for Products A, B and C across five countries are compiled manually from 6–12 months of purchase orders, and
fragmented customer records across SPD, QTS and QTG make a clean regional view hard.

## 3. Solution architecture

```
Vue 3 SPA ──REST/JSON──▶ FastAPI routers ──▶ services (validation · duplicates · workflow · SLA · audit
                                                      · SAP adapter · notifications · analytics · forecasting · opportunities)
                                                 └──▶ SQLAlchemy ──▶ SQLite (PostgreSQL-compatible schema, Alembic)
Approved record ──▶ SapAdapter (mock today | Service Layer later) ──▶ sap_sync_jobs · sap_record_mappings · integration logs
Workflow events ──▶ NotificationService ──▶ in-app (real) + Teams/Outlook outbox (mock, never sent)
```

Diagrams (architecture, ERD, state machine) are in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## 4. Technology stack

* **Frontend:** Vue 3 (Composition API, JavaScript), Vite, Vue Router, Pinia, Bootstrap 5 + custom design tokens, Apache ECharts via vue-echarts, Lucide icons, Axios.
* **Backend:** Python 3.11+ (tested on 3.13), FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, Uvicorn, passlib/bcrypt, python-jose (JWT).
* **Data science:** pandas, NumPy, scikit-learn (Ridge), statsmodels (exponential smoothing), RapidFuzz.
* **Tests:** pytest (30 backend tests), Vitest (frontend logic), Playwright (end-to-end demo story).

## 5. Installation requirements

Python ≥ 3.11 and Node.js ≥ 20. No SAP or Microsoft 365 credentials are needed.

## 6. Start the app

```bash
# Backend (terminal 1)
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.seed                                      # migrate (Alembic) + load synthetic demo data
uvicorn app.main:app --reload --port 8000               # API docs at http://127.0.0.1:8000/docs

# Frontend (terminal 2)
cd frontend
npm install
npm run dev                                             # http://127.0.0.1:5173 (proxies /api to :8000)
```

`python -m app.seed` resets the database to the same reproducible demo state at any time — run it before recording the demo.
It drops and recreates tables in place, so it is safe to run while the API is up.

## 7. Environment variables

Backend (`backend/.env`, see [`backend/.env.example`](backend/.env.example)) — all optional for a local demo:

| Variable | Default | Purpose |
|---|---|---|
| `LIVES_DATABASE_URL` | `sqlite:///backend/lives_one.db` | Any SQLAlchemy URL (e.g. PostgreSQL) |
| `LIVES_SECRET_KEY` | dev value | JWT signing key — **set in any shared deployment** |
| `LIVES_CORS_ORIGINS` | localhost:5173 | Allowed browser origins |
| `LIVES_DEMO_MODE` | `true` | Enables the persona picker / one-click persona switching |
| `LIVES_DEMO_PASSWORD` | `lives-demo` | Password shared by demo accounts |
| `LIVES_SAP_ADAPTER` | `mock` | `mock` only in the prototype; `service_layer` is a documented stub |
| `LIVES_SLA_SWEEP_SECONDS` | `300` | SLA reminder/escalation sweep interval (0 disables) |

Frontend (`frontend/.env`): `VITE_API_BASE_URL` (empty = use the dev proxy).

## 8. Demo credentials

Pick a persona on the sign-in page (demo mode), or sign in with username + password `lives-demo`.

| Username | Persona | Roles | Source |
|---|---|---|---|
| `amy` | Amy, Product Manager (SPD) | Requestor | Brief persona |
| `weijie` | Wei Jie, Finance Manager | Finance approver | Brief persona |
| `priya` | Priya, MDM Analyst | MDM Analyst | Brief persona |
| `marcus` | Marcus, Regional Sales, new BU (QTG) | Sales, Requestor | Brief persona |
| `daniel` | Daniel, Business Unit Head | BU Head approver | Fictional supporting persona |
| `siti` | Siti, Quality & Regulatory Affairs | QRA approver | Fictional supporting persona |
| `kevin` | Kevin, Business Support | Business Support approver | Fictional supporting persona |
| `alex` | Alex, System Administrator | Administrator | Fictional supporting persona |
| `elaine` | Elaine, Executive Viewer | Executive (read-only) | Fictional supporting persona |
| `ben`, `nurul`, `putri`, `anan`, `linh` | Requestor / country account owners | Requestor / Sales | Fictional |

Persona switching is a **demo convenience** (`LIVES_DEMO_MODE=false` disables it). Every API call is authorised server-side
against the signed-in persona's roles.

## 9. Synthetic dataset

Generated by `backend/app/seed/` with seed `20261028`:

* **Master data:** 58 canonical customers across SG/MY/ID/TH/VN (illustrative), items, vendors, cost centres. Each business
  entity keyed its own customer record — often under a variant name — giving **125 source customer records → 63 distinct customers** after confirmed mappings
  (58 canonical customers + 5 source records whose proposed mapping still awaits MDM review — confirming them reduces the count further). Includes the *National University Hospital* naming scenario (`NUH`, `Natl Univ. Hospital (S)`) **solely to
  demonstrate fuzzy matching**.
* **Purchasing (Oct 2025 – Sep 2026):** ~1,700 raw events — purchase orders with explicit statuses (confirmed, fulfilled,
  cancelled, returned, incomplete), purchase requests (incl. ones waiting on customer MDM set-up), general enquiries.
* **Planted patterns** (so insights are found, not hardcoded): country × family trends, Product C under-adoption among peers,
  customers who stop or reduce ordering, new customers ramping up, Product C not registered in VN.
* **Planted data-quality defects:** double-loaded lines, country spelling variants (`S'pore`, `Viet Nam`), missing product codes,
  zero quantities.
* **Workflow history:** 36 MDM requests produced by driving the real workflow services with a back-dated clock (so every
  state, audit event and timestamp is internally consistent): completed, rejected, returned-and-corrected, overdue/escalated,
  awaiting MDM, a failed SAP call, drafts, and a prevented duplicate.

## 10. Database schema summary

34 tables in seven groups — identity & organisation, master data & canonical mapping, MDM requests, workflow & audit,
SAP integration, purchasing, analytics, configuration. ERD and table notes: [`docs/ARCHITECTURE.md#4-data-model`](docs/ARCHITECTURE.md#4-data-model).
Highlights: request field values are rows (`mdm_request_fields`) driven by `field_definitions`; approval rules are
`workflow_steps` with a validated JSON condition; `workflow_events` is append-only (ORM-level guards) and hash-chained;
canonical mappings are never overwritten (history rows with `is_current`).

## 11. API overview

OpenAPI docs at `/docs`. Main groups: `/api/auth/*`, `/api/mdm/*` (forms, validate, duplicate-check, requests, submit, attachments,
verify), `/api/master-records`, `/api/canonical-mappings`, `/api/approvals/*`, `/api/workflows/*`, `/api/audit-events`,
`/api/notifications`, `/api/sap/*`, `/api/analytics/*`, `/api/forecasts/*`, `/api/opportunities/*`, `/api/config/*`,
`/api/dashboard`, `/api/impact/*`. Full list in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#7-api).

## 12. Forecasting methodology

Target: monthly **confirmed** units per country × product family (15 series × 12 months).
Models: **rolling 6-month average** (today's method), **damped-trend exponential smoothing**, **pooled ridge regression** on
scale-free lag features (one model across all 15 series, so it learns from ~45–90 rows rather than ≤ 11).
Evaluation: **rolling-origin backtest** (origins from month 7, horizons 1–3; never shuffled; no future information in features
or scaling — covered by a leakage test). Metrics: MAE (native units), WAPE, bias. Because A/B/C are measured in different units,
errors are never pooled across families; a **champion model is selected per family** by lowest WAPE (ties → simpler).
Uncertainty: empirical 80% band from backtest relative errors. **Result on the synthetic data:** pooled ridge wins for recurring
Product A (WAPE 12.6% vs 16.9%); the rolling average remains best for Products B and C, so it is kept there — headline WAPE
28.6% vs 30.0% (−4.8% relative) and bias −11% vs −17%. With 12 months, seasonality cannot be estimated (stated in-app).

## 13. Duplicate detection methodology

Normalisation (case, accents, punctuation, legal suffixes such as *Pte Ltd / Sdn Bhd / PT*, abbreviations such as
*Hosp → Hospital, Natl → National*) → exact identifier match (registration no., manufacturer part no., cost-centre code) →
RapidFuzz token similarity against the record **and its known aliases**, plus acronym detection (NUH) → weighted context
(country and address for business partners; manufacturer and unit for items). Score bands are configurable settings:
**≥ 85 likely duplicate** (continue only with documented justification), **70–85 needs review**, **< 70 no significant match**;
an exact identifier match blocks unless the record is reused or flagged for MDM. In-flight requests are checked too.
Nothing is merged automatically. Threshold rationale: obvious variants (abbreviations, suffixes, acronyms) score ≥ 90 while
different institutions sharing words (e.g. "National University Hospital" vs "National Heart Centre") score < 60.

## 14. SAP B1 integration assumptions

The adapter builds a per-domain payload (BusinessPartners for customers/vendors, Items, ProfitCenters for cost centres —
**field mapping assumed, to be confirmed**), validates it, submits with an idempotency key per request cycle, persists job
status, logs failures and supports safe retry and manual resolution. A failed creation is never shown as completed.
The mock returns keys prefixed `MOCK-`. A real integration needs: SAP B1 version and Service Layer availability, company
database, service account and permissions, confirmed field mapping and UDFs, and an idempotency check (LIVES ONE request
number stored in a UDF).

## 15. Known limitations

* Synthetic data only; insights demonstrate the method, not Lives Group facts.
* 12 months of history: no seasonality; Product C forecasts are inherently noisy (periodic purchasing).
* Maintenance (update) requests, attachment virus scanning, public-holiday calendars and delegation/out-of-office are out of scope.
* Demo authentication (JWT + demo personas); no SSO. SQLite for the prototype.
* Approvers are assigned by role (any holder of the role can act), not to named individuals per entity.

## 16. Prototype vs production

| Area | Prototype | Production |
|---|---|---|
| SAP B1 | Mock adapter, simulated keys | Service Layer adapter, confirmed mapping, UDF idempotency |
| Notifications | In-app real; Teams/Outlook mock outbox | Microsoft Graph (Teams activity feed, Outlook) |
| Auth | JWT + demo personas | Entra ID SSO, MFA |
| Database | SQLite | PostgreSQL, backups |
| Audit | Hash-chained application log | + external log shipping / WORM storage if required |
| Data | Synthetic seed | SAP B1 purchase-order extract (scheduled) |

## 17. Testing

```bash
cd backend && pytest -q                        # 30 tests: validation, duplicates, RBAC, parallel/sequential approvals,
                                               # SAP failure & idempotency, audit immutability, analytics policy, leakage, filters
cd frontend && npm test                        # Vitest: formatting + condition-language logic
# End-to-end (API on :8000 freshly seeded, Vite on :5173):
cd frontend && npx playwright install chromium && npm run test:e2e
```

The Playwright suite drives the whole demo story: Amy is blocked by the missing licence, uploads evidence, reviews a near
duplicate and submits; QRA and BU Head approve in parallel, Business Support after; Priya verifies and the mock SAP adapter
returns a key; Amy is notified; Marcus filters the regional view and assigns a cross-sell follow-up; Amy is denied analytics (403).

## 18. Competition deliverables checklist

- [x] Working prototype demonstrating the approach and its connection to SAP B1 (mock adapter + documented real path)
- [x] Visual of process/solution (in-app flow preview, timeline; diagrams in `docs/ARCHITECTURE.md`)
- [x] Regional business view: Products A/B/C × five locations, stated 12-month period, defined growth metric
- [x] Data science improves forecasting (backtested) and productivity (validation, routing, SLA)
- [x] Business implications and recommended actions (in-app + `docs/REGIONAL_BUSINESS_VIEW.md`)
- [x] Purchase requests/orders distinguished from MDM set-up requests (classification & exclusion summary)
- [x] Two-page executive summary with cost/effort, adoption, assumptions
- [ ] Record the 2–3 minute demo (script ready) and upload to YouTube; add the link to `docs/EXECUTIVE_SUMMARY.md`
- [ ] Push to GitHub and add the repository link to `docs/EXECUTIVE_SUMMARY.md`
