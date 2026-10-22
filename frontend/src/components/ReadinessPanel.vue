<template>
  <aside class="card-x ready" aria-label="Submission readiness">
    <div class="card-x-head">
      <h3>Submission readiness</h3>
      <span class="pill" :class="stateTone"><component :is="stateIcon" :size="12" /> {{ stateLabel }}</span>
    </div>
    <div class="card-x-body">
      <div class="bar" role="progressbar" :aria-valuenow="pct" aria-valuemin="0" aria-valuemax="100" :aria-label="`${pct}% of required fields complete`">
        <span :style="{ width: pct + '%' }" />
      </div>
      <div class="small text-muted-2 mt-1 num">{{ readiness?.required_complete ?? 0 }} / {{ readiness?.required_total ?? 0 }} required fields</div>
      <ul class="checks">
        <li v-for="c in readiness?.checks || []" :key="c.key" :class="c.passed ? 'ok' : 'todo'">
          <component :is="c.passed ? CheckCircle2 : CircleDashed" :size="16" aria-hidden="true" />
          <div><strong>{{ c.label }}</strong><small>{{ c.detail }}</small></div>
          <span class="visually-hidden">{{ c.passed ? 'passed' : 'outstanding' }}</span>
        </li>
      </ul>
      <div v-if="outstanding.length" class="mt-2">
        <div class="small-label mb-1">Still needed</div>
        <ul class="todo-list">
          <li v-for="[k, msg] in outstanding" :key="k"><button type="button" class="link-btn text-start" @click="$emit('focus', k)">{{ msg }}</button></li>
        </ul>
      </div>
      <template v-if="route?.length">
        <div class="divider" />
        <div class="small-label mb-2">Who will approve — and why</div>
        <ol class="route">
          <li v-for="s in route" :key="s.step_id">
            <span class="stage num">{{ s.stage }}</span>
            <div><strong>{{ s.name }}</strong><small>{{ s.reason }}</small></div>
          </li>
          <li><span class="stage">✓</span><div><strong>MDM final verification → SAP B1</strong><small>Always the last step</small></div></li>
        </ol>
        <p class="form-text mb-0">Same stage number = reviewed in parallel. Routing is computed from configurable rules.</p>
      </template>
    </div>
  </aside>
</template>
<script setup>
import { computed } from 'vue'
import { AlertTriangle, CheckCircle2, CircleDashed, Search } from 'lucide-vue-next'
const props = defineProps({ readiness: Object, route: Array })
defineEmits(['focus'])
const pct = computed(() => props.readiness?.completion_pct ?? 0)
const state = computed(() => props.readiness?.state || 'INCOMPLETE')
const stateLabel = computed(() => ({ COMPLETE: 'Ready to submit', INCOMPLETE: 'Incomplete', REQUIRES_REVIEW: 'Requires review' }[state.value]))
const stateTone = computed(() => ({ COMPLETE: 'tone-success', INCOMPLETE: 'tone-warning', REQUIRES_REVIEW: 'tone-info' }[state.value]))
const stateIcon = computed(() => ({ COMPLETE: CheckCircle2, INCOMPLETE: AlertTriangle, REQUIRES_REVIEW: Search }[state.value]))
const outstanding = computed(() => Object.entries(props.readiness?.errors || {}).slice(0, 8))
</script>
<style scoped>
.ready { position: sticky; top: calc(var(--topbar-h) + 1rem); }
.bar { height: 8px; background: var(--surface-2); border-radius: 99px; overflow: hidden; }
.bar span { display: block; height: 100%; background: linear-gradient(90deg, var(--accent), var(--teal)); border-radius: 99px; transition: width .25s ease; }
.checks { list-style: none; padding: 0; margin: .9rem 0 0; display: flex; flex-direction: column; gap: .55rem; }
.checks li { display: flex; gap: .55rem; align-items: flex-start; font-size: .84rem; }
.checks li small { display: block; color: var(--muted); font-size: .76rem; }
.checks li.ok svg { color: var(--success); }
.checks li.todo svg { color: var(--muted); }
.todo-list { padding-left: 1rem; margin: 0; font-size: .8rem; }
.todo-list .link-btn { font-weight: 500; color: #b45309; }
.route { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: .5rem; }
.route li { display: flex; gap: .6rem; font-size: .83rem; }
.route small { display: block; color: var(--muted); font-size: .75rem; }
.stage { width: 22px; height: 22px; border-radius: 6px; background: var(--accent-soft); color: var(--accent); font-weight: 700; font-size: .75rem; display: inline-flex; align-items: center; justify-content: center; flex: none; }
</style>
