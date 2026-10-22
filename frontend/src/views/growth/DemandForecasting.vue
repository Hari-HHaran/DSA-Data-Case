<template>
  <div class="page">
    <PageHeader title="Demand forecasting" eyebrow="Growth Intelligence" subtitle="The current rolling-average approach vs lighter-weight improvements, judged on rolling-origin backtests — the model is chosen by evidence, not complexity.">
      <template #badge><span class="pill tag-synthetic">Synthetic data</span></template>
      <button class="btn btn-light" type="button" :disabled="running" @click="rerun"><RotateCw :size="15" :class="{ spin: running }" /> Re-run backtest</button>
    </PageHeader>
    <ErrorState v-if="error" :error="error" :retry="load" class="mb-3" />
    <div class="grid grid-kpi mb-3">
      <KpiTile label="Selected approach — WAPE" :value="fmtPct(sel?.wape, 1)" :hint="`Rolling average: ${fmtPct(base?.wape, 1)} · avg. across A/B/C`" :icon="Target" tone="teal" :loading="!sum" />
      <KpiTile label="Error reduction vs baseline" :value="fmtPct(sum?.wape_reduction_vs_baseline, 1)" hint="Relative change in WAPE on held-out months" :icon="TrendingDown" tone="success" :loading="!sum" />
      <KpiTile label="Forecast bias" :value="fmtPct(sel?.bias, 1, true)" :hint="`Baseline ${fmtPct(base?.bias, 1, true)} (negative = under-forecast)`" :icon="Scale" :loading="!sum" />
      <KpiTile label="Backtest points" :value="sel?.n_points" :hint="`${sum?.notes.series} series × origins ${sum?.notes.backtest_origins?.[0]}…${sum?.notes.backtest_origins?.at(-1)} × horizons 1–3`" :icon="FlaskConical" :loading="!sum" />
    </div>
    <div v-if="sum" class="callout warn mb-3"><AlertTriangle :size="18" /><div><strong>Data sufficiency:</strong> {{ sum.notes.data_sufficiency }} Forecast ranges are approximate (empirical 80% band from backtest errors).</div></div>

    <div class="card-x p-3 mb-3 d-flex flex-wrap gap-3 align-items-center">
      <div><span class="small-label d-block mb-1">Country</span><div class="filters-row">
        <button v-for="c in ref_.countries" :key="c.code" type="button" class="chip" :class="{ on: country === c.code }" @click="pick(c.code, family)">{{ c.name }}</button></div></div>
      <div><span class="small-label d-block mb-1">Product</span><div class="filters-row">
        <button v-for="f in ['A', 'B', 'C']" :key="f" type="button" class="chip" :class="{ on: family === f }" @click="pick(country, f)"><span class="legend-dot" :style="{ background: FAMILY_COLORS[f] }" />Product {{ f }}</button></div></div>
      <div v-if="s" class="ms-auto small text-end"><div class="small-label">Model used for Product {{ family }}</div><strong>{{ MODEL_LABEL[s.selected_model] }}</strong></div>
    </div>

    <div class="grid grid-main-side mb-3">
      <ChartCard :title="`Product ${family} · ${ref_.countryName(country)}`" :subtitle="`Confirmed demand in ${s?.unit || ''} per month`"
                 note="Solid = actual confirmed demand. Hollow markers = held-out predictions (each made using only earlier months). Dashed = future forecast; shaded = approx. 80% range.">
        <template #actions><label class="small d-flex align-items-center gap-1"><input v-model="showBacktest" type="checkbox" class="form-check-input m-0" /> Held-out predictions</label></template>
        <LoadingBlock v-if="!s" :rows="6" />
        <EChart v-else :option="opt" height="400px" aria-label="Actual demand, held-out predictions and forecast" />
        <template #table><table v-if="s" class="table table-sm"><thead><tr><th>Month</th><th>Actual</th><th>Selected (held-out / future)</th><th>Rolling avg</th><th>Range</th></tr></thead>
          <tbody><tr v-for="m in [...s.months, ...s.future_months]" :key="m"><td>{{ monthLabel(m) }}</td><td class="num">{{ fmtNumber(s.history[s.months.indexOf(m)]) }}</td>
            <td class="num">{{ fmtNumber((s.models[s.selected_model].backtest[m] || s.models[s.selected_model].future[m])?.predicted) }}</td>
            <td class="num">{{ fmtNumber((s.models.ROLLING_AVG.backtest[m] || s.models.ROLLING_AVG.future[m])?.predicted) }}</td>
            <td class="num">{{ s.models[s.selected_model].future[m] ? `${fmtNumber(s.models[s.selected_model].future[m].lower)}–${fmtNumber(s.models[s.selected_model].future[m].upper)}` : '' }}</td></tr></tbody></table></template>
      </ChartCard>
      <section class="card-x">
        <div class="card-x-head"><h2>What this means</h2><span class="pill tone-info"><Sparkles :size="11" /> Generated from computed metrics</span></div>
        <div class="card-x-body" v-if="s">
          <p class="mb-3">{{ s.explanation.summary }}</p>
          <div class="small-label mb-1">Evidence</div>
          <dl class="kv small mb-3">
            <dt>Recent change (3M vs prior)</dt><dd class="num">{{ fmtPct(s.explanation.recent_change, 1, true) }}</dd>
            <dt>Forecast vs recent avg.</dt><dd class="num">{{ fmtPct(s.explanation.forecast_change, 1, true) }}</dd>
            <dt>Volatility (CV)</dt><dd class="num">{{ s.explanation.volatility_cv?.toFixed(2) ?? '—' }}</dd>
            <template v-for="(e, m) in s.evaluations" :key="m"><dt>{{ MODEL_LABEL[m] }} WAPE</dt><dd class="num">{{ fmtPct(e.wape, 1) }} <span class="text-muted-2">· bias {{ fmtPct(e.bias, 0, true) }}</span></dd></template>
          </dl>
          <div v-if="s.low_volume" class="callout warn small mb-2"><AlertTriangle :size="14" /><div>Low volume series — percentage errors can mislead; use MAE.</div></div>
          <div class="small-label mb-1">Suggested review actions</div>
          <ul class="small ps-3 mb-2"><li v-for="r in s.explanation.recommendations" :key="r">{{ r }}</li></ul>
          <p class="form-text mb-0">{{ s.explanation.note }} The text describes what the data shows; it does not claim causes.</p>
        </div>
      </section>
    </div>

    <div class="grid grid-2 mb-3">
      <section class="card-x">
        <div class="card-x-head"><h2>Model comparison by product family</h2><span class="small text-muted-2">Rolling-origin backtest · horizons 1–3 months</span></div>
        <div class="table-responsive"><table class="table">
          <thead><tr><th>Product</th><th>Model</th><th class="text-end">MAE</th><th class="text-end">WAPE</th><th class="text-end">Bias</th></tr></thead>
          <tbody>
            <template v-for="fe in sum?.family_evaluations || []" :key="fe.family">
              <tr v-for="(m, i) in CAND" :key="m" :class="{ champ: sum.champions[fe.family] === m }">
                <td v-if="i === 0" :rowspan="3"><span class="legend-dot me-1" :style="{ background: FAMILY_COLORS[fe.family] }" />Product {{ fe.family }}<div class="small text-muted-2">{{ fe.unit }}</div></td>
                <td>{{ MODEL_LABEL[m] }} <span v-if="sum.champions[fe.family] === m" class="pill tone-success ms-1"><Trophy :size="11" /> Selected</span></td>
                <td class="num text-end">{{ fmtNumber(fe[m].mae, 1) }}</td><td class="num text-end">{{ fmtPct(fe[m].wape, 1) }}</td><td class="num text-end">{{ fmtPct(fe[m].bias, 1, true) }}</td>
              </tr>
            </template>
            <tr class="total"><td colspan="2"><strong>Headline (avg. of A, B, C)</strong> — selected vs baseline</td><td class="text-end">—</td>
              <td class="num text-end"><strong>{{ fmtPct(sel?.wape, 1) }}</strong> vs {{ fmtPct(base?.wape, 1) }}</td><td class="num text-end">{{ fmtPct(sel?.bias, 1, true) }}</td></tr>
          </tbody></table></div>
        <div class="card-x-body pt-2 small text-muted-2">MAE is in each family's own unit, so it is never pooled across families. Selection rule: lowest family WAPE; ties go to the simpler model.</div>
      </section>
      <section class="card-x">
        <div class="card-x-head"><h2>Best model by series</h2><span class="small text-muted-2">Lowest backtest WAPE for each country × product</span></div>
        <div class="table-responsive" style="max-height: 420px"><table class="table table-sm">
          <thead><tr><th>Series</th><th class="text-end">Rolling</th><th class="text-end">Holt</th><th class="text-end">Ridge</th><th>Best</th></tr></thead>
          <tbody><tr v-for="g in grid" :key="g.scope" :class="{ hl: g.country === country && g.family === family }" @click="pick(g.country, g.family)" style="cursor:pointer">
            <td>{{ g.country }} · {{ g.family }}</td>
            <td v-for="m in CAND" :key="m" class="num text-end" :class="{ best: g.best_model === m }">{{ fmtPct(g[m]?.wape, 0) }}</td>
            <td class="small">{{ SHORT[g.best_model] }}</td></tr></tbody></table></div>
        <div class="card-x-body pt-2 small text-muted-2">No single model wins every series — which is why selection is evidence-based and re-run as data arrives.</div>
      </section>
    </div>

    <section class="card-x mb-3">
      <div class="card-x-head"><h2>Methodology</h2></div>
      <div class="card-x-body grid grid-3 small">
        <div><h3 class="h6">Models</h3><ul class="ps-3 mb-0">
          <li><strong>Rolling average</strong> — mean of the last {{ sum?.params.rolling_window }} months; today's spreadsheet method.</li>
          <li><strong>Damped-trend exponential smoothing</strong> — follows recent level and a trend that flattens.</li>
          <li><strong>Pooled ridge regression</strong> — one model across all 15 series on scale-free lag features, so 12 months per series is not the whole training set.</li></ul></div>
        <div><h3 class="h6">Evaluation</h3><ul class="ps-3 mb-0">
          <li>Rolling-origin backtest: train on months before each origin, predict the next 1–3 months. Never shuffled.</li>
          <li>Features and scaling use only past data (tested for leakage).</li>
          <li>MAE (units), WAPE = Σ|error| ÷ Σ actual, bias = Σ(forecast − actual) ÷ Σ actual.</li></ul></div>
        <div><h3 class="h6">Limits & next steps</h3><ul class="ps-3 mb-0">
          <li>12 months cannot identify seasonality — collect ≥ 24 months before adding seasonal models.</li>
          <li>Product C is periodic and lumpy; quarterly planning may suit it better than monthly point forecasts.</li>
          <li>Forecasts inform review; they never change inventory or procurement automatically.</li></ul></div>
      </div>
    </section>
    <SyntheticNote />
  </div>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { AlertTriangle, FlaskConical, RotateCw, Scale, Sparkles, Target, TrendingDown, Trophy } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import KpiTile from '@/components/KpiTile.vue'
