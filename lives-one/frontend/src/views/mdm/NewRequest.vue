<template>
  <div class="page">
    <PageHeader :title="editing ? `Edit ${request?.request_number}` : 'New request'" eyebrow="Requests"
                subtitle="Answer a few short questions. The form only asks for what your request needs and tells you if anything is missing.">
      <span v-if="request" class="save-state small text-muted-2"><component :is="saving ? Loader2 : CheckCheck" :size="14" :class="{ spin: saving }" />
        {{ saving ? 'Saving…' : `Draft saved · ${request.request_number}` }}</span>
      <button v-if="request && editable" class="btn btn-ghost btn-sm" type="button" @click="cancelDraft"><Trash2 :size="14" /> Cancel draft</button>
    </PageHeader>

    <ol class="stepper" aria-label="Progress">
      <li v-for="(s, i) in steps" :key="s" :class="{ done: step > i + 1, current: step === i + 1 }" :aria-current="step === i + 1 ? 'step' : undefined">
        <button type="button" :disabled="!canJump(i + 1)" @click="goStep(i + 1)"><span class="n">{{ step > i + 1 ? '✓' : i + 1 }}</span>{{ s }}</button>
      </li>
    </ol>

    <div v-if="request?.status === 'NEEDS_CHANGES'" class="callout warn mb-3"><Undo2 :size="18" />
      <div><strong>Sent back for changes.</strong> {{ lastReturnComment }} Please update the request and submit it again. The approvers will review it again.</div></div>
    <ErrorState v-if="loadError" :error="loadError" :retry="init" class="mb-3" />

    <!-- Step 1: category -->
    <section v-if="step === 1" class="grid grid-2">
      <button v-for="d in domains" :key="d.code" type="button" class="domain card-x" :class="{ sel: domain === d.code }" @click="chooseDomain(d.code)">
        <span class="dic"><component :is="d.icon" :size="22" /></span>
        <span><strong>{{ d.label }}</strong><small>{{ d.desc }}</small></span>
        <ArrowRight :size="18" class="ms-auto" />
      </button>
    </section>

    <!-- Step 2: context -->
    <section v-if="step === 2" class="card-x">
      <div class="card-x-head"><h2>{{ domainLabel }} · company &amp; country</h2><span class="small text-muted-2">This decides who approves it and which country rules apply</span></div>
      <div class="card-x-body">
        <div class="form-grid">
          <div><label class="form-label" for="ent">Company <span class="req">*</span></label>
            <select id="ent" v-model="header.entity_code" class="form-select"><option value="">Select…</option>
              <option v-for="e in ref_.entities" :key="e.code" :value="e.code">{{ e.code }}</option></select></div>
          <div><label class="form-label" for="cty">Country <span class="req">*</span></label>
            <select id="cty" v-model="header.country_code" class="form-select"><option value="">Select…</option>
              <option v-for="c in ref_.countries" :key="c.code" :value="c.code">{{ c.name }}</option></select></div>
          <div><label class="form-label" for="rt">Request type</label>
            <select id="rt" v-model="header.request_type" class="form-select"><option value="CREATE">Create new record</option></select>
            <div class="form-text">Changing an existing record is not available yet.</div></div>
          <div><label class="form-label" for="dep">Department</label>
            <input id="dep" v-model="header.department" class="form-control" placeholder="e.g. Product Management" /></div>
        </div>
        <div class="d-flex justify-content-between mt-4">
          <button class="btn btn-light" type="button" @click="step = 1"><ArrowLeft :size="15" /> Back</button>
          <button class="btn btn-primary" type="button" :disabled="!header.entity_code || !header.country_code || busy" @click="startDraft">
            Continue <ArrowRight :size="15" /></button>
        </div>
      </div>
    </section>

    <!-- Steps 3–5 with readiness panel -->
    <div v-if="step >= 3 && form" class="grid grid-main-side">
      <div class="d-flex flex-column gap-3 min-w-0">
        <template v-if="step === 3">
          <section v-for="sec in sections" :key="sec.name" class="card-x">
            <div class="card-x-head"><h2>{{ sec.name }}</h2></div>
            <div class="card-x-body form-grid">
              <DynamicField v-for="f in sec.fields" :key="f.key" :field="f" :model-value="data[f.key]" :required="isRequired(f)"
                            :error="fieldErrors[f.key]" :touched="touched.has(f.key) || showAll" :disabled="!editable"
                            @update:model-value="(v) => setField(f.key, v)" @touch="touched.add(f.key)" />
            </div>
          </section>
          <section class="card-x" id="docs">
            <div class="card-x-head"><h2>Supporting documents</h2><span class="small text-muted-2">PDF, image, Word or Excel, up to 5 MB each</span></div>
            <div class="card-x-body">
              <div v-if="!requiredDocs.length" class="small text-muted-2 mb-2">No documents are required for the details entered so far.</div>
              <div v-for="d in requiredDocs" :key="d.category" class="doc-row" :class="{ missing: !d.provided && showAll }">
                <component :is="d.provided ? CheckCircle2 : FileWarning" :size="18" :class="d.provided ? 'text-success' : 'text-warning'" />
                <div class="flex-grow-1"><strong>{{ d.label }}</strong> <span class="req">*</span><div class="small text-muted-2">{{ d.message }}</div></div>
                <label v-if="editable" class="btn btn-light btn-sm mb-0"><Upload :size="14" /> {{ d.provided ? 'Add another' : 'Upload' }}
                  <input type="file" class="visually-hidden" accept=".pdf,.png,.jpg,.jpeg,.docx,.xlsx,.txt" @change="upload($event, d.category)" /></label>
              </div>
              <div v-if="attachments.length" class="mt-2">
                <div class="small-label mb-1">Uploaded</div>
                <div v-for="a in attachments" :key="a.id" class="att"><Paperclip :size="14" /> <span class="truncate">{{ a.filename }}</span>
                  <span class="pill tone-neutral">{{ a.category.replace(/_/g, ' ').toLowerCase() }}</span>
                  <button v-if="editable" class="btn btn-ghost btn-sm ms-auto" type="button" :aria-label="`Remove ${a.filename}`" @click="removeAtt(a)"><X :size="14" /></button></div>
              </div>
              <label v-if="editable" class="btn btn-ghost btn-sm mt-2 mb-0"><Plus :size="14" /> Other supporting document
                <input type="file" class="visually-hidden" accept=".pdf,.png,.jpg,.jpeg,.docx,.xlsx,.txt" @change="upload($event, 'OTHER')" /></label>
            </div>
          </section>
          <div class="d-flex justify-content-between">
            <button class="btn btn-light" type="button" :disabled="editing" @click="step = 2"><ArrowLeft :size="15" /> Back</button>
            <button class="btn btn-primary" type="button" @click="toDuplicates">Check for duplicates <ArrowRight :size="15" /></button>
          </div>
        </template>

        <template v-if="step === 4">
          <section class="card-x">
            <div class="card-x-head"><div><h2>Duplicate check</h2><p class="sub">We compare your request with records that already exist (name, ID number, address and manufacturer). Nothing is merged unless you decide.</p></div>
              <button class="btn btn-light btn-sm" type="button" :disabled="busy" @click="runDup"><RotateCw :size="14" /> Check again</button></div>
            <div class="card-x-body">
              <LoadingBlock v-if="busy && !dupChecked" :rows="3" />
              <DuplicatePanel v-else :status="request.duplicate_check_status" :candidates="candidates" :reviews="request.duplicate_reviews"
                              :editable="editable" @decide="decideDup" @correct="step = 3" />
            </div>
          </section>
          <div class="d-flex justify-content-between">
            <button class="btn btn-light" type="button" @click="step = 3"><ArrowLeft :size="15" /> Back to details</button>
            <button class="btn btn-primary" type="button" :disabled="!['CLEAR', 'RESOLVED'].includes(request.duplicate_check_status)" @click="step = 5">
              Review & submit <ArrowRight :size="15" /></button>
          </div>
        </template>

        <template v-if="step === 5">
          <section class="card-x">
            <div class="card-x-head"><h2>Review {{ request.request_number }}</h2><StatusBadge :status="request.status" /></div>
            <div class="card-x-body">
              <dl class="kv">
                <dt>Type of request</dt><dd>{{ domainLabel }}</dd>
                <dt>Company · Country</dt><dd>{{ request.entity_code }} · {{ ref_.countryName(request.country_code) }}</dd>
                <template v-for="f in visibleFields" :key="f.key"><dt>{{ f.label }}</dt><dd>{{ data[f.key] || '—' }}</dd></template>
                <dt>Documents</dt><dd>{{ attachments.map((a) => a.filename).join(', ') || '—' }}</dd>
                <dt>Duplicate check</dt><dd>{{ dupSummary }}</dd>
              </dl>
              <ErrorState v-if="submitError" :error="submitError" title="Not ready to submit" class="mt-3" />
            </div>
          </section>
          <div class="d-flex justify-content-between">
            <button class="btn btn-light" type="button" @click="step = 4"><ArrowLeft :size="15" /> Back</button>
            <button class="btn btn-primary" type="button" :disabled="busy || !editable" @click="submit"><Send :size="15" /> Submit for approval</button>
          </div>
        </template>
      </div>
      <ReadinessPanel :readiness="readiness" :route="route" @focus="focusField" />
    </div>

    <ModalDialog :open="!!submitted" title="Request submitted" width="520px" @close="$router.push(`/mdm/requests/${submitted.id}`)">
      <div class="text-center py-2">
        <div class="big-ok"><CheckCircle2 :size="34" /></div>
        <h3 class="mt-2 mb-1">{{ submitted?.request_number }}</h3>
        <p class="text-muted-2">Everything checks out. It has gone to {{ submitted?.routeCount }} approval step(s) and the approvers have been told. We'll let you know at every stage.</p>
      </div>
      <template #footer>
        <RouterLink class="btn btn-light" to="/mdm/requests">My requests</RouterLink>
        <RouterLink class="btn btn-primary" :to="`/mdm/requests/${submitted?.id}`">Track request</RouterLink>
      </template>
    </ModalDialog>
    <ModalDialog :open="!!reused" title="No new record needed" width="520px" @close="$router.push('/mdm/requests')">
      <p>You chose to use the existing record <strong>{{ reused }}</strong>, so nothing new needs to be created. We have closed this request for you.</p>
      <template #footer><RouterLink class="btn btn-primary" to="/mdm/requests">Done</RouterLink></template>
    </ModalDialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft, ArrowRight, Building2, CheckCircle2, CheckCheck, FileWarning, Landmark, Loader2, Package, Paperclip, Plus, RotateCw, Send, Trash2,
  Truck, Undo2, Upload, X,
} from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import DynamicField from '@/components/DynamicField.vue'
import ReadinessPanel from '@/components/ReadinessPanel.vue'
import DuplicatePanel from '@/components/DuplicatePanel.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import ErrorState from '@/components/ErrorState.vue'
import LoadingBlock from '@/components/LoadingBlock.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import { api, get, patch, post } from '@/api/client'
import { useReference } from '@/stores/reference'
import { useToast } from '@/stores/toast'
import { useAuth } from '@/stores/auth'
import { evalCondition } from '@/utils/format'

