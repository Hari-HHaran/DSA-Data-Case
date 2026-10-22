<template>
  <div class="card-x filters mb-3" role="group" aria-label="Dashboard filters">
    <div class="fgroup"><span class="small-label">Country</span>
      <div class="filters-row"><button v-for="c in countries" :key="c.code" type="button" class="chip" :class="{ on: sel(model.countries, c.code) }" :aria-pressed="sel(model.countries, c.code)"
              @click="toggle('countries', c.code)"><span class="legend-dot" :style="{ background: countryColor(c.code) }" />{{ c.name }}</button></div></div>
    <div class="fgroup"><span class="small-label">Product</span>
      <div class="filters-row"><button v-for="f in ['A', 'B', 'C']" :key="f" type="button" class="chip" :class="{ on: sel(model.families, f) }" :aria-pressed="sel(model.families, f)"
              @click="toggle('families', f)"><span class="legend-dot" :style="{ background: FAMILY_COLORS[f] }" />Product {{ f }}</button></div></div>
    <div class="fgroup"><label class="small-label" for="gf-ent">Entity</label>
      <select id="gf-ent" class="form-select form-select-sm" :value="model.entities[0] || ''" @change="set('entities', $event.target.value ? [$event.target.value] : [])">
        <option value="">All entities</option><option v-for="e in ['SPD', 'QTS', 'QTG']" :key="e" :value="e">{{ e }}</option></select></div>
    <div class="fgroup"><span class="small-label">Period</span>
      <div class="d-flex gap-1 align-items-center">
        <select class="form-select form-select-sm" aria-label="From month" :value="model.start" @change="set('start', $event.target.value)"><option v-for="m in months" :key="m" :value="m">{{ monthLabel(m) }}</option></select>
        <span class="text-muted-2">–</span>
        <select class="form-select form-select-sm" aria-label="To month" :value="model.end" @change="set('end', $event.target.value)"><option v-for="m in months" :key="m" :value="m">{{ monthLabel(m) }}</option></select>
      </div></div>
    <div class="fgroup"><label class="small-label" for="gf-cust">Customer</label>
      <select id="gf-cust" class="form-select form-select-sm" :value="model.customer" @change="set('customer', $event.target.value)">
        <option value="">All customers</option><option v-for="c in customers" :key="c.key" :value="c.key">{{ c.name }} ({{ c.country }})</option></select></div>
    <div class="fgroup"><label class="small-label" for="gf-st">Order status</label>
      <select id="gf-st" class="form-select form-select-sm" :value="model.status" @change="set('status', $event.target.value)">
        <option value="">Confirmed + fulfilled</option><option value="CONFIRMED">Confirmed (open)</option><option value="FULFILLED">Fulfilled</option></select></div>
    <button class="btn btn-ghost btn-sm align-self-end" type="button" :disabled="!active" @click="$emit('reset')"><RotateCcw :size="13" /> Reset</button>
  </div>
</template>
<script setup>
import { computed } from 'vue'
import { RotateCcw } from 'lucide-vue-next'
import { FAMILY_COLORS, countryColor } from '@/utils/charts'
import { monthLabel } from '@/utils/format'
const props = defineProps({ model: Object, countries: Array, months: Array, customers: Array })
const emit = defineEmits(['change', 'reset'])
const sel = (arr, v) => arr.includes(v)
const active = computed(() => props.model.countries.length || props.model.families.length || props.model.entities.length || props.model.customer || props.model.status
  || props.model.start !== props.months[0] || props.model.end !== props.months.at(-1))
function toggle(key, v) {
  const arr = props.model[key].includes(v) ? props.model[key].filter((x) => x !== v) : [...props.model[key], v]
  emit('change', { ...props.model, [key]: arr })
}
function set(key, v) { emit('change', { ...props.model, [key]: v }) }
</script>
<style scoped>
.filters { display: flex; flex-wrap: wrap; gap: .8rem 1.4rem; padding: .85rem 1rem; align-items: flex-start; }
.fgroup { display: flex; flex-direction: column; gap: .3rem; }
.fgroup select { min-width: 140px; }
</style>
