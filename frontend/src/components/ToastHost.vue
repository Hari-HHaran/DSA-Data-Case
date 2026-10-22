<template>
  <div class="toasts" aria-live="polite" role="status">
    <TransitionGroup name="fade">
      <div v-for="t in toast.items" :key="t.id" class="toast-x" :class="`t-${t.tone}`">
        <component :is="t.tone === 'error' ? AlertTriangle : t.tone === 'info' ? Info : CheckCircle2" :size="17" aria-hidden="true" />
        <span>{{ t.message }}</span>
        <button type="button" aria-label="Dismiss" @click="toast.dismiss(t.id)"><X :size="15" /></button>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup>
import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-vue-next'
import { useToast } from '@/stores/toast'
const toast = useToast()
</script>

<style scoped>
.toasts { position: fixed; right: 1rem; bottom: 1rem; display: flex; flex-direction: column; gap: .5rem; z-index: 100; max-width: min(440px, calc(100vw - 2rem)); }
.toast-x { display: flex; gap: .6rem; align-items: flex-start; background: var(--navy); color: #fff; padding: .7rem .85rem; border-radius: 10px; box-shadow: var(--shadow-2); font-size: .85rem; }
.toast-x button { margin-left: auto; background: none; border: none; color: #9fb0cf; padding: 0; }
.t-success svg:first-child { color: #4ade80; }
.t-error { background: #7f1d1d; }
.t-info svg:first-child { color: #93c5fd; }
</style>