const routeR = useRoute()
const router = useRouter()
const ref_ = useReference()
const toast = useToast()
const auth = useAuth()
const steps = ['What you need', 'Company & country', 'Details & documents', 'Check for duplicates', 'Review & submit']
const domains = [
  { code: 'ITEM', label: 'Item / Material', icon: Package, desc: 'New product or material code (e.g. a lab consumable)' },
  { code: 'CUSTOMER', label: 'Customer', icon: Building2, desc: 'New hospital, laboratory or clinic account' },
  { code: 'VENDOR', label: 'Vendor', icon: Truck, desc: 'New supplier, including bank details for Finance' },
  { code: 'COST_CENTER', label: 'Finance / Cost Center', icon: Landmark, desc: 'New cost centre for finance reporting' },
]
const step = ref(1)
const domain = ref(null)
const header = reactive({ entity_code: auth.user?.entity_code || '', country_code: auth.user?.country_code || '', department: '', request_type: 'CREATE' })
const data = reactive({})
const form = ref(null)
const request = ref(null)
const readiness = ref(null)
const route = ref([])
const candidates = ref([])
const touched = reactive(new Set())
const showAll = ref(false)
const busy = ref(false)
const saving = ref(false)
const dupChecked = ref(false)
const loadError = ref(null)
const submitError = ref(null)
const submitted = ref(null)
const reused = ref(null)
let timer = null

