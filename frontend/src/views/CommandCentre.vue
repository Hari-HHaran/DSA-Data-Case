<template>
  <div class="page home">
    <!-- Greeting -->
    <header class="hello">
      <div>
        <h1>Hello, {{ firstName }}!</h1>
        <p>{{ helloLine }}</p>
      </div>
      <div class="hello-actions">
        <RouterLink v-for="a in heroActions" :key="a.to" :to="a.to" class="btn" :class="a.primary ? 'btn-glow' : 'btn-soft'">
          <component :is="a.icon" :size="16" /> {{ a.label }}</RouterLink>
      </div>
    </header>

    <div v-if="$route.query.denied" class="callout warn mb-3"><Lock :size="16" /><div>Your role does not have access to <strong>{{ $route.query.denied }}</strong>.</div></div>
    <ErrorState v-if="error" :error="error" :retry="load" class="mb-3" />

    <!-- Highlight banner: the single most important thing for this person right now -->
    <Transition name="fade">
      <section v-if="focus && !hideFocus" class="focus-banner" role="status">
        <div class="fb-icon"><component :is="focus.icon" :size="22" /></div>
        <div class="fb-text"><strong>{{ focus.title }}</strong><span>{{ focus.text }}</span></div>
        <RouterLink :to="focus.to" class="btn fb-btn">{{ focus.cta }} <ArrowRight :size="15" /></RouterLink>
        <button class="fb-close" type="button" aria-label="Dismiss" @click="hideFocus = true"><X :size="16" /></button>
        <span class="fb-blob a" aria-hidden="true" /><span class="fb-blob b" aria-hidden="true" />
      </section>
    </Transition>

    <!-- Shortcut carousel -->
    <CardCarousel title="Quick start" label="Shortcuts for your role" class="mb-4">
      <RouterLink v-for="t in tiles" :key="t.to" :to="t.to" class="tile">
        <div class="tile-art" :class="`th-${t.theme}`">
          <span class="art-dots" aria-hidden="true"><i /><i /><i /></span>
          <span class="art-bars" aria-hidden="true"><i /><i /></span>
          <span class="art-ic"><component :is="t.icon" :size="22" /></span>
          <span v-if="t.badge != null" class="art-badge num">{{ t.badge }}</span>
        </div>
        <div class="tile-body">
          <small>{{ t.caption }}</small>
          <strong>{{ t.title }} <ChevronRight :size="15" /></strong>
        </div>
      </RouterLink>
      <RouterLink v-if="canRequest" to="/mdm/new" class="tile tile-add">
        <span class="add-orb" aria-hidden="true" /><span class="add-orb two" aria-hidden="true" />
        <span class="add-pill"><Plus :size="15" /> New request</span>
        <small>Item, customer, vendor or cost centre</small>
      </RouterLink>
    </CardCarousel>

    <!-- Stat cards -->
    <div class="stats mb-4">
      <template v-if="!d && !error"><div v-for="i in 4" :key="i" class="soft-card stat"><span class="skeleton" style="height:76px" /></div></template>
      <component :is="s.to ? RouterLink : 'div'" v-for="s in stats" :key="s.label" :to="s.to" class="soft-card stat" :class="{ link: !!s.to }">
        <div class="stat-top">
          <span class="stat-ic" :style="{ background: s.soft, color: s.color }"><component :is="s.icon" :size="17" /></span>
          <span class="stat-label">{{ s.label }}</span>
        </div>
        <div class="stat-value num">{{ s.value ?? '—' }}<small v-if="s.unit">{{ s.unit }}</small></div>
        <div v-if="s.hint" class="stat-hint">{{ s.hint }}</div>
        <SparkLine v-if="s.spark" :values="s.spark" :color="s.color" :label="`${s.label} trend`" />
        <div v-else-if="s.progress != null" class="stat-bar"><span :style="{ width: Math.min(100, s.progress * 100) + '%', background: s.color }" /></div>
      </component>
    </div>

    <div class="main-grid mb-4">
      <!-- LEFT: work lists -->
      <div class="col-stack">
        <section v-if="d?.my_tasks" class="soft-card">
          <div class="sc-head"><h2>Waiting on you</h2><RouterLink to="/flow/inbox" class="see-all">Open inbox <ChevronRight :size="14" /></RouterLink></div>
          <EmptyState v-if="!d.my_tasks.length" :icon="PartyPopper" title="You're all caught up" text="Nothing is waiting for your approval." />
          <div v-else class="tbl-wrap"><table class="tbl">
            <thead><tr><th>Request</th><th>Your step</th><th>From</th><th>Deadline</th><th /></tr></thead>
            <tbody><tr v-for="t in d.my_tasks" :key="t.id" @click="$router.push(`/mdm/requests/${t.request_id}`)">
              <td><RouterLink :to="`/mdm/requests/${t.request_id}`" class="t-title" @click.stop>{{ t.request.title }}</RouterLink><small>{{ t.request.request_number }} · {{ t.request.domain_label }}</small></td>
              <td>{{ t.step_name }}</td>
              <td><span class="who"><span class="mini-av">{{ initials(t.request.requester.name) }}</span>{{ t.request.requester.name }}</span></td>
              <td><span class="date-pill" :class="slaTone(t.sla_state)">{{ slaText(t) }}</span></td>
              <td class="text-end"><ChevronRight :size="16" class="text-muted-2" /></td>
            </tr></tbody>
          </table></div>
        </section>

        <section v-if="d?.mdm_queue" class="soft-card">
          <div class="sc-head"><h2>Ready for checking &amp; SAP</h2><RouterLink to="/flow/tracker" class="see-all">Tracker <ChevronRight :size="14" /></RouterLink></div>
          <EmptyState v-if="!d.mdm_queue.length" :icon="PartyPopper" title="Queue is clear" text="No approved requests are waiting for you." />
          <div v-else class="tbl-wrap"><table class="tbl">
            <thead><tr><th>Request</th><th>Category</th><th>Raised by</th><th>Status</th></tr></thead>
            <tbody><tr v-for="r in d.mdm_queue.slice(0, 6)" :key="r.id" @click="$router.push(`/mdm/requests/${r.id}`)">
              <td><RouterLink :to="`/mdm/requests/${r.id}`" class="t-title" @click.stop>{{ r.title }}</RouterLink><small>{{ r.request_number }}</small></td>
              <td>{{ r.domain_label }}</td>
              <td><span class="who"><span class="mini-av">{{ initials(r.requester.name) }}</span>{{ r.requester.name }}</span></td>
              <td><StatusBadge :status="r.status" /></td>
            </tr></tbody>
          </table></div>
        </section>

        <section v-if="d && (d.my_requests?.length || canRequest)" class="soft-card">
          <div class="sc-head"><h2>My requests</h2><RouterLink to="/mdm/requests" class="see-all">View all <ChevronRight :size="14" /></RouterLink></div>
          <EmptyState v-if="!d.my_requests?.length" :icon="FilePlus2" title="No requests yet" text="When you need a new item, customer or vendor code, start here.">
            <RouterLink to="/mdm/new" class="btn btn-glow btn-sm"><Plus :size="14" /> New request</RouterLink></EmptyState>
          <div v-else class="tbl-wrap"><table class="tbl">
            <thead><tr><th>Request</th><th>Category</th><th>Status</th><th>Last update</th></tr></thead>
            <tbody><tr v-for="r in myRequestsSorted" :key="r.id" :class="{ attn: needsAction.includes(r) }" @click="$router.push(rowTo(r))">
              <td><RouterLink :to="rowTo(r)" class="t-title" @click.stop>{{ r.title }}</RouterLink><small>{{ r.request_number }}</small></td>
              <td>{{ r.domain_label }}</td>
              <td><StatusBadge :status="r.status" /></td>
              <td class="text-muted-2">{{ relTime(r.updated_at) }}</td>
            </tr></tbody>
          </table></div>
        </section>

        <ChartCard v-if="d?.regional && showRegional" title="Confirmed purchase orders by country" subtitle="Per month, each order counted once" class="soft-card chart-soft">
          <template #actions><RouterLink to="/growth/regional" class="see-all">Regional overview <ChevronRight :size="14" /></RouterLink></template>
          <EChart :option="trendOpt" height="260px" aria-label="Monthly confirmed purchase orders by country" />
        </ChartCard>
      </div>

      <!-- RIGHT: breakdown + progress + activity -->
      <aside class="col-stack">
        <section v-if="donut" class="soft-card">
          <div class="sc-head"><div><h2>{{ donut.title }}</h2><p class="sc-sub">{{ donut.sub }}</p></div></div>
          <div class="sc-body"><DonutChart :data="donut.data" :center-label="donut.center" :aria-label="donut.title" /></div>
        </section>

        <section v-for="p in progressCards" :key="p.label" class="soft-card prog">
          <div class="prog-top">
            <div><strong>{{ p.label }}</strong><small>{{ p.sub }}</small></div>
            <span class="prog-ic" :style="{ background: p.soft, color: p.color }"><component :is="p.icon" :size="16" /></span>
          </div>
          <div class="prog-val num">{{ fmtPct(p.value, 0) }}</div>
          <div class="stat-bar"><span :style="{ width: Math.min(100, (p.value || 0) * 100) + '%', background: p.color }" /></div>
        </section>

        <section v-if="d" class="soft-card">
          <div class="sc-head"><h2>{{ d.activity_scope === 'all' ? 'Recent activity' : 'Updates on your work' }}</h2>
            <RouterLink v-if="d.activity_scope === 'all'" to="/flow/audit" class="see-all">Audit log <ChevronRight :size="14" /></RouterLink></div>
          <EmptyState v-if="!d.activity?.length" :icon="Bell" title="No updates yet" />
          <ol v-else class="feed">
            <li v-for="e in d.activity.slice(0, 6)" :key="e.id">
              <span class="feed-dot" :class="eventMeta(e).tone"><component :is="eventMeta(e).icon" :size="13" /></span>
              <div class="min-w-0">
                <div><strong>{{ eventMeta(e).label }}</strong>
                  <RouterLink v-if="e.request_id" :to="`/mdm/requests/${e.request_id}`" class="ms-1 small">{{ e.entity_ref }}</RouterLink></div>
                <small>{{ e.actor?.name || 'System' }} · {{ relTime(e.created_at) }}</small>
              </div>
            </li>
          </ol>
        </section>
      </aside>
    </div>

    <!-- Opportunities carousel (sales, leadership) -->
    <CardCarousel v-if="d?.opportunities?.top?.length" :title="d.opportunities.scope === 'mine' ? 'Opportunities in your market' : 'Top new opportunities'" label="Sales opportunities" class="mb-4">
      <template #link><RouterLink to="/growth/opportunities" class="see-all me-1">View all <ChevronRight :size="14" /></RouterLink></template>
      <RouterLink v-for="o in d.opportunities.top" :key="o.id" :to="`/growth/opportunities?id=${o.id}`" class="soft-card opp">
        <div class="opp-top">
          <span class="opp-cat" :style="{ background: catMeta(o.category).soft, color: catMeta(o.category).color }"><component :is="catMeta(o.category).icon" :size="16" /></span>
          <span class="pill" :class="o.priority === 'HIGH' ? 'tone-error' : 'tone-warning'">{{ o.priority === 'HIGH' ? 'High priority' : 'Medium' }}</span>
        </div>
        <strong>{{ o.title }}</strong>
        <p>{{ o.insight }}</p>
        <span class="opp-go">See details <ArrowRight :size="14" /></span>
      </RouterLink>
    </CardCarousel>

    <!-- Guides & tips -->
    <section v-if="tips.length">
      <div class="sc-head bare"><h2>Guides &amp; tips</h2></div>
      <div class="tips">
        <RouterLink v-for="t in tips" :key="t.title" :to="t.to" class="soft-card tip">
          <span class="tip-ic" :style="{ background: t.color }"><component :is="t.icon" :size="16" /></span>
          <span>{{ t.title }}</span>
        </RouterLink>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import {
  AlarmClock, ArrowRight, BarChart3, Bell, BookOpen, CheckCircle2, ChevronRight, CircleHelp, ClipboardCheck, Copy, Database, FilePlus2, FileStack,
  Gauge, Globe2, History, Hourglass, Inbox, Lightbulb, LineChart, Lock, Network, PackagePlus, PartyPopper, Plug, Plus, Recycle, Rocket, Search,
  Send, ShieldCheck, ShoppingCart, Siren, SlidersHorizontal, Store, Target, Timer, TrendingUp, Truck, Undo2, UserPlus, Workflow, X, XCircle,
} from 'lucide-vue-next'
import CardCarousel from '@/components/CardCarousel.vue'
import SparkLine from '@/components/SparkLine.vue'
import DonutChart from '@/components/DonutChart.vue'
import ChartCard from '@/components/ChartCard.vue'
import EChart from '@/components/EChart.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorState from '@/components/ErrorState.vue'
import { get } from '@/api/client'
import { useAuth } from '@/stores/auth'
import { fmtNumber, fmtPct, hoursLabel, relTime } from '@/utils/format'
import { INK, axisCategory, axisValue, baseGrid, countryColor, legend, lineSeries, months as mlabels, tooltip } from '@/utils/charts'

