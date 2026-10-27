<template>
  <div class="page">
    <PageHeader title="Sales by country" eyebrow="Sales insights" subtitle="Confirmed orders for Products A, B and C across our five countries. Each order is counted once.">
    </PageHeader>

    <div class="callout info mb-3 statement"><CalendarRange :size="18" />
      <div>Showing <strong>{{ monthLabel(o?.window.selected_start) }} – {{ monthLabel(o?.window.selected_end) }}</strong>. Only confirmed orders are counted, not enquiries.
        "Growth" compares the last 3 months with the 3 months before.</div></div>

    <GrowthFilters v-if="months.length" :model="f" :countries="countries" :months="months" :customers="customers" @change="applyFilters" @reset="resetFilters" />
    <ErrorState v-if="error" :error="error" :retry="load" class="mb-3" />
    <CountryMap v-if="countries.length" class="mb-3" :countries="countries" :stats="countryStats" :selected="f.countries" @change="(list) => applyFilters({ countries: list })" />

    <div class="grid grid-kpi mb-3">
      <KpiTile label="Confirmed orders" :value="fmtNumber(k?.confirmed_pos.value)" unit="orders" :hint="`About ${fmtNumber(k?.avg_monthly_pos.value)} a month`" :icon="ShoppingCart" :loading="loading" />
      <KpiTile label="Order growth" :value="fmtPct(k?.po_growth.value, 1, true)" :icon="TrendingUp" :tone="(k?.po_growth.value ?? 0) >= 0 ? 'success' : 'error'" hint="Last 3 months vs the 3 before" :loading="loading" />
      <KpiTile label="Customers who ordered" :value="fmtNumber(k?.active_customers.value)" hint="Each customer counted once" :icon="Users" :loading="loading" />
      <KpiTile label="Forecast accuracy" :value="fmtPct(o?.forecast?.accuracy, 1)" :hint="`How close past forecasts were · old method ${fmtPct(o?.forecast?.baseline_accuracy, 0)}`" :icon="Target" tone="teal" to="/growth/forecasting" :loading="loading" />
      <KpiTile label="Sales opportunities" :value="fmtNumber(o?.open_opportunities)" hint="Open, high or medium priority" :icon="Lightbulb" tone="warning" to="/growth/opportunities" :loading="loading" />
    </div>
    <div class="grid grid-3 mb-3">
      <div v-for="u in k?.units_by_family || []" :key="u.family" class="card-x fam">
        <span class="legend-dot" :style="{ background: FAMILY_COLORS[u.family] }" />
        <div><div class="small-label">{{ u.label }} · amount ordered</div><div class="num fw-bold fs-5">{{ fmtNumber(u.units) }} <span class="small text-muted-2 fw-normal">{{ u.unit }}</span></div></div>
        <span class="ms-auto pill num" :class="(u.growth ?? 0) >= 0 ? 'tone-success' : 'tone-error'"><component :is="(u.growth ?? 0) >= 0 ? TrendingUp : TrendingDown" :size="12" />{{ fmtPct(u.growth, 1, true) }}</span>
      </div>
    </div>

    <section class="card-x mb-3">
      <div class="card-x-head"><h2>What this means and what to do</h2><span class="small text-muted-2">Worked out from the numbers on this page. Please check before acting.</span></div>
      <div class="card-x-body"><ul class="impl mb-0"><li v-for="(t, i) in implications" :key="i" v-html="t" /></ul></div>
    </section>
    <div class="grid grid-2 mb-3">
      <ChartCard title="Orders per month, by country" subtitle="Each order counted once">
        <EChart :option="trendOpt" aria-label="Line chart of orders per month by country" />
        <template #table><table class="table table-sm"><thead><tr><th>Country</th><th v-for="m in o?.window.months" :key="m">{{ monthLabel(m) }}</th></tr></thead>
          <tbody><tr v-for="t in o?.trend" :key="t.country"><td>{{ t.country }}</td><td v-for="(v, i) in t.values" :key="i" class="num">{{ v }}</td></tr></tbody></table></template>
      </ChartCard>
      <ChartCard title="Growth by country and product" subtitle="Blue = growing, red = shrinking (last 3 months)" note="Each product is counted in its own unit: boxes, kits or units.">
        <EChart :option="matrixOpt" aria-label="Heatmap of growth by country and product family" />
        <template #table><table class="table table-sm"><thead><tr><th>Country</th><th>Product</th><th>Amount</th><th>Growth</th><th>Customers</th></tr></thead>
          <tbody><tr v-for="m in o?.matrix" :key="m.country + m.family"><td>{{ m.country }}</td><td>{{ m.family }}</td><td class="num">{{ fmtNumber(m.units) }} {{ UNIT[m.family] }}</td><td class="num">{{ fmtPct(m.growth, 1, true) }}</td><td class="num">{{ m.customers }}</td></tr></tbody></table></template>
      </ChartCard>
    </div>
    <div class="grid grid-3 mb-3">
      <ChartCard title="What each country buys" subtitle="Share of orders for each product">
        <EChart :option="mixOpt" height="260px" aria-label="Stacked bar of product mix by country" />
        <template #table><table class="table table-sm"><thead><tr><th>Country</th><th v-for="f in fams" :key="f">{{ f }}</th></tr></thead>
          <tbody><tr v-for="m in o?.mix" :key="m.country"><td>{{ m.country }}</td><td v-for="f in fams" :key="f" class="num">{{ fmtPct(m.shares[f], 0) }}</td></tr></tbody></table></template>
      </ChartCard>
      <ChartCard title="Growth by product" subtitle="Last 3 months vs the 3 before">
        <EChart :option="growthOpt" height="260px" aria-label="Grouped bar chart of growth by country and product" />
        <template #table><table class="table table-sm"><tbody><tr v-for="m in o?.matrix" :key="m.country + m.family"><td>{{ m.country }} · {{ m.family }}</td><td class="num">{{ fmtPct(m.growth, 1, true) }}</td></tr></tbody></table></template>
      </ChartCard>
      <ChartCard title="Countries ranked by orders" subtitle="Most orders at the top">
        <EChart :option="rankOpt" height="260px" aria-label="Bar chart ranking countries by confirmed purchase orders" />
        <template #table><table class="table table-sm"><thead><tr><th>#</th><th>Country</th><th>Orders</th><th>Growth</th><th>Customers</th></tr></thead>
          <tbody><tr v-for="(r, i) in o?.ranking" :key="r.country"><td>{{ i + 1 }}</td><td>{{ r.country }}</td><td class="num">{{ r.confirmed_pos }}</td><td class="num">{{ fmtPct(r.po_growth, 1, true) }}</td><td class="num">{{ r.active_customers }}</td></tr></tbody></table></template>
      </ChartCard>
    </div>
    <div class="grid grid-3 mb-3">
      <ChartCard :title="`Past sales and forecast · Product ${fc.family} in ${ref_.countryName(fc.country)}`" :subtitle="fcSub" class="span-2">
        <template #actions><RouterLink :to="`/growth/forecasting?country=${fc.country}&family=${fc.family}`" class="btn btn-ghost btn-sm">More detail <ArrowRight :size="13" /></RouterLink></template>
        <EChart v-if="series" :option="fcOpt" height="260px" aria-label="Actual demand and forecast" />
        <LoadingBlock v-else />
      </ChartCard>
      <section class="card-x">
        <div class="card-x-head"><h2>Sales opportunities</h2><RouterLink to="/growth/opportunities" class="small">See all</RouterLink></div>
        <div class="card-x-body p-0">
          <EmptyState v-if="!opps.length" title="No open opportunities for this selection" />
          <RouterLink v-for="op in opps" :key="op.id" :to="`/growth/opportunities?id=${op.id}`" class="alert-row">
            <span class="pill" :class="op.priority === 'HIGH' ? 'tone-error' : 'tone-warning'">{{ op.priority === 'HIGH' ? 'High' : 'Medium' }}</span>
            <div><strong>{{ op.title }}</strong><small>{{ op.insight }}</small></div></RouterLink>
        </div>
      </section>
    </div>
    <div class="grid grid-2 mb-3">
      <ChartCard title="Customers by how often they buy" subtitle="In the selected period">
        <EChart :option="segOpt" height="240px" aria-label="Bar chart of customer segments" />
        <template #table><table class="table table-sm"><tbody><tr v-for="b in o?.segments.buckets" :key="b.bucket"><td>{{ b.bucket }}</td><td class="num">{{ b.customers }} customers</td><td class="num">{{ b.lines }} lines</td></tr></tbody></table></template>
      </ChartCard>
      <section class="card-x">
        <div class="card-x-head"><h2>Who buys each product</h2><span class="small text-muted-2">Share of customers in each country who buy it</span></div>
        <div class="table-responsive"><table class="table">
          <thead><tr><th>Country</th><th class="text-end">Customers</th><th v-for="f in fams" :key="f" class="text-end">Product {{ f }}</th></tr></thead>
          <tbody><tr v-for="p in o?.penetration" :key="p.country"><td><span class="legend-dot me-1" :style="{ background: countryColor(p.country) }" />{{ ref_.countryName(p.country) }}</td>
            <td class="num text-end">{{ p.customers }}</td><td v-for="f in fams" :key="f" class="num text-end">
              <div class="pen"><span :style="{ width: (p[f] * 100) + '%', background: FAMILY_COLORS[f] }" /></div>{{ fmtPct(p[f]) }}</td></tr></tbody></table></div>
        <div class="card-x-body pt-2 small text-muted-2">Not counted as orders: {{ fmtNumber(o?.signals?.ENQUIRY) }} enquiries, {{ fmtNumber(o?.signals?.PURCHASE_REQUEST) }} purchase requests,
          and {{ fmtNumber(o?.signals?.PENDING_MDM_SETUP) }} orders waiting for a new customer code.</div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, CalendarRange, Lightbulb, ShoppingCart, Target, TrendingDown, TrendingUp, Users } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import KpiTile from '@/components/KpiTile.vue'
