<template>
  <div class="page">
    <PageHeader title="Data quality & canonical mapping" eyebrow="Growth Intelligence"
                subtitle="How raw purchasing records become a clean regional view — what is counted as demand, what is excluded and why, and what mapping aliases changes.">
      <template #badge><span class="pill tag-synthetic">Synthetic data</span></template>
      <RouterLink to="/mdm/records?tab=mapping" class="btn btn-light"><GitMerge :size="15" /> Review mappings</RouterLink>
    </PageHeader>
    <ErrorState v-if="error" :error="error" :retry="load" />
    <LoadingBlock v-else-if="!dq" :rows="8" />
    <template v-else>
      <div class="flow-strip mb-3">
        <div class="step"><Database :size="18" /><strong class="num">{{ fmtNumber(dq.raw_records) }}</strong><small>raw purchasing records</small></div>
        <ChevronRight :size="18" class="arrow" />
        <div class="step warn"><AlertTriangle :size="18" /><strong class="num">{{ fmtNumber(dq.flagged_records) }}</strong><small>flagged data-quality issues</small></div>
        <ChevronRight :size="18" class="arrow" />
        <div class="step neutral"><Filter :size="18" /><strong class="num">{{ fmtNumber(dq.excluded_by_policy) }}</strong><small>excluded by policy (not demand)</small></div>
        <ChevronRight :size="18" class="arrow" />
        <div class="step ok"><CheckCircle2 :size="18" /><strong class="num">{{ fmtNumber(dq.valid_records) }}</strong><small>confirmed demand lines</small></div>
        <ChevronRight :size="18" class="arrow" />
        <div class="step teal"><GitMerge :size="18" /><strong class="num">{{ dq.before_after.customers_without_mapping }} → {{ dq.before_after.customers_with_mapping }}</strong><small>customer records → canonical customers</small></div>
      </div>

      <div class="grid grid-main-side mb-3">
        <section class="card-x">
          <div class="card-x-head"><h2>Classification & exclusion summary</h2><span class="small text-muted-2">Click a row to inspect the records</span></div>
          <div class="table-responsive"><table class="table table-hover">
            <thead><tr><th>Category</th><th>Type</th><th class="text-end">Records</th><th class="text-end">Quantity</th><th>In demand?</th></tr></thead>
            <tbody>
              <tr @click="inspect('CONFIRMED_DEMAND')"><td><strong>Confirmed purchase order</strong> (Confirmed / Fulfilled)</td><td><span class="pill tone-success">Included</span></td>
                <td class="num text-end">{{ fmtNumber(dq.valid_records) }}</td><td class="num text-end">{{ fmtNumber(totalClean) }}</td><td><Check :size="15" class="text-success" /> Yes</td></tr>
              <tr v-for="r in dq.reasons" :key="r.code" @click="inspect(r.code)"><td>{{ r.label }}</td>
                <td><span class="pill" :class="r.kind === 'Data quality' ? 'tone-warning' : 'tone-neutral'">{{ r.kind }}</span></td>
                <td class="num text-end">{{ fmtNumber(r.records) }}</td><td class="num text-end">{{ r.quantity ? fmtNumber(r.quantity) : '—' }}</td><td><X :size="15" class="text-danger" /> No</td></tr>
              <tr class="mdm"><td><strong>MDM set-up requests</strong> (customer, vendor, item, cost centre)</td><td><span class="pill tone-info">Separate object</span></td>
                <td class="num text-end">{{ dq.mdm_setup_requests_separate }}</td><td class="text-end">—</td><td><X :size="15" class="text-danger" /> Never</td></tr>
            </tbody></table></div>
          <div class="card-x-body pt-2 small text-muted-2">Quantities are summed in each product's own unit only for this audit view; dashboards never add boxes, kits and units together.</div>
        </section>
        <section class="card-x">
          <div class="card-x-head"><h2>Inclusion policy</h2></div>
          <div class="card-x-body small">
            <p class="mb-2">{{ dq.inclusion_policy }}</p>
            <div class="callout neutral"><Info :size="15" /><div>A <strong>customer purchase enquiry</strong> is interest; a <strong>purchase request</strong> needs processing; a <strong>purchase order</strong> is the formal transaction; an <strong>MDM set-up request</strong> is an internal request to create a record. Only eligible purchase orders feed the forecast.</div></div>
          </div>
        </section>
      </div>

      <div class="grid grid-2 mb-3">
        <ChartCard title="Before vs after: how much a naive roll-up overstates demand" subtitle="Naive sum of all PO lines (incl. cancelled, returned, double-loaded) vs governed confirmed demand, per product">
          <EChart :option="baOpt" height="260px" aria-label="Bar chart comparing naive and clean quantities" />
          <template #table><table class="table table-sm"><thead><tr><th>Product</th><th>Naive</th><th>Clean</th><th>Overstatement</th></tr></thead>
            <tbody><tr v-for="f in ['A', 'B', 'C']" :key="f"><td>{{ f }}</td><td class="num">{{ fmtNumber(dq.before_after.naive_units[f]) }}</td><td class="num">{{ fmtNumber(dq.before_after.clean_units[f]) }}</td>
              <td class="num">{{ fmtPct(dq.before_after.naive_units[f] / dq.before_after.clean_units[f] - 1, 1, true) }}</td></tr></tbody></table></template>
        </ChartCard>
        <section class="card-x">
          <div class="card-x-head"><h2>Why canonical mapping matters for growth insight</h2></div>
          <div class="card-x-body">
            <div class="grid grid-2">
              <div class="stat"><div class="num big">{{ dq.before_after.raw_name_variants }}</div><small>customer name variants in raw purchase orders</small></div>
              <div class="stat"><div class="num big">{{ dq.before_after.customers_with_mapping }}</div><small>distinct customers after confirmed mappings (proposed ones await review)</small></div>
              <div class="stat"><div class="num big">{{ fmtPct(eff.false_gap_share) }}</div><small>of apparent "customer doesn't buy product X" gaps are false without mapping ({{ eff.false_gaps_avoided }} of {{ eff.apparent_gaps_without_mapping }})</small></div>
              <div class="stat"><div class="num big">{{ eff.recommendations_without_mapping }} → {{ eff.recommendations_with_mapping }}</div><small>evidence-based cross-sell candidates (peer analysis needs a full view of each customer)</small></div>
            </div>
            <div v-if="eff.examples?.length" class="small mt-2 text-muted-2">e.g. {{ eff.examples.slice(0, 3).map((x) => `"${x.customer}" appears not to buy Product ${x.family}`).join('; ') }} — but does, under another entity's record.</div>
          </div>
        </section>
      </div>

      <section class="card-x mb-3">
        <div class="card-x-head"><h2>Consolidation examples</h2><span class="small text-muted-2">One customer, several source records — each transaction counted once</span></div>
        <div class="card-x-body grid grid-3">
          <div v-for="c in dq.consolidation_examples" :key="c.canonical_key" class="cons">
            <strong>{{ c.canonical_name }}</strong> <span class="small text-muted-2">{{ c.country }}</span>
            <div v-for="s in c.sources" :key="s.name + s.entity" class="small d-flex justify-content-between"><span>{{ s.entity }} · "{{ s.name }}"</span><span class="num">{{ s.orders }} POs</span></div>
            <div class="small d-flex justify-content-between fw-semibold border-top mt-1 pt-1"><span>Consolidated</span><span class="num">{{ c.total_orders }} POs</span></div>
          </div>
        </div>
      </section>

      <section v-if="rows" class="card-x" ref="rowsEl">
        <div class="card-x-head"><h2>Records: {{ inspectLabel }}</h2><span class="small text-muted-2">{{ rows.total }} records · raw values preserved</span></div>
        <div class="table-responsive"><table class="table table-sm">
          <thead><tr><th>Source txn</th><th>Type</th><th>Status</th><th>Date</th><th>Raw customer</th><th>Canonical</th><th>Product</th><th>Raw country → code</th><th class="text-end">Qty</th></tr></thead>
          <tbody><tr v-for="r in rows.items" :key="r.id"><td class="mono small">{{ r.source_txn_id }}/{{ r.line_no }}</td><td class="small">{{ r.event_type.replace('_', ' ').toLowerCase() }}</td>
            <td class="small">{{ r.status.toLowerCase() }}</td><td class="small">{{ r.event_date }}</td><td class="small">{{ r.raw_customer_name }}</td><td class="small">{{ r.canonical_name || '—' }}</td>
            <td class="small">{{ r.product_code || '∅' }}</td><td class="small">"{{ r.raw_country }}" → {{ r.country_code || '?' }}</td><td class="num text-end">{{ r.quantity ?? '∅' }}</td></tr></tbody></table></div>
        <div class="d-flex justify-content-end gap-1 p-2"><button class="btn btn-light btn-sm" :disabled="rowsPage === 1" @click="rowsPage--; fetchRows()">Previous</button>
          <button class="btn btn-light btn-sm" :disabled="rowsPage * 25 >= rows.total" @click="rowsPage++; fetchRows()">Next</button></div>
      </section>
      <SyntheticNote class="mt-3">Data-quality defects (double-loaded lines, country spelling variants, missing product codes, zero quantities) were injected deliberately and are detected by the pipeline, not hardcoded.</SyntheticNote>
    </template>
  </div>
