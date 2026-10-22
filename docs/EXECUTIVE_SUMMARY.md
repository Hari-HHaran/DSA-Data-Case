# LIVES ONE — Executive summary

**One Record. One Workflow. One Regional Intelligence Layer.**
Demo video: *[YouTube link — add after recording]* · Code: *[GitHub link — add after pushing]* · All data synthetic; SAP B1 and Teams/Outlook mocked.

## 1. The problem

Lives Group's master data — customers, vendors, items, cost centres in one shared SAP B1 — is created through email. Requests are
incomplete (Amy guesses regulatory fields), duplicates slip in (is "NUH" the same as "National University Hospital"?), approvals
crawl serially through inboxes (two to three weeks for five approvals), nobody can prove who approved what, bank details travel
by email, and every new BU or approval step needs IT. The same fragmentation hurts the commercial side: three entities key the
same hospital three ways, so five-country demand for Products A, B and C is reconciled by hand and forecast with a rolling average.

## 2. Our solution — one platform, three connected pillars

* **Smart MDM:** a guided form that adapts to the record type and its answers (e.g. Class B items require a licence and evidence),
  validated by the server, with **explainable duplicate detection** against master records, known aliases and in-flight requests.
* **Flow Engine:** rules route each request to the right approvers — **in parallel** where checks are independent — with an
  inbox, Teams/Outlook alerts, SLA reminders and escalation in local working days, a live timeline per approver, role-based masking
  of banking/credit fields, a tamper-evident audit trail, and an **SAP B1 adapter** (idempotent submit, failure state, safe retry).
  Admins change fields, approvers and SLAs as configuration — no IT ticket.
* **Growth Intelligence:** canonical customer mapping turns 125 entity-specific records into 63 customers; purchasing events are
  classified so enquiries, purchase requests and MDM set-up requests never inflate demand; a five-country × A/B/C view with a
  defined growth measure; **backtested forecasting** and explainable cross-sell, inactivity and demand-change opportunities that
  become tracked follow-ups with outcomes.

**Why this over alternatives.** *Email templates / SharePoint lists* fix intake but not duplicates, routing, audit or analytics.
*A Power Automate flow* helps approvals but leaves duplicate detection, SAP hand-off and the regional view fragmented. *A full
MDM suite* is costly and heavy for a lean team. LIVES ONE is purpose-built and small, keeps Outlook/Teams as the front door, and
links data quality to commercial value through one data model.

## 3. Expected impact (prototype evidence on synthetic data + labelled projections)

| | Evidence in prototype | Projection (editable assumptions) |
|---|---|---|
| Speed | Median **2.45 working days** submit→SAP in simulated workflow (brief: 2–3 weeks) | ~1,026 staff hours/yr released (≈0.6 FTE) — capacity, not cash |
| Quality | Incomplete submissions blocked before approvers; duplicate prevented and justified | Bad records 12% → 4%: ~S$21k/yr error cost avoided |
| Governance | 100% of decisions recorded with actor and time; hash chain verifies | Audit evidence in minutes, not email archaeology |
| Forecasting | Product A error −25% (WAPE 12.6% vs 16.9%); headline −4.8%, bias −17% → −11% | Better stock cover for growing markets |
| Growth | 30 evidence-based cross-sell candidates; 11 retention alerts; 67% of naive "gaps" shown to be false | Pipeline for sales review; realised revenue measured only from closed follow-ups |

## 4. Business case — rough cost & effort (assumptions)

* **Pilot build/configuration:** lean 2-person team + MDM team, 6–8 weeks. **SAP B1 Service Layer integration:** SAP partner,
  3–4 weeks. **M365 notifications:** 1 week. **Security review:** 1 week. **Hosting/maintenance:** small VM + PostgreSQL.
* Indicative one-time S$45k and S$18k/year (placeholders in the in-app calculator). Including released capacity, payback ≈ 9
  months; on a cash-only view the first year is negative — we show both.

## 5. Adoption — getting people off email

1. Pilot with the **new business unit** (Marcus' team): no legacy habits, highest pain.
2. Keep people where they work: **Teams/Outlook alerts deep-link to one-click approval**; no new inbox to check.
3. Short train-the-trainer sessions; the form explains *why* each field and approver is needed.
4. Measure turnaround, first-pass validation and duplicates on the Command Centre; refine rules as configuration.
5. Roll out to remaining BUs and countries; then the MDM mailbox auto-replies with the form link and email requests stop.

## 6. Key assumptions

Five illustrative locations (SG, MY, ID, TH, VN); product-to-entity allocation, form fields, routing rules, SLAs, thresholds and ROI
inputs are prototype choices (see `docs/ASSUMPTIONS.md`); SAP B1 field mapping and Service Layer availability must be confirmed;
12 months of history cannot support seasonal models; all data is synthetic.