const auth = useAuth()
const d = ref(null)
const error = ref(null)
const hideFocus = ref(false)
async function load() { error.value = null; try { d.value = await get('/api/dashboard') } catch (e) { error.value = e } }
onMounted(load)

// ---- Who is this person? -------------------------------------------------
const C = { indigo: '#6366f1', pink: '#ec4899', teal: '#14b8a6', amber: '#f59e0b', red: '#ef4444', slate: '#94a3b8', navy: '#1e2a5a', green: '#22c55e' }
const SOFT = { indigo: '#eef0ff', pink: '#fdeef6', teal: '#e6f7f5', amber: '#fef5e4', red: '#fdecec', navy: '#e9ecf5', green: '#e8f8ee' }
const isReq = computed(() => auth.has('REQUESTOR'))
const isApprover = computed(() => auth.has('BU_HEAD', 'FINANCE', 'QRA', 'BUSINESS_SUPPORT'))
const isAnalyst = computed(() => auth.has('MDM_ANALYST'))
const isSales = computed(() => auth.has('SALES'))
const isAdmin = computed(() => auth.has('ADMIN'))
const isExec = computed(() => auth.has('EXECUTIVE'))
const canRequest = computed(() => auth.has('REQUESTOR', 'SALES', 'ADMIN'))
// The role that decides the page's focus when someone has several.
const primary = computed(() => isApprover.value ? 'approver' : isAnalyst.value ? 'analyst' : isSales.value ? 'sales'
  : isExec.value ? 'exec' : isAdmin.value ? 'admin' : 'requestor')
