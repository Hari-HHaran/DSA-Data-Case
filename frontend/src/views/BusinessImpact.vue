<template>
  <div class="page">
    <PageHeader title="Business impact" eyebrow="Impact & feasibility" subtitle="What the prototype measured (on synthetic data), what we project (under editable assumptions), and what it takes to adopt — kept strictly separate." />

    <h2 class="sec-title">1 · Measured in the prototype <span class="pill tag-synthetic ms-1">Synthetic data · mechanism evidence</span></h2>
    <ErrorState v-if="mErr" :error="mErr" class="mb-3" />
    <div class="grid grid-kpi mb-2">
      <KpiTile label="Median turnaround (simulated)" :value="m?.workflow.median_turnaround_days" unit="working days" :hint="`p90 ${m?.workflow.p90_turnaround_days ?? '—'} · brief: '2–3 weeks'`" :icon="Timer" tone="teal" :loading="!m" />
      <KpiTile label="Submissions blocked at intake" :value="m?.submissions_blocked_by_validation" hint="Incomplete requests that never reached an approver" :icon="ShieldCheck" :loading="!m" />
      <KpiTile label="Duplicates prevented" :value="m?.duplicates_prevented" hint="Existing record reused instead of a new one" :icon="Recycle" :loading="!m" />
      <KpiTile label="Decisions with actor + time" :value="m ? `${m.audit_decisions_with_actor_and_time}/${m.audit_decisions_total}` : null" hint="Approval evidence in one audit log, not email" :icon="FileCheck" tone="success" :loading="!m" />
      <KpiTile label="Forecast error vs baseline" :value="fmtPct(m?.forecast?.wape_reduction_vs_baseline, 1)" :hint="`WAPE ${fmtPct(1 - (m?.forecast?.accuracy ?? 0), 1)} vs ${fmtPct(1 - (m?.forecast?.baseline_accuracy ?? 0), 1)} (lower is better)`" :icon="Target" :loading="!m" />
    </div>
    <p class="small text-muted-2 mb-4">{{ m?.label }} {{ m?.brief_reference }}</p>

    <div class="grid grid-2 mb-4">
      <section class="card-x">
        <div class="card-x-head"><h2>Before → after LIVES ONE</h2></div>
        <div class="table-responsive"><table class="table">
          <thead><tr><th>Dimension</th><th>Before (as described in the brief)</th><th>After (demonstrated in prototype)</th></tr></thead>
          <tbody><tr v-for="r in beforeAfter" :key="r[0]"><td class="fw-semibold">{{ r[0] }}</td><td class="small">{{ r[1] }}</td><td class="small">{{ r[2] }}</td></tr></tbody></table></div>
      </section>
      <section class="card-x">
        <div class="card-x-head"><h2>Commercial outcomes tracked</h2><span class="small text-muted-2">Only completed follow-ups count as outcomes</span></div>
        <div class="card-x-body">
          <EmptyState v-if="!m?.opportunity_outcomes?.length" title="No completed follow-ups yet" />
          <div v-for="o in m?.opportunity_outcomes || []" :key="o.title" class="callout neutral mb-2 small"><CheckCircle2 :size="15" /><div><strong>{{ o.title }}</strong> — {{ humanize(o.outcome) }}<div class="text-muted-2">{{ o.note }}</div></div></div>
          <div v-if="m?.data_quality" class="small mt-2">Clean data: {{ fmtNumber(m.data_quality.raw) }} raw purchasing records → {{ fmtNumber(m.data_quality.valid) }} confirmed-demand lines ({{ fmtNumber(m.data_quality.flagged) }} data-quality issues, {{ fmtNumber(m.data_quality.excluded_by_policy) }} non-demand signals);
            {{ m.data_quality.before_after.customers_without_mapping }} customer records → {{ m.data_quality.before_after.customers_with_mapping }} canonical customers.</div>
        </div>
      </section>
    </div>

    <h2 class="sec-title">2 · Projected value <span class="pill tone-warning ms-1">Assumptions — edit them</span></h2>
    <div class="grid grid-main-side mb-4">
      <section class="card-x">
        <div class="card-x-head"><h2>Assumptions</h2><button class="btn btn-ghost btn-sm" type="button" @click="reset"><RotateCcw :size="13" /> Defaults</button></div>
        <div class="card-x-body form-grid">
          <div v-for="f in fields" :key="f.key"><label class="form-label" :for="f.key">{{ f.label }}</label>
            <div class="input-group input-group-sm"><span v-if="f.prefix" class="input-group-text">{{ f.prefix }}</span>
              <input :id="f.key" v-model.number="a[f.key]" type="number" class="form-control" :step="f.step || 1" min="0" :max="f.max" @input="calc" />
              <span v-if="f.suffix" class="input-group-text">{{ f.suffix }}</span></div>
            <div class="form-text">{{ f.hint }}</div></div>
        </div>
      </section>
      <section class="card-x">
        <div class="card-x-head"><h2>Results</h2><span class="small text-muted-2">First year</span></div>
        <div class="card-x-body" v-if="r">
          <div class="res"><span class="lbl"><Clock :size="15" /> Staff capacity released</span><span class="num v">{{ fmtNumber(r.staff_hours_released) }} h</span><small>≈ {{ r.fte_equivalent }} FTE · valued at {{ fmtMoney(r.labour_capacity_value) }} — <em>capacity, not cash</em></small></div>
          <div class="res"><span class="lbl"><ShieldCheck :size="15" /> Error-cost avoidance</span><span class="num v">{{ fmtMoney(r.error_cost_avoided) }}</span><small>{{ fmtNumber(r.errors_avoided) }} bad records avoided — closest to a cash saving</small></div>
          <div class="res"><span class="lbl"><Lightbulb :size="15" /> Revenue opportunity identified</span><span class="num v">{{ fmtMoney(r.revenue_opportunity_identified) }}</span><small>Pipeline for review; expected at {{ fmtPct(a.conversion_rate) }} conversion: {{ fmtMoney(r.expected_incremental_revenue) }}</small></div>
          <div class="res"><span class="lbl"><BadgeCheck :size="15" /> Realised incremental revenue</span><span class="num v">Not yet measured</span><small>Recorded only from completed sales follow-ups after rollout</small></div>
          <div class="divider" />
          <div class="res"><span class="lbl">Net value incl. capacity</span><span class="num v" :class="r.first_year_net_value_including_capacity >= 0 ? 'text-success' : 'text-danger'">{{ fmtMoney(r.first_year_net_value_including_capacity) }}</span></div>
          <div class="res"><span class="lbl">Net cash-only view (conservative)</span><span class="num v" :class="r.first_year_net_cash_only >= 0 ? 'text-success' : 'text-danger'">{{ fmtMoney(r.first_year_net_cash_only) }}</span></div>
          <div class="res"><span class="lbl">Payback (incl. capacity)</span><span class="num v">{{ r.payback_months_including_capacity ? `${r.payback_months_including_capacity} months` : 'n/a' }}</span></div>
          <ul class="small text-muted-2 ps-3 mt-2 mb-0"><li v-for="n in r.notes" :key="n">{{ n }}</li></ul>
        </div>
      </section>
    </div>

    <h2 class="sec-title">3 · Feasibility, cost & adoption</h2>
    <div class="grid grid-2 mb-3">
      <section class="card-x">
        <div class="card-x-head"><h2>Rough cost & effort (assumption)</h2><span class="small text-muted-2">No large internal IT team assumed</span></div>
        <div class="table-responsive"><table class="table">
          <thead><tr><th>Item</th><th>Who</th><th class="text-end">Effort / cost</th></tr></thead>
          <tbody><tr v-for="c in costs" :key="c[0]"><td><strong>{{ c[0] }}</strong><div class="small text-muted-2">{{ c[3] }}</div></td><td class="small">{{ c[1] }}</td><td class="num text-end small">{{ c[2] }}</td></tr></tbody></table></div>
      </section>
      <section class="card-x">
        <div class="card-x-head"><h2>Adoption plan — getting people off email</h2></div>
        <div class="card-x-body">
          <ol class="plan">
            <li v-for="(p, i) in plan" :key="i"><span class="n">{{ i + 1 }}</span><div><strong>{{ p[0] }}</strong><small>{{ p[1] }}</small></div></li>
          </ol>
        </div>
      </section>
    </div>
    <div class="callout ok"><BadgeCheck :size="18" /><div><strong>Implementation feasibility.</strong> The prototype runs on a lean, open stack (Vue, FastAPI, SQLite→PostgreSQL). Forms, approval rules and SLAs are configuration, so the MDM team can add a domain, field or approval step without IT. The only specialist work is the SAP B1 Service Layer connection (field mapping, authentication, idempotency) and Microsoft 365 notifications — both already isolated behind adapters that run in mock mode today.</div></div>
  </div>
