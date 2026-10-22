<template>
  <span v-if="state && state !== 'N/A'" class="pill" :class="tone"><component :is="icon" :size="11" aria-hidden="true" />{{ label }}</span>
</template>
<script setup>
import { computed } from 'vue'
import { AlarmClock, Clock, CheckCircle2 } from 'lucide-vue-next'
const props = defineProps({ state: String })
const tone = computed(() => ({ OVERDUE: 'tone-error', DUE_SOON: 'tone-warning', ON_TRACK: 'tone-success' }[props.state]))
const label = computed(() => ({ OVERDUE: 'Overdue', DUE_SOON: 'Due < 24h', ON_TRACK: 'On track' }[props.state]))
const icon = computed(() => ({ OVERDUE: AlarmClock, DUE_SOON: Clock, ON_TRACK: CheckCircle2 }[props.state]))
</script>
