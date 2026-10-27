<template>
  <div class="page">
    <PageHeader title="SAP & email status" eyebrow="Setup" subtitle="What has been sent to SAP, what failed, and the Teams/Outlook messages people were sent.">
      <button class="btn btn-light" type="button" @click="load"><RotateCw :size="15" /> Refresh</button>
    </PageHeader>
    <ul class="nav nav-tabs mb-3">
      <li class="nav-item"><button class="nav-link" :class="{ active: tab === 'sap' }" @click="tab = 'sap'">SAP Business One</button></li>
      <li class="nav-item"><button class="nav-link" :class="{ active: tab === 'm365' }" @click="tab = 'm365'; loadOutbox()">Teams &amp; Outlook messages</button></li>
    </ul>
    <ErrorState v-if="error" :error="error" :retry="load" />
    <template v-if="tab === 'sap' && s">
      <div class="callout mb-3" style="background:#f3e8ff;color:#581c87"><Plug :size="18" /><div><strong>Demo mode.</strong> No real SAP system is connected, so records are created in a simulated SAP.</div></div>
      <div class="grid grid-kpi mb-3">
        <KpiTile label="Records created in SAP" :value="s.mapped_records" :icon="Database" tone="success" />
        <KpiTile label="Sent successfully" :value="s.counts.SUCCESS || 0" :icon="CheckCircle2" tone="success" />
        <KpiTile label="Failed (can try again)" :value="s.counts.FAILED || 0" :icon="AlertTriangle" tone="error" />
        <KpiTile label="Waiting to be sent" :value="s.awaiting_sync" :icon="Hourglass" tone="warning" />
      </div>
      <div class="mb-3">
        <section class="card-x">
          <div class="card-x-head"><h2>Recently sent to SAP</h2><span class="small text-muted-2">Trying again never creates a second copy</span></div>
          <div class="table-responsive"><table class="table table-hover">
            <thead><tr><th>Request</th><th>What was sent</th><th>Result</th><th>Tries</th><th>SAP code</th><th>When</th></tr></thead>
            <tbody><tr v-for="j in s.jobs" :key="j.id" @click="$router.push(`/mdm/requests/${j.request_id}`)">
              <td class="mono small">{{ j.request_number }}</td><td class="small">{{ humanize(j.operation) }} {{ humanize(j.object_type).toLowerCase() }}</td>
              <td><span class="pill" :class="{ SUCCESS: 'tone-success', FAILED: 'tone-error', PENDING: 'tone-warning' }[j.status]">{{ { SUCCESS: 'Done', FAILED: 'Failed', PENDING: 'Waiting' }[j.status] || j.status.toLowerCase() }}</span></td>
              <td class="num">{{ j.attempts }}</td><td class="mono small">{{ j.sap_key || '—' }}</td><td class="small text-muted-2">{{ relTime(j.updated_at) }}</td></tr></tbody></table></div>
        </section>
      </div>
      <section class="card-x">
        <div class="card-x-head"><h2>Detailed log</h2><span class="small text-muted-2">For troubleshooting</span></div>
        <div class="table-responsive" style="max-height: 360px"><table class="table table-sm"><tbody>
          <tr v-for="l in s.logs" :key="l.id"><td class="small text-muted-2 num" style="width:170px">{{ fmtDate(l.created_at, true) }}</td>
            <td style="width:70px"><span class="pill" :class="{ INFO: 'tone-info', WARN: 'tone-warning', ERROR: 'tone-error' }[l.level]">{{ { INFO: 'Info', WARN: 'Warning', ERROR: 'Error' }[l.level] || l.level }}</span></td><td class="small">{{ l.message }}</td></tr>
        </tbody></table></div>
      </section>
    </template>
    <template v-if="tab === 'm365'">
      <div class="callout warn mb-3"><MailWarning :size="18" /><div><strong>Demo mode: these Teams and Outlook messages were not really sent.</strong> In-app notifications (the bell at the top) work for real.</div></div>
      <div class="filters-row mb-3">
        <button v-for="c in ['', 'MOCK_TEAMS', 'MOCK_OUTLOOK']" :key="c" class="chip" :class="{ on: channel === c }" type="button" @click="channel = c; loadOutbox()">
          {{ c ? (c === 'MOCK_TEAMS' ? 'Teams' : 'Outlook') : 'All' }}</button>
      </div>
      <section class="card-x">
        <LoadingBlock v-if="!outbox" class="p-3" />
        <div v-else class="table-responsive"><table class="table">
          <thead><tr><th>When</th><th>Sent by</th><th>To</th><th>About</th><th>Message</th><th>Status</th></tr></thead>
          <tbody><tr v-for="n in outbox.items" :key="n.id"><td class="small text-muted-2 num">{{ fmtDate(n.created_at, true) }}</td>
            <td><span class="pill tag-mock">{{ n.channel === 'MOCK_TEAMS' ? 'Teams' : 'Outlook' }}</span></td><td class="small">{{ n.recipient.name }}</td>
            <td class="small">{{ eventLabel(n.event_type) }}</td><td class="small"><strong>{{ n.title }}</strong><div class="text-muted-2">{{ n.body }}</div></td>
            <td><span class="pill tone-neutral">{{ n.delivery_status === 'MOCK_QUEUED' ? 'Not sent (demo)' : humanize(n.delivery_status) }}</span></td></tr></tbody></table></div>
      </section>
    </template>
  </div>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import { AlertTriangle, CheckCircle2, Database, Hourglass, MailWarning, Plug, RotateCw } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import KpiTile from '@/components/KpiTile.vue'
import ErrorState from '@/components/ErrorState.vue'
import LoadingBlock from '@/components/LoadingBlock.vue'
import { get, put } from '@/api/client'
import { useAuth } from '@/stores/auth'
import { useToast } from '@/stores/toast'
import { eventLabel, fmtDate, humanize, relTime } from '@/utils/format'

const auth = useAuth()
const toast = useToast()
const tab = ref('sap')
const s = ref(null)
const outbox = ref(null)
const channel = ref('')
const error = ref(null)
async function load() { error.value = null; try { s.value = await get('/api/sap/status') } catch (e) { error.value = e } }
async function loadOutbox() { try { outbox.value = await get('/api/notifications/outbox', { channel: channel.value || undefined, page_size: 100 }) } catch (e) { error.value = e } }
async function setFail(n) { try { await put('/api/sap/mock-failure', { value: n }); toast.push(n ? 'The next SAP call will fail (demo)' : 'Back to normal', 'info'); load() } catch (e) { toast.error(e) } }
onMounted(load)
</script>
