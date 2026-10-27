<template>
  <section class="card-x map-card">
    <div class="card-x-head">
      <div>
        <h2>Where we sell</h2>
        <p class="sub">Click a country on the map or a button below to filter the whole page. Bigger circles mean more confirmed orders.</p>
      </div>
      <button v-if="selected.length" class="btn btn-light btn-sm" type="button" @click="$emit('change', [])"><Globe2 :size="14" /> Show all countries</button>
    </div>
    <div ref="el" class="map" role="application" aria-label="Map of the five country locations. Use the country buttons below for keyboard access." />
    <div class="country-row" role="group" aria-label="Filter by country">
      <button type="button" class="ctry" :class="{ on: !selected.length }" :aria-pressed="!selected.length" @click="$emit('change', [])">
        <span class="c-ic all"><Globe2 :size="15" /></span>
        <span class="c-txt"><strong>All countries</strong><small>{{ fmtNumber(totalPos) }} orders</small></span>
      </button>
      <button v-for="c in rows" :key="c.code" type="button" class="ctry" :class="{ on: isOn(c.code), dim: selected.length && !isOn(c.code) }"
              :aria-pressed="isOn(c.code)" @click="toggle(c.code)">
        <span class="c-ic" :style="{ background: countryColor(c.code) }">{{ c.code }}</span>
        <span class="c-txt"><strong>{{ c.name }}</strong>
          <small v-if="c.stats">{{ fmtNumber(c.stats.confirmed_pos) }} orders
            <span :class="(c.stats.po_growth ?? 0) >= 0 ? 'up' : 'down'">{{ fmtPct(c.stats.po_growth, 0, true) }}</span></small>
          <small v-else>Click to include</small></span>
        <Check v-if="isOn(c.code)" :size="15" class="c-check" />
      </button>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Check, Globe2 } from 'lucide-vue-next'
import { countryColor } from '@/utils/charts'
import { fmtNumber, fmtPct } from '@/utils/format'

const props = defineProps({
  countries: { type: Array, default: () => [] }, // [{ code, name }]
  stats: { type: Object, default: () => ({}) }, // { SG: { confirmed_pos, po_growth, active_customers } }
  selected: { type: Array, default: () => [] }, // selected country codes; empty = all
})
const emit = defineEmits(['change'])

// Location of each country office (map pin position) and which side its label sits on.
const PLACES = {
  SG: { lat: 1.3521, lng: 103.8198, dir: 'right' },
  MY: { lat: 3.139, lng: 101.6869, dir: 'left' },
  ID: { lat: -6.2088, lng: 106.8456, dir: 'bottom' },
  TH: { lat: 13.7563, lng: 100.5018, dir: 'left' },
  VN: { lat: 10.8231, lng: 106.6297, dir: 'right' }, // Ho Chi Minh City
}

const el = ref(null)
let map = null
const markers = {}

const rows = computed(() => props.countries.filter((c) => PLACES[c.code]).map((c) => ({ ...c, stats: props.stats[c.code] })))
const totalPos = computed(() => rows.value.reduce((s, c) => s + (c.stats?.confirmed_pos || 0), 0))
const isOn = (code) => props.selected.includes(code)
function toggle(code) {
  emit('change', isOn(code) ? props.selected.filter((x) => x !== code) : [...props.selected, code])
}

