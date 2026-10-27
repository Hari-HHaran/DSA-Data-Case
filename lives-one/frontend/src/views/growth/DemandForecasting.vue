<template>
  <div class="page">
    <PageHeader title="Sales forecast" eyebrow="Sales insights" subtitle="What we expect to sell in the next few months, based on past orders. Pick a country and a product." />
    <ErrorState v-if="error" :error="error" :retry="load" class="mb-3" />
    <div class="grid grid-kpi mb-3">
      <KpiTile label="How accurate the forecast is" :value="sel ? fmtPct(1 - sel.wape, 0) : null" :hint="`Tested on past months · the old method was ${base ? fmtPct(1 - base.wape, 0) : '—'}`" :icon="Target" tone="teal" :loading="!sum" />
      <KpiTile label="Fewer forecast mistakes" :value="fmtPct(sum?.wape_reduction_vs_baseline, 0)" hint="Compared with the old average-based method" :icon="TrendingDown" tone="success" :loading="!sum" />
    </div>

    <div class="card-x p-3 mb-3 d-flex flex-wrap gap-3 align-items-center">
      <div><span class="small-label d-block mb-1">Country</span><div class="filters-row">
        <button v-for="c in ref_.countries" :key="c.code" type="button" class="chip" :class="{ on: country === c.code }" @click="pick(c.code, family)">{{ c.name }}</button></div></div>
      <div><span class="small-label d-block mb-1">Product</span><div class="filters-row">
        <button v-for="f in ['A', 'B', 'C']" :key="f" type="button" class="chip" :class="{ on: family === f }" @click="pick(country, f)"><span class="legend-dot" :style="{ background: FAMILY_COLORS[f] }" />Product {{ f }}</button></div></div>
    </div>

    <div class="grid grid-main-side mb-3">
      <ChartCard :title="`Product ${family} · ${ref_.countryName(country)}`" :subtitle="`Orders in ${s?.unit || ''} per month`"
                 note="Solid line = what was actually ordered. Dashed line = forecast. Shaded area = the likely range.">
        <LoadingBlock v-if="!s" :rows="6" />
        <EChart v-else :option="opt" height="400px" aria-label="Past orders and forecast" />
        <template #table><table v-if="s" class="table table-sm"><thead><tr><th>Month</th><th>Actual</th><th>Forecast</th><th>Old method</th><th>Likely range</th></tr></thead>
          <tbody><tr v-for="m in [...s.months, ...s.future_months]" :key="m"><td>{{ monthLabel(m) }}</td><td class="num">{{ fmtNumber(s.history[s.months.indexOf(m)]) }}</td>
            <td class="num">{{ fmtNumber((s.models[s.selected_model].backtest[m] || s.models[s.selected_model].future[m])?.predicted) }}</td>
            <td class="num">{{ fmtNumber((s.models.ROLLING_AVG.backtest[m] || s.models.ROLLING_AVG.future[m])?.predicted) }}</td>
            <td class="num">{{ s.models[s.selected_model].future[m] ? `${fmtNumber(s.models[s.selected_model].future[m].lower)}–${fmtNumber(s.models[s.selected_model].future[m].upper)}` : '' }}</td></tr></tbody></table></template>
      </ChartCard>
      <section class="card-x">
        <div class="card-x-head"><h2>What this means</h2></div>
        <div class="card-x-body" v-if="s">
          <p class="mb-3">{{ s.explanation.summary }}</p>
          <dl class="kv small mb-3">
            <dt>Last 3 months vs the 3 before</dt><dd class="num">{{ fmtPct(s.explanation.recent_change, 1, true) }}</dd>
            <dt>Forecast vs recent months</dt><dd class="num">{{ fmtPct(s.explanation.forecast_change, 1, true) }}</dd>
          </dl>
          <div v-if="s.low_volume" class="callout warn small mb-2"><AlertTriangle :size="14" /><div>Only small amounts are sold here, so percentages can look bigger than they really are.</div></div>
          <div class="small-label mb-1">What you could do</div>
          <ul class="small ps-3 mb-2"><li v-for="r in s.explanation.recommendations" :key="r">{{ r }}</li></ul>
          <p class="form-text mb-0">This describes what the numbers show, not the reasons behind them.</p>
        </div>
      </section>
    </div>

  </div>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { AlertTriangle, Target, TrendingDown } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import KpiTile from '@/components/KpiTile.vue'
