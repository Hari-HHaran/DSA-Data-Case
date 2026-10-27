<template>
  <div class="dyn" :class="{ wide: field.field_type === 'textarea' }">
    <label class="form-label" :for="id">
      {{ field.label }}<span v-if="required" class="req" aria-hidden="true"> *</span>
      <span v-if="required" class="visually-hidden">(required)</span>
      <span v-if="field.sensitivity === 'FINANCIAL'" class="pill tone-warning ms-1" title="Only you, Finance and the Master Data team can see this"><Lock :size="11" /> Private</span>
      <span v-if="field.is_identifier" class="pill tone-neutral ms-1" title="Used to spot duplicates"><Fingerprint :size="11" /> ID</span>
    </label>
    <select v-if="field.field_type === 'select'" :id="id" class="form-select" :class="{ 'is-invalid': showError }" :value="modelValue || ''"
            :disabled="disabled" :aria-invalid="showError" :aria-describedby="descId" @change="emitVal($event.target.value)" @blur="$emit('touch')">
      <option value="">Select…</option>
      <option v-for="o in field.options" :key="o" :value="o">{{ o }}</option>
    </select>
    <textarea v-else-if="field.field_type === 'textarea'" :id="id" class="form-control" rows="2" :class="{ 'is-invalid': showError }" :value="modelValue || ''"
              :disabled="disabled" :aria-invalid="showError" :aria-describedby="descId" @input="emitVal($event.target.value)" @blur="$emit('touch')" />
    <input v-else :id="id" class="form-control" :class="{ 'is-invalid': showError }" :type="inputType" :value="modelValue || ''" :disabled="disabled"
           :inputmode="field.field_type === 'number' ? 'decimal' : undefined" :aria-invalid="showError" :aria-describedby="descId"
           @input="emitVal($event.target.value)" @blur="$emit('touch')" />
    <div :id="descId">
      <div v-if="showError" class="invalid-msg"><AlertCircle :size="13" aria-hidden="true" /> {{ error }}</div>
      <div v-else-if="field.help_text" class="form-text">{{ field.help_text }}</div>
    </div>
  </div>
</template>
<script setup>
import { computed } from 'vue'
import { AlertCircle, Fingerprint, Lock } from 'lucide-vue-next'
const props = defineProps({ field: Object, modelValue: [String, Number], required: Boolean, error: String, touched: Boolean, disabled: Boolean })
const emit = defineEmits(['update:modelValue', 'touch'])
const id = computed(() => `f-${props.field.key}`)
const descId = computed(() => `${id.value}-desc`)
const showError = computed(() => !!props.error && props.touched)
const inputType = computed(() => ({ email: 'email', phone: 'tel', date: 'date', number: 'number' }[props.field.field_type] || 'text'))
const emitVal = (v) => emit('update:modelValue', v)
</script>
<style scoped>
.req { color: var(--error); }
.dyn.wide { grid-column: 1 / -1; }
</style>
