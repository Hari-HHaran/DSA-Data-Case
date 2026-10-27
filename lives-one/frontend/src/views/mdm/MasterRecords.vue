<template>
  <div class="page">
    <PageHeader title="Existing records" eyebrow="Requests" subtitle="Items, customers and vendors that already exist in SAP. Search here before asking for a new one." />
    <ul class="nav nav-tabs mb-3" role="tablist">
      <li class="nav-item"><button class="nav-link" :class="{ active: tab === 'records' }" role="tab" @click="tab = 'records'">All records</button></li>
      <li class="nav-item"><button class="nav-link" :class="{ active: tab === 'mapping' }" role="tab" @click="tab = 'mapping'; loadMappings()">
        Same customer, different names <span v-if="mapCounts.PROPOSED" class="pill tone-warning ms-1">{{ mapCounts.PROPOSED }} to review</span></button></li>
    </ul>

    <template v-if="tab === 'records'">
      <div class="filters-row mb-3">
        <button v-for="d in [{ code: '', label: 'All' }, ...ref_.domains]" :key="d.code" class="chip" :class="{ on: domain === d.code }" type="button" @click="domain = d.code; page = 1; load()">
          {{ d.label }} <span class="num">{{ d.code ? counts[d.code] || 0 : Object.values(counts).reduce((a, b) => a + b, 0) }}</span></button>
        <input v-model="q" class="form-control form-control-sm ms-auto" style="max-width: 260px" placeholder="Search by name, code or ID number" aria-label="Search existing records" @input="debounced" />
      </div>
      <div class="card-x">
        <LoadingBlock v-if="loading" class="p-3" />
        <ErrorState v-else-if="error" :error="error" :retry="load" class="m-3" />
        <EmptyState v-else-if="!items.length" title="No records found" />
        <div v-else class="table-responsive">
          <table class="table table-hover">
            <thead><tr><th>Code</th><th>Name</th><th>Type</th><th>Country</th><th>ID number</th><th>SAP code</th><th>Also known as</th><th>Added by</th></tr></thead>
            <tbody><tr v-for="m in items" :key="m.id" @click="openRecord(m)">
              <td class="mono">{{ m.code }}</td><td class="fw-semibold">{{ m.name }}</td><td>{{ m.domain_label }}</td><td>{{ m.country_code || '—' }}</td>
              <td class="mono small">{{ m.identifier || '—' }}</td><td class="mono small">{{ m.sap_code || '—' }}</td>
              <td class="small">{{ m.aliases.length ? m.aliases.slice(0, 2).join(' · ') + (m.aliases.length > 2 ? ` +${m.aliases.length - 2}` : '') : '—' }}</td>
              <td><span class="pill" :class="m.source === 'LIVES_ONE' ? 'tone-teal' : 'tag-synthetic'">{{ m.source === 'LIVES_ONE' ? 'A LIVES ONE request' : 'Sample data' }}</span></td>
            </tr></tbody>
          </table>
        </div>
        <div v-if="total > 25" class="d-flex justify-content-between p-3 small"><span class="text-muted-2">{{ total }} records</span>
          <div class="d-flex gap-1"><button class="btn btn-light btn-sm" :disabled="page === 1" @click="page--; load()">Previous</button>
            <button class="btn btn-light btn-sm" :disabled="page * 25 >= total" @click="page++; load()">Next</button></div></div>
      </div>
    </template>

    <template v-else>
      <div class="callout info mb-3"><Info :size="18" /><div>Each of our companies often saved the same customer under a slightly different name. Here we link those names to one customer, so sales are counted once.
        Nothing is overwritten. Only links that someone has <strong>confirmed</strong> are used in the sales numbers.</div></div>
      <div class="grid grid-2">
        <section class="card-x">
          <div class="card-x-head"><h2>Suggested matches to check</h2><span class="small text-muted-2">Found because the names look alike</span></div>
          <div class="card-x-body">
            <EmptyState v-if="!proposed.length" title="Nothing to check" text="All suggested matches have been decided." />
            <div v-for="m in proposed" :key="m.id" class="map-row">
              <div class="flex-grow-1">
                <div><span class="pill tone-neutral">{{ m.source_customer.entity }}</span> <strong>"{{ m.alias_name }}"</strong> <span class="text-muted-2 small">{{ m.source_customer.code }}</span></div>
                <div class="small mt-1"><ArrowRight :size="13" /> {{ m.master_record.name }} <span class="text-muted-2">{{ m.master_record.code }}</span></div>
                <div class="small text-muted-2">{{ Math.round(m.confidence * 100) }}% sure · {{ m.method.replace('_', ' ').toLowerCase() }}</div>
              </div>
              <div v-if="auth.has('MDM_ANALYST', 'ADMIN')" class="d-flex gap-1">
                <button class="btn btn-teal btn-sm" type="button" @click="review(m, 'CONFIRM')"><Check :size="14" /> Yes, same customer</button>
                <button class="btn btn-light btn-sm" type="button" title="Not the same customer" aria-label="Not the same customer" @click="review(m, 'REJECT')"><X :size="14" /></button>
              </div>
            </div>
            <p v-if="proposed.length && !auth.has('MDM_ANALYST', 'ADMIN')" class="small text-muted-2 mt-2 mb-0">Only the Master Data team can confirm matches.</p>
          </div>
        </section>
        <section class="card-x">
          <div class="card-x-head"><h2>Example: one customer saved under several names</h2></div>
          <div class="card-x-body">
            <LoadingBlock v-if="!consolidation" />
            <div v-for="c in consolidation" :key="c.canonical_key" class="cons">
              <div class="d-flex justify-content-between"><strong>{{ c.canonical_name }}</strong><span class="small text-muted-2">{{ c.country }} · {{ c.total_orders }} orders</span></div>
              <div class="d-flex flex-wrap gap-1 mt-1">
                <span v-for="s in c.sources" :key="s.name + s.entity" class="pill tone-neutral">{{ s.entity }} · "{{ s.name }}" · {{ s.orders }} orders</span></div>
            </div>
            <p class="small text-muted-2 mt-2 mb-0">Each order is counted only once, even when the customer has several names.</p>
          </div>
        </section>
      </div>
      <section class="card-x mt-3">
        <div class="card-x-head"><h2>All name links</h2><span class="small text-muted-2">{{ mappings.length }} saved names</span></div>
        <div class="table-responsive" style="max-height: 420px">
          <table class="table"><thead><tr><th>Name as saved</th><th>Company</th><th>Linked to customer</th><th>How sure</th><th>How it was found</th><th>Status</th><th>Checked on</th></tr></thead>
            <tbody><tr v-for="m in mappings" :key="m.id"><td>{{ m.alias_name }} <span class="mono small text-muted-2">{{ m.source_customer.code }}</span></td><td>{{ m.source_customer.entity }}</td>
              <td>{{ m.master_record.name }}</td><td class="num">{{ Math.round(m.confidence * 100) }}%</td><td class="small">{{ m.method.replace('_', ' ').toLowerCase() }}</td>
              <td><span class="pill" :class="{ CONFIRMED: 'tone-success', PROPOSED: 'tone-warning', REJECTED: 'tone-error' }[m.review_status]">{{ { CONFIRMED: 'confirmed', PROPOSED: 'to check', REJECTED: 'not a match' }[m.review_status] || m.review_status.toLowerCase() }}</span></td>
              <td class="small text-muted-2">{{ fmtDate(m.reviewed_at) }}</td></tr></tbody></table>
        </div>
      </section>
    </template>

    <ModalDialog :open="!!record" :title="record?.name" width="640px" @close="record = null">
      <dl class="kv" v-if="record">
        <dt>Code</dt><dd class="mono">{{ record.code }}</dd><dt>Type</dt><dd>{{ record.domain }}</dd><dt>ID number</dt><dd class="mono">{{ record.identifier || '—' }}</dd>
        <dt>SAP code</dt><dd class="mono">{{ record.sap_code || '—' }}</dd><dt>Country · company</dt><dd>{{ record.country_code }} · {{ record.entity_code }}</dd>
        <template v-for="(v, k) in record.attributes" :key="k"><dt>{{ k.replace(/_/g, ' ') }}</dt><dd>{{ v || '—' }}</dd></template>
        <dt>Added by</dt><dd><RouterLink v-if="record.created_from_request_id" :to="`/mdm/requests/${record.created_from_request_id}`" @click="record = null">LIVES ONE request</RouterLink><span v-else>Sample data</span></dd>
      </dl>
      <template v-if="record?.aliases?.length"><div class="small-label mt-3 mb-1">Also known as</div>
        <div v-for="a in record.aliases" :key="a.name + a.source_system" class="small">{{ a.source_system }} · "{{ a.name }}" <span class="text-muted-2 mono">{{ a.source_code }}</span></div></template>
    </ModalDialog>
  </div>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowRight, Check, Info, X } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import LoadingBlock from '@/components/LoadingBlock.vue'
