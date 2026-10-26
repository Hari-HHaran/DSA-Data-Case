<template>
  <div class="page">
    <PageHeader title="Growth opportunities" eyebrow="Growth Intelligence" subtitle="Clean data → reliable insight → business action → measured outcome. Every item shows its evidence and is a review candidate for a person, not an automated decision.">
      <template #badge><span class="pill tag-synthetic">Synthetic data</span></template>
      <button v-if="auth.has('SALES', 'ADMIN')" class="btn btn-light" type="button" :disabled="refreshing" @click="refresh"><RotateCw :size="15" /> Recompute from latest data</button>
    </PageHeader>
    <div class="filters-row mb-2">
      <button v-for="c in cats" :key="c.key" type="button" class="chip" :class="{ on: category === c.key }" @click="category = c.key; load()">
        <component :is="c.icon" :size="13" />{{ c.label }} <span class="num">{{ c.key ? counts[c.key] || 0 : total }}</span></button>
    </div>
    <div class="filters-row mb-3">
      <select v-model="status" class="form-select form-select-sm" style="max-width: 200px" aria-label="Status" @change="load"><option value="">Open (not completed/dismissed)</option>
        <option v-for="s in statuses" :key="s" :value="s">{{ statusMeta(s).label }}</option><option value="ALL">All statuses</option></select>
      <select v-model="country" class="form-select form-select-sm" style="max-width: 180px" aria-label="Country" @change="load"><option value="">All countries</option>
        <option v-for="c in ref_.countries" :key="c.code" :value="c.code">{{ c.name }}</option></select>
      <span class="ms-auto small text-muted-2">Pipeline: <span v-for="s in statuses" :key="s" class="me-2">{{ statusMeta(s).label }} <strong class="num">{{ byStatus[s] || 0 }}</strong></span></span>
    </div>
    <ErrorState v-if="error" :error="error" :retry="load" />
    <LoadingBlock v-else-if="loading" :rows="6" :height="54" />
    <EmptyState v-else-if="!items.length" :icon="Lightbulb" title="No opportunities for this filter" />
    <div v-else class="grid grid-2">
      <article v-for="o in items" :key="o.id" class="card-x opp" :class="{ focus: String(o.id) === String(selected?.id) }" tabindex="0" @click="selected = o" @keydown.enter="selected = o">
        <div class="d-flex gap-2 align-items-center flex-wrap mb-1">
          <span class="pill" :class="PRI[o.priority]"><Flame v-if="o.priority === 'HIGH'" :size="11" />{{ o.priority.toLowerCase() }} · {{ Math.round(o.priority_score) }}</span>
          <span class="pill tone-neutral"><component :is="catIcon(o.category)" :size="11" />{{ o.category_label }}</span>
          <StatusBadge :status="o.status" />
          <span v-if="o.family" class="pill tone-neutral"><span class="legend-dot" :style="{ background: FAMILY_COLORS[o.family] }" />Product {{ o.family }}</span>
          <span class="small text-muted-2 ms-auto">{{ o.country }}</span>
        </div>
        <strong class="d-block">{{ o.title }}</strong>
        <p class="small mb-1 mt-1">{{ o.insight }}</p>
        <p class="small text-muted-2 mb-2 clamp">{{ o.explanation }}</p>
        <div class="d-flex justify-content-between align-items-center small">
          <span><User :size="13" /> {{ o.owner ? o.owner.name : 'Unassigned' }}</span>
          <span v-if="o.outcome" class="pill tone-success">{{ humanize(o.outcome) }}</span>
          <span class="link-btn">Open <ArrowRight :size="13" /></span>
        </div>
      </article>
    </div>

    <ModalDialog :open="!!selected" :title="selected?.title" width="760px" @close="selected = null; $router.replace({ query: {} })">
      <template v-if="selected">
        <div class="d-flex gap-2 flex-wrap mb-3">
          <span class="pill" :class="PRI[selected.priority]">Priority {{ selected.priority.toLowerCase() }} ({{ Math.round(selected.priority_score) }}/100)</span>
          <span class="pill tone-neutral">{{ selected.category_label }}</span><StatusBadge :status="selected.status" />
          <span v-if="selected.customer" class="pill tone-info">{{ selected.customer.code }}</span>
        </div>
        <div class="sec"><div class="small-label">1 · Insight</div><p class="mb-0">{{ selected.insight }}</p></div>
        <div class="sec"><div class="small-label">2 · Supporting data</div>
          <dl class="kv small mb-0"><template v-for="(v, k) in evidenceRows" :key="k"><dt>{{ k }}</dt><dd class="num">{{ v }}</dd></template></dl>
          <EChart v-if="selected.evidence.monthly_units" :option="sparkOpt" height="140px" aria-label="Monthly confirmed units for this customer and product" class="mt-2" /></div>
        <div class="sec"><div class="small-label">3 · Explanation</div><p class="mb-0 small">{{ selected.explanation }}</p></div>
        <div class="sec"><div class="small-label">4 · Suggested action</div><p class="mb-0 small">{{ selected.suggested_action }}</p></div>
        <div class="sec"><div class="small-label">5 · Priority</div><p class="mb-0 small">{{ selected.priority_reason }}</p></div>
        <div class="sec"><div class="small-label">6–8 · Owner, status & outcome</div>
          <div class="small mb-2">Owner: <strong>{{ selected.owner?.name || 'Unassigned' }}</strong> · Status: <strong>{{ statusMeta(selected.status).label }}</strong>
            <template v-if="selected.outcome"> · Outcome: <strong>{{ humanize(selected.outcome) }}</strong> <span class="text-muted-2">{{ selected.outcome_note }}</span></template></div>
          <div v-for="f in selected.followups" :key="f.id" class="callout neutral small mb-1"><ClipboardList :size="14" /><div>Follow-up → <strong>{{ f.assigned_to }}</strong>{{ f.due_date ? ` · due ${fmtDate(f.due_date)}` : '' }} · {{ f.status.toLowerCase() }}{{ f.note ? ` — ${f.note}` : '' }}</div></div>
          <template v-if="auth.has('SALES', 'ADMIN')">
            <div class="act mt-2">
              <div class="small-label mb-1">Create sales follow-up</div>
              <div class="d-flex flex-wrap gap-2">
                <select v-model="fu.assignee_id" class="form-select form-select-sm" style="max-width: 220px" aria-label="Assign to"><option :value="null">Assign to…</option>
                  <option v-for="u in salesUsers" :key="u.id" :value="u.id">{{ u.name }} · {{ u.title }}</option></select>
                <input v-model="fu.due_date" type="date" class="form-control form-control-sm" style="max-width: 160px" aria-label="Due date" />
                <input v-model="fu.note" class="form-control form-control-sm flex-grow-1" style="min-width: 180px" placeholder="Note for the account owner" aria-label="Note" />
                <button class="btn btn-primary btn-sm" type="button" :disabled="!fu.assignee_id" @click="assign"><Send :size="13" /> Create follow-up</button>
              </div>
            </div>
            <div class="act mt-2">
              <div class="small-label mb-1">Update status / record outcome</div>
              <div class="d-flex flex-wrap gap-2">
                <select v-model="upd.status" class="form-select form-select-sm" style="max-width: 180px" aria-label="Status"><option v-for="s in statuses" :key="s" :value="s">{{ statusMeta(s).label }}</option></select>
                <select v-model="upd.outcome" class="form-select form-select-sm" style="max-width: 220px" aria-label="Outcome"><option value="">Outcome…</option>
                  <option v-for="x in outcomes" :key="x" :value="x">{{ humanize(x) }}</option></select>
                <input v-model="upd.note" class="form-control form-control-sm flex-grow-1" style="min-width: 160px" placeholder="Note (required to dismiss)" aria-label="Outcome note" />
                <button class="btn btn-light btn-sm" type="button" @click="update">Save</button>
              </div>
              <p class="form-text mb-0">Outcomes are recorded only from completed follow-ups — so realised value is measured, not assumed.</p>
            </div>
          </template>
          <p v-else class="small text-muted-2 mb-0">Read-only for your role.</p>
        </div>
      </template>
    </ModalDialog>
  </div>