import ChartCard from '@/components/ChartCard.vue'
import EChart from '@/components/EChart.vue'
import ErrorState from '@/components/ErrorState.vue'
import LoadingBlock from '@/components/LoadingBlock.vue'
import { get } from '@/api/client'
import { useReference } from '@/stores/reference'
import { fmtNumber, fmtPct, monthLabel } from '@/utils/format'
import { FAMILY_COLORS, axisCategory, axisValue, baseGrid, legend, lineSeries, months as mlabels, tooltip } from '@/utils/charts'

const route = useRoute()
const router = useRouter()
const ref_ = useReference()
const country = ref(route.query.country || 'SG')
const family = ref(route.query.family || 'A')
const sum = ref(null)
const s = ref(null)
const error = ref(null)
const showBacktest = ref(false) // test predictions on past months: hidden for everyday users
const sel = computed(() => sum.value?.evaluations.find((e) => e.is_selected))
const base = computed(() => sum.value?.evaluations.find((e) => e.model === 'ROLLING_AVG'))

async function load() {
  error.value = null
  try {
    const r = await get('/api/forecasts', { country: country.value, family: family.value })
    sum.value = r.summary; s.value = r.series
  } catch (e) { error.value = e }
}
function pick(c, f) { country.value = c; family.value = f; router.replace({ query: { country: c, family: f } }); s.value = null; load() }
const opt = computed(() => {
  const x = s.value
  if (!x) return {}
  const all = [...x.months, ...x.future_months]
  const n = x.months.length
  const selM = x.models[x.selected_model]
  const baseM = x.models.ROLLING_AVG
  const pad = (arr) => [...arr, ...x.future_months.map(() => null)]
  const fut = (m) => all.map((mm, i) => (i === n - 1 ? x.history[n - 1] : m.future[mm]?.predicted ?? null))
  const bt = (m) => all.map((mm) => m.backtest[mm]?.predicted ?? null)
  const lower = all.map((m) => selM.future[m]?.lower ?? null)
  const band = all.map((m) => (selM.future[m] ? selM.future[m].upper - selM.future[m].lower : null))
  const series = [
    { name: 'low', type: 'line', data: lower, stack: 'band', lineStyle: { opacity: 0 }, symbol: 'none', silent: true, tooltip: { show: false } },
    { name: 'Likely range', type: 'line', data: band, stack: 'band', lineStyle: { opacity: 0 }, symbol: 'none', areaStyle: { color: 'rgba(42,120,214,.14)' }, tooltip: { show: false } },
    lineSeries('Actual orders', pad(x.history), '#172033', { markArea: { silent: true, itemStyle: { color: 'rgba(16,28,53,.035)' }, data: [[{ xAxis: mlabels([x.future_months[0]])[0] }, { xAxis: mlabels([x.future_months.at(-1)])[0] }]],
      label: { show: true, position: 'insideTop', color: '#64748b', fontSize: 11, formatter: 'Next months' } } }),
    lineSeries('Forecast', fut(selM), FAMILY_COLORS.A, { lineStyle: { type: 'dashed', width: 2, color: FAMILY_COLORS.A } }),
  ]
  if (x.selected_model !== 'ROLLING_AVG') series.push(lineSeries('Old method (average)', fut(baseM), '#94a3b8', { lineStyle: { type: 'dotted', width: 2, color: '#94a3b8' }, symbolSize: 5 }))
  if (showBacktest.value) {
    series.push({ name: 'Held-out (selected)', type: 'line', data: bt(selM), lineStyle: { opacity: 0 }, symbol: 'emptyCircle', symbolSize: 9, itemStyle: { color: FAMILY_COLORS.A, borderWidth: 2 } })
    if (x.selected_model !== 'ROLLING_AVG') series.push({ name: 'Held-out (rolling avg)', type: 'line', data: bt(baseM), lineStyle: { opacity: 0 }, symbol: 'emptyDiamond', symbolSize: 9, itemStyle: { color: '#94a3b8', borderWidth: 2 } })
  }
  return { tooltip: tooltip(), legend: legend({ data: series.filter((z) => z.name !== 'low').map((z) => z.name) }), grid: baseGrid({ top: 56 }),
    xAxis: axisCategory(mlabels(all)), yAxis: axisValue(x.unit), series }
})
onMounted(() => { ref_.load(); load() })
</script>
<style scoped>
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
