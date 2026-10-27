<template>
  <div class="donut-wrap">
    <ul class="donut-legend">
      <li v-for="s in slices" :key="s.label">
        <RouterLink v-if="s.to" :to="s.to" class="lg-row">
          <span class="lg-label">{{ s.label }}</span><span class="lg-val num">{{ s.value }}</span>
          <span class="lg-bar"><span :style="{ width: s.pct + '%', background: s.color }" /></span>
        </RouterLink>
        <div v-else class="lg-row">
          <span class="lg-label">{{ s.label }}</span><span class="lg-val num">{{ s.value }}</span>
          <span class="lg-bar"><span :style="{ width: s.pct + '%', background: s.color }" /></span>
        </div>
      </li>
    </ul>
    <svg class="donut" viewBox="0 0 120 120" role="img" :aria-label="ariaLabel">
      <circle cx="60" cy="60" :r="r" fill="none" stroke="var(--surface-2)" :stroke-width="sw" />
      <circle v-for="s in slices" :key="s.label" cx="60" cy="60" :r="r" fill="none" :stroke="s.color" :stroke-width="sw"
              :stroke-dasharray="`${s.len} ${circ - s.len}`" :stroke-dashoffset="-s.offset" stroke-linecap="butt" transform="rotate(-90 60 60)">
        <title>{{ s.label }}: {{ s.value }}</title>
      </circle>
      <text x="60" y="57" text-anchor="middle" class="d-total">{{ total }}</text>
      <text x="60" y="73" text-anchor="middle" class="d-cap">{{ centerLabel }}</text>
    </svg>
  </div>
</template>
<script setup>
import { computed } from 'vue'
const props = defineProps({ data: { type: Array, default: () => [] }, centerLabel: { type: String, default: 'total' }, ariaLabel: String })
const r = 46
const sw = 16
const circ = 2 * Math.PI * r
const total = computed(() => props.data.reduce((s, d) => s + (d.value || 0), 0))
const slices = computed(() => {
  let acc = 0
  const gap = props.data.filter((d) => d.value).length > 1 ? 1.5 : 0
  return props.data.map((d) => {
    const share = total.value ? (d.value || 0) / total.value : 0
    const len = Math.max(0, share * circ - (d.value ? gap : 0))
    const out = { ...d, len, offset: acc, pct: Math.round(share * 100) }
    acc += share * circ
    return out
  })
})
</script>
<style scoped>
.donut-wrap { display: grid; grid-template-columns: minmax(0, 1fr) 150px; gap: 1.25rem; align-items: center; }
.donut { width: 150px; height: 150px; }
.d-total { font-size: 22px; font-weight: 700; fill: var(--text); }
.d-cap { font-size: 9px; fill: var(--muted); text-transform: uppercase; letter-spacing: .06em; }
.donut-legend { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: .7rem; }
.lg-row { display: grid; grid-template-columns: 1fr auto; gap: .2rem .75rem; color: var(--text); text-decoration: none; font-size: .86rem; }
a.lg-row:hover { text-decoration: none; }
a.lg-row:hover .lg-label { color: var(--accent); }
.lg-val { font-weight: 650; }
.lg-bar { grid-column: 1 / -1; height: 6px; border-radius: 6px; background: var(--surface-2); overflow: hidden; }
.lg-bar span { display: block; height: 100%; border-radius: 6px; transition: width .4s ease; }
@media (max-width: 480px) { .donut-wrap { grid-template-columns: 1fr; justify-items: center; } .donut-legend { width: 100%; } }
</style>
