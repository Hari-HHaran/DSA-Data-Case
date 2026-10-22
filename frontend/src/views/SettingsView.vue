<template>
  <div class="page">
    <PageHeader title="Settings" eyebrow="Configuration" subtitle="Tunable thresholds and service levels. Values are prototype design choices — change them and the system's behaviour follows." />
    <div class="grid grid-main-side">
      <section class="card-x">
        <div class="card-x-head"><h2>Application settings</h2><span v-if="!isAdmin" class="pill tone-neutral"><Eye :size="11" /> Read-only for your role</span></div>
        <div class="card-x-body">
          <div v-for="st in settings" :key="st.key" class="setting">
            <div class="flex-grow-1"><strong>{{ LABELS[st.key] || st.key }}</strong><div class="small text-muted-2">{{ st.description }}</div>
              <div v-if="WHY[st.key]" class="small mt-1"><Info :size="12" /> {{ WHY[st.key] }}</div></div>
            <div class="d-flex gap-1 align-items-center" style="min-width: 180px">
              <input v-if="EDITABLE.includes(st.key) && isAdmin" v-model="draft[st.key]" class="form-control form-control-sm" :aria-label="LABELS[st.key]" />
              <span v-else class="mono">{{ st.value }}</span>
              <button v-if="EDITABLE.includes(st.key) && isAdmin" class="btn btn-light btn-sm" type="button" :disabled="String(draft[st.key]) === String(st.value)" @click="save(st)">Save</button>
            </div>
          </div>
        </div>
      </section>
      <div class="d-flex flex-column gap-3">
        <section class="card-x">
          <div class="card-x-head"><h3>Your profile</h3></div>
          <div class="card-x-body"><dl class="kv small"><dt>Name</dt><dd>{{ auth.user?.name }}</dd><dt>Title</dt><dd>{{ auth.user?.title }}</dd><dt>Roles</dt><dd>{{ auth.roles.map((r) => ROLE_LABELS[r]).join(', ') }}</dd>
            <dt>Entity</dt><dd>{{ auth.user?.entity_code || '—' }}</dd><dt>Country</dt><dd>{{ auth.user?.country_code || '—' }}</dd><dt>Persona</dt><dd>{{ auth.user?.persona_note }}</dd></dl></div>
        </section>
        <section class="card-x">
          <div class="card-x-head"><h3>About this prototype</h3></div>
          <div class="card-x-body small">
            <p>LIVES ONE — competition prototype for the SMU DSA Society 2026 Data Case Competition brief on Lives Group.</p>
            <ul class="ps-3 mb-2"><li>All master data, purchasing and workflow history are synthetic (fixed seed).</li><li>Five country locations are illustrative and configurable.</li>
              <li>SAP B1 and Teams/Outlook run as mock adapters.</li><li>Demo persona switching is for demonstration only and can be disabled.</li></ul>
            <p class="mb-0">Reset the demo with <code>python -m app.seed</code> in <code>backend/</code>.</p>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>
<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Eye, Info } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import { get, put } from '@/api/client'
import { useAuth } from '@/stores/auth'
import { useToast } from '@/stores/toast'
import { ROLE_LABELS } from '@/utils/format'

const auth = useAuth()
const toast = useToast()
const isAdmin = computed(() => auth.has('ADMIN'))
const settings = ref([])
const draft = reactive({})
const EDITABLE = ['duplicate.likely_threshold', 'duplicate.review_threshold', 'sla.escalate_after_overdue_days', 'sla.total_turnaround_target_days', 'forecast.rolling_window']
const LABELS = { 'duplicate.likely_threshold': 'Likely-duplicate threshold', 'duplicate.review_threshold': 'Needs-review threshold', 'sla.escalate_after_overdue_days': 'Escalate after overdue (working days)',
  'sla.total_turnaround_target_days': 'Turnaround target (working days)', 'sap.mock_fail_next': 'Mock SAP failures queued', 'analytics.window_start': 'Analysis window start',
  'analytics.window_end': 'Analysis window end', 'forecast.rolling_window': 'Baseline rolling window (months)' }
const WHY = { 'duplicate.likely_threshold': 'Set so obvious variants (abbreviations, legal suffixes, acronyms) score above it while different hospitals sharing one word stay below.',
  'duplicate.review_threshold': 'Lower band catches partial matches for a human glance without blocking.', 'forecast.rolling_window': 'Baseline mirrors the brief\'s 6–12-month approach; 6 leaves room for backtests in 12 months of data.' }
async function load() { settings.value = await get('/api/config/settings'); for (const s of settings.value) draft[s.key] = s.value }
async function save(st) {
  try { await put(`/api/config/settings/${st.key}`, { value: isNaN(Number(draft[st.key])) ? draft[st.key] : Number(draft[st.key]) }); toast.push(`${LABELS[st.key]} updated (audited)`); load() } catch (e) { toast.error(e) }
}
onMounted(load)
</script>
<style scoped>
.setting { display: flex; gap: 1rem; align-items: center; padding: .75rem 0; border-bottom: 1px solid var(--border); flex-wrap: wrap; }
.setting:last-child { border-bottom: none; }
</style>
