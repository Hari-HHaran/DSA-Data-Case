<template>
  <div class="page">
    <PageHeader title="Approval inbox" eyebrow="Flow Engine" :subtitle="`Only tasks for your responsibility (${roleNames}). Decisions are recorded with your name and time — no more hunting through email threads.`" />
    <div class="filters-row mb-3">
      <button v-for="v in views" :key="v.key" class="chip" :class="{ on: view === v.key }" type="button" @click="view = v.key; load()">
        <component :is="v.icon" :size="13" /> {{ v.label }} <span class="num">{{ counts[v.key] ?? 0 }}</span></button>
      <input v-model="q" class="form-control form-control-sm ms-auto" style="max-width: 240px" placeholder="Search requests" aria-label="Search inbox" @input="debounced" />
    </div>
    <ErrorState v-if="error" :error="error" :retry="load" />
    <LoadingBlock v-else-if="loading" :rows="5" :height="60" />
    <EmptyState v-else-if="!items.length" :icon="CheckCircle2" :title="view === 'pending' ? 'Inbox zero' : 'Nothing here'" :text="view === 'pending' ? 'No approvals are waiting on you.' : ''" />
    <div v-else class="d-flex flex-column gap-2">
      <article v-for="t in items" :key="t.id" class="card-x task" :class="{ focus: String(t.request_id) === String($route.query.request) }">
        <div class="t-main" @click="$router.push(`/mdm/requests/${t.request_id}`)">
          <div class="d-flex gap-2 align-items-center flex-wrap">
            <strong>{{ t.request.title }}</strong><span class="mono small text-muted-2">{{ t.request.request_number }}</span>
            <StatusBadge :status="t.status" /><SlaPill :state="t.sla_state" />
            <span v-if="t.request.priority === 'HIGH'" class="pill tone-error">High priority</span>
            <span v-if="t.request.flagged_for_review" class="pill tone-warning"><Flag :size="11" /> Duplicate justification</span>
            <span v-if="t.escalated_at" class="pill tone-error"><Siren :size="11" /> Escalated</span>
          </div>
          <div class="meta small">
            <span><Tag :size="13" /> {{ t.request.domain_label }}</span>
            <span><User :size="13" /> {{ t.request.requester.name }}</span>
            <span><MapPin :size="13" /> {{ ref_.countryName(t.request.country_code) }} · {{ t.request.entity_code }}</span>
            <span><Calendar :size="13" /> Submitted {{ fmtDate(t.request.submitted_at) }}</span>
            <span><Layers :size="13" /> {{ t.step_name }} (stage {{ t.stage }})</span>
            <span v-if="view !== 'completed'"><Clock :size="13" /> Waiting {{ hoursLabel(t.hours_pending) }}</span>
            <span v-else><Check :size="13" /> {{ t.status.toLowerCase().replace('_', ' ') }} {{ fmtDate(t.decided_at, true) }}</span>
          </div>
          <div v-if="t.parallel_tasks.length" class="small text-muted-2 mt-1">In parallel: <span v-for="p in t.parallel_tasks" :key="p.step_name" class="me-2">{{ p.step_name }} — {{ p.status.toLowerCase() }}</span></div>
          <div v-if="t.decision_comment" class="small mt-1">“{{ t.decision_comment }}”</div>
        </div>
        <div v-if="t.status === 'PENDING'" class="t-actions">
          <button class="btn btn-teal btn-sm" type="button" @click="open(t, 'APPROVE')"><Check :size="14" /> Approve</button>
          <button class="btn btn-light btn-sm" type="button" @click="open(t, 'REQUEST_CHANGES')"><Undo2 :size="14" /> Changes</button>
          <button class="btn btn-light btn-sm text-danger" type="button" @click="open(t, 'REJECT')"><X :size="14" /> Reject</button>
          <RouterLink class="btn btn-ghost btn-sm" :to="`/mdm/requests/${t.request_id}`"><Eye :size="14" /> Details</RouterLink>
        </div>
      </article>
    </div>
    <DecisionDialog :task="dlg.task" :mode="dlg.mode" @close="dlg.task = null" @done="dlg.task = null; load()" />
  </div>
</template>
<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { AlarmClock, Calendar, Check, CheckCircle2, Clock, Eye, Flag, Hourglass, Inbox, Layers, MapPin, MessageSquare, Siren, Tag, Undo2, User, X } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import SlaPill from '@/components/SlaPill.vue'
import LoadingBlock from '@/components/LoadingBlock.vue'
import ErrorState from '@/components/ErrorState.vue'
import EmptyState from '@/components/EmptyState.vue'
import DecisionDialog from '@/components/DecisionDialog.vue'
import { get } from '@/api/client'
import { useAuth } from '@/stores/auth'
import { useReference } from '@/stores/reference'
import { fmtDate, hoursLabel, ROLE_LABELS } from '@/utils/format'

const auth = useAuth()
const ref_ = useReference()
const route = useRoute()
const view = ref(['pending', 'due_soon', 'overdue', 'clarification', 'completed'].includes(route.query.view) ? route.query.view : 'pending')
const q = ref('')
const items = ref([])
const counts = ref({})
const loading = ref(true)
const error = ref(null)
const dlg = reactive({ task: null, mode: 'APPROVE' })
const views = [
  { key: 'pending', label: 'Pending', icon: Inbox }, { key: 'due_soon', label: 'Due soon', icon: Hourglass }, { key: 'overdue', label: 'Overdue', icon: AlarmClock },
  { key: 'clarification', label: 'Sent back for changes', icon: MessageSquare }, { key: 'completed', label: 'Decided by me', icon: CheckCircle2 },
]
const roleNames = computed(() => auth.roles.map((r) => ROLE_LABELS[r]).join(', '))
let t = null
const debounced = () => { clearTimeout(t); t = setTimeout(load, 300) }
async function load() {
  loading.value = true; error.value = null
  try { const r = await get('/api/approvals/inbox', { view: view.value, q: q.value || undefined }); items.value = r.items; counts.value = r.counts } catch (e) { error.value = e } finally { loading.value = false }
}
function open(task, mode) { dlg.task = task; dlg.mode = mode }
onMounted(() => { ref_.load(); load() })
</script>
<style scoped>
.task { display: flex; gap: 1rem; padding: 1rem 1.15rem; align-items: center; flex-wrap: wrap; transition: transform .2s, box-shadow .2s; }
.task:hover { transform: translateY(-2px); box-shadow: var(--shadow-2); }
.task.focus { border-color: var(--accent-2); box-shadow: var(--ring), var(--shadow-2); }
.t-main { flex: 1; min-width: 300px; cursor: pointer; }
.meta { display: flex; flex-wrap: wrap; gap: .35rem 1rem; color: var(--text-2); margin-top: .35rem; }
.meta span { display: inline-flex; align-items: center; gap: .3rem; }
.meta svg { color: var(--muted); }
.t-actions { display: flex; gap: .4rem; flex-wrap: wrap; }
</style>
