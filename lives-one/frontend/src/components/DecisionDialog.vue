<template>
  <ModalDialog :open="!!task" :title="titles[mode]" @close="$emit('close')">
    <p class="small text-muted-2 mb-2">{{ task?.step_name }} · {{ task?.request?.request_number || requestNumber }}</p>
    <label class="form-label" for="dc">{{ mode === 'APPROVE' ? 'Comment (optional)' : 'Reason (required)' }}</label>
    <textarea id="dc" v-model="comment" class="form-control" rows="3" :placeholder="placeholder[mode]" />
    <p class="form-text">Your decision is saved with your name and the time.</p>
    <template #footer>
      <button class="btn btn-light" type="button" @click="$emit('close')">Cancel</button>
      <button class="btn" :class="mode === 'APPROVE' ? 'btn-teal' : mode === 'REJECT' ? 'btn-danger' : 'btn-primary'" type="button"
              :disabled="busy || (mode !== 'APPROVE' && comment.trim().length < 5)" @click="go">{{ titles[mode] }}</button>
    </template>
  </ModalDialog>
</template>
<script setup>
import { ref, watch } from 'vue'
import ModalDialog from './ModalDialog.vue'
import { post } from '@/api/client'
import { useToast } from '@/stores/toast'
import { statusMeta } from '@/utils/format'
const props = defineProps({ task: Object, mode: { type: String, default: 'APPROVE' }, requestNumber: String })
const emit = defineEmits(['close', 'done'])
const toast = useToast()
const comment = ref('')
const busy = ref(false)
const titles = { APPROVE: 'Approve', REJECT: "Don't approve", REQUEST_CHANGES: 'Send back for changes' }
const placeholder = { APPROVE: 'e.g. Credit terms are within our policy', REJECT: 'Why are you not approving it?', REQUEST_CHANGES: 'What should the requester change?' }
const path = { APPROVE: 'approve', REJECT: 'reject', REQUEST_CHANGES: 'request-changes' }
watch(() => props.task, () => { comment.value = '' })
async function go() {
  busy.value = true
  try {
    const r = await post(`/api/approvals/${props.task.id}/${path[props.mode]}`, { comment: comment.value })
    toast.push(`Saved. The request is now: ${statusMeta(r.request.status).label.toLowerCase()}`)
    emit('done', r)
  } catch (e) { toast.error(e) } finally { busy.value = false }
}
</script>
