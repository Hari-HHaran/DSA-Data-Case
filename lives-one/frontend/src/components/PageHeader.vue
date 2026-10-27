<template>
  <div class="ph">
    <div class="ph-text">
      <div v-if="eyebrow" class="ph-eyebrow">{{ eyebrow }}</div>
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
.ph { display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem; margin: .25rem 0 1.5rem; flex-wrap: wrap; }
.ph-eyebrow { display: inline-block; background: var(--accent-soft); color: var(--accent); font-size: .72rem; font-weight: 700; letter-spacing: .04em; padding: .2rem .65rem; border-radius: 999px; margin-bottom: .5rem; }
.ph h1 { margin: 0; display: flex; align-items: center; gap: .6rem; flex-wrap: wrap; }
.ph-sub { color: var(--muted); margin: .4rem 0 0; max-width: 760px; font-size: .95rem; }
.ph-actions { display: flex; gap: .5rem; flex-wrap: wrap; }
</style>
