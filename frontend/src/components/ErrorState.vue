<template>
  <div class="callout err" role="alert">
    <AlertTriangle :size="18" aria-hidden="true" />
    <div class="flex-grow-1">
      <strong>{{ title || 'Something went wrong' }}</strong>
      <div>{{ error?.message || error }}</div>
      <ul v-if="error?.problems?.length" class="mb-0 mt-1 ps-3"><li v-for="p in error.problems" :key="p">{{ p }}</li></ul>
    </div>
    <button v-if="retry" class="btn btn-light btn-sm" type="button" @click="retry"><RotateCw :size="14" /> Retry</button>
  </div>
</template>
<script setup>
import { AlertTriangle, RotateCw } from 'lucide-vue-next'
defineProps({ error: [Object, String], title: String, retry: Function })
</script>