</template>
<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { AlertTriangle, Check, CheckCircle2, ChevronRight, Database, Filter, GitMerge, Info, X } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import ChartCard from '@/components/ChartCard.vue'
import EChart from '@/components/EChart.vue'
import ErrorState from '@/components/ErrorState.vue'
import LoadingBlock from '@/components/LoadingBlock.vue'
import SyntheticNote from '@/components/SyntheticNote.vue'
import { get } from '@/api/client'
import { fmtNumber, fmtPct } from '@/utils/format'
import { FAMILY_COLORS, INK, axisCategory, axisValue, baseGrid, tooltip } from '@/utils/charts'

const dq = ref(null)
const error = ref(null)
const rows = ref(null)
const rowsEl = ref(null)
const rowsPage = ref(1)
const reason = ref('')
const eff = computed(() => dq.value?.cross_sell_mapping_effect || {})
const totalClean = computed(() => Object.values(dq.value?.before_after.clean_units || {}).reduce((a, b) => a + b, 0))
const inspectLabel = computed(() => reason.value === 'CONFIRMED_DEMAND' ? 'confirmed demand' : dq.value?.reasons.find((r) => r.code === reason.value)?.label)
async function load() { error.value = null; try { dq.value = await get('/api/analytics/data-quality') } catch (e) { error.value = e } }
async function inspect(code) { reason.value = code; rowsPage.value = 1; await fetchRows(); await nextTick(); rowsEl.value?.scrollIntoView({ behavior: 'smooth' }) }
async function fetchRows() { rows.value = await get('/api/analytics/purchasing', { reason: reason.value, page: rowsPage.value, page_size: 25 }) }
const baOpt = computed(() => {
  const b = dq.value?.before_after
  if (!b) return {}
  const fams = ['A', 'B', 'C']
  const over = fams.map((f) => +(100 * (b.naive_units[f] / b.clean_units[f] - 1)).toFixed(1))
  return { tooltip: tooltip({ axisPointer: { type: 'shadow' }, valueFormatter: (v) => `+${v}%` }), grid: baseGrid({ top: 16, right: 48 }),
    xAxis: axisValue('', { axisLabel: { color: INK.muted, fontSize: 11, formatter: (v) => `${v}%` } }), yAxis: { ...axisCategory(fams.map((f) => `Product ${f}`)), inverse: true },
    series: [{ name: 'Overstatement vs confirmed demand', type: 'bar', barMaxWidth: 22,
      data: over.map((v, i) => ({ value: v, itemStyle: { color: FAMILY_COLORS[fams[i]], borderRadius: [0, 4, 4, 0] } })),
      label: { show: true, position: 'right', color: INK.text, fontSize: 11, formatter: (p) => `+${p.value}%` } }] }
})
onMounted(load)
</script>
<style scoped>
.flow-strip { display: flex; align-items: stretch; gap: .5rem; flex-wrap: wrap; }
.step { flex: 1; min-width: 150px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: .8rem 1rem; display: flex; flex-direction: column; gap: .15rem; box-shadow: var(--shadow-1); }
.step strong { font-size: 1.35rem; }
.step small { color: var(--muted); font-size: .76rem; }
.step.warn svg { color: var(--warning-ink); } .step.ok svg { color: var(--success); } .step.teal svg { color: var(--teal); } .step.neutral svg { color: var(--muted); }
.arrow { align-self: center; color: var(--muted); flex: none; }
@media (max-width: 900px) { .arrow { display: none; } }
tr.mdm td { background: #f6f9ff; }
.stat { background: var(--surface-2); border-radius: 8px; padding: .7rem .8rem; }
.stat .big { font-size: 1.45rem; font-weight: 700; }
.stat small { color: var(--text-2); font-size: .76rem; }
.cons { border: 1px solid var(--border); border-radius: 8px; padding: .7rem .8rem; }
</style>