import ErrorState from '@/components/ErrorState.vue'
import EmptyState from '@/components/EmptyState.vue'
import ModalDialog from '@/components/ModalDialog.vue'
import { get, post } from '@/api/client'
import { useAuth } from '@/stores/auth'
import { useReference } from '@/stores/reference'
import { useToast } from '@/stores/toast'
import { fmtDate } from '@/utils/format'

const route = useRoute()
const auth = useAuth()
const ref_ = useReference()
const toast = useToast()
const tab = ref(route.query.tab === 'mapping' ? 'mapping' : 'records')
const items = ref([])
const counts = ref({})
const total = ref(0)
const page = ref(1)
const domain = ref('')
const q = ref(route.query.q || '')
const loading = ref(true)
const error = ref(null)
const mappings = ref([])
const mapCounts = ref({})
const consolidation = ref(null)
const record = ref(null)
const proposed = computed(() => mappings.value.filter((m) => m.review_status === 'PROPOSED'))
let t = null
const debounced = () => { clearTimeout(t); t = setTimeout(() => { page.value = 1; load() }, 300) }
async function load() {
  loading.value = true; error.value = null
  try {
    const r = await get('/api/master-records', { domain: domain.value || undefined, q: q.value || undefined, page: page.value, page_size: 25 })
    items.value = r.items; total.value = r.total; counts.value = r.domain_counts
  } catch (e) { error.value = e } finally { loading.value = false }
}
async function loadMappings() {
  const [m, c] = await Promise.all([get('/api/canonical-mappings'), get('/api/canonical-mappings/consolidation')])
  mappings.value = m.items; mapCounts.value = m.counts; consolidation.value = c.slice(0, 6)
}
async function review(m, decision) {
  try {
    await post(`/api/canonical-mappings/${m.id}/review`, { decision })
    toast.push(decision === 'CONFIRM' ? `Linked "${m.alias_name}" to ${m.master_record.name}. Their sales are now counted together.` : 'Marked as not the same customer')
    loadMappings()
  } catch (e) { toast.error(e) }
}
async function openRecord(m) { try { record.value = await get(`/api/master-records/${m.id}`) } catch (e) { toast.error(e) } }
onMounted(() => { ref_.load(); load(); loadMappings() })
</script>
<style scoped>
.map-row { display: flex; gap: .75rem; align-items: center; padding: .65rem 0; border-bottom: 1px solid var(--border); }
.map-row:last-child { border-bottom: none; }
.cons { padding: .6rem 0; border-bottom: 1px solid var(--border); font-size: .86rem; }
.cons:last-of-type { border-bottom: none; }
</style>
