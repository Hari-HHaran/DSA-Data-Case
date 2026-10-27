<template>
  <div class="page">
    <LoadingBlock v-if="loading && !req" :rows="6" />
    <ErrorState v-else-if="error" :error="error" :retry="load" />
    <template v-else-if="req">
      <PageHeader :title="req.title" :eyebrow="`${req.domain_label} · ${req.request_number}`"
                  :subtitle="`Raised by ${req.requester.name} (${req.requester.title}) · ${req.entity_code} · ${ref_.countryName(req.country_code)}`">
        <template #badge><StatusBadge :status="req.status" /><span v-if="req.flagged_for_review" class="pill tone-warning"><Flag :size="11" /> Reason given: not a duplicate</span>
          <span v-if="req.is_synthetic" class="pill tag-synthetic">Sample data</span></template>
        <RouterLink v-if="req.permissions.can_edit" :to="`/mdm/new?edit=${req.id}`" class="btn btn-primary"><Pencil :size="15" /> {{ req.status === 'DRAFT' ? 'Continue draft' : 'Fix and send again' }}</RouterLink>
        <button class="btn btn-light" type="button" @click="clone"><Copy :size="15" /> Copy as new request</button>
      </PageHeader>

      <!-- Action bars -->
      <div v-if="myTasks.length" class="card-x action-bar mb-3">
        <Inbox :size="18" class="text-primary" />
        <div class="flex-grow-1"><strong>Your decision is needed:</strong> {{ myTasks.map((t) => t.step_name).join(', ') }}</div>
        <button class="btn btn-teal btn-sm" type="button" @click="openDecision(myTasks[0], 'APPROVE')"><Check :size="14" /> Approve</button>
        <button class="btn btn-light btn-sm" type="button" @click="openDecision(myTasks[0], 'REQUEST_CHANGES')"><Undo2 :size="14" /> Send back for changes</button>
        <button class="btn btn-light btn-sm text-danger" type="button" @click="openDecision(myTasks[0], 'REJECT')"><X :size="14" /> Don't approve</button>
      </div>
      <div v-if="req.permissions.can_verify" class="card-x action-bar mb-3">
        <ShieldCheck :size="18" class="text-primary" />
        <div class="flex-grow-1"><strong>Final check.</strong> Everyone who needed to approve has approved. Check the details, then create the record in SAP.
          <div class="checks small mt-1"><label v-for="(c, i) in verifyChecks" :key="i" class="me-3"><input v-model="checked[i]" type="checkbox" class="form-check-input me-1" />{{ c }}</label></div></div>
        <button class="btn btn-teal btn-sm" type="button" :disabled="busy || !allChecked" @click="verifyAndSync"><Database :size="14" /> Verify & create in SAP B1</button>
        <button class="btn btn-light btn-sm" type="button" :disabled="busy" @click="returnOpen = true"><Undo2 :size="14" /> Send back</button>
      </div>
      <div v-if="req.permissions.can_sync" class="card-x action-bar mb-3" :class="{ failed: req.status === 'SAP_FAILED' }">
        <AlertTriangle v-if="req.status === 'SAP_FAILED'" :size="18" class="text-danger" /><Database v-else :size="18" />
        <div class="flex-grow-1"><strong>{{ req.status === 'SAP_FAILED' ? 'SAP set-up failed. The record cannot be used yet.' : 'Checked and ready to create in SAP.' }}</strong>
          <div class="small text-muted-2">{{ lastJob?.error || 'This sends the record to SAP (simulated in this demo).' }}</div></div>
        <button class="btn btn-teal btn-sm" type="button" :disabled="busy" @click="sync"><RotateCw :size="14" /> {{ req.status === 'SAP_FAILED' ? 'Try again' : 'Create in SAP B1' }}</button>
        <button v-if="req.status === 'SAP_FAILED'" class="btn btn-light btn-sm" type="button" @click="manualOpen = true">I created it in SAP myself</button>
      </div>
      <div v-if="req.status === 'SAP_COMPLETED' && req.sap.mapping" class="callout ok mb-3"><CheckCircle2 :size="18" />
        <div><strong>Live in SAP B1:</strong> <span class="mono">{{ req.sap.mapping.sap_key }}</span> ({{ req.sap.mapping.object_type }})
          <span v-if="req.sap.mapping.is_mock" class="pill tag-mock ms-1">Simulated SAP confirmation</span><span v-else class="pill tone-info ms-1">Manually keyed</span>
          · Took {{ turnaround }} from start to finish</div></div>

      <section class="card-x mb-3">
        <div class="card-x-head"><h2>Where this request stands</h2><span class="small"><strong>Next:</strong> {{ timeline?.next_action }}</span></div>
        <div class="card-x-body"><RequestTimeline v-if="timeline" :stages="timeline.stages" :tasks="timeline.tasks" /></div>
      </section>

      <div class="grid grid-main-side">
        <div class="d-flex flex-column gap-3 min-w-0">
          <section class="card-x">
            <div class="card-x-head"><h2>Record details</h2>
              <span v-if="req.masked_fields.length" class="pill tone-warning"><Lock :size="11" /> {{ req.masked_fields.length }} private field(s) hidden for your role</span></div>
            <div class="card-x-body">
              <dl class="kv">
                <template v-for="f in fields" :key="f.key"><dt>{{ f.label }}</dt>
                  <dd :class="{ 'text-muted-2': req.masked_fields.includes(f.key) }">{{ req.data[f.key] || '—' }}</dd></template>
              </dl>
            </div>
          </section>
          <section class="card-x">
            <div class="card-x-head"><h2>History</h2><span class="small text-muted-2">Every step, with who did it and when</span></div>
            <div class="card-x-body"><AuditList :events="[...req.events].reverse()" /></div>
          </section>
        </div>
        <div class="d-flex flex-column gap-3">
          <section class="card-x">
            <div class="card-x-head"><h3>Documents</h3></div>
            <div class="card-x-body">
              <div v-if="!req.attachments.length" class="small text-muted-2">No documents.</div>
              <button v-for="a in req.attachments" :key="a.id" type="button" class="doc" @click="download(a)">
                <FileText :size="16" /><span class="truncate">{{ a.filename }}</span><small>{{ a.category.replace(/_/g, ' ').toLowerCase() }}</small></button>
            </div>
          </section>
          <section class="card-x">
            <div class="card-x-head"><h3>Duplicate review</h3><span class="pill tone-neutral">{{ DUP_STATUS[req.duplicate_check_status] || req.duplicate_check_status.replace('_', ' ').toLowerCase() }}</span></div>
            <div class="card-x-body small">
              <div v-if="!req.duplicate_candidates.length">No similar records were found.</div>
              <div v-for="c in req.duplicate_candidates" :key="c.id" class="mb-2"><strong class="num">{{ Math.round(c.score) }}% match</strong> · {{ c.existing?.name }} <span class="text-muted-2">({{ c.existing?.code }})</span>
                <div class="text-muted-2">{{ c.explanation }}</div></div>
              <div v-for="(r, i) in req.duplicate_reviews" :key="i" class="callout neutral mt-2"><div><strong>{{ r.decision.replace(/_/g, ' ').toLowerCase() }}</strong> — {{ r.justification }}</div></div>
            </div>
          </section>
          <section class="card-x">
            <div class="card-x-head"><h3>SAP set-up</h3><span class="pill tag-mock">Simulated</span></div>
            <div class="card-x-body small">
              <div v-if="!req.sap.jobs.length" class="text-muted-2">Not sent yet. Records go to SAP only after all approvals and the final check.</div>
              <div v-for="j in req.sap.jobs" :key="j.id">
                <div class="d-flex justify-content-between"><span>{{ j.operation }} → <span class="mono">{{ j.object_type }}</span></span><StatusBadge :status="j.status === 'SUCCESS' ? 'COMPLETED' : j.status === 'FAILED' ? 'SAP_FAILED' : 'PENDING'" :label="j.status" /></div>
                <div class="text-muted-2">Tries: {{ j.attempts }} · {{ fmtDate(j.updated_at, true) }}</div>
                <details class="mt-1"><summary>Technical details: data sent</summary><pre class="mono payload">{{ JSON.stringify(j.payload, null, 2) }}</pre></details>
                <details v-if="j.response"><summary>Technical details: SAP reply</summary><pre class="mono payload">{{ JSON.stringify(j.response, null, 2) }}</pre></details>
              </div>
            </div>
          </section>
        </div>
      </div>
    </template>

    <DecisionDialog :task="decision.task" :mode="decision.mode" :request-number="req?.request_number" @close="decision.task = null" @done="decision.task = null; load()" />
    <ModalDialog :open="returnOpen" title="Send back to the requester" @close="returnOpen = false">
      <textarea v-model="returnComment" class="form-control" rows="3" placeholder="What needs to change?" />
      <template #footer><button class="btn btn-light" @click="returnOpen = false">Cancel</button>
        <button class="btn btn-primary" :disabled="returnComment.trim().length < 5" @click="doReturn">Send back</button></template>
    </ModalDialog>
    <ModalDialog :open="manualOpen" title="I created it in SAP myself" @close="manualOpen = false">
      <p class="small text-muted-2">Only use this if the record was typed into SAP directly. Enter the SAP code it was given, and we'll note that it was done by hand.</p>
      <label class="form-label">SAP code</label><input v-model="manual.sap_key" class="form-control mb-2" />
      <label class="form-label">Note</label><textarea v-model="manual.comment" class="form-control" rows="2" />
      <template #footer><button class="btn btn-light" @click="manualOpen = false">Cancel</button>
        <button class="btn btn-primary" :disabled="!manual.sap_key || manual.comment.length < 5" @click="doManual">Save</button></template>
    </ModalDialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { AlertTriangle, Check, CheckCircle2, Copy, Database, FileText, Flag, Inbox, Lock, Pencil, RotateCw, ShieldCheck, Undo2, X } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import RequestTimeline from '@/components/RequestTimeline.vue'