import ChartCard from '@/components/ChartCard.vue'
import EChart from '@/components/EChart.vue'
import GrowthFilters from '@/components/GrowthFilters.vue'
import CountryMap from '@/components/CountryMap.vue'
import ErrorState from '@/components/ErrorState.vue'
import EmptyState from '@/components/EmptyState.vue'
import LoadingBlock from '@/components/LoadingBlock.vue'
import { get } from '@/api/client'
import { useReference } from '@/stores/reference'
import { fmtNumber, fmtPct, monthLabel } from '@/utils/format'
import { DIVERGING, FAMILY_COLORS, INK, axisCategory, axisValue, barSeries, baseGrid, countryColor, legend, lineSeries, months as mlabels, tooltip } from '@/utils/charts'

const route = useRoute()
const router = useRouter()
const ref_ = useReference()
const UNIT = { A: 'boxes', B: 'kits', C: 'units' }
const o = ref(null)
const loading = ref(true)
const error = ref(null)
const customers = ref([])
const opps = ref([])
// Last known numbers per country for the map; countries outside the current filter keep their previous values.
const countryStats = reactive({})
const series = ref(null)
const months = ref([])
const countries = computed(() => ref_.countries)
const split = (v) => (v ? String(v).split(',').filter(Boolean) : [])
const f = reactive({ countries: split(route.query.countries), families: split(route.query.families), entities: split(route.query.entities),
  start: route.query.start || '', end: route.query.end || '', customer: route.query.customer || '', status: route.query.status || '' })
