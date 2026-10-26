<template>
  <div class="page">
    <PageHeader :title="`Good ${greeting}, ${auth.user?.name}`" eyebrow="Command Centre" :subtitle="roleLine">
      <RouterLink v-if="auth.has('REQUESTOR', 'SALES')" to="/mdm/new" class="btn btn-primary"><Plus :size="15" /> New request</RouterLink>
      <RouterLink v-if="d?.my_tasks?.length" to="/flow/inbox" class="btn btn-primary"><Inbox :size="15" /> {{ d.my_tasks.length }} awaiting you</RouterLink>
    </PageHeader>
    <div v-if="$route.query.denied" class="callout warn mb-3"><Lock :size="16" /><div>Your role does not have access to <strong>{{ $route.query.denied }}</strong>. Access is enforced by the server, not just hidden in the menu.</div></div>
    <ErrorState v-if="error" :error="error" :retry="load" class="mb-3" />
    <!-- CHANGED: tell the requestor what needs them, instead of making them scan the list -->
    <div v-if="needsAction.length" class="callout warn mb-3"><AlertTriangle :size="16" /><div><strong>{{ needsAction.length === 1 ? '1 request needs' : `${needsAction.length} requests need` }} your attention:</strong> <RouterLink :to="rowTo(needsAction[0])">{{ needsAction[0].title }}</RouterLink></div></div>

    <div class="pillars mb-3">
      <RouterLink to="/mdm/requests" class="pillar"><ShieldCheck :size="18" /><div><strong>Smart MDM</strong><small>{{ op?.submissions_blocked_by_validation ?? '…' }} bad submissions stopped at intake · {{ op?.duplicates_prevented ?? '…' }} duplicates prevented</small></div></RouterLink>
      <RouterLink to="/flow/tracker" class="pillar"><Workflow :size="18" /><div><strong>Flow Engine</strong><small>{{ op?.awaiting_approval ?? '…' }} in approval · median {{ op?.median_turnaround_days ?? '…' }} working days to SAP</small></div></RouterLink>
      <RouterLink :to="d?.regional ? '/growth/regional' : '/impact'" class="pillar"><LineChart :size="18" /><div><strong>Growth Intelligence</strong>
        <small v-if="d?.regional">{{ fmtNumber(d.regional.kpis.confirmed_pos.value) }} confirmed POs · {{ d.opportunities.open }} open opportunities</small><small v-else>Regional insight for sales & leadership</small></div></RouterLink>
    </div>

    <!-- CHANGED: process-wide numbers only for ops roles and approvers -->
    <template v-if="showOps">
      <h2 class="sec-title">Operations</h2>
      <div class="grid grid-kpi mb-3">
        <KpiTile label="Open MDM requests" :value="op?.open_requests" :icon="FileStack" to="/flow/tracker" :loading="!op" />
        <KpiTile label="Awaiting approval" :value="op?.awaiting_approval" :icon="Hourglass" tone="warning" to="/flow/tracker" :loading="!op" />
        <KpiTile label="Overdue approval tasks" :value="op?.overdue_approvals" :icon="AlarmClock" tone="error" hint="Auto-reminded & escalated" :loading="!op" />
        <KpiTile label="Median turnaround" :value="op?.median_turnaround_days" unit="working days" :hint="`p90 ${op?.p90_turnaround_days ?? '—'} · simulated history`" :icon="Timer" tone="teal" :loading="!op" />
        <KpiTile label="Successful SAP hand-offs" :value="op?.sap_success" :icon="Database" tone="success" :hint="op?.sap_failed_open ? `${op.sap_failed_open} failed, awaiting retry` : 'Mock adapter'" to="/admin/integrations" :loading="!op" />
      </div>
    </template>
    <!-- CHANGED: data-quality metrics only for ops roles -->
    <template v-if="isOps">
      <h2 class="sec-title">Data quality</h2>
      <div class="grid grid-kpi mb-3">
        <KpiTile label="First-pass validation" :value="fmtPct(op?.first_pass_validation_rate)" hint="Submissions accepted on first attempt; the rest were blocked before reaching an approver" :icon="CheckCircle2" tone="success" :loading="!op" />
        <KpiTile label="Potential duplicate rate" :value="fmtPct(op?.potential_duplicate_rate)" hint="Checked requests with ≥1 similar record" :icon="Copy" tone="warning" :loading="!op" />
        <KpiTile label="Duplicates prevented" :value="op?.duplicates_prevented" hint="Requestor reused the existing record" :icon="Recycle" tone="teal" :loading="!op" />
        <KpiTile label="Open requests flagged for review" :value="op?.flagged_for_review" hint="Continued with documented justification" :icon="Flag" :loading="!op" />
      </div>
    </template>

    <template v-if="d?.regional">
      <h2 class="sec-title">Regional business <span class="pill tag-synthetic ms-1">Synthetic</span></h2>
      <div class="grid grid-kpi mb-3">
        <KpiTile label="Confirmed purchase orders" :value="fmtNumber(d.regional.kpis.confirmed_pos.value)" :hint="`${monthLabel(d.regional.window.start)} – ${monthLabel(d.regional.window.end)}`" :icon="ShoppingCart" to="/growth/regional" />
        <KpiTile label="PO growth" :value="fmtPct(d.regional.kpis.po_growth.value, 1, true)" hint="Last 3 months vs preceding 3" :icon="TrendingUp" :tone="d.regional.kpis.po_growth.value >= 0 ? 'success' : 'error'" />
        <KpiTile label="Strongest growth" :value="strongest ? `${strongest.country} · ${strongest.family}` : '—'" :hint="strongest ? `${fmtPct(strongest.growth, 0, true)} confirmed quantity` : ''" :icon="Rocket" tone="teal" />
        <KpiTile label="Forecast accuracy" :value="fmtPct(d.regional.forecast?.accuracy, 1)" :hint="`vs ${fmtPct(d.regional.forecast?.baseline_accuracy, 1)} rolling average`" :icon="Target" to="/growth/forecasting" />
        <KpiTile label="New opportunities" :value="d.opportunities.high" unit="high priority" :hint="`${d.opportunities.open} open · ${d.opportunities.followups_open} follow-ups in progress`" :icon="Lightbulb" tone="warning" to="/growth/opportunities" />
      </div>
    </template>

    <!-- CHANGED: two-column layout only when the activity column is shown -->
    <div class="grid" :class="{ 'grid-main-side': isOps }">
      <div class="d-flex flex-column gap-3 min-w-0">
        <ChartCard v-if="d?.regional" title="Confirmed purchase orders by country" subtitle="Per month, each PO counted once">
          <EChart :option="trendOpt" height="260px" aria-label="Monthly confirmed purchase orders by country" />
        </ChartCard>
        <section v-if="d?.my_tasks" class="card-x">
          <div class="card-x-head"><h2>Waiting on you</h2><RouterLink to="/flow/inbox" class="small">Open inbox</RouterLink></div>
          <EmptyState v-if="!d.my_tasks.length" :icon="CheckCircle2" title="Inbox zero" />
          <RouterLink v-for="t in d.my_tasks" :key="t.id" :to="`/mdm/requests/${t.request_id}`" class="row-link">
            <div class="flex-grow-1"><strong>{{ t.request.title }}</strong><small>{{ t.request.request_number }} · {{ t.step_name }} · {{ t.request.requester.name }}</small></div><SlaPill :state="t.sla_state" /></RouterLink>
        </section>
        <section v-if="d?.mdm_queue" class="card-x">
          <div class="card-x-head"><h2>MDM verification & SAP queue</h2><span class="small text-muted-2">{{ d.mdm_queue.length }} request(s)</span></div>
          <EmptyState v-if="!d.mdm_queue.length" :icon="CheckCircle2" title="Queue clear" />
          <RouterLink v-for="r in d.mdm_queue" :key="r.id" :to="`/mdm/requests/${r.id}`" class="row-link">
            <div class="flex-grow-1"><strong>{{ r.title }}</strong><small>{{ r.request_number }} · {{ r.domain_label }} · {{ r.requester.name }}</small></div><StatusBadge :status="r.status" /></RouterLink>
        </section>
        <section v-if="d?.my_requests?.length || auth.has('REQUESTOR')" class="card-x">
          <div class="card-x-head"><h2>My recent requests</h2><RouterLink to="/mdm/requests" class="small">All</RouterLink></div>
          <EmptyState v-if="!d?.my_requests?.length" title="No requests yet" />
          <!-- CHANGED: requests that need the requestor come first -->
          <RouterLink v-for="r in myRequestsSorted" :key="r.id" :to="rowTo(r)" class="row-link">
            <div class="flex-grow-1"><strong>{{ r.title }}</strong><small>{{ r.request_number }} · {{ r.domain_label }} · updated {{ relTime(r.updated_at) }}</small></div><StatusBadge :status="r.status" /></RouterLink>
        </section>
        <section v-if="d?.opportunities?.top?.length" class="card-x">
          <div class="card-x-head"><h2>Top new opportunities</h2><RouterLink to="/growth/opportunities" class="small">Workspace</RouterLink></div>
          <RouterLink v-for="o in d.opportunities.top" :key="o.id" :to="`/growth/opportunities?id=${o.id}`" class="row-link">
            <div class="flex-grow-1"><strong>{{ o.title }}</strong><small>{{ o.insight }}</small></div><span class="pill" :class="o.priority === 'HIGH' ? 'tone-error' : 'tone-warning'">{{ o.priority.toLowerCase() }}</span></RouterLink>
        </section>
      </div>
      <!-- CHANGED: whole-system activity feed only for the roles that already get the Audit log link -->
      <section v-if="isOps" class="card-x">
        <div class="card-x-head"><h2>Recent activity</h2><RouterLink to="/flow/audit" class="small">Audit log</RouterLink></div>
        <div class="card-x-body"><LoadingBlock v-if="!d" :rows="6" /><AuditList v-else :events="d.activity" show-ref /></div>
      </section>
    </div>
  </div>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  AlarmClock, AlertTriangle, CheckCircle2, Copy, Database, FileStack, Flag, Hourglass, Inbox, Lightbulb, LineChart, Lock, Plus, Recycle, Rocket, ShieldCheck, ShoppingCart,
  Target, Timer, TrendingUp, Workflow,
} from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import KpiTile from '@/components/KpiTile.vue'
import ChartCard from '@/components/ChartCard.vue'
import EChart from '@/components/EChart.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import SlaPill from '@/components/SlaPill.vue'
import AuditList from '@/components/AuditList.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorState from '@/components/ErrorState.vue'
import LoadingBlock from '@/components/LoadingBlock.vue'
import { get } from '@/api/client'
import { useAuth } from '@/stores/auth'
import { fmtNumber, fmtPct, monthLabel, relTime, ROLE_LABELS } from '@/utils/format'
import { INK, axisCategory, axisValue, baseGrid, countryColor, legend, lineSeries, months as mlabels, tooltip } from '@/utils/charts'