import AuditList from '@/components/AuditList.vue'
import LoadingBlock from '@/components/LoadingBlock.vue'
import ErrorState from '@/components/ErrorState.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import DecisionDialog from '@/components/DecisionDialog.vue'
import { api, get, post } from '@/api/client'
import { useAuth } from '@/stores/auth'
import { useReference } from '@/stores/reference'
import { useToast } from '@/stores/toast'
import { useNotifications } from '@/stores/notifications'
import { fmtDate } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const auth = useAuth()
const ref_ = useReference()
const toast = useToast()
const notes = useNotifications()
const req = ref(null)
const timeline = ref(null)
const form = ref(null)
const loading = ref(true)
const error = ref(null)
const busy = ref(false)
const decision = reactive({ task: null, mode: 'APPROVE' })
const returnOpen = ref(false)
const returnComment = ref('')
const manualOpen = ref(false)
const manual = reactive({ sap_key: '', comment: '' })
const verifyChecks = ['Details match the documents', 'No open duplicate questions', 'The right people have approved']
const DUP_STATUS = { CLEAR: 'No similar records', RESOLVED: 'Checked', NOT_RUN: 'Not checked yet', BLOCKED: 'Same ID found', NEEDS_REVIEW: 'Needs a look' }
const checked = ref([false, false, false])
const allChecked = computed(() => checked.value.every(Boolean))

