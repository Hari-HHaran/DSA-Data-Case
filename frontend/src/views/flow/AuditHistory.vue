<template>
  <div class="page">
    <PageHeader title="Audit history" eyebrow="Flow Engine" subtitle="Append-only application audit log of every decision, status change, configuration change and integration event.">
      <button class="btn btn-light" type="button" :disabled="verifying" @click="verify"><ShieldCheck :size="15" /> Verify integrity</button>
    </PageHeader>
    <div v-if="chain" class="callout mb-3" :class="chain.valid ? 'ok' : 'err'"><component :is="chain.valid ? ShieldCheck : ShieldAlert" :size="18" />
      <div><strong>{{ chain.valid ? 'Hash chain intact.' : `Chain broken at event #${chain.broken_at_event_id}.` }}</strong> {{ chain.events_checked }} events checked.
        Each event stores the SHA-256 of its content plus the previous event's hash, so editing or deleting history is detectable. This is a tamper-evident application log, not a legally certified immutable ledger.</div></div>
    <div class="filters-row mb-3">
      <select v-model="eventType" class="form-select form-select-sm" style="max-width: 260px" aria-label="Event type" @change="page = 1; load()"><option value="">All event types</option>
        <option v-for="t in types" :key="t" :value="t">{{ humanize(t) }}</option></select>
      <select v-model="entityType" class="form-select form-select-sm" style="max-width: 220px" aria-label="Entity type" @change="page = 1; load()"><option value="">All objects</option>
        <option v-for="t in ['MDM_REQUEST', 'OPPORTUNITY', 'CANONICAL_MAPPING', 'WORKFLOW', 'FORM', 'SETTING', 'USER']" :key="t" :value="t">{{ humanize(t) }}</option></select>
      <input v-model="q" class="form-control form-control-sm ms-auto" style="max-width: 260px" placeholder="Search comments or references" aria-label="Search audit" @input="debounced" />
    </div>
    <div class="card-x"><div class="card-x-body">
      <LoadingBlock v-if="loading" :rows="8" />
      <ErrorState v-else-if="error" :error="error" :retry="load" />
      <EmptyState v-else-if="!items.length" title="No events match" />
      <AuditList v-else :events="items" show-ref show-hash />
    </div>
      <div class="d-flex justify-content-between align-items-center p-3 small border-top"><span class="text-muted-2">{{ total }} events · newest first</span>
        <div class="d-flex gap-1"><button class="btn btn-light btn-sm" :disabled="page === 1" @click="page--; load()">Newer</button>
          <button class="btn btn-light btn-sm" :disabled="page * 50 >= total" @click="page++; load()">Older</button></div></div>
    </div>
  </div>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import { ShieldAlert, ShieldCheck } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import AuditList from '@/components/AuditList.vue'
import LoadingBlock from '@/components/LoadingBlock.vue'
import ErrorState from '@/components/ErrorState.vue'
import EmptyState from '@/components/EmptyState.vue'
import { get } from '@/api/client'
import { useToast } from '@/stores/toast'
import { humanize } from '@/utils/format'

const toast = useToast()
const items = ref([])
const types = ref([])
const total = ref(0)
const page = ref(1)
const eventType = ref('')
const entityType = ref('')
const q = ref('')
const loading = ref(true)
const error = ref(null)
const chain = ref(null)
const verifying = ref(false)
let t = null
const debounced = () => { clearTimeout(t); t = setTimeout(() => { page.value = 1; load() }, 300) }
async function load() {
  loading.value = true; error.value = null
  try {
    const r = await get('/api/audit-events', { event_type: eventType.value || undefined, entity_type: entityType.value || undefined, q: q.value || undefined, page: page.value, page_size: 50 })
    items.value = r.items; total.value = r.total; types.value = r.event_types
  } catch (e) { error.value = e } finally { loading.value = false }
}
async function verify() { verifying.value = true; try { chain.value = await get('/api/audit-events/verify') } catch (e) { toast.error(e) } finally { verifying.value = false } }
onMounted(() => { load(); verify() })
</script>
