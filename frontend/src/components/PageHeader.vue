<template>
  <div class="ph">
    <div class="ph-text">
      <div v-if="eyebrow" class="small-label mb-1">{{ eyebrow }}</div>
      <h1>{{ title }} <slot name="badge" /></h1>
      <p v-if="subtitle" class="ph-sub">{{ subtitle }}</p>
    </div>
    <div class="ph-actions"><slot /></div>
  </div>
</template>
<script setup>
defineProps({ title: String, subtitle: String, eyebrow: String })
</script>
<style scoped>
.ph { display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem; margin-bottom: 1.25rem; flex-wrap: wrap; }
.ph h1 { margin: 0; display: flex; align-items: center; gap: .6rem; flex-wrap: wrap; }
.ph-sub { color: var(--muted); margin: .3rem 0 0; max-width: 760px; }
.ph-actions { display: flex; gap: .5rem; flex-wrap: wrap; }
</style>
