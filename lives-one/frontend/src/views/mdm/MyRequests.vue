<template>
  <div class="page">
    <PageHeader title="My requests" eyebrow="Smart MDM" subtitle="Everything you have asked for, and where each request is right now.">
      <RouterLink v-if="auth.has('REQUESTOR', 'SALES', 'ADMIN')" to="/mdm/new" class="btn btn-primary"><Plus :size="15" /> New request</RouterLink>
    </PageHeader>
    <div class="filters-row mb-3">
      <button v-for="f in filters" :key="f.key" type="button" class="chip" :class="{ on: status === f.key }" @click="setStatus(f.key)">
        {{ f.label }} <span class="num">{{ count(f) }}</span></button>
      <div class="ms-auto d-flex gap-2">
        <select v-model="domain" class="form-select form-select-sm" aria-label="Record category" @change="load"><option value="">All categories</option>
          <option v-for="d in ref_.domains" :key="d.code" :value="d.code">{{ d.label }}</option></select>
        <input v-model="q" class="form-control form-control-sm" placeholder="Search by name or request number" aria-label="Search requests" @input="debouncedLoad" />
      </div>
    </div>
    <div class="card-x">
      <ErrorState v-if="error" :error="error" :retry="load" class="m-3" />
      <LoadingBlock v-else-if="loading" class="p-3" />
      <EmptyState v-else-if="!items.length" title="No requests found" text="Try a different filter, or start a new request.">
        <RouterLink v-if="auth.has('REQUESTOR', 'SALES')" to="/mdm/new" class="btn btn-primary btn-sm"><Plus :size="14" /> New request</RouterLink></EmptyState>
      <div v-else class="table-responsive">
        <table class="table table-hover">
          <thead><tr><th>Request</th><th>Category</th><th>Company · Country</th><th>Status</th><th>Waiting for</th><th>Last update</th><th class="text-end">Actions</th></tr></thead>
          <tbody>
            <tr v-for="r in items" :key="r.id" @click="open(r)">
              <td><div class="fw-semibold">{{ r.title }}</div><div class="small text-muted-2 num">{{ r.request_number }}<span v-if="r.flagged_for_review" class="pill tone-warning ms-1">Flagged</span></div></td>
              <td>{{ r.domain_label }}</td>
              <td>{{ r.entity_code }} · {{ r.country_code }}</td>
              <td><StatusBadge :status="r.status" /></td>
              <td class="small"><template v-if="r.pending_with?.length"><div v-for="p in r.pending_with" :key="p.step">{{ p.step }} <SlaPill :state="p.sla_state" /></div></template>
                <span v-else class="text-muted-2">{{ r.resolution || '—' }}</span></td>
              <td class="small text-muted-2">{{ relTime(r.updated_at) }}</td>
              <td class="text-end" @click.stop>
                <RouterLink v-if="['DRAFT', 'NEEDS_CHANGES'].includes(r.status)" :to="`/mdm/new?edit=${r.id}`" class="btn btn-light btn-sm">
                  <Pencil :size="13" /> {{ r.status === 'DRAFT' ? 'Resume' : 'Correct' }}</RouterLink>
                <button class="btn btn-ghost btn-sm" type="button" title="Copy into a new draft" aria-label="Copy into a new draft" @click="clone(r)"><Copy :size="13" /></button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="total > pageSize" class="d-flex justify-content-between align-items-center p-3 small">
        <span class="text-muted-2">{{ (page - 1) * pageSize + 1 }}–{{ Math.min(page * pageSize, total) }} of {{ total }}</span>
        <div class="d-flex gap-1"><button class="btn btn-light btn-sm" :disabled="page === 1" @click="page--; load()">Previous</button>
          <button class="btn btn-light btn-sm" :disabled="page * pageSize >= total" @click="page++; load()">Next</button></div>
      </div>
    </div>
  </div>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Copy, Pencil, Plus } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import SlaPill from '@/components/SlaPill.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorState from '@/components/ErrorState.vue'
import LoadingBlock from '@/components/LoadingBlock.vue'
import { get, post } from '@/api/client'
import { useAuth } from '@/stores/auth'
import { useReference } from '@/stores/reference'
import { useToast } from '@/stores/toast'
import { relTime } from '@/utils/format'

const auth = useAuth()
const ref_ = useReference()
const toast = useToast()
const router = useRouter()
const route = useRoute()
const items = ref([])
const counts = ref({})
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(true)
const error = ref(null)
const status = ref(route.query.status || '')
const domain = ref('')
const q = ref(route.query.q || '')
const filters = [
  { key: '', label: 'All' }, { key: 'DRAFT,NEEDS_CHANGES', label: 'Needs my action' },
  { key: 'SUBMITTED,VALIDATION_COMPLETED,PENDING_APPROVAL,APPROVED,MDM_VERIFICATION,SAP_PENDING,SAP_FAILED', label: 'In progress' },
  { key: 'SAP_COMPLETED', label: 'Completed' }, { key: 'REJECTED,CANCELLED', label: 'Closed' },
]
const count = (f) => (f.key ? f.key.split(',') : Object.keys(counts.value)).reduce((s, k) => s + (counts.value[k] || 0), 0)
let t = null
function debouncedLoad() { clearTimeout(t); t = setTimeout(() => { page.value = 1; load() }, 300) }
function setStatus(k) { status.value = k; page.value = 1; load() }
async function load() {
  loading.value = true; error.value = null
  try {
    const r = await get('/api/mdm/requests', { scope: 'mine', status: status.value || undefined, domain: domain.value || undefined, q: q.value || undefined, page: page.value, page_size: pageSize })
    items.value = r.items; total.value = r.total; counts.value = r.status_counts
  } catch (e) { error.value = e } finally { loading.value = false }
}
function open(r) { router.push(['DRAFT'].includes(r.status) ? `/mdm/new?edit=${r.id}` : `/mdm/requests/${r.id}`) }
async function clone(r) {
  try { const c = await post(`/api/mdm/requests/${r.id}/clone`); toast.push(`Copied into new draft ${c.request_number}`); router.push(`/mdm/new?edit=${c.id}`) } catch (e) { toast.error(e) }
}
onMounted(() => { ref_.load(); load() })
</script>