const showRegional = computed(() => ['sales', 'exec'].includes(primary.value) || isApprover.value)

const firstName = computed(() => auth.user?.name || '')
const initials = (n = '') => n.split(' ').map((x) => x[0]).join('').slice(0, 2).toUpperCase()
const helloLine = computed(() => ({
  requestor: 'Here is where your requests stand today.',
  approver: 'Here is what is waiting for your decision.',
  analyst: 'Here is what is ready for checking and SAP set-up.',
  sales: 'Here is how your market is doing and where to act next.',
  exec: 'Here is how the business and the request process are performing.',
  admin: 'Here is the health of forms, approvals and integrations.',
})[primary.value])

const heroActions = computed(() => {
  const out = []
  if (isApprover.value) out.push({ to: '/flow/inbox', label: 'Open approval inbox', icon: Inbox, primary: true })
  if (canRequest.value) out.push({ to: '/mdm/new', label: 'New request', icon: Plus, primary: !out.length })
  if (isAnalyst.value) out.push({ to: '/flow/tracker', label: 'Workflow tracker', icon: Workflow, primary: !out.length })
  if (isExec.value) out.push({ to: '/impact', label: 'Business impact', icon: Gauge, primary: !out.length })
  return out.slice(0, 2)
})

// ---- My requests ----------------------------------------------------------
const needsAction = computed(() => (d.value?.my_requests || []).filter((r) => ['DRAFT', 'NEEDS_CHANGES'].includes(r.status)))
const myRequestsSorted = computed(() => {
  const mine = d.value?.my_requests || []
  return [...needsAction.value, ...mine.filter((r) => !needsAction.value.includes(r))]
})
const rowTo = (r) => (['DRAFT', 'NEEDS_CHANGES'].includes(r.status) ? `/mdm/new?edit=${r.id}` : `/mdm/requests/${r.id}`)
const sumOf = (counts, keys) => keys.reduce((s, k) => s + (counts?.[k] || 0), 0)
const ACTION = ['DRAFT', 'NEEDS_CHANGES']
const IN_PROGRESS = ['SUBMITTED', 'VALIDATION_COMPLETED', 'PENDING_APPROVAL', 'APPROVED', 'MDM_VERIFICATION', 'SAP_PENDING', 'SAP_FAILED']
const DONE = ['SAP_COMPLETED']
const CLOSED = ['REJECTED', 'CANCELLED']
const mine = computed(() => d.value?.my_request_counts || {})
const tc = computed(() => d.value?.my_task_counts)
const op = computed(() => d.value?.operational)
const reg = computed(() => d.value?.regional)

// ---- The one thing to do next ----------------------------------------------
const focus = computed(() => {
  if (!d.value) return null
  const plural = (n, one, many) => (n === 1 ? one : many)
  if (tc.value?.overdue) return { icon: Siren, title: `${tc.value.overdue} ${plural(tc.value.overdue, 'approval is', 'approvals are')} overdue`, text: 'These have passed their deadline. A quick decision keeps the request moving.', to: '/flow/inbox?view=overdue', cta: 'Review now' }
  const act = sumOf(mine.value, ACTION)
  if (act) return { icon: CircleHelp, title: `${act} of your ${plural(act, 'request needs', 'requests need')} you`, text: needsAction.value[0] ? `Start with “${needsAction.value[0].title}”.` : 'Finish a draft or correct what was sent back.', to: needsAction.value[0] ? rowTo(needsAction.value[0]) : '/mdm/requests?status=DRAFT,NEEDS_CHANGES', cta: 'Take a look' }
  if (tc.value?.pending) return { icon: Inbox, title: `${tc.value.pending} ${plural(tc.value.pending, 'approval is', 'approvals are')} waiting for you`, text: tc.value.due_soon ? `${tc.value.due_soon} due within a day.` : 'All on track. Nice work.', to: '/flow/inbox', cta: 'Open inbox' }
  if (d.value.mdm_queue?.length) return { icon: Database, title: `${d.value.mdm_queue.length} approved ${plural(d.value.mdm_queue.length, 'request is', 'requests are')} ready for you`, text: 'Check the details and send them to SAP B1.', to: `/mdm/requests/${d.value.mdm_queue[0].id}`, cta: 'Start checking' }
  if (isAdmin.value && op.value?.sap_failed_open) return { icon: Plug, title: `${op.value.sap_failed_open} SAP hand-${plural(op.value.sap_failed_open, 'off', 'offs')} failed`, text: 'Retry them from SAP & Notifications.', to: '/admin/integrations', cta: 'Fix now' }
  if (d.value.opportunities?.high) return { icon: Rocket, title: `${d.value.opportunities.high} new high-priority ${plural(d.value.opportunities.high, 'opportunity', 'opportunities')}`, text: d.value.opportunities.scope === 'mine' ? 'In your market or assigned to you.' : 'Across all five countries.', to: '/growth/opportunities', cta: 'See them' }
  return null
})