import ChartCard from '@/components/ChartCard.vue'
import EChart from '@/components/EChart.vue'
import ErrorState from '@/components/ErrorState.vue'
import LoadingBlock from '@/components/LoadingBlock.vue'
import SyntheticNote from '@/components/SyntheticNote.vue'
import { get, post } from '@/api/client'
import { useReference } from '@/stores/reference'
import { useToast } from '@/stores/toast'
import { fmtNumber, fmtPct, monthLabel } from '@/utils/format'
import { FAMILY_COLORS, axisCategory, axisValue, baseGrid, legend, lineSeries, months as mlabels, tooltip } from '@/utils/charts'

const route = useRoute()
const router = useRouter()
const ref_ = useReference()
const toast = useToast()
const CAND = ['ROLLING_AVG', 'HOLT_DAMPED', 'RIDGE_POOLED']
const MODEL_LABEL = { ROLLING_AVG: 'Rolling average (baseline)', HOLT_DAMPED: 'Damped-trend smoothing', RIDGE_POOLED: 'Pooled ridge regression', CHAMPION: 'Selected per family' }
const SHORT = { ROLLING_AVG: 'Rolling avg', HOLT_DAMPED: 'Holt', RIDGE_POOLED: 'Ridge' }
const country = ref(route.query.country || 'SG')
const family = ref(route.query.family || 'A')
const sum = ref(null)
const s = ref(null)
const grid = ref([])
const error = ref(null)
const running = ref(false)
const showBacktest = ref(true)
const sel = computed(() => sum.value?.evaluations.find((e) => e.is_selected))
const base = computed(() => sum.value?.evaluations.find((e) => e.model === 'ROLLING_AVG'))