const auth = useAuth()
const d = ref(null)
const error = ref(null)
const op = computed(() => d.value?.operational)
const h = new Date().getHours()
const greeting = h < 12 ? 'morning' : h < 18 ? 'afternoon' : 'evening'
const roleLine = computed(() => {
  const roles = auth.roles.map((r) => ROLE_LABELS[r]).filter((r) => r !== auth.user?.title)
  return `${auth.user?.title}${roles.length ? ' · ' + roles.join(', ') : ''}. One view across master data, approvals and regional growth.`
})
// CHANGED (script): same role check the template already used for the Audit log link
const isOps = computed(() => auth.has('ADMIN', 'MDM_ANALYST', 'EXECUTIVE'))
// Approvers are recognised the same way the template does: the API only sends them my_tasks
const showOps = computed(() => isOps.value || d.value?.my_tasks != null)
// ASSUMPTION: matches status keys containing CHANGE / RETURN / DRAFT; adjust to your real keys
const needsAction = computed(() => (d.value?.my_requests || []).filter((r) => /change|return|draft/i.test(r.status)))
const myRequestsSorted = computed(() => {
  const mine = d.value?.my_requests || []
  return [...needsAction.value, ...mine.filter((r) => !needsAction.value.includes(r))]
})
const rowTo = (r) => (r.status === 'DRAFT' ? `/mdm/new?edit=${r.id}` : `/mdm/requests/${r.id}`)
const strongest = computed(() => [...(d.value?.regional?.matrix || [])].filter((m) => m.growth != null).sort((a, b) => b.growth - a.growth)[0])
const trendOpt = computed(() => {
  const r = d.value?.regional
  if (!r) return {}
  return { tooltip: tooltip(), legend: legend(), grid: baseGrid({ top: 56 }), xAxis: axisCategory(mlabels(r.window.months)), yAxis: axisValue('POs / month'),
    series: r.trend.map((t) => lineSeries(t.country, t.values, countryColor(t.country), { endLabel: { show: true, formatter: '{a}', color: INK.text, fontSize: 11 } })) }
})
async function load() { error.value = null; try { d.value = await get('/api/dashboard') } catch (e) { error.value = e } }
onMounted(load)
</script>
<style scoped>
.sec-title { font-size: .8rem; text-transform: uppercase; letter-spacing: .07em; color: var(--muted); margin: 0 0 .6rem; display: flex; align-items: center; }
.pillars { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .75rem; }
@media (max-width: 900px) { .pillars { grid-template-columns: 1fr; } }
.pillar { display: flex; gap: .75rem; align-items: flex-start; padding: .85rem 1rem; border-radius: var(--radius); background: var(--navy); color: #c9d3e6; text-decoration: none; }
.pillar:hover { background: var(--navy-2); text-decoration: none; }
.pillar svg { color: #2dd4bf; flex: none; margin-top: 2px; }
.pillar strong { color: #fff; display: block; }
.pillar small { font-size: .78rem; }
.row-link { display: flex; gap: .75rem; align-items: center; padding: .65rem 1.1rem; border-top: 1px solid var(--border); color: var(--text); text-decoration: none; font-size: .86rem; }
.row-link:hover { background: var(--surface-2); text-decoration: none; }
.row-link small { display: block; color: var(--muted); }
.min-w-0 { min-width: 0; }
</style>