// ---- Shortcut tiles -------------------------------------------------------
const tiles = computed(() => {
  const out = []
  const add = (t) => { if (!out.some((x) => x.to === t.to)) out.push(t) }
  const groups = {
    approver: () => {
      add({ to: '/flow/inbox', title: 'Approval inbox', caption: 'Decide on requests', icon: Inbox, theme: 'lavender', badge: tc.value?.pending || null })
      add({ to: '/flow/inbox?view=overdue', title: 'Overdue', caption: 'Past their deadline', icon: AlarmClock, theme: 'pink', badge: tc.value?.overdue || null })
      add({ to: '/flow/inbox?view=due_soon', title: 'Due soon', caption: 'Within the next day', icon: Hourglass, theme: 'amber', badge: tc.value?.due_soon || null })
      add({ to: '/flow/inbox?view=completed', title: 'Decided by me', caption: 'Your past decisions', icon: ClipboardCheck, theme: 'navy' })
      add({ to: '/flow/tracker', title: 'Where is my request?', caption: 'Track any request', icon: Workflow, theme: 'teal' })
    },
    analyst: () => {
      add({ to: '/flow/tracker', title: 'Workflow tracker', caption: 'Every request, live', icon: Workflow, theme: 'lavender' })
      add({ to: '/mdm/records', title: 'Master records', caption: 'Search existing codes', icon: Database, theme: 'navy' })
      add({ to: '/growth/data-quality', title: 'Data quality', caption: 'Customer name mapping', icon: Network, theme: 'teal' })
      add({ to: '/admin/integrations', title: 'SAP & notifications', caption: 'Hand-offs and retries', icon: Plug, theme: 'pink' })
      add({ to: '/flow/audit', title: 'Audit history', caption: 'Who did what, when', icon: History, theme: 'amber' })
    },
    sales: () => {
      add({ to: '/growth/regional', title: 'Regional overview', caption: 'Orders by country', icon: Globe2, theme: 'lavender' })
      add({ to: '/growth/opportunities', title: 'Opportunities', caption: 'Where to act next', icon: Lightbulb, theme: 'pink', badge: d.value?.opportunities?.open || null })
      add({ to: '/growth/forecasting', title: 'Demand forecast', caption: 'The next few months', icon: LineChart, theme: 'navy' })
    },
    exec: () => {
      add({ to: '/impact', title: 'Business impact', caption: 'Time and cost saved', icon: Gauge, theme: 'lavender' })
      add({ to: '/growth/regional', title: 'Regional overview', caption: 'Orders by country', icon: Globe2, theme: 'navy' })
      add({ to: '/flow/tracker', title: 'Workflow tracker', caption: 'Every request, live', icon: Workflow, theme: 'teal' })
      add({ to: '/flow/audit', title: 'Audit history', caption: 'Who did what, when', icon: History, theme: 'amber' })
    },
    admin: () => {
      add({ to: '/admin/forms', title: 'Forms', caption: 'Change fields, no IT needed', icon: SlidersHorizontal, theme: 'lavender' })
      add({ to: '/admin/approval-rules', title: 'Approval rules', caption: 'Who approves what', icon: ShieldCheck, theme: 'navy' })
      add({ to: '/admin/integrations', title: 'SAP & notifications', caption: 'Hand-offs and retries', icon: Plug, theme: 'pink' })
      add({ to: '/flow/audit', title: 'Audit history', caption: 'Who did what, when', icon: History, theme: 'amber' })
    },
    requestor: () => {
      add({ to: '/mdm/new?domain=ITEM', title: 'New item code', caption: 'Product or material', icon: PackagePlus, theme: 'lavender' })
      add({ to: '/mdm/new?domain=CUSTOMER', title: 'New customer', caption: 'Hospital, clinic, distributor', icon: UserPlus, theme: 'navy' })
      add({ to: '/mdm/new?domain=VENDOR', title: 'New vendor', caption: 'Supplier or partner', icon: Truck, theme: 'pink' })
      add({ to: '/mdm/requests', title: 'My requests', caption: 'See where each one is', icon: FileStack, theme: 'teal', badge: sumOf(mine.value, ACTION) || null })
      add({ to: '/mdm/records', title: 'Check existing records', caption: 'Avoid creating duplicates', icon: Search, theme: 'amber' })
    },
  }
  groups[primary.value]()
  if (isApprover.value && auth.has('BU_HEAD', 'FINANCE')) add({ to: '/growth/regional', title: 'Regional overview', caption: 'Orders by country', icon: Globe2, theme: 'navy' })
  if (isReq.value && primary.value !== 'requestor') add({ to: '/mdm/requests', title: 'My requests', caption: 'See where each one is', icon: FileStack, theme: 'teal', badge: sumOf(mine.value, ACTION) || null })
  if (isAdmin.value && primary.value !== 'admin') groups.admin()
  return out.slice(0, 8)
})

