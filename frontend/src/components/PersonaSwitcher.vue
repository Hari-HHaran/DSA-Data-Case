<template>
  <div class="persona" ref="root">
    <button class="who" type="button" @click="open = !open" :aria-expanded="open" aria-haspopup="menu">
      <span class="avatar" aria-hidden="true">{{ initials(auth.user?.name) }}</span>
      <span class="who-text d-none d-md-flex"><strong>{{ auth.user?.name }}</strong><small>{{ auth.user?.title }}</small></span>
      <ChevronDown :size="15" />
    </button>
    <div v-if="open" class="menu card-x" role="menu">
      <div class="menu-head">
        <div class="small-label">Signed in as</div>
        <strong>{{ auth.user?.name }}</strong> · <span class="text-muted-2">{{ auth.user?.title }}</span>
        <div class="mt-1 d-flex flex-wrap gap-1"><span v-for="r in auth.roles" :key="r" class="pill tone-info">{{ ROLE_LABELS[r] || r }}</span></div>
      </div>
      <template v-if="auth.demoMode">
        <div class="menu-sub"><span class="small-label">Demo: switch persona</span><span class="pill tag-mock">Demo auth</span></div>
        <div class="menu-list">
          <button v-for="p in personas" :key="p.username" class="menu-item" role="menuitem" type="button" :class="{ current: p.username === auth.user?.username }"
                  @click="switchTo(p.username)">
            <span class="avatar sm" aria-hidden="true">{{ initials(p.name) }}</span>
            <span class="flex-grow-1 text-start"><strong>{{ p.name }}</strong><small>{{ p.title }}</small></span>
            <span v-if="brief.includes(p.username)" class="pill tone-teal">Brief</span>
          </button>
        </div>
        <p class="note">Every action is still authorised server-side against the persona's roles. Demo switching is disabled when LIVES_DEMO_MODE=false.</p>
      </template>
      <button class="menu-item" type="button" role="menuitem" @click="logout"><LogOut :size="16" /> Sign out</button>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ChevronDown, LogOut } from 'lucide-vue-next'
import { homeFor, useAuth } from '@/stores/auth'
import { useNotifications } from '@/stores/notifications'
import { useToast } from '@/stores/toast'
import { ROLE_LABELS } from '@/utils/format'

const auth = useAuth()
const router = useRouter()
const toast = useToast()
const notes = useNotifications()
const open = ref(false)
const root = ref(null)
const brief = ['amy', 'weijie', 'priya', 'marcus']
const order = ['amy', 'weijie', 'priya', 'marcus', 'daniel', 'siti', 'kevin', 'alex', 'elaine', 'ben']
const personas = computed(() => [...auth.personas].filter((p) => order.includes(p.username)).sort((a, b) => order.indexOf(a.username) - order.indexOf(b.username)))
const initials = (n = '') => n.split(/\s+/).map((x) => x[0]).join('').slice(0, 2).toUpperCase()

async function switchTo(username) {
  open.value = false
  try {
    await auth.switchPersona(username)
    notes.refresh()
    toast.push(`Now acting as ${auth.user.name} (${auth.user.title})`, 'info')
    const r = router.currentRoute.value
    const allowed = !r.meta.roles || auth.has(...r.meta.roles)
    if (!allowed || r.name === 'mdm-new') router.replace(homeFor(auth.roles))
  } catch (e) { toast.error(e) }
}
function logout() { auth.logout(); router.push('/login') }
function onDoc(e) { if (root.value && !root.value.contains(e.target)) open.value = false }
onMounted(() => document.addEventListener('click', onDoc))
onBeforeUnmount(() => document.removeEventListener('click', onDoc))
</script>

<style scoped>
.persona { position: relative; }
.who { display: flex; align-items: center; gap: .55rem; background: var(--surface); border: 1px solid var(--border); border-radius: 999px; padding: .25rem .55rem .25rem .3rem; color: var(--text); }
.who:hover { background: var(--surface-2); }
.who-text { flex-direction: column; line-height: 1.1; text-align: left; }
.who-text strong { font-size: .84rem; }
.who-text small { font-size: .72rem; color: var(--muted); max-width: 170px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.avatar { width: 30px; height: 30px; border-radius: 50%; background: linear-gradient(140deg, #818cf8, #4f46e5); color: #fff; font-size: .72rem; font-weight: 700; display: inline-flex; align-items: center; justify-content: center; flex: none; }
.avatar.sm { width: 28px; height: 28px; }
.menu { position: absolute; right: 0; top: calc(100% + 6px); width: 330px; max-height: 80vh; overflow: auto; box-shadow: var(--shadow-2); padding: .4rem; z-index: 50; }
.menu-head { padding: .6rem .65rem .7rem; border-bottom: 1px solid var(--border); margin-bottom: .3rem; font-size: .86rem; }
.menu-sub { display: flex; justify-content: space-between; align-items: center; padding: .45rem .65rem .2rem; }
.menu-item { width: 100%; display: flex; align-items: center; gap: .6rem; padding: .5rem .6rem; border: none; background: none; border-radius: 10px; font-size: .84rem; color: var(--text); }
.menu-item small { display: block; color: var(--muted); font-size: .72rem; }
.menu-item:hover { background: var(--surface-2); }
.menu-item.current { background: var(--accent-soft); }
.note { font-size: .72rem; color: var(--muted); padding: .3rem .65rem .5rem; margin: 0; border-bottom: 1px solid var(--border); }
</style>