async function load() {
  error.value = null
  try {
    const r = await get('/api/forecasts', { country: country.value, family: family.value })
    sum.value = r.summary; s.value = r.series
  } catch (e) { error.value = e }
}
async function loadGrid() { try { grid.value = (await get('/api/forecasts/evaluations')).series } catch { /* shown elsewhere */ } }
function pick(c, f) { country.value = c; family.value = f; router.replace({ query: { country: c, family: f } }); s.value = null; load() }
async function rerun() {
  running.value = true
  try { const r = await post('/api/forecasts/run'); toast.push(`Backtest re-run (#${r.run_id}). Selected approach WAPE ${fmtPct(r.evaluations.find((e) => e.is_selected).wape, 1)}.`); await Promise.all([load(), loadGrid()]) }
  catch (e) { toast.error(e) } finally { running.value = false }
}
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
    { name: '80% range', type: 'line', data: band, stack: 'band', lineStyle: { opacity: 0 }, symbol: 'none', areaStyle: { color: 'rgba(42,120,214,.14)' }, tooltip: { show: false } },
    lineSeries('Actual', pad(x.history), '#172033', { markArea: { silent: true, itemStyle: { color: 'rgba(16,28,53,.035)' }, data: [[{ xAxis: mlabels([x.future_months[0]])[0] }, { xAxis: mlabels([x.future_months.at(-1)])[0] }]],
      label: { show: true, position: 'insideTop', color: '#64748b', fontSize: 11, formatter: 'Forecast horizon' } } }),
    lineSeries('Forecast (selected)', fut(selM), FAMILY_COLORS.A, { lineStyle: { type: 'dashed', width: 2, color: FAMILY_COLORS.A } }),
  ]
  if (x.selected_model !== 'ROLLING_AVG') series.push(lineSeries('Forecast (rolling avg)', fut(baseM), '#94a3b8', { lineStyle: { type: 'dotted', width: 2, color: '#94a3b8' }, symbolSize: 5 }))
  if (showBacktest.value) {
    series.push({ name: 'Held-out (selected)', type: 'line', data: bt(selM), lineStyle: { opacity: 0 }, symbol: 'emptyCircle', symbolSize: 9, itemStyle: { color: FAMILY_COLORS.A, borderWidth: 2 } })
    if (x.selected_model !== 'ROLLING_AVG') series.push({ name: 'Held-out (rolling avg)', type: 'line', data: bt(baseM), lineStyle: { opacity: 0 }, symbol: 'emptyDiamond', symbolSize: 9, itemStyle: { color: '#94a3b8', borderWidth: 2 } })
  }
  return { tooltip: tooltip(), legend: legend({ data: series.filter((z) => z.name !== 'low').map((z) => z.name) }), grid: baseGrid({ top: 56 }),
    xAxis: axisCategory(mlabels(all)), yAxis: axisValue(x.unit), series }
})
onMounted(() => { ref_.load(); load(); loadGrid() })
</script>
<style scoped>
.champ td { background: #f3fbf6; }
tr.total td { background: var(--surface-2); }
td.best { font-weight: 700; color: var(--success); }
tr.hl td { background: #f5f8ff; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