const fields = computed(() => (form.value?.fields || []).filter((f) => req.value.data[f.key] !== undefined))
const myTasks = computed(() => (req.value?.tasks || []).filter((t) => t.status === 'PENDING' && t.cycle === req.value.cycle && auth.has(t.role_code) && req.value.requester.id !== auth.user.id))
const lastJob = computed(() => req.value?.sap.jobs.at(-1))
const turnaround = computed(() => {
  if (!req.value?.submitted_at || !req.value?.completed_at) return '—'
  const h = (new Date(req.value.completed_at) - new Date(req.value.submitted_at)) / 36e5
  return h < 48 ? `${h.toFixed(1)} hours` : `${(h / 24).toFixed(1)} days`
})

async function load() {
  loading.value = true; error.value = null
  try {
    const id = route.params.id
    const [r, t] = await Promise.all([get(`/api/mdm/requests/${id}`), get(`/api/workflows/${id}`)])
    req.value = r; timeline.value = t
    if (!form.value || form.value.domain !== r.domain) form.value = await get(`/api/mdm/forms/${r.domain}`)
  } catch (e) { error.value = e } finally { loading.value = false }
}
function openDecision(task, mode) { decision.task = task; decision.mode = mode }
async function verifyAndSync() {
  busy.value = true
  try {
    await post(`/api/mdm/requests/${req.value.id}/verify`, { action: 'VERIFY', comment: verifyChecks.join('; ') })
    const r = await post(`/api/sap/sync/${req.value.id}`)
    toast.push(r.job_status === 'SUCCESS' ? `Created in SAP (simulated): ${r.request.sap.mapping.sap_key}` : 'SAP set-up failed. See the details on this page.', r.job_status === 'SUCCESS' ? 'success' : 'error')
    await load(); notes.refresh()
  } catch (e) { toast.error(e); load() } finally { busy.value = false }
}
async function sync() {
  busy.value = true
  try {
    const r = await post(`/api/sap/sync/${req.value.id}`)
    toast.push(r.job_status === 'SUCCESS' ? `Created in SAP (simulated): ${r.request.sap.mapping.sap_key}` : 'SAP set-up failed again.', r.job_status === 'SUCCESS' ? 'success' : 'error')
    await load()
  } catch (e) { toast.error(e) } finally { busy.value = false }
}
async function doReturn() {
  try { await post(`/api/mdm/requests/${req.value.id}/verify`, { action: 'RETURN', comment: returnComment.value }); returnOpen.value = false; toast.push('Sent back to the requester'); load() } catch (e) { toast.error(e) }
}
async function doManual() {
  try { await post(`/api/sap/sync/${req.value.id}/manual-resolve`, manual); manualOpen.value = false; toast.push('Saved'); load() } catch (e) { toast.error(e) }
}
async function clone() {
  try { const c = await post(`/api/mdm/requests/${req.value.id}/clone`); toast.push(`Copied into new draft ${c.request_number}`); router.push(`/mdm/new?edit=${c.id}`) } catch (e) { toast.error(e) }
}
async function download(a) {
  try {
    const r = await api.get(`/api/mdm/requests/${req.value.id}/attachments/${a.id}`, { responseType: 'blob' })
    const url = URL.createObjectURL(r.data)
    window.open(url, '_blank', 'noopener')
    setTimeout(() => URL.revokeObjectURL(url), 60000)
  } catch (e) { toast.error(e) }
}
onMounted(() => { ref_.load(); load() })
</script>

<style scoped>
.action-bar { display: flex; gap: .75rem; align-items: center; padding: 1rem 1.15rem; flex-wrap: wrap; border-left: 5px solid var(--accent-2); background: linear-gradient(90deg, #f5f5ff, var(--surface) 40%); }
.action-bar.failed { border-left-color: var(--error); }
.doc { display: flex; align-items: center; gap: .5rem; width: 100%; border: 1px solid var(--border); background: var(--surface); border-radius: 12px; padding: .5rem .6rem; margin-bottom: .4rem; font-size: .84rem; text-align: left; }
.doc:hover { background: var(--surface-2); }
.doc small { margin-left: auto; color: var(--muted); white-space: nowrap; }
.payload { background: var(--surface-2); border-radius: 10px; padding: .5rem; max-height: 220px; overflow: auto; font-size: .72rem; white-space: pre-wrap; }
.min-w-0 { min-width: 0; }
</style>
