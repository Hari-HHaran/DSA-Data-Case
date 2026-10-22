# Demo walkthrough & video script (2:45)

**Before recording:** `cd backend && python -m app.seed`, start API and frontend, browser at 1440×900, zoom 90%.
Have `docs/demo-assets/sample-product-licence.pdf` ready (a synthetic placeholder document).
The same story is automated in `frontend/e2e/demo.spec.js` — run it once to confirm the environment, then reseed.

| Time | Screen | Action | Say |
|---|---|---|---|
| 0:00 | Sign-in | Show the three pillars | "Lives Group's master-data process runs on email. LIVES ONE replaces it with one record, one workflow and one regional intelligence layer. Everything you'll see runs on synthetic data." |
| 0:12 | Sign in as **Amy** → New Request → *Item / Material* → Continue (SPD, Singapore pre-filled) | | "Amy needs a new item code — the case's exact story." |
| 0:20 | Details | Item name `Viral Transport Medium Swab Kit, 3 mL`, description `50-pack`, Product A, Consumable, BOX, manufacturer `Meditrans Biologics`, part no `MTB-VTM-3ML-50`, **Regulatory classification `Class B`**, Ambient, Stock-managed Yes. Point at the right panel. | "The form explains itself: because it's Class B, licence fields and evidence appear, and the panel shows *who* will approve and *why* — Quality/Regulatory because of the class, Business Support because it's stocked." |
| 0:40 | Click **Check for duplicates** | Licence fields still empty → blocked, highlighted | "Last time Amy left this blank and lost a week. Here, incomplete requests never reach an approver — enforced by the server, not just the screen." |
| 0:48 | Fill licence `HSA-DE-2026-0815`, expiry `2028-06-30`, upload PDF → Check for duplicates | Duplicate card: existing *Viral Transport Medium Kit, 3 mL*, score, reasons | "It finds a near-duplicate and explains why: name similarity after normalisation, same manufacturer, different part number. Nothing merges automatically." |
| 1:00 | *Continue with justification* → "New 50-pack with its own part number" → Review → **Submit** | Success dialog with request number | "Submitted, validated and routed in one step." |
| 1:08 | Switch persona (top-right) → **Siti** → Inbox → Approve; **Daniel** → Approve | | "Quality and the BU Head review in parallel — no more serial email chain. Each sees only their part; banking and credit fields are masked for roles that don't need them." |
| 1:22 | **Kevin** → Approve | | "Business Support follows in stage 2." |
| 1:28 | **Priya** → Command Centre → request in MDM queue → open | Timeline shows each approver, name and time | "Priya sees exactly where it stands — every decision is in a tamper-evident audit trail." |
| 1:38 | Tick the 3 checks → **Verify & create in SAP B1** | `Live in SAP B1: MOCK-I…` | "The SAP adapter submits with an idempotency key; this is a simulated confirmation in the prototype, and a failure is never shown as done." |
| 1:48 | Switch to **Amy** → bell | "…is live" notification | "Amy is told the moment she can transact." |
| 1:55 | Switch to **Marcus** → Regional Overview | Show period statement, KPIs, country × product matrix; click *Malaysia* | "Clean master data pays off commercially: confirmed orders for Products A, B and C across five locations, counted once. Growth is last three months vs the three before." |
| 2:08 | Data Quality & Mapping | Classification table; 125 → 63; 67% false gaps | "Enquiries, purchase requests and MDM set-up requests never inflate demand. And without mapping aliases, two thirds of apparent 'customer doesn't buy X' gaps are false." |
| 2:20 | Demand Forecasting → Product A · Singapore | Held-out markers vs actual; model table | "We backtest the current rolling average against better models. For recurring Product A, the pooled model cuts error by a quarter; for lumpy Product C the simple average still wins — so we keep it. Evidence, not complexity." |
| 2:32 | Growth Opportunities → a cross-sell card → assign to Nurul | Evidence: "x of y comparable hospitals also buy…" | "Every recommendation shows its evidence and becomes a tracked follow-up with an outcome." |
| 2:40 | Business Impact | Hover results | "Capacity released is shown separately from cash and from realised revenue. Pilot one BU in six to eight weeks — no large IT team required." |

**Fallback clips** (if time allows): Admin → Approval Rules → add *Cold-chain regulatory review* when storage is Frozen → the
new-request panel immediately shows the extra approver; Admin → SAP & Notifications → *Fail next call* → Priya sees
"SAP creation failed — NOT live" → *Retry safely*.