const k = computed(() => o.value?.kpis)
const fams = computed(() => (f.families.length ? f.families : ['A', 'B', 'C']).slice().sort())
const fc = computed(() => ({ country: f.countries[0] || 'SG', family: f.families[0] || 'B' }))
const fcSub = computed(() => series.value ? `In ${UNIT[fc.value.family]} · the shaded area is the likely range` : '')

function applyFilters(v) {
  Object.assign(f, v)
  const q = {}
  for (const key of ['countries', 'families', 'entities']) if (f[key].length) q[key] = f[key].join(',')
  for (const key of ['start', 'end', 'customer', 'status']) if (f[key]) q[key] = f[key]
  router.replace({ query: q })
}
function resetFilters() { applyFilters({ countries: [], families: [], entities: [], start: months.value[0], end: months.value.at(-1), customer: '', status: '' }) }

async function load() {
  loading.value = true; error.value = null
  try {
    const params = { countries: f.countries.join(',') || undefined, families: f.families.join(',') || undefined, entities: f.entities.join(',') || undefined,
      start: f.start || undefined, end: f.end || undefined, customer: f.customer || undefined, status: f.status || undefined }
    const [ov, op, fcr] = await Promise.all([
      get('/api/analytics/overview', params),
      get('/api/opportunities', { status: 'NEW,UNDER_REVIEW,ASSIGNED,IN_PROGRESS', country: f.countries.length === 1 ? f.countries[0] : undefined }).catch(() => ({ items: [] })),
      get('/api/forecasts', { country: fc.value.country, family: fc.value.family }).catch(() => null),
    ])
    o.value = ov
    if (!f.countries.length) for (const k of Object.keys(countryStats)) delete countryStats[k]
    for (const r of ov.ranking || []) countryStats[r.country] = r
    if (!months.value.length) { months.value = ov.window.months; if (!f.start) f.start = months.value[0]; if (!f.end) f.end = months.value.at(-1) }
    opps.value = op.items.filter((x) => !f.families.length || !x.family || f.families.includes(x.family)).slice(0, 5)
    series.value = fcr?.series || null
  } catch (e) { error.value = e } finally { loading.value = false }
}
watch(() => route.query, load)
onMounted(async () => {
  await ref_.load()
  load()
  get('/api/analytics/customers').then((c) => { customers.value = c }).catch(() => {})
})