// ---- Stat cards -----------------------------------------------------------
const poSpark = computed(() => {
  const t = reg.value?.trend || []
  if (!t.length) return null
  return t[0].values.map((_, i) => t.reduce((s, c) => s + (c.values[i] || 0), 0))
})
const stats = computed(() => {
  if (!d.value) return []
  const k = reg.value?.kpis
  const p = primary.value
  if (p === 'approver' && tc.value) {
    const total = tc.value.pending || 1
    return [
      { label: 'Waiting on me', value: tc.value.pending, icon: Inbox, color: C.indigo, soft: SOFT.indigo, hint: 'Approvals for your role', to: '/flow/inbox' },
      { label: 'Overdue', value: tc.value.overdue, icon: AlarmClock, color: C.red, soft: SOFT.red, progress: tc.value.overdue / total, hint: 'Past the deadline', to: '/flow/inbox?view=overdue' },
      { label: 'Due soon', value: tc.value.due_soon, icon: Hourglass, color: C.amber, soft: SOFT.amber, progress: tc.value.due_soon / total, hint: 'Within 24 hours', to: '/flow/inbox?view=due_soon' },
      { label: 'Decided by me', value: tc.value.decided, icon: CheckCircle2, color: C.teal, soft: SOFT.teal, hint: 'All time', to: '/flow/inbox?view=completed' },
    ]
  }
  if ((p === 'analyst' || p === 'admin') && op.value) {
    return [
      { label: 'Open requests', value: op.value.open_requests, icon: FileStack, color: C.indigo, soft: SOFT.indigo, hint: 'Across all teams', to: '/flow/tracker' },
      { label: 'With approvers', value: op.value.awaiting_approval, icon: Hourglass, color: C.amber, soft: SOFT.amber, hint: `${op.value.overdue_approvals} overdue`, to: '/flow/tracker' },
      { label: 'Ready for SAP', value: (op.value.awaiting_mdm || 0) + (op.value.sap_failed_open || 0), icon: Database, color: C.pink, soft: SOFT.pink, hint: op.value.sap_failed_open ? `${op.value.sap_failed_open} failed, need a retry` : 'Being checked by MDM' },
      { label: 'Typical turnaround', value: op.value.median_turnaround_days, unit: 'days', icon: Timer, color: C.teal, soft: SOFT.teal, hint: 'From submit to live in SAP' },
    ]
  }
  if ((p === 'sales' || p === 'exec') && k) {
    return [
      { label: 'Confirmed orders', value: fmtNumber(k.confirmed_pos.value), icon: ShoppingCart, color: C.indigo, soft: SOFT.indigo, spark: poSpark.value, to: '/growth/regional' },
      { label: 'Order growth', value: fmtPct(k.po_growth.value, 1, true), icon: TrendingUp, color: k.po_growth.value >= 0 ? C.green : C.red, soft: k.po_growth.value >= 0 ? SOFT.green : SOFT.red, hint: 'Last 3 months vs the 3 before' },
      { label: 'Active customers', value: fmtNumber(k.active_customers.value), icon: Store, color: C.teal, soft: SOFT.teal, hint: 'Bought in the period' },
      { label: 'Open opportunities', value: d.value.opportunities?.open ?? '—', icon: Lightbulb, color: C.pink, soft: SOFT.pink, hint: `${d.value.opportunities?.high ?? 0} high priority`, to: '/growth/opportunities' },
    ]
  }
  const m = mine.value
  const total = Object.values(m).reduce((s, v) => s + v, 0) || 1
  return [
    { label: 'Needs my action', value: sumOf(m, ACTION), icon: CircleHelp, color: C.pink, soft: SOFT.pink, progress: sumOf(m, ACTION) / total, hint: 'Drafts or sent back', to: '/mdm/requests?status=DRAFT,NEEDS_CHANGES' },
    { label: 'In progress', value: sumOf(m, IN_PROGRESS), icon: Send, color: C.indigo, soft: SOFT.indigo, progress: sumOf(m, IN_PROGRESS) / total, hint: 'With approvers or MDM' },
    { label: 'Live in SAP', value: sumOf(m, DONE), icon: CheckCircle2, color: C.teal, soft: SOFT.teal, progress: sumOf(m, DONE) / total, hint: 'Ready to use' },
    { label: 'Not approved', value: sumOf(m, CLOSED), icon: XCircle, color: C.slate, soft: SOFT.navy, progress: sumOf(m, CLOSED) / total, hint: 'Rejected or cancelled' },
  ]
})

// ---- Donut ----------------------------------------------------------------
const donut = computed(() => {
  if (!d.value) return null
  const p = primary.value
  if (p === 'approver' && tc.value?.pending) {
    return { title: 'My approvals by deadline', sub: 'What is waiting for you', center: 'waiting', data: [
      { label: 'Overdue', value: tc.value.overdue, color: C.red, to: '/flow/inbox?view=overdue' },
      { label: 'Due within a day', value: tc.value.due_soon, color: C.amber, to: '/flow/inbox?view=due_soon' },
      { label: 'On track', value: tc.value.on_track, color: C.teal, to: '/flow/inbox' },
    ] }
  }
  if ((p === 'sales' || p === 'exec') && reg.value?.ranking?.length) {
    return { title: 'Orders by country', sub: 'Confirmed purchase orders in the period', center: 'orders', data:
      reg.value.ranking.map((r) => ({ label: r.country, value: r.confirmed_pos, color: countryColor(r.country), to: `/growth/regional?countries=${r.country}` })) }
  }
  if (op.value && (p === 'analyst' || p === 'admin')) {
    const s = op.value.status_counts || {}
    return { title: 'All requests by stage', sub: 'Across every team', center: 'requests', data: [
      { label: 'With approvers', value: sumOf(s, ['SUBMITTED', 'VALIDATION_COMPLETED', 'PENDING_APPROVAL']), color: C.indigo },
      { label: 'Sent back for changes', value: sumOf(s, ['NEEDS_CHANGES']), color: C.amber },
      { label: 'MDM check & SAP', value: sumOf(s, ['APPROVED', 'MDM_VERIFICATION', 'SAP_PENDING', 'SAP_FAILED']), color: C.pink },
      { label: 'Live in SAP', value: sumOf(s, DONE), color: C.teal },
      { label: 'Not approved', value: sumOf(s, CLOSED), color: C.slate },
    ] }
  }
  const m = mine.value
  if (!Object.keys(m).length) return null
  return { title: 'My requests by stage', sub: 'Everything you have raised', center: 'requests', data: [
    { label: 'Needs my action', value: sumOf(m, ACTION), color: C.pink, to: '/mdm/requests?status=DRAFT,NEEDS_CHANGES' },
    { label: 'In progress', value: sumOf(m, IN_PROGRESS), color: C.indigo, to: `/mdm/requests?status=${IN_PROGRESS.join(',')}` },
    { label: 'Live in SAP', value: sumOf(m, DONE), color: C.teal, to: '/mdm/requests?status=SAP_COMPLETED' },
    { label: 'Not approved', value: sumOf(m, CLOSED), color: C.slate, to: '/mdm/requests?status=REJECTED,CANCELLED' },
  ] }
})

// ---- Progress cards (right column) -----------------------------------------
const progressCards = computed(() => {
  const out = []
  if (op.value && (isAnalyst.value || isAdmin.value || isExec.value)) {
    out.push({ label: 'Right first time', sub: 'Requests accepted on the first try', value: op.value.first_pass_validation_rate, icon: CheckCircle2, color: C.teal, soft: SOFT.teal })
    out.push({ label: 'Possible duplicates caught', sub: 'Requests that looked like an existing record', value: op.value.potential_duplicate_rate, icon: Copy, color: C.amber, soft: SOFT.amber })
  }
  if (reg.value?.forecast && ['sales', 'exec'].includes(primary.value)) {
    out.push({ label: 'Forecast accuracy', sub: `vs ${fmtPct(reg.value.forecast.baseline_accuracy, 0)} with a simple average`, value: reg.value.forecast.accuracy, icon: Target, color: C.indigo, soft: SOFT.indigo })
  }
  return out
})

