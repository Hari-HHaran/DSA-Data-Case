<template>
  <span class="pill" :class="`tone-${meta.tone}`"><component :is="icon" :size="12" aria-hidden="true" />{{ label || meta.label }}</span>
</template>
<script setup>
import { computed } from 'vue'
import { AlertTriangle, Check, Circle, Clock, Eye, Pause, Pencil, Send, ShieldCheck, Sparkles, User, X } from 'lucide-vue-next'
import { statusMeta } from '@/utils/format'
const props = defineProps({ status: String, label: String })
const meta = computed(() => statusMeta(props.status))
const icons = { pencil: Pencil, send: Send, check: Check, clock: Clock, alert: AlertTriangle, x: X, shield: ShieldCheck, pause: Pause, sparkle: Sparkles, eye: Eye, user: User }
const icon = computed(() => icons[meta.value.icon] || Circle)
</script>