const xMonths = computed(() => mlabels(o.value?.window.months || []))
const trendOpt = computed(() => ({
  aria: { enabled: true }, grid: baseGrid({ top: 56 }), tooltip: tooltip(), legend: legend(),
  xAxis: axisCategory(xMonths.value), yAxis: axisValue('Orders'),
  series: (o.value?.trend || []).map((t) => lineSeries(t.country, t.values, countryColor(t.country), {
    endLabel: { show: (o.value?.trend.length || 0) <= 5, formatter: '{a}', color: INK.text, fontSize: 11 } })),
}))
const matrixOpt = computed(() => {
  const cs = [...new Set((o.value?.matrix || []).map((m) => m.country))]
  const data = (o.value?.matrix || []).map((m) => [fams.value.indexOf(m.family), cs.indexOf(m.country), m.growth == null ? null : +(m.growth * 100).toFixed(1), m.units])
  return {
    tooltip: { backgroundColor: '#101c35', textStyle: { color: '#fff' }, formatter: (p) => `${cs[p.value[1]]} · Product ${fams.value[p.value[0]]}<br/>${fmtNumber(p.value[3])} ${UNIT[fams.value[p.value[0]]]}<br/>Growth ${p.value[2] == null ? '—' : (p.value[2] > 0 ? '+' : '') + p.value[2] + '%'}` },
    grid: { left: 8, right: 8, top: 8, bottom: 56, containLabel: true },
    xAxis: { type: 'category', data: fams.value.map((x) => `Product ${x}`), axisTick: { show: false }, axisLine: { show: false }, axisLabel: { color: INK.text } },
    yAxis: { type: 'category', data: cs, inverse: true, axisTick: { show: false }, axisLine: { show: false }, axisLabel: { color: INK.text } },
    visualMap: { min: -30, max: 30, dimension: 2, orient: 'horizontal', left: 'center', bottom: 0, itemHeight: 140, calculable: false, text: ['Growing', 'Shrinking'],
      textStyle: { color: INK.muted, fontSize: 11 }, inRange: { color: DIVERGING } },
    series: [{ type: 'heatmap', data, itemStyle: { borderColor: '#fff', borderWidth: 3, borderRadius: 6 },
      label: { show: true, color: INK.text, fontSize: 11, formatter: (p) => `${fmtNumber(p.value[3])}\n${p.value[2] == null ? '—' : (p.value[2] > 0 ? '+' : '') + p.value[2] + '%'}` } }],
  }
})
const mixOpt = computed(() => {
  const rows = o.value?.mix || []
  return { tooltip: tooltip({ trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (v) => fmtPct(v, 0) }), legend: legend(), grid: baseGrid({ top: 32 }),
    xAxis: { type: 'value', max: 1, axisLabel: { formatter: (v) => fmtPct(v), color: INK.muted, fontSize: 11 }, splitLine: { lineStyle: { color: INK.grid } } },
    yAxis: { ...axisCategory(rows.map((r) => r.country)), inverse: true },
    series: fams.value.map((fm) => ({ name: `Product ${fm}`, type: 'bar', stack: 'mix', barMaxWidth: 22, data: rows.map((r) => r.shares[fm] || 0),
      itemStyle: { color: FAMILY_COLORS[fm], borderColor: '#fff', borderWidth: 2 } })) }
})
const growthOpt = computed(() => {
  const cs = [...new Set((o.value?.matrix || []).map((m) => m.country))]
  return { tooltip: tooltip({ axisPointer: { type: 'shadow' }, valueFormatter: (v) => (v == null ? '—' : `${v > 0 ? '+' : ''}${v}%`) }), legend: legend(), grid: baseGrid({ top: 32 }),
    xAxis: axisCategory(cs), yAxis: axisValue('', { axisLabel: { formatter: (v) => `${v}%`, color: INK.muted, fontSize: 11 } }),
    series: fams.value.map((fm) => barSeries(`Product ${fm}`, cs.map((c) => { const m = o.value.matrix.find((x) => x.country === c && x.family === fm); return m?.growth == null ? null : +(m.growth * 100).toFixed(1) }), FAMILY_COLORS[fm],
      { barMaxWidth: 14, itemStyle: { color: FAMILY_COLORS[fm], borderRadius: 3, borderColor: '#fff', borderWidth: 1 }, markLine: fm === fams.value[0] ? { silent: true, symbol: 'none', data: [{ yAxis: 0 }], lineStyle: { color: INK.axis } } : undefined })) }
})
const rankOpt = computed(() => {
  const r = o.value?.ranking || []
  return { tooltip: tooltip({ axisPointer: { type: 'shadow' } }), grid: baseGrid({ top: 8, right: 70 }),
    xAxis: axisValue(''), yAxis: { ...axisCategory(r.map((x) => x.country)), inverse: true },
    series: [{ type: 'bar', name: 'Orders', barMaxWidth: 18, data: r.map((x) => ({ value: x.confirmed_pos, itemStyle: { color: countryColor(x.country), borderRadius: [0, 4, 4, 0] } })),
      label: { show: true, position: 'right', color: INK.text, fontSize: 11, formatter: (p) => `${p.value} · ${fmtPct(r[p.dataIndex].po_growth, 0, true)}` } }] }
})
const fcOpt = computed(() => {
  const s = series.value
  if (!s) return {}
  const all = [...s.months, ...s.future_months]
  const sel = s.models[s.selected_model]
  const base = s.models.ROLLING_AVG
  const hist = [...s.history, ...s.future_months.map(() => null)]
  const fut = all.map((m, i) => (i === s.months.length - 1 ? s.history.at(-1) : sel.future[m]?.predicted ?? null))
  const baseF = all.map((m, i) => (i === s.months.length - 1 ? s.history.at(-1) : base.future[m]?.predicted ?? null))
  const lower = all.map((m) => sel.future[m]?.lower ?? null)
  const band = all.map((m) => (sel.future[m] ? sel.future[m].upper - sel.future[m].lower : null))
  return { tooltip: tooltip(), legend: legend(), grid: baseGrid({ top: 56 }), xAxis: axisCategory(mlabels(all)), yAxis: axisValue(UNIT[s.family]),
    series: [
      { name: 'range-low', type: 'line', data: lower, stack: 'band', lineStyle: { opacity: 0 }, symbol: 'none', tooltip: { show: false }, silent: true },
      { name: 'Likely range', type: 'line', data: band, stack: 'band', lineStyle: { opacity: 0 }, symbol: 'none', areaStyle: { color: 'rgba(42,120,214,.14)' }, tooltip: { show: false } },
      lineSeries('Actual orders', hist, '#172033'),
      lineSeries('Forecast', fut, FAMILY_COLORS.A, { lineStyle: { width: 2, type: 'dashed', color: FAMILY_COLORS.A } }),
      lineSeries('Old method (average)', baseF, '#94a3b8', { lineStyle: { width: 2, type: 'dotted', color: '#94a3b8' }, symbolSize: 5 }),
    ],
    legend: legend({ data: ['Actual orders', 'Forecast', 'Old method (average)', 'Likely range'] }) }
})
const segOpt = computed(() => {
  const b = o.value?.segments.buckets || []
  return { tooltip: tooltip({ axisPointer: { type: 'shadow' } }), grid: baseGrid({ top: 8, right: 40 }), xAxis: axisValue(''),
    yAxis: { ...axisCategory(b.map((x) => x.bucket)), inverse: true, axisLabel: { color: INK.text, fontSize: 11, width: 170, overflow: 'break' } },
    series: [{ type: 'bar', name: 'Customers', barMaxWidth: 18, data: b.map((x, i) => ({ value: x.customers, itemStyle: { color: i === 3 ? '#e34948' : '#2a78d6', borderRadius: [0, 4, 4, 0] } })),
      label: { show: true, position: 'right', color: INK.text, fontSize: 11 } }] }
})
const implications = computed(() => {
  if (!o.value) return []
  const out = []
  const m = [...o.value.matrix].filter((x) => x.growth != null)
  const top = m.sort((a, b) => b.growth - a.growth)[0]
  const low = m.sort((a, b) => a.growth - b.growth)[0]
  const famMax = (fam) => Math.max(...o.value.matrix.filter((x) => x.family === fam).map((x) => x.units))
  const smallBase = (x) => x.units < 0.5 * famMax(x.family) ? `, but from only ${fmtNumber(x.units)} ${UNIT[x.family]}, so be careful` : ''
  if (top) out.push(`<strong>Fastest growth:</strong> Product ${top.family} in ${ref_.countryName(top.country)} (${fmtPct(top.growth, 0, true)} in the last 3 months${smallBase(top)}). <em>What to do:</em> check there is enough stock, and how long suppliers need, before the next order.`)
  if (low && low.growth < 0) out.push(`<strong>Largest decline:</strong> Product ${low.family} in ${ref_.countryName(low.country)} (${fmtPct(low.growth, 0, true)}${smallBase(low)}). <em>What to do:</em> ask the account owners if one customer is behind it, before buying less stock.`)
  const pen = o.value.penetration.map((p) => ({ c: p.country, v: p.C })).filter((p) => p.v !== undefined).sort((a, b) => a.v - b.v)[0]
  if (pen) out.push(`<strong>Fewest customers buying Product C:</strong> ${ref_.countryName(pen.c)} (${fmtPct(pen.v)} of customers). <em>What to do:</em> offer Product C to customers who buy A or B there, if it is registered and suitable.`)
  const lapsing = o.value.segments.buckets.find((b) => b.bucket.startsWith('Lapsing'))
  if (lapsing?.customers) out.push(`<strong>${lapsing.customers} customer(s) have not ordered in the last 2 months.</strong> <em>What to do:</em> account owners should check in with them. They may not have stopped buying.`)
  if (o.value.signals?.PENDING_MDM_SETUP) out.push(`<strong>${o.value.signals.PENDING_MDM_SETUP} order(s) are waiting for a new customer code.</strong> Approving customer requests faster turns these into sales.`)
  return out
})
</script>
<style scoped>
.fam { display: flex; gap: .75rem; align-items: center; padding: .8rem 1rem; }
.alert-row { display: flex; gap: .6rem; padding: .7rem 1rem; border-bottom: 1px solid var(--border); color: var(--text); text-decoration: none; font-size: .84rem; align-items: flex-start; }
.alert-row:hover { background: #f7f7ff; text-decoration: none; }
.alert-row small { display: block; color: var(--muted); }
.span-2 { grid-column: span 2; }
@media (max-width: 1100px) { .span-2 { grid-column: auto; } }
.pen { height: 6px; background: var(--surface-2); border-radius: 4px; margin-bottom: 2px; overflow: hidden; }
.pen span { display: block; height: 100%; border-radius: 4px; }
.impl li { margin-bottom: .45rem; }
.statement { font-size: .84rem; }
</style>
