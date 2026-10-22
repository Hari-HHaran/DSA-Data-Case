<template>
  <div class="empty">
    <div class="ic"><component :is="icon || Inbox" :size="20" aria-hidden="true" /></div>
    <div class="fw-semibold text-body">{{ title }}</div>
    <div v-if="text" class="small mt-1">{{ text }}</div>
    <div class="mt-3"><slot /></div>
  </div>
</template>
<script setup>
import { Inbox } from 'lucide-vue-next'
defineProps({ title: String, text: String, icon: Object })
</script>
