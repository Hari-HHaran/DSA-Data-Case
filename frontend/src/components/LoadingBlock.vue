<template>
  <div class="d-flex flex-column gap-2" aria-busy="true" aria-label="Loading">
    <div v-for="i in rows" :key="i" class="skeleton" :style="{ height: height + 'px', width: i === rows ? '65%' : '100%' }" />
  </div>
</template>
<script setup>
defineProps({ rows: { type: Number, default: 4 }, height: { type: Number, default: 18 } })
</script>
