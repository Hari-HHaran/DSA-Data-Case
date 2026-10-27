<template>
  <ol class="audit">
    <li v-for="e in events" :key="e.id">
      <span class="ic" :class="toneOf(e.event_type)" aria-hidden="true"><component :is="iconOf(e.event_type)" :size="13" /></span>
      <div class="flex-grow-1 min-w-0">
        <div class="d-flex justify-content-between gap-2 flex-wrap">
          <span><strong>{{ eventLabel(e.event_type) }}</strong>
            <span v-if="e.from_status && e.to_status && e.from_status !== e.to_status" class="text-muted-2 small"> · now {{ statusMeta(e.to_status).label.toLowerCase() }}</span>
            <RouterLink v-if="showRef && e.request_id" :to="`/mdm/requests/${e.request_id}`" class="small ms-1">{{ e.entity_ref }}</RouterLink>
            <span v-else-if="showRef && e.entity_ref" class="small ms-1 text-muted-2">{{ e.entity_ref }}</span>
          </span>
          <span class="small text-muted-2 num">{{ fmtDate(e.created_at, true) }}</span>
        </div>
        <div class="small"><span class="text-muted-2">{{ e.actor ? `${e.actor.name} (${e.actor.title})` : 'System' }}</span><template v-if="e.comment"> — {{ e.comment }}</template></div>
        <div v-if="e.changes && changeList(e).length" class="changes">
          <span v-for="c in changeList(e)" :key="c" class="pill tone-neutral">{{ c }}</span>
        </div>
        <div v-if="showHash" class="mono text-muted-2 small truncate" :title="e.hash">#{{ e.hash.slice(0, 16) }}… ← {{ e.prev_hash.slice(0, 8) }}</div>
      </div>
    </li>
  </ol>
</template>
<script setup>
import { AlertTriangle, CheckCircle2, Circle, Clock, FilePen, GitBranch, Send, Siren, Undo2, XCircle, Database, Recycle, Search } from 'lucide-vue-next'
import { eventLabel, fmtDate, humanize, statusMeta } from '@/utils/format'
defineProps({ events: Array, showRef: Boolean, showHash: Boolean })
const map = { STATUS_SUBMITTED: [Send, 'tone-info'], ROUTED: [GitBranch, 'tone-info'], TASK_APPROVED: [CheckCircle2, 'tone-success'], TASK_REJECTED: [XCircle, 'tone-error'],
  TASK_CHANGES_REQUESTED: [Undo2, 'tone-warning'], RETURNED_FOR_CHANGES: [Undo2, 'tone-warning'], REQUEST_REJECTED: [XCircle, 'tone-error'],
  SAP_CREATION_COMPLETED: [Database, 'tone-success'], SAP_CREATION_FAILED: [AlertTriangle, 'tone-error'], SLA_REMINDER: [Clock, 'tone-warning'],
  ESCALATED: [Siren, 'tone-error'], DRAFT_UPDATED: [FilePen, 'tone-neutral'], DUPLICATE_PREVENTED: [Recycle, 'tone-success'], DUPLICATE_CHECK_RUN: [Search, 'tone-neutral'],
  SUBMISSION_BLOCKED: [AlertTriangle, 'tone-warning'] }
const iconOf = (t) => (map[t] || [Circle])[0]
const toneOf = (t) => (map[t] || [null, 'tone-neutral'])[1]
function changeList(e) {
  const c = e.changes || {}
  if (c.steps) return c.steps.map((s) => `Step ${s.stage}: ${s.name}`)
  if (c.sap_key) return [`SAP code ${c.sap_key}`, c.mock ? 'simulated' : 'entered by hand']
  return Object.entries(c).filter(([k]) => !['errors', 'candidates', 'before', 'after', 'payload_keys'].includes(k))
    .filter(([, v]) => v === null || typeof v !== 'object' || 'to' in v).slice(0, 6) // skip raw data, keep readable changes
    .map(([k, v]) => (v && typeof v === 'object' ? `${humanize(k)}: ${v.from ?? '(empty)'} → ${v.to ?? '(empty)'}` : `${humanize(k)}: ${v ?? '(empty)'}`))
}
</script>
<style scoped>
.audit { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: .85rem; }
.audit li { display: flex; gap: .7rem; font-size: .86rem; }
.ic { width: 26px; height: 26px; border-radius: 7px; display: inline-flex; align-items: center; justify-content: center; flex: none; }
.changes { display: flex; flex-wrap: wrap; gap: .25rem; margin-top: .25rem; }
.changes .pill { font-weight: 500; white-space: normal; }
.min-w-0 { min-width: 0; }
</style>
