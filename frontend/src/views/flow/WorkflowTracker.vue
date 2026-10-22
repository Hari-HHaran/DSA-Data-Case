<template>
  <div class="page">
    <PageHeader title="Workflow tracker" eyebrow="Flow Engine" subtitle="Every submitted request, where it is, who it is waiting on and whether it is within SLA.">
      <button v-if="auth.has('ADMIN', 'MDM_ANALYST')" class="btn btn-light" type="button" :disabled="running" @click="runSla"><AlarmClock :size="15" /> Run SLA check now</button>
    </PageHeader>
    <div class="grid grid-kpi mb-3">
      <KpiTile label="Median turnaround" :value="m.median_turnaround_days ?? '—'" unit="working days" :hint="`Submission → SAP creation · ${m.completed_requests ?? 0} completed (simulated)`" :icon="Timer" :loading="loading" />
      <KpiTile label="90th percentile" :value="m.p90_turnaround_days ?? '—'" unit="working days" hint="9 in 10 requests finish within this" :icon="Gauge" :loading="loading" />
      <KpiTile label="Median approver response" :value="m.median_approval_handling_days ?? '—'" unit="working days" :hint="`p90 ${m.p90_approval_handling_days ?? '—'} · ${m.decided_tasks ?? 0} decisions`" :icon="UserCheck" :loading="loading" />
      <KpiTile label="Overdue approval tasks" :value="overdue" tone="warning" hint="Reminders and escalations are sent automatically" :icon="AlarmClock" :loading="loading" />
    </div>
    <div class="callout neutral mb-3 small"><Info :size="16" /><div>Turnaround figures come from seeded, simulated requests processed through the real workflow engine — they show the mechanism, not observed Lives Group performance. The brief's reference point is "two to three weeks" for a five-approval request.</div></div>
    <div class="filters-row mb-3">
      <button v-for="f in filters" :key="f.key" class="chip" :class="{ on: status === f.key }" type="button" @click="status = f.key; load()">{{ f.label }}</button>
      <input v-model="q" class="form-control form-control-sm ms-auto" style="max-width: 240px" placeholder="Search name or ID" aria-label="Search" @input="debounced" />
    </div>
    <div class="card-x">
      <LoadingBlock v-if="loading" class="p-3" />
      <ErrorState v-else-if="error" :error="error" :retry="load" class="m-3" />
      <EmptyState v-else-if="!items.length" title="No requests match" />
      <div v-else class="table-responsive">
        <table class="table table-hover">
          <thead><tr><th>Request</th><th>Requestor</th><th>Status</th><th>Approval tasks</th><th>Age</th><th>Updated</th></tr></thead>
          <tbody><tr v-for="r in items" :key="r.id" :class="{ hl: String(r.id) === String($route.query.request) }" @click="$router.push(`/mdm/requests/${r.id}`)">
            <td><div class="fw-semibold">{{ r.title }}</div><div class="small text-muted-2"><span class="mono">{{ r.request_number }}</span> · {{ r.domain_label }} · {{ r.country_code }}</div></td>
            <td class="small">{{ r.requester.name }}</td>
            <td><StatusBadge :status="r.status" /></td>
            <td class="small"><div class="tasks">
              <span v-for="t in r.tasks" :key="t.step_name + t.stage" class="tk" :class="t.status.toLowerCase()" :title="`${t.step_name}: ${t.status}${t.due_at ? ' · due ' + fmtDate(t.due_at, true) : ''}`">
                <component :is="t.status === 'APPROVED' ? Check : t.status === 'PENDING' ? Clock : t.status === 'WAITING' ? Pause : X" :size="11" />{{ short(t.step_name) }}
                <AlarmClock v-if="t.sla_state === 'OVERDUE'" :size="11" class="text-danger" /><Siren v-if="t.escalated" :size="11" class="text-danger" /></span>
              <span v-if="!r.tasks.length" class="text-muted-2">—</span></div></td>
            <td class="num small">{{ r.age_days }} d</td>
            <td class="small text-muted-2">{{ relTime(r.updated_at) }}</td>
          </tr></tbody>
        </table>
      </div>
    </div>
  </div>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { AlarmClock, Check, Clock, Gauge, Info, Pause, Siren, Timer, UserCheck, X } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import KpiTile from '@/components/KpiTile.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import LoadingBlock from '@/components/LoadingBlock.vue'
import ErrorState from '@/components/ErrorState.vue'
import EmptyState from '@/components/EmptyState.vue'
import { get, post } from '@/api/client'
import { useAuth } from '@/stores/auth'
import { useToast } from '@/stores/toast'
import { fmtDate, relTime } from '@/utils/format'

const auth = useAuth()
const toast = useToast()
const route = useRoute()
const items = ref([])
const m = ref({})
const loading = ref(true)
const error = ref(null)
const running = ref(false)
const status = ref('')
const q = ref(route.query.q || '')
const filters = [{ key: '', label: 'All' }, { key: 'PENDING_APPROVAL', label: 'Pending approval' }, { key: 'NEEDS_CHANGES', label: 'Needs changes' },
  { key: 'MDM_VERIFICATION,SAP_PENDING,SAP_FAILED', label: 'MDM & SAP' }, { key: 'SAP_COMPLETED', label: 'Completed' }, { key: 'REJECTED,CANCELLED', label: 'Closed' }]
const overdue = computed(() => items.value.reduce((s, r) => s + r.tasks.filter((t) => t.sla_state === 'OVERDUE').length, 0))
const short = (n) => n.replace(' approval', '').replace(' sign-off', '').replace(' set-up check', '').replace(' verification', '').replace(' review', '')
let t = null
const debounced = () => { clearTimeout(t); t = setTimeout(load, 300) }
async function load() {
  loading.value = true; error.value = null
  try { const r = await get('/api/workflows', { status: status.value || undefined, q: q.value || undefined, page_size: 100 }); items.value = r.items; m.value = r.metrics } catch (e) { error.value = e } finally { loading.value = false }
}
async function runSla() {
  running.value = true
  try { const r = await post('/api/workflows/sla/run'); toast.push(`SLA check: ${r.reminders_sent} reminder(s), ${r.escalations} escalation(s) across ${r.checked} open tasks`); load() } catch (e) { toast.error(e) } finally { running.value = false }
}
onMounted(load)
</script>
<style scoped>
.tasks { display: flex; flex-wrap: wrap; gap: .25rem; }
.tk { display: inline-flex; align-items: center; gap: .2rem; border-radius: 6px; padding: .1rem .4rem; font-size: .72rem; font-weight: 600; background: #eef1f6; color: #475569; }
.tk.approved { background: var(--success-soft); color: var(--success); }
.tk.pending { background: var(--warning-soft); color: var(--warning); }
.tk.rejected, .tk.changes_requested { background: var(--error-soft); color: #b91c1c; }
tr.hl td { background: #f5f8ff; }
</style>
