<template>
  <div class="page">
    <PageHeader title="Track requests" eyebrow="Approvals" subtitle="Every request that has been sent in: where it is now, who it is waiting for, and whether it is on time.">
      <button v-if="auth.has('ADMIN', 'MDM_ANALYST')" class="btn btn-light" type="button" :disabled="running" @click="runSla"><AlarmClock :size="15" /> Check deadlines now</button>
    </PageHeader>
    <div class="grid grid-kpi mb-3">
      <KpiTile label="Typical time to finish" :value="m.median_turnaround_days ?? '—'" unit="working days" :hint="`From sending in to ready in SAP · ${m.completed_requests ?? 0} finished requests`" :icon="Timer" :loading="loading" />
      <KpiTile label="Most requests finish within" :value="m.p90_turnaround_days ?? '—'" unit="working days" hint="9 out of 10 requests are done in this time" :icon="Gauge" :loading="loading" />
      <KpiTile label="Typical time to approve" :value="m.median_approval_handling_days ?? '—'" unit="working days" :hint="`Per approver · based on ${m.decided_tasks ?? 0} decisions`" :icon="UserCheck" :loading="loading" />
      <KpiTile label="Overdue approvals" :value="overdue" tone="warning" hint="Reminders are sent automatically" :icon="AlarmClock" :loading="loading" />
    </div>
    <div class="filters-row mb-3">
      <button v-for="f in filters" :key="f.key" class="chip" :class="{ on: status === f.key }" type="button" @click="status = f.key; load()">{{ f.label }}</button>
      <input v-model="q" class="form-control form-control-sm ms-auto" style="max-width: 240px" placeholder="Search by name or request number" aria-label="Search requests" @input="debounced" />
    </div>
    <div class="card-x">
      <LoadingBlock v-if="loading" class="p-3" />
      <ErrorState v-else-if="error" :error="error" :retry="load" class="m-3" />
      <EmptyState v-else-if="!items.length" title="No requests found" />
      <div v-else class="table-responsive">
        <table class="table table-hover">
          <thead><tr><th>Request</th><th>Requested by</th><th>Status</th><th>Approvals</th><th>Open for</th><th>Last update</th></tr></thead>
          <tbody><tr v-for="r in items" :key="r.id" :class="{ hl: String(r.id) === String($route.query.request) }" @click="$router.push(`/mdm/requests/${r.id}`)">
            <td><div class="fw-semibold">{{ r.title }}</div><div class="small text-muted-2"><span class="mono">{{ r.request_number }}</span> · {{ r.domain_label }} · {{ r.country_code }}</div></td>
            <td class="small">{{ r.requester.name }}</td>
            <td><StatusBadge :status="r.status" /></td>
            <td class="small"><div class="tasks">
              <span v-for="t in r.tasks" :key="t.step_name + t.stage" class="tk" :class="t.status.toLowerCase()" :title="`${t.step_name}: ${statusMeta(t.status).label}${t.due_at ? ' · due ' + fmtDate(t.due_at, true) : ''}`">
                <component :is="t.status === 'APPROVED' ? Check : t.status === 'PENDING' ? Clock : t.status === 'WAITING' ? Pause : X" :size="11" />{{ short(t.step_name) }}
                <AlarmClock v-if="t.sla_state === 'OVERDUE'" :size="11" class="text-danger" /><Siren v-if="t.escalated" :size="11" class="text-danger" /></span>
              <span v-if="!r.tasks.length" class="text-muted-2">—</span></div></td>
            <td class="num small">{{ r.age_days }} {{ r.age_days === 1 ? 'day' : 'days' }}</td>
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
import { AlarmClock, Check, Clock, Gauge, Pause, Siren, Timer, UserCheck, X } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import KpiTile from '@/components/KpiTile.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import LoadingBlock from '@/components/LoadingBlock.vue'
import ErrorState from '@/components/ErrorState.vue'
import EmptyState from '@/components/EmptyState.vue'
import { get, post } from '@/api/client'
import { useAuth } from '@/stores/auth'
import { useToast } from '@/stores/toast'
import { fmtDate, relTime, statusMeta } from '@/utils/format'

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
const filters = [{ key: '', label: 'All' }, { key: 'PENDING_APPROVAL', label: 'Waiting for approval' }, { key: 'NEEDS_CHANGES', label: 'Sent back' },
  { key: 'MDM_VERIFICATION,SAP_PENDING,SAP_FAILED', label: 'Final check & SAP' }, { key: 'SAP_COMPLETED', label: 'Done' }, { key: 'REJECTED,CANCELLED', label: 'Closed' }]
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
  try { const r = await post('/api/workflows/sla/run'); toast.push(`Deadlines checked: ${r.reminders_sent} reminder(s) and ${r.escalations} escalation(s) sent`); load() } catch (e) { toast.error(e) } finally { running.value = false }
}
onMounted(load)
</script>
<style scoped>
.tasks { display: flex; flex-wrap: wrap; gap: .25rem; }
.tk { display: inline-flex; align-items: center; gap: .2rem; border-radius: 999px; padding: .1rem .4rem; font-size: .72rem; font-weight: 600; background: #eef1f6; color: #475569; }
.tk.approved { background: var(--success-soft); color: var(--success); }
.tk.pending { background: var(--warning-soft); color: var(--warning); }
.tk.rejected, .tk.changes_requested { background: var(--error-soft); color: #b91c1c; }
tr.hl td { background: #f1f0ff; }
</style>
