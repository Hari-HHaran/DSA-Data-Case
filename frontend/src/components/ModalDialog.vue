<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="open" class="backdrop" @click.self="$emit('close')" @keydown.esc="$emit('close')">
        <div class="dialog card-x" role="dialog" aria-modal="true" :aria-label="title" :style="{ maxWidth: width }" ref="dlg" tabindex="-1">
          <div class="card-x-head"><h2>{{ title }}</h2><button class="btn btn-ghost btn-sm" type="button" aria-label="Close" @click="$emit('close')"><X :size="16" /></button></div>
          <div class="card-x-body"><slot /></div>
          <div v-if="$slots.footer" class="foot"><slot name="footer" /></div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
<script setup>
import { nextTick, ref, watch } from 'vue'
import { X } from 'lucide-vue-next'
const props = defineProps({ open: Boolean, title: String, width: { type: String, default: '560px' } })
defineEmits(['close'])
const dlg = ref(null)
watch(() => props.open, async (v) => { if (v) { await nextTick(); dlg.value?.focus() } })
</script>
<style scoped>
.backdrop { position: fixed; inset: 0; background: rgba(16, 28, 53, .45); display: flex; align-items: center; justify-content: center; z-index: 90; padding: 1rem; }
.dialog { width: 100%; max-height: 90vh; overflow: auto; box-shadow: var(--shadow-2); outline: none; }
.foot { padding: .8rem 1.1rem; border-top: 1px solid var(--border); display: flex; justify-content: flex-end; gap: .5rem; }
</style>