const editing = computed(() => !!routeR.query.edit)
const editable = computed(() => !request.value || ['DRAFT', 'NEEDS_CHANGES'].includes(request.value.status))
const domainLabel = computed(() => domains.find((d) => d.code === domain.value)?.label)
const ctx = computed(() => ({ ...data, ...header, domain: domain.value }))
const visibleFields = computed(() => (form.value?.fields || []).filter((f) => evalCondition(f.visible_when, ctx.value)))
const sections = computed(() => {
  const out = []
  for (const f of visibleFields.value) {
    let s = out.find((x) => x.name === f.section)
    if (!s) out.push((s = { name: f.section, fields: [] }))
    s.fields.push(f)
  }
  return out
})
const fieldErrors = computed(() => readiness.value?.field_errors || {})
const requiredDocs = computed(() => readiness.value?.attachments_required || [])
const attachments = computed(() => request.value?.attachments || [])
const lastReturnComment = computed(() => [...(request.value?.events || [])].reverse().find((e) => e.event_type === 'RETURNED_FOR_CHANGES')?.comment || '')
const dupSummary = computed(() => ({ CLEAR: 'No similar records found', RESOLVED: 'Checked, with your reason noted' }[request.value?.duplicate_check_status] || 'Not finished yet'))
const isRequired = (f) => f.required || (!!f.required_when && evalCondition(f.required_when, ctx.value))
const canJump = (n) => n < step.value || (n <= 2 && domain.value) || (request.value && n <= 4)