function radius(code) {
  const max = Math.max(1, ...rows.value.map((c) => c.stats?.confirmed_pos || 0))
  const v = props.stats[code]?.confirmed_pos || 0
  return 8 + 14 * Math.sqrt(v / max)
}
function label(c) {
  const s = c.stats
  return `<strong>${c.name}</strong>${s ? `<br>${fmtNumber(s.confirmed_pos)} orders · ${fmtPct(s.po_growth, 0, true)}` : ''}`
}
function draw() {
  if (!map) return
  const anySel = props.selected.length > 0
  for (const c of rows.value) {
    const on = !anySel || isOn(c.code)
    const style = { radius: radius(c.code), color: '#fff', weight: 3, fillColor: countryColor(c.code), fillOpacity: on ? 0.85 : 0.25, opacity: on ? 1 : 0.6 }
    let m = markers[c.code]
    if (!m) {
      const p = PLACES[c.code]
      m = L.circleMarker([p.lat, p.lng], style).addTo(map)
      m.bindTooltip('', { permanent: true, direction: p.dir, offset: [p.dir === 'left' ? -8 : p.dir === 'right' ? 8 : 0, p.dir === 'bottom' ? 8 : 0], className: 'map-label' })
      m.on('click', () => toggle(c.code))
      markers[c.code] = m
    } else m.setStyle(style)
    m.setTooltipContent(label(c))
    const tip = m.getTooltip()?.getElement()
    if (tip) tip.classList.toggle('dim', !on)
    if (isOn(c.code)) m.bringToFront()
  }
}

onMounted(async () => {
  await nextTick()
  map = L.map(el.value, { scrollWheelZoom: false, zoomSnap: 0.25, attributionControl: true })
  // Free OpenStreetMap tiles (no API key). Softened with CSS below to match the app's look.
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 10,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map)
  map.fitBounds(Object.values(PLACES).map((p) => [p.lat, p.lng]), { padding: [40, 60] })
  draw()
  setTimeout(() => map?.invalidateSize(), 200) // the page fades in, so re-measure once it is visible
})
onBeforeUnmount(() => { map?.remove(); map = null })
watch(() => [props.selected, props.stats, props.countries], () => draw(), { deep: true })
</script>

<style scoped>
.map-card { overflow: hidden; }
.map { height: 420px; background: #eef1f7; z-index: 0; }
@media (max-width: 760px) { .map { height: 280px; } }
.country-row { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: .6rem; padding: 1rem 1.2rem 1.2rem; }
@media (max-width: 1200px) { .country-row { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 560px) { .country-row { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.ctry { position: relative; display: flex; align-items: center; gap: .6rem; padding: .6rem .7rem; border: 1px solid var(--border); border-radius: 14px; background: var(--surface);
  text-align: left; color: var(--text); transition: transform .15s, box-shadow .15s, border-color .15s, opacity .15s; min-width: 0; }
.ctry:hover { transform: translateY(-2px); box-shadow: var(--shadow-2); border-color: #c7d2fe; }
.ctry.on { border-color: var(--accent-2); background: var(--accent-soft); box-shadow: var(--ring); }
.ctry.dim { opacity: .6; }
.c-ic { width: 34px; height: 34px; border-radius: 11px; color: #fff; font-weight: 700; font-size: .74rem; display: inline-flex; align-items: center; justify-content: center; flex: none; }
.c-ic.all { background: var(--accent-grad); }
.c-txt { display: flex; flex-direction: column; min-width: 0; line-height: 1.25; }
.c-txt strong { font-size: .86rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.c-txt small { color: var(--muted); font-size: .74rem; }
.c-txt .up { color: var(--success); font-weight: 600; }
.c-txt .down { color: var(--error); font-weight: 600; }
.c-check { position: absolute; top: 6px; right: 7px; color: var(--accent); }
/* Leaflet draws its own elements outside Vue's scope */
.map :deep(.map-label) { background: #fff; border: none; border-radius: 10px; box-shadow: 0 8px 20px -8px rgba(16, 28, 53, .35); padding: .3rem .55rem; font-size: .76rem; color: var(--text); font-family: var(--font); }
.map :deep(.map-label::before) { display: none; }
.map :deep(.map-label.dim) { opacity: .55; }
.map :deep(.leaflet-interactive) { cursor: pointer; }
.map :deep(.leaflet-tile-pane) { filter: grayscale(.65) brightness(1.06) contrast(.92); }
.map :deep(.leaflet-control-zoom a) { border-radius: 8px; }
.map :deep(.leaflet-bar) { border: none; box-shadow: var(--shadow-1); border-radius: 10px; overflow: hidden; }
</style>