</template>
<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowRight, ClipboardList, Flame, Layers, Lightbulb, RotateCw, Send, TrendingDown, TrendingUp, User, UserMinus } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import EChart from '@/components/EChart.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorState from '@/components/ErrorState.vue'
import LoadingBlock from '@/components/LoadingBlock.vue'
import { get, patch, post } from '@/api/client'
import { useAuth } from '@/stores/auth'
import { useReference } from '@/stores/reference'
import { useToast } from '@/stores/toast'
import { fmtDate, fmtPct, humanize, monthLabel, statusMeta } from '@/utils/format'
import { FAMILY_COLORS, axisCategory, axisValue, baseGrid, tooltip } from '@/utils/charts'

const route = useRoute()
const auth = useAuth()
const ref_ = useReference()
const toast = useToast()
const PRI = { HIGH: 'tone-error', MEDIUM: 'tone-warning', LOW: 'tone-neutral' }
const cats = [{ key: '', label: 'All', icon: Layers }, { key: 'CROSS_SELL', label: 'Cross-selling', icon: Lightbulb }, { key: 'INACTIVITY', label: 'Potential inactivity', icon: UserMinus },
  { key: 'GROWTH_MARKET', label: 'Growing product-markets', icon: TrendingUp }, { key: 'DEMAND_CHANGE', label: 'Demand changes', icon: TrendingDown }]
const catIcon = (c) => cats.find((x) => x.key === c)?.icon || Layers
const category = ref(route.query.category || '')
const status = ref('')
const country = ref('')
const items = ref([])
const counts = ref({})
const byStatus = ref({})
const statuses = ref(['NEW', 'UNDER_REVIEW', 'ASSIGNED', 'IN_PROGRESS', 'COMPLETED', 'DISMISSED'])
const outcomes = ref([])
const salesUsers = ref([])
const loading = ref(true)
const error = ref(null)
const refreshing = ref(false)
const selected = ref(null)
const fu = reactive({ assignee_id: null, due_date: '', note: '' })
const upd = reactive({ status: 'UNDER_REVIEW', outcome: '', note: '' })
const total = computed(() => Object.values(counts.value).reduce((a, b) => a + b, 0))

