<template>
  <section class="card-x chart-card">
    <div class="card-x-head">
      <div>
        <h2>{{ title }}</h2>
        <p v-if="subtitle" class="sub">{{ subtitle }}</p>
      </div>
      <div class="d-flex gap-1 align-items-center">
        <slot name="actions" />
        <button v-if="$slots.table" class="btn btn-ghost btn-sm" type="button" :aria-pressed="showTable" @click="showTable = !showTable">
          <component :is="showTable ? BarChart3 : Table2" :size="14" /> {{ showTable ? 'Show chart' : 'Show as table' }}
        </button>
      </div>
    </div>
    <div class="card-x-body">
      <div v-if="showTable" class="table-responsive" style="max-height: 360px"><slot name="table" /></div>
      <slot v-else />
      <p v-if="note" class="chart-note"><Info :size="12" aria-hidden="true" /> {{ note }}</p>
    </div>
  </section>
</template>
<script setup>
import { ref } from 'vue'
import { BarChart3, Info, Table2 } from 'lucide-vue-next'
defineProps({ title: String, subtitle: String, note: String })
const showTable = ref(false)
</script>
<style scoped>
.chart-note { font-size: .74rem; color: var(--muted); margin: .6rem 0 0; display: flex; gap: .35rem; align-items: flex-start; }
.chart-note svg { margin-top: 2px; flex: none; }
</style>
