<template>
  <div class="page">
    <PageHeader title="Form configuration" eyebrow="Administration" subtitle="Fields, required rules and conditional logic for each record type. Changes apply to the request form immediately — no code change, no IT ticket.">
      <template #badge><span v-if="!isAdmin" class="pill tone-neutral"><Eye :size="11" /> Read-only for your role</span></template>
      <button v-if="isAdmin" class="btn btn-primary" type="button" :disabled="!dirty || saving" @click="save"><Save :size="15" /> Save as v{{ (form?.version || 0) + 1 }}</button>
    </PageHeader>
    <ul class="nav nav-tabs mb-3">
      <li v-for="f in forms" :key="f.id" class="nav-item"><button class="nav-link" :class="{ active: form?.id === f.id }" @click="select(f)">{{ f.name }} <span class="small text-muted-2">v{{ f.version }}</span></button></li>
    </ul>
    <ErrorState v-if="error" :error="error" title="Configuration not saved" class="mb-3" />
    <LoadingBlock v-if="!form" :rows="8" />
    <template v-else>
      <section class="card-x mb-3">
        <div class="table-responsive"><table class="table">
          <thead><tr><th style="width:28%">Field</th><th>Type</th><th>Section</th><th>Required</th><th>Conditional</th><th>Sensitivity</th><th>Active</th><th></th></tr></thead>
          <tbody><tr v-for="(f, i) in fields" :key="f.id || f.key" :class="{ off: !f.is_active }">
            <td><input v-model="f.label" class="form-control form-control-sm" :disabled="!isAdmin" aria-label="Label" @input="dirty = true" />
              <div class="mono small text-muted-2 mt-1">{{ f.key }}<span v-if="f.is_identifier" class="pill tone-neutral ms-1">ID</span></div></td>
            <td class="small">{{ f.field_type }}</td>
            <td><input v-model="f.section" class="form-control form-control-sm" :disabled="!isAdmin" aria-label="Section" @input="dirty = true" /></td>
            <td><div class="form-check form-switch"><input v-model="f.required" class="form-check-input" type="checkbox" :disabled="!isAdmin" :aria-label="`${f.label} required`" @change="dirty = true" /></div></td>
            <td class="small">{{ describe(f) }} <button v-if="isAdmin" class="link-btn small" @click="editing = f">edit</button></td>
            <td><select v-model="f.sensitivity" class="form-select form-select-sm" :disabled="!isAdmin" aria-label="Sensitivity" @change="dirty = true"><option value="NONE">Normal</option><option value="FINANCIAL">Restricted (financial)</option></select></td>
            <td><div class="form-check form-switch"><input v-model="f.is_active" class="form-check-input" type="checkbox" :disabled="!isAdmin || f.is_identifier" :aria-label="`${f.label} active`" @change="dirty = true" /></div></td>
            <td><button v-if="isAdmin" class="btn btn-ghost btn-sm" :disabled="i === 0" aria-label="Move up" @click="move(i, -1)"><ArrowUp :size="13" /></button></td>
          </tr></tbody></table></div>
      </section>
      <section v-if="isAdmin" class="card-x mb-3">
        <div class="card-x-head"><h2>Add a field</h2><span class="small text-muted-2">e.g. a field a new business unit or regulation requires</span></div>
        <div class="card-x-body d-flex flex-wrap gap-2 align-items-end">
          <div><label class="form-label">Label</label><input v-model="nf.label" class="form-control form-control-sm" placeholder="e.g. Import permit number" /></div>
          <div><label class="form-label">Type</label><select v-model="nf.field_type" class="form-select form-select-sm"><option v-for="t in ['text', 'textarea', 'number', 'date', 'email', 'phone', 'select']" :key="t">{{ t }}</option></select></div>
          <div v-if="nf.field_type === 'select'"><label class="form-label">Options (comma-separated)</label><input v-model="nf.options" class="form-control form-control-sm" /></div>
          <div><label class="form-label">Section</label><input v-model="nf.section" class="form-control form-control-sm" /></div>
          <div class="form-check mb-1"><input id="nfr" v-model="nf.required" type="checkbox" class="form-check-input" /><label for="nfr" class="form-check-label small">Required</label></div>
          <button class="btn btn-light btn-sm" type="button" :disabled="!nf.label" @click="addField"><Plus :size="13" /> Add</button>
        </div>
      </section>
      <section class="card-x">
        <div class="card-x-head"><h2>Document & validation rules</h2></div>
        <div class="table-responsive"><table class="table"><thead><tr><th>Rule</th><th>Type</th><th>Applies</th></tr></thead>
          <tbody><tr v-for="r in rules.filter((x) => x.domain === form.domain)" :key="r.id"><td>{{ r.message }}</td><td class="small">{{ r.rule_type.replace('_', ' ').toLowerCase() }}</td><td class="small">{{ r.condition_text }}</td></tr></tbody></table></div>
      </section>
    </template>
    <ModalDialog :open="!!editing" :title="`Conditions · ${editing?.label}`" width="720px" @close="editing = null">
      <template v-if="editing">
        <div class="small-label mb-1">Show this field…</div>
        <ConditionEditor v-model="editing.visible_when" :fields="condFields" @update:model-value="dirty = true" />
        <div class="small-label mt-3 mb-1">Make it required… (in addition to the Required switch)</div>
        <ConditionEditor v-model="editing.required_when" :fields="condFields" @update:model-value="dirty = true" />
      </template>
      <template #footer><button class="btn btn-primary" type="button" @click="editing = null">Done</button></template>
    </ModalDialog>
  </div>
