<template>
  <div class="bell-wrap" ref="root">
    <button class="btn btn-ghost bell" type="button" @click="open = !open" :aria-label="`Notifications, ${notes.unread} unread`" :aria-expanded="open">
      <Bell :size="18" />
      <span v-if="notes.unread" class="dot num">{{ notes.unread > 99 ? '99+' : notes.unread }}</span>
    </button>
    <div v-if="open" class="panel card-x" role="dialog" aria-label="Notifications">
      <div class="head">
        <strong>Notifications</strong>
        <button class="link-btn small" type="button" :disabled="!notes.unread" @click="notes.markAll()">Mark all read</button>
      </div>
      <div v-if="!notes.items.length" class="empty py-4">No notifications yet.</div>
      <ul v-else class="list">
        <li v-for="n in notes.items" :key="n.id" :class="{ unread: !n.read }">
          <button type="button" @click="go(n)">
            <span class="ic" :class="toneOf(n.event_type)" aria-hidden="true"><component :is="iconOf(n.event_type)" :size="15" /></span>
            <span class="txt"><strong>{{ n.title }}</strong><small>{{ n.body }}</small><small class="when">{{ relTime(n.created_at) }}</small></span>
          </button>
        </li>
      </ul>
      <div class="foot">In-app notifications are live. Teams/Outlook copies go to a <RouterLink to="/admin/integrations" @click="open = false">mock outbox</RouterLink> (not sent).</div>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { AlertTriangle, Bell, CheckCircle2, Clock, Inbox, Send, Siren, Undo2, XCircle, Lightbulb } from 'lucide-vue-next'
import { useNotifications } from '@/stores/notifications'
import { relTime } from '@/utils/format'

const notes = useNotifications()
const router = useRouter()
const open = ref(false)
const root = ref(null)
const ICONS = { APPROVAL_ASSIGNED: Inbox, SLA_REMINDER: Clock, ESCALATION: Siren, RETURNED_FOR_CHANGES: Undo2, REQUEST_REJECTED: XCircle,
  SAP_CREATED: CheckCircle2, SAP_FAILED: AlertTriangle, REQUEST_SUBMITTED: Send, APPROVAL_COMPLETED: CheckCircle2, MDM_VERIFICATION_READY: Inbox, FOLLOWUP_ASSIGNED: Lightbulb }
const TONES = { SLA_REMINDER: 'tone-warning', ESCALATION: 'tone-error', RETURNED_FOR_CHANGES: 'tone-warning', REQUEST_REJECTED: 'tone-error',
  SAP_CREATED: 'tone-success', SAP_FAILED: 'tone-error', APPROVAL_COMPLETED: 'tone-success' }
const iconOf = (t) => ICONS[t] || Bell
const toneOf = (t) => TONES[t] || 'tone-info'
async function go(n) {
  open.value = false
  if (!n.read) notes.markOne(n.id)
  if (n.link) router.push(n.link)
}
function onDoc(e) { if (root.value && !root.value.contains(e.target)) open.value = false }
onMounted(() => document.addEventListener('click', onDoc))
onBeforeUnmount(() => document.removeEventListener('click', onDoc))
</script>

<style scoped>
.bell-wrap { position: relative; }
.bell { position: relative; padding: .4rem .5rem; }
.dot { position: absolute; top: 1px; right: 0; background: #ec4899; color: #fff; border-radius: 999px; font-size: .62rem; font-weight: 700; padding: 0 .3rem; min-width: 16px; line-height: 16px; }
.panel { position: absolute; right: 0; top: calc(100% + 6px); width: 380px; max-width: 92vw; box-shadow: var(--shadow-2); z-index: 50; }
.head { display: flex; justify-content: space-between; align-items: center; padding: .7rem .9rem; border-bottom: 1px solid var(--border); }
.list { list-style: none; margin: 0; padding: .25rem; max-height: 420px; overflow: auto; }
.list li button { width: 100%; display: flex; gap: .65rem; text-align: left; border: none; background: none; padding: .6rem; border-radius: 12px; }
.list li button:hover { background: var(--surface-2); }
.list li.unread button { background: #f5f5ff; }
.ic { width: 28px; height: 28px; border-radius: 8px; display: inline-flex; align-items: center; justify-content: center; flex: none; }
.txt { display: flex; flex-direction: column; min-width: 0; font-size: .82rem; }
.txt small { color: var(--text-2); font-size: .76rem; }
.txt .when { color: var(--muted); margin-top: 2px; }
.foot { font-size: .72rem; color: var(--muted); padding: .55rem .9rem; border-top: 1px solid var(--border); }
</style>
