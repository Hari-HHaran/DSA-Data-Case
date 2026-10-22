<template>
  <div class="page">
    <PageHeader title="SAP & notification integrations" eyebrow="Administration" subtitle="Integration status, job history and logs. Both adapters run in clearly-labelled mock mode in this prototype — no SAP B1 system or Microsoft 365 tenant is contacted.">
      <button class="btn btn-light" type="button" @click="load"><RotateCw :size="15" /> Refresh</button>
    </PageHeader>
    <ul class="nav nav-tabs mb-3">
      <li class="nav-item"><button class="nav-link" :class="{ active: tab === 'sap' }" @click="tab = 'sap'">SAP Business One</button></li>
      <li class="nav-item"><button class="nav-link" :class="{ active: tab === 'm365' }" @click="tab = 'm365'; loadOutbox()">Teams / Outlook outbox</button></li>
    </ul>
    <ErrorState v-if="error" :error="error" :retry="load" />
    <template v-if="tab === 'sap' && s">
      <div class="callout mb-3" style="background:#f3e8ff;color:#581c87"><Plug :size="18" /><div><strong>Adapter mode: {{ s.adapter_mode }}.</strong> {{ s.adapter_note }}</div></div>
      <div class="grid grid-kpi mb-3">
        <KpiTile label="Records created (mapped)" :value="s.mapped_records" :icon="Database" tone="success" />
        <KpiTile label="Successful jobs" :value="s.counts.SUCCESS || 0" :icon="CheckCircle2" tone="success" />
        <KpiTile label="Failed jobs (retryable)" :value="s.counts.FAILED || 0" :icon="AlertTriangle" tone="error" />
        <KpiTile label="Awaiting SAP sync" :value="s.awaiting_sync" :icon="Hourglass" tone="warning" />
      </div>
      <div class="grid grid-main-side mb-3">
        <section class="card-x">
          <div class="card-x-head"><h2>Recent sync jobs</h2><span class="small text-muted-2">Idempotency key per request cycle — retries never create a second record</span></div>
          <div class="table-responsive"><table class="table table-hover">
            <thead><tr><th>Request</th><th>Operation → object</th><th>Status</th><th>Attempts</th><th>SAP key</th><th>Updated</th></tr></thead>
            <tbody><tr v-for="j in s.jobs" :key="j.id" @click="$router.push(`/mdm/requests/${j.request_id}`)">
              <td class="mono small">{{ j.request_number }}</td><td class="small">{{ j.operation }} → <span class="mono">{{ j.object_type }}</span></td>
              <td><span class="pill" :class="{ SUCCESS: 'tone-success', FAILED: 'tone-error', PENDING: 'tone-warning' }[j.status]">{{ j.status.toLowerCase() }}</span></td>
              <td class="num">{{ j.attempts }}</td><td class="mono small">{{ j.sap_key || '—' }}</td><td class="small text-muted-2">{{ relTime(j.updated_at) }}</td></tr></tbody></table></div>
        </section>
        <div class="d-flex flex-column gap-3">
          <section v-if="auth.has('ADMIN', 'MDM_ANALYST')" class="card-x">
            <div class="card-x-head"><h3>Failure simulation (demo)</h3></div>
            <div class="card-x-body small">
              <p>Force the next mock SAP call(s) to fail to demonstrate that a failed creation is never shown as completed, and that retry is safe.</p>
              <div class="d-flex gap-2 align-items-center"><span>Next failing calls: <strong class="num">{{ s.mock_fail_next }}</strong></span>
                <button class="btn btn-light btn-sm" type="button" @click="setFail(1)">Fail next call</button>
                <button class="btn btn-ghost btn-sm" type="button" :disabled="!s.mock_fail_next" @click="setFail(0)">Reset</button></div>
            </div>
          </section>
          <section class="card-x">
            <div class="card-x-head"><h3>Before a real integration</h3></div>
            <div class="card-x-body"><ul class="small ps-3 mb-0"><li v-for="x in s.future_integration" :key="x">{{ x }}</li></ul></div>
          </section>
        </div>
      </div>
      <section class="card-x">
        <div class="card-x-head"><h2>Integration log</h2></div>
        <div class="table-responsive" style="max-height: 360px"><table class="table table-sm"><tbody>
          <tr v-for="l in s.logs" :key="l.id"><td class="small text-muted-2 num" style="width:170px">{{ fmtDate(l.created_at, true) }}</td>
            <td style="width:70px"><span class="pill" :class="{ INFO: 'tone-info', WARN: 'tone-warning', ERROR: 'tone-error' }[l.level]">{{ l.level }}</span></td><td class="small">{{ l.message }}</td></tr>
        </tbody></table></div>
      </section>
    </template>
    <template v-if="tab === 'm365'">
      <div class="callout warn mb-3"><MailWarning :size="18" /><div><strong>Mock outbox — nothing here was sent.</strong> {{ outbox?.note }} In-app notifications (the bell) are real and delivered.</div></div>
      <div class="filters-row mb-3">
        <button v-for="c in ['', 'MOCK_TEAMS', 'MOCK_OUTLOOK']" :key="c" class="chip" :class="{ on: channel === c }" type="button" @click="channel = c; loadOutbox()">
          {{ c ? (c === 'MOCK_TEAMS' ? 'Teams (mock)' : 'Outlook (mock)') : 'All channels' }}</button>
      </div>
      <section class="card-x">
        <LoadingBlock v-if="!outbox" class="p-3" />
        <div v-else class="table-responsive"><table class="table">
          <thead><tr><th>When</th><th>Channel</th><th>Recipient</th><th>Event</th><th>Message</th><th>Delivery</th></tr></thead>
          <tbody><tr v-for="n in outbox.items" :key="n.id"><td class="small text-muted-2 num">{{ fmtDate(n.created_at, true) }}</td>
            <td><span class="pill tag-mock">{{ n.channel === 'MOCK_TEAMS' ? 'Teams' : 'Outlook' }}</span></td><td class="small">{{ n.recipient.name }}</td>
            <td class="small">{{ humanize(n.event_type) }}</td><td class="small"><strong>{{ n.title }}</strong><div class="text-muted-2">{{ n.body }}</div></td>
            <td><span class="pill tone-neutral">{{ n.delivery_status === 'MOCK_QUEUED' ? 'Not sent (mock)' : n.delivery_status }}</span></td></tr></tbody></table></div>
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
import { fmtDate, humanize, relTime } from '@/utils/format'

const auth = useAuth()
const toast = useToast()
const tab = ref('sap')
const s = ref(null)
const outbox = ref(null)
const channel = ref('')
const error = ref(null)
async function load() { error.value = null; try { s.value = await get('/api/sap/status') } catch (e) { error.value = e } }
async function loadOutbox() { try { outbox.value = await get('/api/notifications/outbox', { channel: channel.value || undefined, page_size: 100 }) } catch (e) { error.value = e } }
async function setFail(n) { try { await put('/api/sap/mock-failure', { value: n }); toast.push(n ? 'The next mock SAP call will fail' : 'Failure simulation reset', 'info'); load() } catch (e) { toast.error(e) } }
onMounted(load)
</script>
