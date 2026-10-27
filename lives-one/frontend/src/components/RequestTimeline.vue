<template>
  <div>
    <ol class="tl" aria-label="Where this request is">
      <li v-for="s in stages" :key="s.status" :class="s.state">
        <span class="dot" aria-hidden="true"><Check v-if="s.state === 'done'" :size="12" /><AlertTriangle v-else-if="s.state === 'exception'" :size="12" /></span>
        <div class="lbl"><strong>{{ s.label }}</strong><small>{{ s.at ? fmtDate(s.at, true) : s.state === 'current' ? 'Now' : '' }}</small></div>
        <span class="visually-hidden">{{ s.state }}</span>
      </li>
    </ol>
    <div v-if="tasks?.length" class="tasks mt-3">
      <div class="small-label mb-2">Who needs to approve<template v-if="tasks[0].cycle > 1"> (round {{ tasks[0].cycle }})</template></div>
      <div v-for="stage in stageGroups" :key="stage.n" class="stage-row">
        <span class="stage-n">Step {{ stage.n }}<small v-if="stage.items.length > 1">at the same time</small></span>
        <div class="d-flex flex-wrap gap-2 flex-grow-1">
          <div v-for="t in stage.items" :key="t.id" class="task" :class="t.status.toLowerCase()">
            <div class="d-flex justify-content-between gap-2 align-items-start"><strong>{{ t.step_name }}</strong><StatusBadge :status="t.status" /></div>
            <small v-if="t.decided_by">{{ t.decided_by.name }} · {{ fmtDate(t.decided_at, true) }}</small>
            <small v-else-if="t.status === 'PENDING'">Due {{ fmtDate(t.due_at, true) }} <SlaPill :state="t.sla_state" /></small>
            <small v-else-if="t.status === 'WAITING'">Starts after step {{ stage.n - 1 }}</small>
            <small v-if="t.escalated_at" class="text-danger">Escalated {{ fmtDate(t.escalated_at) }}</small>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup>
import { computed } from 'vue'
import { AlertTriangle, Check } from 'lucide-vue-next'
import StatusBadge from './StatusBadge.vue'
import SlaPill from './SlaPill.vue'
import { fmtDate } from '@/utils/format'
const props = defineProps({ stages: Array, tasks: Array })
const stageGroups = computed(() => {
  const g = {}
  for (const t of props.tasks || []) (g[t.stage] ||= []).push(t)
  return Object.entries(g).map(([n, items]) => ({ n: Number(n), items }))
})
</script>
<style scoped>
.tl { list-style: none; display: flex; padding: 0; margin: 0; overflow-x: auto; gap: 0; }
.tl li { flex: 1; min-width: 104px; position: relative; padding-top: 4px; }
.tl li::before { content: ''; position: absolute; top: 14px; left: 0; right: 0; height: 2px; background: var(--border); }
.tl li:first-child::before { left: 50%; }
.tl li:last-child::before { right: 50%; }
.tl li.done::before { background: var(--success); }
.dot { position: relative; z-index: 1; width: 22px; height: 22px; border-radius: 50%; background: var(--surface); border: 2px solid var(--border-strong); display: flex; align-items: center; justify-content: center; margin: 0 auto; color: #fff; }
.done .dot { background: var(--success); border-color: var(--success); }
.current .dot { border-color: var(--accent); box-shadow: 0 0 0 5px rgba(99, 102, 241, .18); background: var(--accent); }
.exception .dot { background: var(--error); border-color: var(--error); }
.lbl { text-align: center; margin-top: .4rem; font-size: .74rem; line-height: 1.25; padding: 0 .2rem; }
.lbl strong { display: block; font-weight: 600; color: var(--text-2); }
.current .lbl strong { color: var(--accent); }
.exception .lbl strong { color: var(--error); }
.lbl small { color: var(--muted); font-size: .68rem; }
.stage-row { display: flex; gap: .8rem; align-items: stretch; margin-bottom: .55rem; }
.stage-n { width: 64px; flex: none; font-size: .75rem; font-weight: 700; color: var(--text-2); padding-top: .5rem; }
.stage-n small { display: block; font-weight: 500; color: var(--muted); }
.task { border: 1px solid var(--border); border-radius: 12px; padding: .55rem .7rem; min-width: 230px; flex: 1; font-size: .83rem; display: flex; flex-direction: column; gap: .2rem; }
.task small { color: var(--muted); font-size: .75rem; }
.task.approved { border-color: #b7e2c6; background: #f6fcf8; }
.task.pending { border-color: #f3d6a4; background: #fffbf3; }
</style>
