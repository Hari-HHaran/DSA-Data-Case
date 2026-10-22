<template>
  <div class="cond">
    <div v-if="!clauses.length" class="small text-muted-2 mb-1">Always applies.</div>
    <div v-for="(c, i) in clauses" :key="i" class="clause">
      <span class="small text-muted-2">{{ i === 0 ? 'When' : 'and' }}</span>
      <select v-model="c.field" class="form-select form-select-sm" aria-label="Field" @change="emitIt"><option v-for="f in fields" :key="f.key" :value="f.key">{{ f.label }}</option></select>
      <select v-model="c.op" class="form-select form-select-sm" aria-label="Operator" @change="emitIt">
        <option v-for="(l, op) in OPS" :key="op" :value="op">{{ l }}</option></select>
      <template v-if="!['exists', 'not_exists'].includes(c.op)">
        <select v-if="opts(c).length && !multi(c)" v-model="c.value" class="form-select form-select-sm" aria-label="Value" @change="emitIt"><option v-for="o in opts(c)" :key="o" :value="o">{{ o }}</option></select>
        <div v-else-if="opts(c).length" class="d-flex flex-wrap gap-1">
          <label v-for="o in opts(c)" :key="o" class="chip" :class="{ on: (c.value || []).includes(o) }"><input type="checkbox" class="visually-hidden" :checked="(c.value || []).includes(o)" @change="toggleVal(c, o)" />{{ o }}</label></div>
        <input v-else :value="multi(c) ? (c.value || []).join(', ') : c.value" class="form-control form-control-sm" aria-label="Value" placeholder="value"
               @change="setText(c, $event.target.value)" />
      </template>
      <button type="button" class="btn btn-ghost btn-sm" aria-label="Remove condition" @click="clauses.splice(i, 1); emitIt()"><X :size="14" /></button>
    </div>
    <button type="button" class="btn btn-ghost btn-sm" @click="add"><Plus :size="13" /> Add condition</button>
  </div>
</template>
<script setup>
import { ref, watch } from 'vue'
import { Plus, X } from 'lucide-vue-next'
const props = defineProps({ modelValue: Object, fields: Array })
const emit = defineEmits(['update:modelValue'])
const OPS = { eq: 'is', neq: 'is not', in: 'is one of', not_in: 'is not one of', exists: 'is provided', not_exists: 'is empty', gt: '>', lt: '<' }
const clauses = ref([])
watch(() => props.modelValue, (v) => { clauses.value = JSON.parse(JSON.stringify(v?.all || v?.any || [])) }, { immediate: true })
const multi = (c) => ['in', 'not_in'].includes(c.op)
const opts = (c) => props.fields.find((f) => f.key === c.field)?.options || []
function toggleVal(c, o) { const v = new Set(c.value || []); v.has(o) ? v.delete(o) : v.add(o); c.value = [...v]; emitIt() }
function setText(c, t) { c.value = multi(c) ? t.split(',').map((x) => x.trim()).filter(Boolean) : t; emitIt() }
function add() { clauses.value.push({ field: props.fields[0]?.key, op: 'eq', value: '' }); emitIt() }
function emitIt() {
  for (const c of clauses.value) { if (multi(c) && !Array.isArray(c.value)) c.value = c.value ? [c.value] : []; if (!multi(c) && Array.isArray(c.value)) c.value = c.value[0] || '' }
  emit('update:modelValue', clauses.value.length ? { all: clauses.value.map((c) => (['exists', 'not_exists'].includes(c.op) ? { field: c.field, op: c.op } : { ...c })) } : null)
}
</script>
<style scoped>
.clause { display: flex; gap: .4rem; align-items: center; flex-wrap: wrap; margin-bottom: .4rem; }
.clause select, .clause input { width: auto; min-width: 120px; }
</style>
