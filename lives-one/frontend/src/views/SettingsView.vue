<template>
  <div class="page">
    <PageHeader title="Settings" eyebrow="Account" :subtitle="isAdmin ? 'Your details, and the settings that control how the app behaves for everyone.' : 'Your details in the app.'" />
    <div class="grid" :class="{ 'grid-main-side': isAdmin }">
      <section v-if="isAdmin" class="card-x">
        <div class="card-x-head"><h2>App settings</h2><span class="small text-muted-2">Changes apply to everyone straight away</span></div>
        <div class="card-x-body">
          <div v-for="st in settings.filter((x) => EDITABLE.includes(x.key))" :key="st.key" class="setting">
            <div class="flex-grow-1"><strong>{{ LABELS[st.key] || st.key }}</strong><div class="small text-muted-2">{{ HELP[st.key] || st.description }}</div></div>
            <div class="d-flex gap-1 align-items-center" style="min-width: 180px">
              <input v-model="draft[st.key]" class="form-control form-control-sm" :aria-label="LABELS[st.key]" />
              <button class="btn btn-light btn-sm" type="button" :disabled="String(draft[st.key]) === String(st.value)" @click="save(st)">Save</button>
            </div>
          </div>
        </div>
      </section>
      <section class="card-x profile">
        <div class="card-x-head"><h3>Your profile</h3></div>
        <div class="card-x-body"><dl class="kv small"><dt>Name</dt><dd>{{ auth.user?.name }}</dd><dt>Job title</dt><dd>{{ auth.user?.title }}</dd>
          <dt>Your roles</dt><dd>{{ auth.roles.map((r) => ROLE_LABELS[r]).join(', ') }}</dd>
          <dt>Company</dt><dd>{{ auth.user?.entity_code || '—' }}</dd><dt>Country</dt><dd>{{ auth.user?.country_code ? ref_.countryName(auth.user.country_code) : '—' }}</dd></dl></div>
      </section>
    </div>
  </div>
</template>
<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import { get, put } from '@/api/client'
import { useAuth } from '@/stores/auth'
import { useToast } from '@/stores/toast'
import { useReference } from '@/stores/reference'
import { ROLE_LABELS } from '@/utils/format'

const auth = useAuth()
const toast = useToast()
const ref_ = useReference()
const isAdmin = computed(() => auth.has('ADMIN'))
const settings = ref([])
const draft = reactive({})
const EDITABLE = ['duplicate.likely_threshold', 'duplicate.review_threshold', 'sla.escalate_after_overdue_days', 'sla.total_turnaround_target_days', 'forecast.rolling_window']
const LABELS = { 'duplicate.likely_threshold': 'Score for "probably a duplicate" (0–100)', 'duplicate.review_threshold': 'Score for "worth a second look" (0–100)',
  'sla.escalate_after_overdue_days': 'Escalate after this many days overdue', 'sla.total_turnaround_target_days': 'Target days to finish a request',
  'forecast.rolling_window': 'Months used by the old forecast method' }
const HELP = { 'duplicate.likely_threshold': 'Above this, people are warned that the record probably already exists.',
  'duplicate.review_threshold': 'Above this, people are asked to take a quick look before sending their request.',
  'sla.escalate_after_overdue_days': "If an approval is this many working days late, it is passed up to the approver's manager.",
  'sla.total_turnaround_target_days': 'Used to show whether requests are finishing on time.',
  'forecast.rolling_window': 'Only used to compare the new sales forecast with the old method.' }
async function load() { settings.value = await get('/api/config/settings'); for (const s of settings.value) draft[s.key] = s.value }
async function save(st) {
  try { await put(`/api/config/settings/${st.key}`, { value: isNaN(Number(draft[st.key])) ? draft[st.key] : Number(draft[st.key]) }); toast.push('Saved'); load() } catch (e) { toast.error(e) }
}
onMounted(() => { ref_.load(); if (isAdmin.value) load() })
</script>
<style scoped>
.setting { display: flex; gap: 1rem; align-items: center; padding: .75rem 0; border-bottom: 1px solid var(--border); flex-wrap: wrap; }
.setting:last-child { border-bottom: none; }
.profile { max-width: 640px; }
</style>