// ---- Tips -----------------------------------------------------------------
const TIPS = {
  requestor: [
    { title: 'Not sure what to fill in? Every field has a short help note.', to: '/mdm/new', icon: CircleHelp, color: C.pink },
    { title: 'What happens after you press Submit', to: '/mdm/requests', icon: Workflow, color: C.indigo },
    { title: 'Search first: the record may already exist', to: '/mdm/records', icon: Search, color: C.teal },
  ],
  approver: [
    { title: 'Approve, send back or reject, with a short note', to: '/flow/inbox', icon: ClipboardCheck, color: C.indigo },
    { title: 'Overdue approvals are escalated automatically', to: '/flow/inbox?view=overdue', icon: AlarmClock, color: C.pink },
    { title: 'See exactly where any request is', to: '/flow/tracker', icon: Workflow, color: C.teal },
  ],
  analyst: [
    { title: 'Retry a failed SAP hand-off in one click', to: '/admin/integrations', icon: Plug, color: C.pink },
    { title: 'Confirm which customer names are the same company', to: '/growth/data-quality', icon: Network, color: C.indigo },
    { title: 'Every action is kept in the audit log', to: '/flow/audit', icon: History, color: C.teal },
  ],
  sales: [
    { title: 'Read your regional numbers in two minutes', to: '/growth/regional', icon: BookOpen, color: C.indigo },
    { title: 'Turn an opportunity into a follow-up', to: '/growth/opportunities', icon: Lightbulb, color: C.pink },
    { title: 'How the demand forecast is checked', to: '/growth/forecasting', icon: BarChart3, color: C.teal },
  ],
  exec: [
    { title: 'Hours and cost saved, explained', to: '/impact', icon: Gauge, color: C.indigo },
    { title: 'Which markets are growing fastest', to: '/growth/regional', icon: Globe2, color: C.teal },
    { title: 'Every decision has a name and a time', to: '/flow/audit', icon: History, color: C.pink },
  ],
  admin: [
    { title: 'Add or change a form field without IT', to: '/admin/forms', icon: SlidersHorizontal, color: C.indigo },
    { title: 'Set who approves what, and how fast', to: '/admin/approval-rules', icon: ShieldCheck, color: C.pink },
    { title: 'Check SAP and email hand-offs', to: '/admin/integrations', icon: Plug, color: C.teal },
  ],
}
const tips = computed(() => TIPS[primary.value] || [])

// ---- Helpers --------------------------------------------------------------
const slaTone = (s) => ({ OVERDUE: 'red', DUE_SOON: 'amber', ON_TRACK: 'green' })[s] || 'grey'
function slaText(t) {
  if (t.sla_state === 'OVERDUE') return 'Overdue'
  if (!t.due_at) return '—'
  const h = (new Date(t.due_at) - Date.now()) / 36e5
  return h > 0 ? `In ${hoursLabel(h)}` : 'Overdue'
}
const EVENTS = {
  STATUS_SUBMITTED: ['Request submitted', Send, 'indigo'], TASK_APPROVED: ['Approved', CheckCircle2, 'green'], TASK_REJECTED: ['Rejected', XCircle, 'red'],
  TASK_CHANGES_REQUESTED: ['Sent back for changes', Undo2, 'amber'], SAP_CREATION_COMPLETED: ['Created in SAP', Database, 'green'],
  SAP_CREATION_FAILED: ['SAP creation failed', XCircle, 'red'], DUPLICATE_PREVENTED: ['Duplicate avoided', Recycle, 'teal'],
  FOLLOWUP_ASSIGNED: ['Follow-up assigned', UserPlus, 'indigo'], MAPPING_CONFIRMED: ['Customer names matched', Network, 'teal'], ESCALATED: ['Escalated (overdue)', Siren, 'red'],
}
const eventMeta = (e) => { const m = EVENTS[e.event_type]; return m ? { label: m[0], icon: m[1], tone: m[2] } : { label: e.event_type, icon: Bell, tone: 'indigo' } }
const CATS = { CROSS_SELL: [Rocket, 'indigo'], INACTIVITY: [Hourglass, 'amber'], GROWTH_MARKET: [TrendingUp, 'teal'], DEMAND_CHANGE: [LineChart, 'pink'] }
const catMeta = (c) => { const m = CATS[c] || [Lightbulb, 'indigo']; return { icon: m[0], color: C[m[1]], soft: SOFT[m[1]] } }

const trendOpt = computed(() => {
  const r = reg.value
  if (!r) return {}
  return { tooltip: tooltip(), legend: legend(), grid: baseGrid({ top: 56 }), xAxis: axisCategory(mlabels(r.window.months)), yAxis: axisValue('Orders'),
    series: r.trend.map((t) => lineSeries(t.country, t.values, countryColor(t.country), { smooth: true, symbolSize: 6, endLabel: { show: true, formatter: '{a}', color: INK.text, fontSize: 11 } })) }
})
</script>

<style scoped>
/* Page backdrop: soft lavender wash behind the whole home page */
.home { --r: 18px; --soft-shadow: 0 14px 34px -16px rgba(67, 56, 202, .22), 0 2px 6px rgba(16, 28, 53, .05); }
.home h2 { font-size: 1.05rem; margin: 0; }
.min-w-0 { min-width: 0; }