</template>
<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ArrowUp, Eye, Plus, Save } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import LoadingBlock from '@/components/LoadingBlock.vue'
import ErrorState from '@/components/ErrorState.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import ConditionEditor from '@/components/ConditionEditor.vue'
import { get, put } from '@/api/client'
import { useAuth } from '@/stores/auth'
import { useToast } from '@/stores/toast'

const auth = useAuth()
const toast = useToast()
const isAdmin = computed(() => auth.has('ADMIN'))
const forms = ref([])
const rules = ref([])
const form = ref(null)
const fields = ref([])
const dirty = ref(false)
const saving = ref(false)
const error = ref(null)
const editing = ref(null)
const nf = reactive({ label: '', field_type: 'text', section: 'Details', required: false, options: '' })
const HEADER = [{ key: 'country_code', label: 'Country', options: ['SG', 'MY', 'ID', 'TH', 'VN'] }, { key: 'entity_code', label: 'Business entity', options: ['SPD', 'QTS', 'QTG'] }]
const condFields = computed(() => [...HEADER, ...fields.value.map((f) => ({ key: f.key, label: f.label, options: f.options }))])
function describe(f) {
  const parts = []
  if (f.visible_when) parts.push('visible conditionally')
  if (f.required_when) parts.push('required conditionally')
  return parts.join(', ') || '—'
}
function select(f) { form.value = f; fields.value = JSON.parse(JSON.stringify(f.fields)); dirty.value = false; error.value = null }
function move(i, d) { const a = fields.value; [a[i], a[i + d]] = [a[i + d], a[i]]; dirty.value = true }
function addField() {
  const key = nf.label.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 50) || 'field'
  fields.value.push({ key: /^[a-z]/.test(key) ? key : `f_${key}`, label: nf.label, field_type: nf.field_type, section: nf.section, required: nf.required, required_when: null, visible_when: null,
    options: nf.field_type === 'select' ? nf.options.split(',').map((x) => x.trim()).filter(Boolean) : null, pattern: null, pattern_message: null, help_text: '', sensitivity: 'NONE', is_identifier: false, is_active: true })
  Object.assign(nf, { label: '', options: '', required: false })
  dirty.value = true
}
async function save() {
  saving.value = true; error.value = null
  try {
    const r = await put(`/api/config/forms/${form.value.id}`, { fields: fields.value })
    const i = forms.value.findIndex((f) => f.id === r.id); forms.value[i] = r; select(r)
    toast.push(`${r.name} form saved as v${r.version}. New and draft requests use it immediately.`)
  } catch (e) { error.value = e } finally { saving.value = false }
}
onMounted(async () => {
  const [f, r] = await Promise.all([get('/api/config/forms'), get('/api/config/validation-rules')])
  forms.value = f; rules.value = r; select(f[0])
})
</script>
<style scoped>
tr.off td { opacity: .55; }
</style>
