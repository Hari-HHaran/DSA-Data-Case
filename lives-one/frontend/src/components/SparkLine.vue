<template>
  <svg class="spark" :viewBox="`0 0 ${w} ${h}`" preserveAspectRatio="none" role="img" :aria-label="label">
    <defs>
      <linearGradient :id="gid" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" :stop-color="color" stop-opacity=".22" /><stop offset="100%" :stop-color="color" stop-opacity="0" />
      </linearGradient>
    </defs>
    <path v-if="path" :d="area" :fill="`url(#${gid})`" />
    <path v-if="path" :d="path" fill="none" :stroke="color" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke" />
  </svg>
</template>
<script setup>
import { computed } from 'vue'
const props = defineProps({ values: { type: Array, default: () => [] }, color: { type: String, default: '#6366f1' }, label: String })
const w = 120
const h = 36
const gid = `sp-${Math.random().toString(36).slice(2, 8)}`
const pts = computed(() => {
  const v = props.values.filter((x) => x != null)
  if (v.length < 2) return []
  const min = Math.min(...v)
  const max = Math.max(...v)
  const span = max - min || 1
  return v.map((x, i) => [(i / (v.length - 1)) * w, h - 3 - ((x - min) / span) * (h - 6)])
})
// Smooth curve through the points (Catmull-Rom → Bézier)
const path = computed(() => {
  const p = pts.value
  if (!p.length) return ''
  let d = `M${p[0][0]},${p[0][1]}`
  for (let i = 0; i < p.length - 1; i++) {
    const p0 = p[i - 1] || p[i]
    const p1 = p[i]
    const p2 = p[i + 1]
    const p3 = p[i + 2] || p2
    d += ` C${p1[0] + (p2[0] - p0[0]) / 6},${p1[1] + (p2[1] - p0[1]) / 6} ${p2[0] - (p3[0] - p1[0]) / 6},${p2[1] - (p3[1] - p1[1]) / 6} ${p2[0]},${p2[1]}`
  }
  return d
})
const area = computed(() => (path.value ? `${path.value} L${w},${h} L0,${h} Z` : ''))
</script>
<style scoped>
.spark { width: 100%; height: 40px; display: block; }
</style>
