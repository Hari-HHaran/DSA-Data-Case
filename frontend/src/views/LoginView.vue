<template>
  <div class="login">
    <section class="hero">
      <div class="brand"><span class="logo"><span></span></span><strong>LIVES ONE</strong></div>
      <h1>One Record. One Workflow.<br />One Regional Intelligence Layer.</h1>
      <p>Master-data intake, governed approvals and SAP B1 hand-off — connected to clean, five-country purchasing intelligence.</p>
      <ul class="pillars">
        <li><ShieldCheck :size="18" /> <div><strong>Smart MDM</strong><span>Validated intake & explainable duplicate prevention</span></div></li>
        <li><Workflow :size="18" /> <div><strong>Flow Engine</strong><span>Parallel approvals, SLAs, audit trail, SAP adapter</span></div></li>
        <li><LineChart :size="18" /> <div><strong>Growth Intelligence</strong><span>Clean regional demand, backtested forecasts, next actions</span></div></li>
      </ul>
      <p class="fine">Competition prototype for the SMU DSA Society 2026 Data Case. All data is synthetic; SAP B1 and Microsoft 365 integrations are clearly-labelled mocks.</p>
    </section>
    <section class="panel">
      <div class="card-x p-4">
        <h2 class="mb-1">Sign in</h2>
        <p class="text-muted-2 small mb-3">Choose a persona to explore the prototype. Each persona has different server-enforced permissions.</p>
        <ErrorState v-if="error" :error="error" class="mb-3" />
        <div v-if="auth.demoMode" class="personas">
          <button v-for="p in personas" :key="p.username" type="button" class="persona" :disabled="busy" @click="pick(p.username)">
            <span class="avatar">{{ p.name.slice(0, 2).toUpperCase() }}</span>
            <span class="flex-grow-1 text-start"><strong>{{ p.name }}</strong> <span v-if="brief.includes(p.username)" class="pill tone-teal ms-1">Brief persona</span>
              <small>{{ p.title }}</small><small class="story">{{ stories[p.username] }}</small></span>
            <ArrowRight :size="16" />
          </button>
        </div>
        <div v-else-if="!auth.ready" class="py-3"><LoadingBlock :rows="3" /></div>
        <details class="mt-3" :open="!auth.demoMode">
          <summary class="small fw-semibold">Sign in with username and password</summary>
          <form class="mt-2" @submit.prevent="submit">
            <label class="form-label" for="u">Username</label>
            <input id="u" v-model="username" class="form-control mb-2" autocomplete="username" required />
            <label class="form-label" for="p">Password</label>
            <input id="p" v-model="password" type="password" class="form-control mb-3" autocomplete="current-password" required />
            <button class="btn btn-primary w-100" :disabled="busy">Sign in</button>
            <p class="form-text mt-2">Demo accounts share the password set by <code>LIVES_DEMO_PASSWORD</code> (default in README).</p>
          </form>
        </details>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, LineChart, ShieldCheck, Workflow } from 'lucide-vue-next'
import ErrorState from '@/components/ErrorState.vue'
import LoadingBlock from '@/components/LoadingBlock.vue'
import { homeFor, useAuth } from '@/stores/auth'

const auth = useAuth()
const router = useRouter()
const route = useRoute()
const busy = ref(false)
const error = ref(null)
const username = ref('')
const password = ref('')
const brief = ['amy', 'weijie', 'priya', 'marcus']
const order = ['amy', 'weijie', 'priya', 'marcus', 'daniel', 'siti', 'kevin', 'alex', 'elaine']
const stories = {
  amy: 'Raise a new item code without guessing regulatory fields.', weijie: 'Approve credit and banking details from one inbox.',
  priya: 'Verify approved records and hand them to SAP B1.', marcus: 'New BU — standard requests, regional demand and opportunities.',
  daniel: 'Business Unit Head approvals.', siti: 'Quality / Regulatory sign-off.', kevin: 'Business Support set-up checks.',
  alex: 'Configure forms, approval rules and SLAs without IT.', elaine: 'Read-only view of performance and impact.',
}
const personas = computed(() => auth.personas.filter((p) => order.includes(p.username)).sort((a, b) => order.indexOf(a.username) - order.indexOf(b.username)))

async function done() {
  router.replace(route.query.next && route.query.next !== '/login' ? route.query.next : homeFor(auth.roles))
}
async function pick(u) {
  busy.value = true; error.value = null
  try { await auth.switchPersona(u); await done() } catch (e) { error.value = e } finally { busy.value = false }
}
async function submit() {
  busy.value = true; error.value = null
  try { await auth.login(username.value, password.value); await done() } catch (e) { error.value = e } finally { busy.value = false }
}
onMounted(async () => { if (!auth.ready) await auth.init(); if (!auth.personas.length && !auth.demoMode) error.value = null })
</script>

<style scoped>
.login { min-height: 100vh; display: grid; grid-template-columns: 1.1fr 1fr; background: var(--bg); }
.hero { background: var(--navy); color: #c9d3e6; padding: 3.5rem 3.5rem; display: flex; flex-direction: column; justify-content: center; gap: 1.2rem; }
.hero h1 { color: #fff; font-size: 2.1rem; line-height: 1.2; margin: 0; }
.hero p { max-width: 520px; margin: 0; }
.brand { display: flex; align-items: center; gap: .7rem; color: #fff; letter-spacing: .1em; }
.logo { width: 38px; height: 38px; border-radius: 10px; background: linear-gradient(140deg, #2563eb, #0d9488); display: inline-flex; align-items: center; justify-content: center; }
.logo span { width: 15px; height: 15px; border: 3px solid #fff; border-radius: 50%; }
.pillars { list-style: none; padding: 0; margin: .5rem 0; display: flex; flex-direction: column; gap: .8rem; }
.pillars li { display: flex; gap: .75rem; align-items: flex-start; }
.pillars svg { color: #2dd4bf; margin-top: 2px; flex: none; }
.pillars strong { color: #fff; display: block; }
.pillars span { font-size: .85rem; }
.fine { font-size: .78rem; color: #8ea0c2; }
.panel { display: flex; align-items: center; justify-content: center; padding: 2rem; }
.panel > .card-x { width: 100%; max-width: 480px; }
.personas { display: flex; flex-direction: column; gap: .45rem; max-height: 60vh; overflow: auto; }
.persona { display: flex; align-items: center; gap: .75rem; padding: .6rem .7rem; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); color: var(--text); }
.persona:hover { border-color: var(--accent); background: #f8fbff; }
.persona small { display: block; color: var(--muted); font-size: .76rem; }
.persona .story { color: var(--text-2); }
.avatar { width: 36px; height: 36px; border-radius: 9px; background: var(--navy); color: #fff; font-weight: 700; font-size: .78rem; display: inline-flex; align-items: center; justify-content: center; flex: none; }
@media (max-width: 900px) { .login { grid-template-columns: 1fr; } .hero { padding: 2rem 1.25rem; } .hero h1 { font-size: 1.6rem; } }
</style>