watch(selected, (o) => { if (o) { upd.status = o.status; upd.outcome = o.outcome || ''; upd.note = o.outcome_note || ''; fu.assignee_id = o.owner?.id || null; fu.note = ''; fu.due_date = '' } })
const evidenceRows = computed(() => {
  const e = selected.value?.evidence || {}
  const r = {}
  if (e.existing) r['Already buys'] = e.existing.map((x) => `Product ${x}`).join(', ')
  if (e.peers !== undefined) r['Comparable customers (same segment, buy the same products)'] = e.peers
  if (e.adopters !== undefined) r['…of which also buy the candidate product'] = `${e.adopters} (${fmtPct(e.rate)})`
  if (e.enquiries !== undefined) r['Enquiries about it, last 6 months'] = e.enquiries
  if (e.segment) r['Segment'] = humanize(e.segment)
  if (e.last) r['Last confirmed order'] = monthLabel(e.last)
  if (e.typical_interval_months !== undefined) r['Typical ordering interval'] = `${e.typical_interval_months} month(s)`
  if (e.months_since_last_order !== undefined) r['Months since last order'] = e.months_since_last_order
  if (e.last_order_month) r['Last order'] = monthLabel(e.last_order_month)
  if (e.orders_in_window !== undefined) r['Order months in window'] = e.orders_in_window
  if (e.growth !== undefined) r['3M vs prior 3M'] = fmtPct(e.growth, 1, true)
  if (e.forecast_change !== undefined && e.forecast_change !== null) r['Forecast vs recent average'] = fmtPct(e.forecast_change, 1, true)
  return r
})
const sparkOpt = computed(() => {
  const u = selected.value?.evidence.monthly_units || []
  const ms = ['2025-10', '2025-11', '2025-12', '2026-01', '2026-02', '2026-03', '2026-04', '2026-05', '2026-06', '2026-07', '2026-08', '2026-09'].slice(-u.length)
  return { tooltip: tooltip({ axisPointer: { type: 'shadow' } }), grid: baseGrid({ top: 10 }), xAxis: axisCategory(ms.map(monthLabel)), yAxis: axisValue(''),
    series: [{ type: 'bar', name: 'Confirmed units', data: u, barMaxWidth: 14, itemStyle: { color: FAMILY_COLORS[selected.value.family] || '#2a78d6', borderRadius: [3, 3, 0, 0] } }] }
})

async function load() {
  loading.value = true; error.value = null
  try {
    const st = status.value === 'ALL' ? undefined : status.value || 'NEW,UNDER_REVIEW,ASSIGNED,IN_PROGRESS'
    const r = await get('/api/opportunities', { category: category.value || undefined, status: st, country: country.value || undefined })
    items.value = r.items; counts.value = r.counts; byStatus.value = r.by_status; statuses.value = r.statuses; outcomes.value = r.outcomes
    if (route.query.id && !selected.value) {
      selected.value = r.items.find((x) => String(x.id) === String(route.query.id)) || null
      if (!selected.value) { const all = await get('/api/opportunities', { status: undefined }); selected.value = all.items.find((x) => String(x.id) === String(route.query.id)) || null }
    }
  } catch (e) { error.value = e } finally { loading.value = false }
}
function replace(o) { const i = items.value.findIndex((x) => x.id === o.id); if (i >= 0) items.value[i] = o; selected.value = o }
async function assign() {
  try { const o = await post(`/api/opportunities/${selected.value.id}/followup`, { assignee_id: fu.assignee_id, due_date: fu.due_date || null, note: fu.note }); replace(o); toast.push(`Follow-up assigned to ${o.owner.name} — they were notified`) } catch (e) { toast.error(e) }
}
async function update() {
  try { const o = await patch(`/api/opportunities/${selected.value.id}`, { status: upd.status, outcome: upd.outcome || null, note: upd.note }); replace(o); toast.push('Opportunity updated') } catch (e) { toast.error(e) }
}
async function refresh() {
  refreshing.value = true
  try { const r = await post('/api/opportunities/refresh'); toast.push(`Recomputed: ${r.created} new, ${r.updated} updated, ${r.marked_stale} no longer supported by data`); load() } catch (e) { toast.error(e) } finally { refreshing.value = false }
}
onMounted(async () => {
  ref_.load()
  load()
  try { salesUsers.value = await get('/api/users', { role: 'SALES' }) } catch { /* optional */ }
})
</script>
<style scoped>
.opp { padding: 1rem 1.15rem; cursor: pointer; transition: transform .2s, border-color .2s, box-shadow .2s; }
.opp:hover, .opp.focus { border-color: #c7d2fe; box-shadow: var(--shadow-2); transform: translateY(-3px); }
.clamp { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.sec { padding: .7rem 0; border-bottom: 1px solid var(--border); }
.sec:last-child { border-bottom: none; }
.act { background: var(--accent-soft); border-radius: 14px; padding: .7rem; }
</style>