function goStep(n) { if (canJump(n)) step.value = n }

async function loadForm(d) {
  form.value = await get(`/api/mdm/forms/${d}`)
}
async function chooseDomain(d) {
  domain.value = d
  Object.keys(data).forEach((k) => delete data[k])
  try { await loadForm(d); step.value = 2 } catch (e) { toast.error(e) }
}
function applyServer(r) {
  request.value = r
  if (r.readiness) readiness.value = r.readiness
  if (r.route_preview) route.value = r.route_preview
  candidates.value = r.duplicate_candidates || candidates.value
}
async function startDraft() {
  busy.value = true
  try {
    if (!request.value) {
      const r = await post('/api/mdm/requests', { domain: domain.value, ...header, data: { ...data } })
      applyServer(r)
      router.replace({ query: { edit: r.id } })
    } else {
      applyServer(await patch(`/api/mdm/requests/${request.value.id}`, { ...header }))
    }
    await validateNow()
    step.value = 3
  } catch (e) { toast.error(e) } finally { busy.value = false }
}
async function validateNow() {
  const r = await post('/api/mdm/validate', { domain: domain.value, ...header, data: { ...data }, request_id: request.value?.id })
  readiness.value = r
  route.value = r.route
}
function setField(k, v) {
  data[k] = v
  clearTimeout(timer)
  timer = setTimeout(save, 550)
}
async function save() {
  if (!request.value || !editable.value) return
  saving.value = true
  try {
    applyServer(await patch(`/api/mdm/requests/${request.value.id}`, { data: { ...data } }))
    await validateNow()
  } catch (e) { toast.error(e) } finally { saving.value = false }
}
async function flush() { if (timer) { clearTimeout(timer); timer = null; await save() } }
async function upload(ev, category) {
  const file = ev.target.files?.[0]
  ev.target.value = ''
  if (!file) return
  const fd = new FormData()
  fd.append('category', category)
  fd.append('file', file)
  try {
    const r = await api.post(`/api/mdm/requests/${request.value.id}/attachments`, fd).then((x) => x.data)
    readiness.value = { ...r.readiness, route: route.value }
    applyServer(await get(`/api/mdm/requests/${request.value.id}`))
    await validateNow()
    toast.push(`Uploaded ${r.filename}`)
  } catch (e) { toast.error(e) }
}
async function removeAtt(a) {
  try {
    await api.delete(`/api/mdm/requests/${request.value.id}/attachments/${a.id}`)
    applyServer(await get(`/api/mdm/requests/${request.value.id}`))
    await validateNow()
  } catch (e) { toast.error(e) }
}
async function focusField(key) {
  showAll.value = true
  if (step.value !== 3) step.value = 3
  await nextTick()
  const el = key.startsWith('attachment:') ? document.getElementById('docs') : document.getElementById(`f-${key}`)
  el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  el?.focus?.()
}
async function toDuplicates() {
  await flush()
  showAll.value = true
  const errs = Object.keys(readiness.value?.errors || {})
  if (errs.length) {
    toast.push(`${errs.length} thing(s) still need filling in. They are highlighted for you.`, 'error')
    focusField(errs[0])
    return
  }
  step.value = 4
  if (request.value.duplicate_check_status === 'NOT_RUN' || !candidates.value.length) await runDup()
}
async function runDup() {
  busy.value = true
  try {
    const r = await post('/api/mdm/duplicate-check', { request_id: request.value.id })
    candidates.value = r.candidates
    applyServer(await get(`/api/mdm/requests/${request.value.id}`))
    dupChecked.value = true
    await validateNow()
  } catch (e) { toast.error(e) } finally { busy.value = false }
}
async function decideDup(body) {
  try {
    const r = await post(`/api/mdm/requests/${request.value.id}/duplicate-review`, body)
    applyServer(r)
    if (body.decision === 'REUSE_EXISTING') { reused.value = r.resolution?.replace('Reused existing record ', ''); return }
    await validateNow()
    toast.push('Your decision has been saved.')
  } catch (e) { toast.error(e) }
}
async function submit() {
  busy.value = true
  submitError.value = null
  try {
    await flush()
    const r = await post(`/api/mdm/requests/${request.value.id}/submit`)
    submitted.value = { id: r.request.id, request_number: r.request.request_number, routeCount: r.route.length }
  } catch (e) {
    submitError.value = { message: e.message, problems: Object.values(e.body?.readiness?.errors || {}) }
    if (e.body?.readiness) readiness.value = { ...e.body.readiness }
  } finally { busy.value = false }
}
async function cancelDraft() {
  if (!confirm('Cancel this draft? You will still see it in your history, marked as cancelled.')) return
  try { await post(`/api/mdm/requests/${request.value.id}/cancel`); toast.push('Draft cancelled'); router.push('/mdm/requests') } catch (e) { toast.error(e) }
}

