<template>
  <div class="page">
    <PageHeader title="Master records" eyebrow="Smart MDM" subtitle="Verified records (as they exist in SAP B1) and the canonical mapping that links each entity's customer aliases to one golden record." />
    <ul class="nav nav-tabs mb-3" role="tablist">
      <li class="nav-item"><button class="nav-link" :class="{ active: tab === 'records' }" role="tab" @click="tab = 'records'">Records</button></li>
      <li class="nav-item"><button class="nav-link" :class="{ active: tab === 'mapping' }" role="tab" @click="tab = 'mapping'; loadMappings()">
        Canonical customer mapping <span v-if="mapCounts.PROPOSED" class="pill tone-warning ms-1">{{ mapCounts.PROPOSED }} to review</span></button></li>
    </ul>

    <template v-if="tab === 'records'">
      <div class="filters-row mb-3">
        <button v-for="d in [{ code: '', label: 'All' }, ...ref_.domains]" :key="d.code" class="chip" :class="{ on: domain === d.code }" type="button" @click="domain = d.code; page = 1; load()">
          {{ d.label }} <span class="num">{{ d.code ? counts[d.code] || 0 : Object.values(counts).reduce((a, b) => a + b, 0) }}</span></button>
        <input v-model="q" class="form-control form-control-sm ms-auto" style="max-width: 260px" placeholder="Search name, code or identifier" aria-label="Search master records" @input="debounced" />
      </div>
      <div class="card-x">
        <LoadingBlock v-if="loading" class="p-3" />
        <ErrorState v-else-if="error" :error="error" :retry="load" class="m-3" />
        <EmptyState v-else-if="!items.length" title="No records found" />
        <div v-else class="table-responsive">
          <table class="table table-hover">
            <thead><tr><th>Code</th><th>Name</th><th>Category</th><th>Country</th><th>Identifier</th><th>SAP key</th><th>Aliases</th><th>Source</th></tr></thead>
            <tbody><tr v-for="m in items" :key="m.id" @click="openRecord(m)">
              <td class="mono">{{ m.code }}</td><td class="fw-semibold">{{ m.name }}</td><td>{{ m.domain_label }}</td><td>{{ m.country_code || '—' }}</td>
              <td class="mono small">{{ m.identifier || '—' }}</td><td class="mono small">{{ m.sap_code || '—' }}</td>
              <td class="small">{{ m.aliases.length ? m.aliases.slice(0, 2).join(' · ') + (m.aliases.length > 2 ? ` +${m.aliases.length - 2}` : '') : '—' }}</td>
              <td><span class="pill" :class="m.source === 'LIVES_ONE' ? 'tone-teal' : 'tag-synthetic'">{{ m.source === 'LIVES_ONE' ? 'Created via LIVES ONE' : 'Synthetic seed' }}</span></td>
            </tr></tbody>
          </table>
        </div>
        <div v-if="total > 25" class="d-flex justify-content-between p-3 small"><span class="text-muted-2">{{ total }} records</span>
          <div class="d-flex gap-1"><button class="btn btn-light btn-sm" :disabled="page === 1" @click="page--; load()">Previous</button>
            <button class="btn btn-light btn-sm" :disabled="page * 25 >= total" @click="page++; load()">Next</button></div></div>
      </div>
    </template>

    <template v-else>
      <div class="callout info mb-3"><Info :size="18" /><div>Each business entity keyed its own customer record, often under a different name. LIVES ONE maps every source record to one canonical customer.
        Original records and transactions are never overwritten — a mapping is a reviewed link with confidence, method, reviewer and timestamp. Only <strong>confirmed</strong> mappings are used by regional analytics.</div></div>
      <div class="grid grid-2">
        <section class="card-x">
          <div class="card-x-head"><h2>Proposed mappings — review</h2><span class="small text-muted-2">Suggested by fuzzy matching</span></div>
          <div class="card-x-body">
            <EmptyState v-if="!proposed.length" title="Nothing to review" text="All proposed mappings have been decided." />
            <div v-for="m in proposed" :key="m.id" class="map-row">
              <div class="flex-grow-1">
                <div><span class="pill tone-neutral">{{ m.source_customer.entity }}</span> <strong>"{{ m.alias_name }}"</strong> <span class="text-muted-2 small">{{ m.source_customer.code }}</span></div>
                <div class="small mt-1"><ArrowRight :size="13" /> {{ m.master_record.name }} <span class="text-muted-2">{{ m.master_record.code }}</span></div>
                <div class="small text-muted-2">Confidence {{ Math.round(m.confidence * 100) }}% · {{ m.method.replace('_', ' ').toLowerCase() }}</div>
              </div>
              <div v-if="auth.has('MDM_ANALYST', 'ADMIN')" class="d-flex gap-1">
                <button class="btn btn-teal btn-sm" type="button" @click="review(m, 'CONFIRM')"><Check :size="14" /> Confirm</button>
                <button class="btn btn-light btn-sm" type="button" @click="review(m, 'REJECT')"><X :size="14" /></button>
              </div>
            </div>
            <p v-if="proposed.length && !auth.has('MDM_ANALYST', 'ADMIN')" class="small text-muted-2 mt-2 mb-0">Only MDM analysts can confirm mappings.</p>
          </div>
        </section>
        <section class="card-x">
          <div class="card-x-head"><h2>Before → after: one customer, many records</h2></div>
          <div class="card-x-body">
            <LoadingBlock v-if="!consolidation" />
            <div v-for="c in consolidation" :key="c.canonical_key" class="cons">
              <div class="d-flex justify-content-between"><strong>{{ c.canonical_name }}</strong><span class="small text-muted-2">{{ c.country }} · {{ c.total_orders }} confirmed POs</span></div>
              <div class="d-flex flex-wrap gap-1 mt-1">
                <span v-for="s in c.sources" :key="s.name + s.entity" class="pill tone-neutral">{{ s.entity }} · "{{ s.name }}" · {{ s.orders }} POs</span></div>
            </div>
            <p class="small text-muted-2 mt-2 mb-0">Totals are counted once per transaction: aliases are joined to the canonical record, never duplicated.</p>
          </div>
        </section>
      </div>
      <section class="card-x mt-3">
        <div class="card-x-head"><h2>All current mappings</h2><span class="small text-muted-2">{{ mappings.length }} source records</span></div>
        <div class="table-responsive" style="max-height: 420px">
          <table class="table"><thead><tr><th>Source record</th><th>Entity</th><th>Canonical customer</th><th>Confidence</th><th>Method</th><th>Status</th><th>Reviewed</th></tr></thead>
            <tbody><tr v-for="m in mappings" :key="m.id"><td>{{ m.alias_name }} <span class="mono small text-muted-2">{{ m.source_customer.code }}</span></td><td>{{ m.source_customer.entity }}</td>
              <td>{{ m.master_record.name }}</td><td class="num">{{ Math.round(m.confidence * 100) }}%</td><td class="small">{{ m.method.replace('_', ' ').toLowerCase() }}</td>
              <td><span class="pill" :class="{ CONFIRMED: 'tone-success', PROPOSED: 'tone-warning', REJECTED: 'tone-error' }[m.review_status]">{{ m.review_status.toLowerCase() }}</span></td>
              <td class="small text-muted-2">{{ fmtDate(m.reviewed_at) }}</td></tr></tbody></table>
        </div>
      </section>
    </template>

    <ModalDialog :open="!!record" :title="record?.name" width="640px" @close="record = null">
      <dl class="kv" v-if="record">
        <dt>Code</dt><dd class="mono">{{ record.code }}</dd><dt>Category</dt><dd>{{ record.domain }}</dd><dt>Identifier</dt><dd class="mono">{{ record.identifier || '—' }}</dd>
        <dt>SAP key</dt><dd class="mono">{{ record.sap_code || '—' }}</dd><dt>Country / entity</dt><dd>{{ record.country_code }} · {{ record.entity_code }}</dd>
        <template v-for="(v, k) in record.attributes" :key="k"><dt>{{ k.replace(/_/g, ' ') }}</dt><dd>{{ v || '—' }}</dd></template>
        <dt>Created from</dt><dd><RouterLink v-if="record.created_from_request_id" :to="`/mdm/requests/${record.created_from_request_id}`" @click="record = null">LIVES ONE request</RouterLink><span v-else>Seed data</span></dd>
      </dl>
      <template v-if="record?.aliases?.length"><div class="small-label mt-3 mb-1">Aliases by source</div>
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
    toast.push(decision === 'CONFIRM' ? `Mapped "${m.alias_name}" → ${m.master_record.name}. Regional analytics now consolidate it.` : 'Mapping rejected')
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
