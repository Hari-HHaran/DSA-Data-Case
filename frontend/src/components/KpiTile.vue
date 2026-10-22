<template>
  <div class="kpi card-x" :class="{ link: !!to }" @click="to && $router.push(to)" :role="to ? 'link' : undefined" :tabindex="to ? 0 : undefined"
       @keydown.enter="to && $router.push(to)">
    <div class="kpi-top">
      <span class="small-label">{{ label }}</span>
      <span v-if="icon" class="kpi-ic" :class="`tone-${tone}`"><component :is="icon" :size="15" aria-hidden="true" /></span>
    </div>
    <div class="kpi-value num"><template v-if="loading"><span class="skeleton d-inline-block" style="width:80px;height:26px" /></template><template v-else>{{ value }}</template>
      <span v-if="unit && !loading" class="kpi-unit">{{ unit }}</span></div>
    <div v-if="delta !== undefined && delta !== null" class="kpi-delta" :class="delta >= 0 ? 'up' : 'down'">
      <component :is="delta >= 0 ? TrendingUp : TrendingDown" :size="13" aria-hidden="true" /> {{ deltaText }}
    </div>
    <div v-if="hint" class="kpi-hint" :title="hint">{{ hint }}</div>
  </div>
</template>
<script setup>
import { TrendingDown, TrendingUp } from 'lucide-vue-next'
defineProps({ label: String, value: [String, Number], unit: String, hint: String, delta: Number, deltaText: String, icon: Object,
  tone: { type: String, default: 'info' }, to: [String, Object], loading: Boolean })
</script>
<style scoped>
.kpi { padding: .95rem 1.05rem; display: flex; flex-direction: column; gap: .3rem; min-height: 112px; }
.kpi.link { cursor: pointer; transition: border-color .15s, box-shadow .15s; }
.kpi.link:hover { border-color: var(--border-strong); box-shadow: var(--shadow-2); }
.kpi-top { display: flex; justify-content: space-between; align-items: center; }
.kpi-ic { width: 26px; height: 26px; border-radius: 7px; display: inline-flex; align-items: center; justify-content: center; }
.kpi-value { font-size: 1.6rem; font-weight: 700; letter-spacing: -0.02em; color: var(--text); line-height: 1.15; }
.kpi-unit { font-size: .8rem; font-weight: 500; color: var(--muted); margin-left: .3rem; letter-spacing: 0; }
.kpi-delta { font-size: .78rem; font-weight: 600; display: flex; align-items: center; gap: .25rem; }
.kpi-delta.up { color: var(--success); }
.kpi-delta.down { color: var(--error); }
.kpi-hint { font-size: .74rem; color: var(--muted); line-height: 1.3; }
</style>