async function init() {
  loadError.value = null
  try {
    await ref_.load()
    if (routeR.query.domain && !routeR.query.edit) await chooseDomain(routeR.query.domain)
    if (routeR.query.edit) {
      const r = await get(`/api/mdm/requests/${routeR.query.edit}`)
      domain.value = r.domain
      Object.assign(header, { entity_code: r.entity_code, country_code: r.country_code, department: r.department, request_type: r.request_type })
      Object.assign(data, r.data)
      await loadForm(r.domain)
      applyServer(r)
      if (editable.value) await validateNow()
      step.value = 3
    }
  } catch (e) { loadError.value = e }
}
onMounted(init)
onBeforeUnmount(() => { if (timer) { clearTimeout(timer); save() } })
</script>

<style scoped>
.stepper { list-style: none; display: flex; gap: .35rem; padding: 0; margin: 0 0 1.2rem; flex-wrap: wrap; }
.stepper li button { display: flex; align-items: center; gap: .45rem; border: 1px solid var(--border); background: var(--surface); color: var(--muted); border-radius: 999px; padding: .35rem .9rem .35rem .4rem; box-shadow: 0 1px 2px rgba(16, 28, 53, .04); font-size: .8rem; font-weight: 600; }
.stepper li .n { width: 22px; height: 22px; border-radius: 50%; background: var(--surface-2); display: inline-flex; align-items: center; justify-content: center; font-size: .72rem; }
.stepper li.current button { border-color: #c7d2fe; color: var(--accent); background: var(--accent-soft); }
.stepper li.current .n { background: var(--accent-grad); color: #fff; }
.stepper li.done button { color: var(--success); }
.stepper li.done .n { background: var(--success-soft); color: var(--success); }
.stepper button:disabled { opacity: .6; cursor: default; }
.domain { display: flex; align-items: center; gap: 1rem; padding: 1.2rem 1.3rem; text-align: left; color: var(--text); transition: transform .2s, border-color .2s, box-shadow .2s; }
.domain:hover, .domain.sel { border-color: #c7d2fe; box-shadow: var(--shadow-2); transform: translateY(-3px); }
.domain small { display: block; color: var(--muted); font-size: .82rem; margin-top: .15rem; }
.dic { width: 52px; height: 52px; border-radius: 16px; background: linear-gradient(140deg, #e0e7ff, #c7d2fe); color: var(--accent); display: inline-flex; align-items: center; justify-content: center; flex: none; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem 1.2rem; }
@media (max-width: 700px) { .form-grid { grid-template-columns: 1fr; } }
.req { color: var(--error); }
.doc-row { display: flex; gap: .75rem; align-items: center; padding: .75rem .9rem; border: 1px solid var(--border); border-radius: 14px; margin-bottom: .5rem; }
.doc-row.missing { border-color: var(--warning-ink); background: var(--warning-soft); }
.att { display: flex; align-items: center; gap: .5rem; font-size: .84rem; padding: .3rem 0; }
.save-state { display: inline-flex; align-items: center; gap: .35rem; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.big-ok { width: 64px; height: 64px; border-radius: 50%; background: var(--success-soft); color: var(--success); display: inline-flex; align-items: center; justify-content: center; }
.min-w-0 { min-width: 0; }
</style>
