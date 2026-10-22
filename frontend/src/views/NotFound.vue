<template>
  <div class="page"><EmptyState title="Page not found" text="The page you are looking for does not exist."><RouterLink to="/" class="btn btn-primary btn-sm">Back to Command Centre</RouterLink></EmptyState></div>
</template>
<script setup>
import EmptyState from '@/components/EmptyState.vue'
</script>
