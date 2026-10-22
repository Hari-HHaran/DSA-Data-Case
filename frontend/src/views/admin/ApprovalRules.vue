<template>
  <div class="page">
    <PageHeader title="Approval rules" eyebrow="Administration" subtitle="Who approves what, in which order, under which conditions, within what SLA. Same stage = parallel; stages run in order. Validated before saving — cycles are impossible by design.">
      <template #badge><span v-if="!isAdmin" class="pill tone-neutral"><Eye :size="11" /> Read-only for your role</span></template>
      <button v-if="isAdmin" class="btn btn-primary" type="button" :disabled="!dirty || saving" @click="save"><Save :size="15" /> Save as v{{ (wf?.version || 0) + 1 }}</button>
    </PageHeader>
    <ul class="nav nav-tabs mb-3">
      <li v-for="w in workflows" :key="w.id" class="nav-item"><button class="nav-link" :class="{ active: wf?.id === w.id }" @click="select(w)">{{ w.name }} <span class="small text-muted-2">v{{ w.version }}</span></button></li>
    </ul>
    <ErrorState v-if="error" :error="error" title="Workflow not saved" class="mb-3" />
    <LoadingBlock v-if="!wf" :rows="6" />
    <template v-else>
      <section class="card-x mb-3">
        <div class="card-x-head"><h2>Flow preview</h2><span class="small text-muted-2">Submit → validation → stages → MDM verification → SAP B1</span></div>
        <div class="card-x-body flow">
          <div class="node fixed">Submit &amp; auto-validate</div><ChevronRight :size="16" class="arr" />
          <template v-for="st in stages" :key="st.n">
            <div class="stage"><div class="small-label mb-1">Stage {{ st.n }}{{ st.items.length > 1 ? ' · parallel' : '' }}</div>
              <div v-for="s in st.items" :key="s.step_key" class="node" :class="{ cond: s.condition }"><strong>{{ s.name }}</strong><small>{{ ROLE_LABELS[s.role_code] }} · {{ s.sla_days }}d SLA</small>
                <small v-if="s.condition" class="c">{{ describe(s.condition) }}</small></div></div>
            <ChevronRight :size="16" class="arr" />
          </template>
          <div class="node fixed">MDM verification ({{ wf.mdm_verification_sla_days }}d)</div><ChevronRight :size="16" class="arr" /><div class="node fixed sap">SAP B1</div>
        </div>
      </section>
      <section class="card-x mb-3">
        <div class="card-x-head"><h2>Steps</h2><button v-if="isAdmin" class="btn btn-light btn-sm" type="button" @click="addStep"><Plus :size="13" /> Add approval step</button></div>
        <div class="card-x-body d-flex flex-column gap-3">
          <div v-for="(s, i) in steps" :key="s.id || i" class="step card-x" :class="{ off: !s.is_active }">
            <div class="d-flex flex-wrap gap-2 align-items-end">
              <div class="flex-grow-1"><label class="form-label">Step name</label><input v-model="s.name" class="form-control form-control-sm" :disabled="!isAdmin" @input="dirty = true" /></div>
              <div><label class="form-label">Approver role</label><select v-model="s.role_code" class="form-select form-select-sm" :disabled="!isAdmin" @change="dirty = true">
                <option v-for="r in approverRoles" :key="r.code" :value="r.code">{{ r.name }}</option></select></div>
              <div style="width:90px"><label class="form-label">Stage</label><input v-model.number="s.stage_order" type="number" min="1" max="20" class="form-control form-control-sm" :disabled="!isAdmin" @input="dirty = true" /></div>
              <div style="width:110px"><label class="form-label">SLA (working days)</label><input v-model.number="s.sla_days" type="number" min="1" max="30" class="form-control form-control-sm" :disabled="!isAdmin" @input="dirty = true" /></div>
              <div class="form-check form-switch mb-1"><input :id="`act${i}`" v-model="s.is_active" class="form-check-input" type="checkbox" :disabled="!isAdmin" @change="dirty = true" /><label :for="`act${i}`" class="form-check-label small">Active</label></div>
            </div>
            <div class="mt-2"><div class="small-label mb-1">Applies</div>
              <ConditionEditor v-if="isAdmin" v-model="s.condition" :fields="condFields" @update:model-value="dirty = true" />
              <div v-else class="small">{{ describe(s.condition) }}</div></div>
          </div>
        </div>
      </section>
      <div class="callout info"><Info :size="16" /><div>Demo idea: add a <strong>Cold-chain regulatory review</strong> (Quality/Regulatory, stage 3) that applies when <em>Storage condition is Frozen (−20°C)</em>. The new-request form immediately shows the extra approver and why — without any code change. In-flight requests keep their original routing.</div></div>
    </template>
  </div>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { ChevronRight, Eye, Info, Plus, Save } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import LoadingBlock from '@/components/LoadingBlock.vue'