/* Greeting */
.hello { display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem; flex-wrap: wrap; margin: .5rem 0 1.5rem; }
.hello h1 { font-size: 2rem; font-weight: 750; margin: 0; letter-spacing: -.02em; }
.hello p { color: var(--muted); margin: .3rem 0 0; font-size: 1rem; }
.hello-actions { display: flex; gap: .6rem; flex-wrap: wrap; }
.btn-glow { background: linear-gradient(135deg, #6366f1, #4f46e5); color: #fff; border: none; border-radius: 12px; padding: .6rem 1.1rem; box-shadow: 0 10px 22px -10px rgba(79, 70, 229, .8); }
.btn-glow:hover { color: #fff; filter: brightness(1.06); transform: translateY(-1px); }
.btn-soft { background: #fff; color: var(--text); border: 1px solid var(--border); border-radius: 12px; padding: .6rem 1.1rem; box-shadow: var(--shadow-1); }
.btn-soft:hover { background: #fff; color: var(--accent); }
.btn-glow, .btn-soft { transition: transform .15s, box-shadow .15s, filter .15s; }

/* Focus banner */
.focus-banner { position: relative; overflow: hidden; display: flex; align-items: center; gap: 1rem; padding: 1.1rem 1.25rem; margin-bottom: 1.75rem; border-radius: var(--r);
  background: linear-gradient(120deg, #7c3aed 0%, #6366f1 55%, #818cf8 100%); color: #fff; box-shadow: 0 18px 36px -18px rgba(99, 102, 241, .9); }
.fb-icon { width: 46px; height: 46px; border-radius: 14px; background: rgba(255, 255, 255, .18); display: inline-flex; align-items: center; justify-content: center; flex: none; z-index: 1; }
.fb-text { flex: 1; display: flex; flex-direction: column; z-index: 1; min-width: 0; }
.fb-text strong { font-size: 1.08rem; }
.fb-text span { opacity: .9; }
.fb-btn { background: #fff; color: #4338ca; border-radius: 11px; font-weight: 650; padding: .55rem 1rem; z-index: 1; flex: none; }
.fb-btn:hover { background: #f5f3ff; color: #3730a3; }
.fb-close { background: transparent; border: none; color: #fff; opacity: .7; z-index: 1; padding: .25rem; }
.fb-close:hover { opacity: 1; }
.fb-blob { position: absolute; border-radius: 50%; background: rgba(255, 255, 255, .12); }
.fb-blob.a { width: 220px; height: 220px; right: 90px; top: -120px; }
.fb-blob.b { width: 140px; height: 140px; right: -40px; bottom: -80px; }
@media (max-width: 640px) { .focus-banner { flex-wrap: wrap; } .fb-btn { width: 100%; } .fb-close { position: absolute; top: .5rem; right: .5rem; } }

/* Tiles */
.tile { display: flex; flex-direction: column; background: #fff; border-radius: var(--r); overflow: hidden; color: var(--text); text-decoration: none;
  box-shadow: var(--soft-shadow); transition: transform .2s ease, box-shadow .2s ease; min-height: 196px; }
.tile:hover { transform: translateY(-4px); box-shadow: 0 22px 40px -18px rgba(67, 56, 202, .35); text-decoration: none; color: var(--text); }
.tile-art { position: relative; height: 120px; padding: 14px; }
.art-dots { position: absolute; top: 16px; right: 16px; display: flex; gap: 5px; }
.art-dots i { width: 7px; height: 7px; border-radius: 50%; background: rgba(255, 255, 255, .7); }
.art-bars { position: absolute; left: 16px; bottom: 18px; display: flex; flex-direction: column; gap: 6px; }
.art-bars i { display: block; height: 8px; border-radius: 6px; background: rgba(255, 255, 255, .55); width: 90px; }
.art-bars i + i { width: 56px; }
.art-ic { position: absolute; right: 16px; bottom: 16px; width: 48px; height: 48px; border-radius: 14px; background: rgba(255, 255, 255, .92);
  display: inline-flex; align-items: center; justify-content: center; box-shadow: 0 8px 18px -8px rgba(16, 28, 53, .35); }
.art-badge { position: absolute; top: 12px; left: 14px; min-width: 26px; height: 26px; padding: 0 .45rem; border-radius: 999px; background: #fff; color: #be185d;
  font-size: .78rem; font-weight: 700; display: inline-flex; align-items: center; justify-content: center; box-shadow: 0 4px 10px -4px rgba(16, 28, 53, .3); }
.th-lavender { background: linear-gradient(140deg, #c7d2fe, #a5b4fc 60%, #818cf8); }
.th-lavender .art-ic { color: #4f46e5; }
.th-navy { background: linear-gradient(140deg, #2b3a74, #172554 70%); }
.th-navy .art-ic { color: #1e3a8a; }
.th-navy .art-dots i, .th-navy .art-bars i { background: rgba(255, 255, 255, .28); }
.th-pink { background: linear-gradient(140deg, #fbcfe8, #f9a8d4 55%, #f472b6); }
.th-pink .art-ic { color: #db2777; }
.th-teal { background: linear-gradient(140deg, #ccfbf1, #5eead4 60%, #2dd4bf); }
.th-teal .art-ic { color: #0f766e; }
.th-amber { background: linear-gradient(140deg, #fef3c7, #fcd34d 60%, #fbbf24); }
.th-amber .art-ic { color: #b45309; }
.tile-body { padding: .8rem 1rem 1rem; display: flex; flex-direction: column; gap: .15rem; }
.tile-body small { color: var(--muted); font-size: .78rem; }
.tile-body strong { display: flex; align-items: center; justify-content: space-between; font-size: .95rem; }
.tile-body strong svg { color: var(--muted); transition: transform .2s; }
.tile:hover .tile-body strong svg { transform: translateX(3px); color: var(--accent); }
.tile-add { position: relative; background: linear-gradient(150deg, #8b5cf6, #6366f1 60%, #4f46e5); color: #fff; align-items: center; justify-content: center; gap: .6rem; padding: 1rem; text-align: center; }
.tile-add:hover { color: #fff; }
.tile-add small { color: rgba(255, 255, 255, .85); font-size: .8rem; z-index: 1; }
.add-pill { background: #fff; color: #4338ca; border-radius: 12px; padding: .55rem 1rem; font-weight: 700; display: inline-flex; align-items: center; gap: .35rem; z-index: 1; box-shadow: 0 10px 20px -10px rgba(16, 28, 53, .5); }
.add-orb { position: absolute; width: 150px; height: 150px; border-radius: 50%; background: rgba(255, 255, 255, .12); top: -50px; left: -40px; }
.add-orb.two { width: 110px; height: 110px; top: auto; left: auto; bottom: -40px; right: -30px; background: rgba(236, 72, 153, .35); }

/* Soft cards */
.soft-card { background: #fff; border-radius: var(--r); box-shadow: var(--soft-shadow); border: 1px solid rgba(227, 232, 240, .6); }
.sc-head { display: flex; justify-content: space-between; align-items: center; gap: .75rem; padding: 1.1rem 1.25rem .6rem; }
.sc-head.bare { padding: 0 0 .75rem; }
.sc-sub { color: var(--muted); font-size: .8rem; margin: .15rem 0 0; }
.sc-body { padding: .4rem 1.25rem 1.25rem; }
.see-all { color: var(--muted); font-size: .82rem; font-weight: 550; display: inline-flex; align-items: center; gap: .15rem; white-space: nowrap; }
.see-all:hover { color: var(--accent); text-decoration: none; }

/* Stats */
.stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1rem; }
@media (max-width: 1100px) { .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 520px) { .stats { grid-template-columns: 1fr; } }
.stat { padding: 1rem 1.1rem; display: flex; flex-direction: column; gap: .35rem; color: var(--text); text-decoration: none; transition: transform .2s, box-shadow .2s; }
.stat.link:hover { transform: translateY(-3px); box-shadow: 0 22px 40px -18px rgba(67, 56, 202, .3); text-decoration: none; color: var(--text); }
.stat-top { display: flex; align-items: center; gap: .6rem; }
.stat-ic { width: 34px; height: 34px; border-radius: 11px; display: inline-flex; align-items: center; justify-content: center; flex: none; }
.stat-label { color: var(--text-2); font-weight: 600; font-size: .86rem; }
.stat-value { font-size: 1.85rem; font-weight: 750; letter-spacing: -.02em; line-height: 1.1; margin-top: .2rem; }
.stat-value small { font-size: .85rem; font-weight: 500; color: var(--muted); margin-left: .3rem; letter-spacing: 0; }
.stat-hint { color: var(--muted); font-size: .78rem; }
.stat-bar { height: 6px; border-radius: 6px; background: var(--surface-2); overflow: hidden; margin-top: auto; }
.stat-bar span { display: block; height: 100%; border-radius: 6px; transition: width .5s ease; }

/* Main grid */
.main-grid { display: grid; grid-template-columns: minmax(0, 1.75fr) minmax(300px, 1fr); gap: 1.25rem; align-items: start; }
@media (max-width: 1100px) { .main-grid { grid-template-columns: 1fr; } }
.col-stack { display: flex; flex-direction: column; gap: 1.25rem; min-width: 0; }

/* Tables */
.tbl-wrap { overflow-x: auto; padding: 0 .5rem .6rem; }
.tbl { width: 100%; border-collapse: separate; border-spacing: 0; font-size: .87rem; }
.tbl th { color: var(--muted); font-weight: 550; font-size: .76rem; padding: .5rem .75rem; text-align: left; white-space: nowrap; border-bottom: 1px solid var(--border); }
.tbl td { padding: .7rem .75rem; border-bottom: 1px solid #f1f3f8; vertical-align: middle; }
.tbl tbody tr { cursor: pointer; transition: background .12s; }
.tbl tbody tr:hover td { background: #f7f7ff; }
.tbl tbody tr:last-child td { border-bottom: none; }
.tbl tr.attn td:first-child { box-shadow: inset 3px 0 0 #ec4899; }
.t-title { color: var(--text); font-weight: 600; display: block; }
.t-title:hover { color: var(--accent); text-decoration: none; }
.tbl small { color: var(--muted); font-size: .76rem; }
.who { display: inline-flex; align-items: center; gap: .45rem; white-space: nowrap; }
.mini-av { width: 26px; height: 26px; border-radius: 50%; background: #eef0ff; color: #4f46e5; font-size: .68rem; font-weight: 700; display: inline-flex; align-items: center; justify-content: center; }
.date-pill { display: inline-block; padding: .2rem .6rem; border-radius: 999px; font-size: .76rem; font-weight: 600; white-space: nowrap; }
.date-pill.red { background: #fde7ef; color: #be185d; }
.date-pill.amber { background: #fef3c7; color: #92400e; }
.date-pill.green { background: #dcfce7; color: #166534; }
.date-pill.grey { background: var(--surface-2); color: var(--muted); }
.chart-soft :deep(.card-x-head) { border-bottom: none; padding: 1.1rem 1.25rem .2rem; }
.chart-soft :deep(.card-x-head h2) { font-size: 1.05rem; }

/* Progress cards */
.prog { padding: 1rem 1.15rem; }
.prog-top { display: flex; justify-content: space-between; gap: .75rem; }
.prog-top strong { display: block; font-size: .95rem; }
.prog-top small { color: var(--muted); font-size: .78rem; }
.prog-ic { width: 34px; height: 34px; border-radius: 11px; display: inline-flex; align-items: center; justify-content: center; flex: none; }
.prog-val { font-size: 1.3rem; font-weight: 700; margin: .5rem 0 .4rem; }

/* Activity feed */
.feed { list-style: none; margin: 0; padding: .2rem 1.25rem 1.1rem; display: flex; flex-direction: column; gap: .85rem; }
.feed li { display: flex; gap: .7rem; align-items: flex-start; font-size: .86rem; }
.feed small { color: var(--muted); }
.feed-dot { width: 28px; height: 28px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; flex: none; }
.feed-dot.indigo { background: #eef0ff; color: #4f46e5; }
.feed-dot.green { background: #dcfce7; color: #15803d; }
.feed-dot.red { background: #fde7ef; color: #be185d; }
.feed-dot.amber { background: #fef3c7; color: #b45309; }
.feed-dot.teal { background: #ccfbf1; color: #0f766e; }

/* Opportunities */
.opp { padding: 1.1rem; display: flex; flex-direction: column; gap: .5rem; color: var(--text); text-decoration: none; min-height: 200px; transition: transform .2s, box-shadow .2s; }
.opp:hover { transform: translateY(-4px); box-shadow: 0 22px 40px -18px rgba(67, 56, 202, .3); text-decoration: none; color: var(--text); }
.opp-top { display: flex; justify-content: space-between; align-items: center; }
.opp-cat { width: 36px; height: 36px; border-radius: 11px; display: inline-flex; align-items: center; justify-content: center; }
.opp strong { font-size: .95rem; line-height: 1.3; }
.opp p { color: var(--muted); font-size: .82rem; margin: 0; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.opp-go { margin-top: auto; color: var(--accent); font-weight: 600; font-size: .84rem; display: inline-flex; align-items: center; gap: .3rem; }

/* Tips */
.tips { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem; }
@media (max-width: 900px) { .tips { grid-template-columns: 1fr; } }
.tip { display: flex; align-items: center; gap: .8rem; padding: .9rem 1rem; color: var(--text); font-size: .88rem; font-weight: 550; text-decoration: none; transition: transform .2s, box-shadow .2s; }
.tip:hover { transform: translateY(-3px); text-decoration: none; color: var(--text); }
.tip-ic { width: 36px; height: 36px; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center; color: #fff; flex: none; }
.skeleton { display: block; }
</style>
