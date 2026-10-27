<template>
  <div>
    <div v-if="status === 'CLEAR'" class="callout ok"><CheckCircle2 :size="18" /> <div><strong>No similar records found.</strong> We checked existing records and requests that are still in progress.</div></div>
    <div v-else-if="status === 'NOT_RUN'" class="callout neutral"><Search :size="18" /><div>Run the check to compare your request with existing records and requests that are still in progress.</div></div>
    <div v-else-if="status === 'RESOLVED'" class="callout ok"><CheckCircle2 :size="18" /><div><strong>Duplicate review recorded.</strong> {{ lastReview }}</div></div>
    <div v-else class="callout" :class="status === 'BLOCKED' ? 'err' : 'warn'"><AlertTriangle :size="18" />
      <div><strong>{{ status === 'BLOCKED' ? 'Same ID number found. This record probably already exists.' : 'This looks similar to something that already exists. Please take a look before submitting.' }}</strong>
        Nothing changes unless you decide, and your choice is saved with your name.</div></div>

    <div v-for="c in candidates" :key="c.id || c.existing?.code" class="cand card-x mt-3">
      <div class="cand-head">
        <div class="score" :class="c.band === 'LIKELY_DUPLICATE' ? 'hi' : 'mid'"><span class="num">{{ Math.round(c.score) }}</span><small>match</small></div>
        <div class="flex-grow-1 min-w-0">
          <div class="d-flex gap-2 align-items-center flex-wrap">
            <strong>{{ c.existing?.name }}</strong>
            <span class="pill" :class="c.band === 'LIKELY_DUPLICATE' ? 'tone-error' : 'tone-warning'">{{ c.band === 'LIKELY_DUPLICATE' ? 'Likely duplicate' : 'Needs review' }}</span>
            <span v-if="c.exact_identifier_match" class="pill tone-error"><Fingerprint :size="11" /> Same ID number</span>
            <span class="pill tone-neutral">{{ c.existing?.type === 'OPEN_REQUEST' ? 'Request in progress' : 'Existing record' }}</span>
          </div>
          <div class="small text-muted-2 mt-1">{{ c.existing?.code }} · {{ c.existing?.country_code || '—' }} <template v-if="c.existing?.identifier">· ID {{ c.existing.identifier }}</template>
            <template v-if="c.existing?.sap_code"> · SAP {{ c.existing.sap_code }}</template></div>
          <div v-if="c.existing?.aliases?.length" class="small mt-1"><span class="text-muted-2">Also known as:</span> {{ c.existing.aliases.join(' · ') }}</div>
        </div>
      </div>
      <div class="cand-body">
        <div class="small-label mb-1">Why it looks similar</div>
        <ul class="why"><li v-for="(p, i) in c.explanation.split('; ')" :key="i">{{ p }}</li></ul>
        <div class="d-flex flex-wrap gap-1 mt-1"><span v-for="f in c.matched_fields" :key="f" class="pill tone-info">{{ f.replace('_', ' ') }}</span></div>
        <div class="small mt-2"><strong>What we suggest:</strong> {{ c.suggested_action }}</div>
        <div v-if="editable && status !== 'RESOLVED'" class="d-flex flex-wrap gap-2 mt-3">
          <button v-if="c.existing?.type === 'MASTER_RECORD'" class="btn btn-teal btn-sm" type="button" @click="$emit('decide', { decision: 'REUSE_EXISTING', candidate_id: c.id })">
            <Recycle :size="14" /> Use the existing record</button>
          <button class="btn btn-light btn-sm" type="button" @click="$emit('correct')"><Pencil :size="14" /> Correct my request</button>
          <button v-if="!c.exact_identifier_match && c.band === 'NEEDS_REVIEW' && !anyLikely" class="btn btn-light btn-sm" type="button"
                  @click="$emit('decide', { decision: 'NOT_DUPLICATE', candidate_id: c.id, justification: 'Reviewed — different entity' })"><Check :size="14" /> Not a duplicate</button>
          <button class="btn btn-ghost btn-sm" type="button" @click="openJustify(c)"><FileText :size="14" /> {{ c.exact_identifier_match ? 'Ask the Master Data team to check' : 'Continue with justification' }}</button>
        </div>
      </div>
    </div>

    <ModalDialog :open="!!justifyFor" title="Tell us why this is not a duplicate" @close="justifyFor = null">
      <p class="small text-muted-2">Your reason is saved with the request, so the approvers and the Master Data team can see it.</p>
      <textarea v-model="justification" class="form-control" rows="3" placeholder="e.g. A different company with its own registration number, confirmed with the customer" />
      <div class="form-text">Please write at least 15 characters.</div>
      <template #footer>
        <button class="btn btn-light" type="button" @click="justifyFor = null">Cancel</button>
        <button class="btn btn-primary" type="button" :disabled="justification.trim().length < 15" @click="confirmJustify">Record decision</button>
      </template>
    </ModalDialog>
  </div>
</template>
<script setup>
import { computed, ref } from 'vue'
import { AlertTriangle, Check, CheckCircle2, FileText, Fingerprint, Pencil, Recycle, Search } from 'lucide-vue-next'
import ModalDialog from './ModalDialog.vue'
const props = defineProps({ status: String, candidates: { type: Array, default: () => [] }, editable: Boolean, reviews: Array })
const emit = defineEmits(['decide', 'correct'])
const justifyFor = ref(null)
const justification = ref('')
const anyLikely = computed(() => props.candidates.some((c) => c.band === 'LIKELY_DUPLICATE'))
const lastReview = computed(() => { const r = props.reviews?.[props.reviews.length - 1]; return r ? `${r.decision.replace(/_/g, ' ').toLowerCase()} — ${r.justification}` : '' })
function openJustify(c) { justifyFor.value = c; justification.value = '' }
function confirmJustify() {
  const c = justifyFor.value
  emit('decide', { decision: c.exact_identifier_match ? 'FLAG_FOR_REVIEW' : 'CONTINUE_WITH_JUSTIFICATION', candidate_id: c.id, justification: justification.value })
  justifyFor.value = null
}
</script>
<style scoped>
.cand { overflow: hidden; }
.cand-head { display: flex; gap: .9rem; padding: .85rem 1rem; border-bottom: 1px solid var(--border); align-items: flex-start; }
.cand-body { padding: .85rem 1rem; }
.score { width: 56px; height: 56px; border-radius: 12px; display: flex; flex-direction: column; align-items: center; justify-content: center; flex: none; }
.score span { font-size: 1.3rem; font-weight: 700; line-height: 1; }
.score small { font-size: .62rem; text-transform: uppercase; letter-spacing: .05em; }
.score.hi { background: var(--error-soft); color: #b91c1c; }
.score.mid { background: var(--warning-soft); color: var(--warning); }
.why { margin: 0; padding-left: 1.1rem; font-size: .84rem; }
</style>