import ErrorState from '@/components/ErrorState.vue'
import ConditionEditor from '@/components/ConditionEditor.vue'
import { get, put } from '@/api/client'
import { useAuth } from '@/stores/auth'
import { useToast } from '@/stores/toast'
import { ROLE_LABELS } from '@/utils/format'

const auth = useAuth()
const toast = useToast()
const isAdmin = computed(() => auth.has('ADMIN'))
const workflows = ref([])
const forms = ref([])
const roles = ref([])
const wf = ref(null)
const steps = ref([])
const dirty = ref(false)
const saving = ref(false)
const error = ref(null)
const approverRoles = computed(() => roles.value.filter((r) => r.is_approver))
const condFields = computed(() => {
  const f = forms.value.find((x) => x.domain === wf.value?.domain)
  return [{ key: 'country_code', label: 'Country', options: ['SG', 'MY', 'ID', 'TH', 'VN'] }, { key: 'entity_code', label: 'Business entity', options: ['SPD', 'QTS', 'QTG'] },
    ...(f?.fields || []).filter((x) => x.is_active).map((x) => ({ key: x.key, label: x.label, options: x.options }))]
})
const labelOf = (k) => condFields.value.find((f) => f.key === k)?.label || k
function describe(c) {
  if (!c) return 'Always'
  const words = { eq: 'is', neq: 'is not', in: 'is one of', not_in: 'is not one of', exists: 'is provided', not_exists: 'is empty', gt: '>', lt: '<' }
  return 'When ' + (c.all || c.any || []).map((x) => `${labelOf(x.field)} ${words[x.op]} ${Array.isArray(x.value) ? x.value.join(', ') : x.value ?? ''}`.trim()).join(' and ')
}
const stages = computed(() => {
  const g = {}
  for (const s of steps.value.filter((x) => x.is_active)) (g[s.stage_order] ||= []).push(s)
  return Object.keys(g).map(Number).sort((a, b) => a - b).map((n, i) => ({ n: i + 1, items: g[n] }))
})
function select(w) { wf.value = w; steps.value = JSON.parse(JSON.stringify(w.steps)); dirty.value = false; error.value = null }
function addStep() {
  const max = Math.max(1, ...steps.value.map((s) => s.stage_order))
  steps.value.push({ step_key: `step_${Date.now().toString(36)}`, name: 'New approval step', role_code: 'QRA', stage_order: max + 1, condition: null, description: '', sla_days: 2, is_active: true })
  dirty.value = true
}
async function save() {
  saving.value = true; error.value = null
  try {
    const r = await put(`/api/config/workflows/${wf.value.id}`, { steps: steps.value.map(({ condition_text, ...s }) => s) })
    const i = workflows.value.findIndex((w) => w.id === r.id); workflows.value[i] = r; select(r)
    toast.push(`${r.name} saved as v${r.version}. Applies to new submissions.`)
  } catch (e) { error.value = e } finally { saving.value = false }
}
onMounted(async () => {
  const [w, f, r] = await Promise.all([get('/api/config/workflows'), get('/api/config/forms'), get('/api/roles')])
  workflows.value = w; forms.value = f; roles.value = r; select(w[0])
})
</script>
<style scoped>
.flow { display: flex; align-items: center; gap: .5rem; overflow-x: auto; padding-bottom: 1rem; }
.arr { color: var(--muted); flex: none; }
.stage { display: flex; flex-direction: column; gap: .4rem; }
.node { border: 1px solid var(--border-strong); border-radius: 8px; padding: .5rem .7rem; background: var(--surface); min-width: 180px; font-size: .82rem; }
.node small { display: block; color: var(--muted); font-size: .72rem; }
.node .c { color: #1d4ed8; }
.node.cond { border-style: dashed; }
.node.fixed { background: var(--surface-2); min-width: 120px; font-weight: 600; white-space: nowrap; }
.node.sap { background: var(--navy); color: #fff; }
.step { padding: .85rem 1rem; box-shadow: none; }
.step.off { opacity: .6; }
</style>
