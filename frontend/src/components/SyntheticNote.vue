<template>
  <div class="callout neutral synth">
    <FlaskConical :size="16" aria-hidden="true" />
    <div><strong>Synthetic demonstration data.</strong> <slot>Generated with a fixed seed across five illustrative country locations. Not Lives Group data; patterns were planted so the analytics have something real to find, and every number shown is computed from that data.</slot></div>
  </div>
</template>
<script setup>
import { FlaskConical } from 'lucide-vue-next'
</script>
<style scoped>
.synth { font-size: .8rem; }
</style>