</template>
<script setup>
import { onMounted, reactive, ref } from 'vue'
import { BadgeCheck, CheckCircle2, Clock, FileCheck, Lightbulb, Recycle, RotateCcw, ShieldCheck, Target, Timer } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import KpiTile from '@/components/KpiTile.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorState from '@/components/ErrorState.vue'
import { get, post } from '@/api/client'
import { fmtMoney, fmtNumber, fmtPct, humanize } from '@/utils/format'

const m = ref(null)
const mErr = ref(null)
const r = ref(null)
const defaults = ref({})
const a = reactive({})
const fields = [
  { key: 'requests_per_month', label: 'MDM requests per month', hint: 'All entities and countries' },
  { key: 'manual_minutes_per_request', label: 'Manual handling time per request', suffix: 'min', hint: 'Requestor + approvers + MDM chasing and re-keying' },
  { key: 'projected_saving_pct', label: 'Share of that effort removed', step: 0.05, max: 1, hint: '0–1 (0.45 = 45%)' },
  { key: 'loaded_hourly_cost', label: 'Loaded hourly staff cost', prefix: 'S$', hint: 'Fully-loaded cost per hour' },
  { key: 'error_rate_before', label: 'Records needing later correction — today', step: 0.01, max: 1, hint: '0–1' },
  { key: 'error_rate_after', label: '…with validation & duplicate checks', step: 0.01, max: 1, hint: '0–1' },
  { key: 'cost_per_error', label: 'Cost to fix one bad record', prefix: 'S$', hint: 'Re-invoicing, reconciliation, wrong shipment' },
  { key: 'one_time_cost', label: 'One-time implementation cost', prefix: 'S$', hint: 'Build/configure, SAP integration, training' },
  { key: 'annual_operating_cost', label: 'Annual operating cost', prefix: 'S$', hint: 'Hosting, support, maintenance' },
  { key: 'pipeline_value', label: 'Opportunity pipeline surfaced / year', prefix: 'S$', hint: 'Not revenue — sales review candidates' },
  { key: 'conversion_rate', label: 'Expected conversion', step: 0.05, max: 1, hint: '0–1' },
]
const beforeAfter = [
  ['Intake', 'Free-text emails, copied spreadsheets; fields guessed', 'Guided form per domain; conditional fields & documents; server-side validation'],
  ['Duplicates', 'Depends on Priya remembering', 'Explainable fuzzy + identifier matching against records and in-flight requests'],
  ['Approvals', 'Sequential email chain; approvers must notice', 'Rule-based routing, parallel stages, inbox + Teams/Outlook alerts, SLAs, escalation'],
  ['Visibility', 'Requestor asks the shared mailbox', 'Live timeline with per-approver status and next action'],
  ['Audit', 'Scattered email threads; bank details in email', 'Hash-chained audit log; banking/credit fields masked by role'],
  ['Change', 'IT redrafts templates and lists', 'Admin edits fields, rules and SLAs as configuration'],
  ['SAP B1', 'Manually keyed, requestor not told', 'Adapter with idempotent submit, retry, failure state, completion notice'],
  ['Regional view', 'Manual spreadsheet consolidation', 'Classified, de-duplicated, alias-mapped confirmed demand'],
  ['Forecasting', '6–12-month rolling average', 'Backtested comparison; per-family champion; uncertainty and plain-language explanation'],
  ['Growth actions', 'Ad hoc', 'Evidence-backed cross-sell / retention candidates with owner, status, outcome'],
]
const costs = [
  ['Pilot build & configuration', 'Lean project team (2 people) + MDM team', '6–8 weeks', 'Harden prototype, configure 4 domains, pilot BU rules'],
  ['SAP B1 Service Layer integration', 'SAP B1 partner (external)', '3–4 weeks', 'Field mapping, auth, idempotency UDF, test company DB'],
  ['Microsoft 365 notifications', 'M365 admin', '1 week', 'Graph app registration for Teams/Outlook'],
  ['Security review', 'External reviewer', '1 week', 'Access control, sensitive fields, hosting'],
  ['Training', 'MDM team (train-the-trainer)', '2 × 1h per group', 'Requestors, approvers, sales'],
  ['Hosting & maintenance', 'Cloud / internal VM', 'Low (see assumptions)', 'PostgreSQL, backups, monitoring'],
]
const plan = [
  ['Pilot with one business unit', 'Start with the new BU (Marcus\' team) — no legacy habits, highest pain.'],
  ['Train requestors and approvers', 'Short sessions; the form explains itself (why each field and approver is needed).'],
  ['Meet people where they are', 'Teams/Outlook alerts link straight to the one-click approval — no new inbox to check.'],
  ['Measure', 'Turnaround, first-pass validation, duplicates prevented, overdue tasks — visible on the Command Centre.'],
  ['Refine rules', 'MDM team adjusts fields, approvers and SLAs as configuration.'],
  ['Extend', 'Roll out to remaining BUs and countries; add maintenance (update) requests.'],
  ['Retire email intake', 'MDM mailbox auto-replies with the form link; email requests no longer accepted.'],
]
let t = null
function calc() { clearTimeout(t); t = setTimeout(async () => { try { r.value = await post('/api/impact/calculate', { assumptions: { ...a } }) } catch { /* invalid input */ } }, 250) }
function reset() { Object.assign(a, defaults.value); calc() }
onMounted(async () => {
  try { m.value = await get('/api/impact/measured') } catch (e) { mErr.value = e }
  defaults.value = await get('/api/impact/assumptions')
  reset()
})
</script>
<style scoped>
.sec-title { font-size: .8rem; text-transform: uppercase; letter-spacing: .07em; color: var(--muted); margin: 0 0 .6rem; display: flex; align-items: center; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .9rem 1rem; }
@media (max-width: 700px) { .form-grid { grid-template-columns: 1fr; } }
.res { display: grid; grid-template-columns: 1fr auto; gap: .1rem .75rem; padding: .45rem 0; }
.res .lbl { font-weight: 600; font-size: .86rem; display: flex; gap: .4rem; align-items: center; }
.res .v { font-weight: 700; font-size: 1.05rem; text-align: right; }
.res small { grid-column: 1 / -1; color: var(--muted); font-size: .76rem; }
.plan { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: .6rem; }
.plan li { display: flex; gap: .65rem; font-size: .86rem; }
.plan small { display: block; color: var(--muted); }
.plan .n { width: 26px; height: 26px; border-radius: 50%; background: linear-gradient(140deg, #ccfbf1, #99f6e4); color: #0f766e; font-weight: 700; font-size: .75rem; display: inline-flex; align-items: center; justify-content: center; flex: none; }
</style>
