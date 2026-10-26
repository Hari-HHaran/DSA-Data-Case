<template>
  <div class="shell" :class="{ collapsed }">
    <aside class="sidebar" aria-label="Main navigation">
      <div class="brand">
        <span class="logo" aria-hidden="true"><span></span></span>
        <div v-if="!collapsed" class="brand-text"><strong>LIVES ONE</strong><small>One record · One workflow</small></div>
      </div>
      <nav>
        <template v-for="group in nav" :key="group.label">
          <div v-if="group.items.length" class="group">
            <div v-if="!collapsed && group.label" class="group-label">{{ group.label }}</div>
            <RouterLink v-for="item in group.items" :key="item.to" :to="item.to" class="nav-item" :title="collapsed ? item.label : undefined"
                        :class="{ active: isActive(item) }">
              <component :is="item.icon" :size="18" aria-hidden="true" />
              <span v-if="!collapsed">{{ item.label }}</span>
              <span v-if="!collapsed && item.badge" class="nav-badge num">{{ item.badge }}</span>
            </RouterLink>
          </div>
        </template>
      </nav>
      <button class="collapse-btn" type="button" @click="toggle" :aria-label="collapsed ? 'Expand sidebar' : 'Collapse sidebar'">
        <ChevronsLeft v-if="!collapsed" :size="16" /><ChevronsRight v-else :size="16" />
        <span v-if="!collapsed">Collapse</span>
      </button>
    </aside>
    <div class="main">
      <header class="topbar">
        <button class="btn btn-ghost btn-sm d-lg-none" type="button" @click="toggle" aria-label="Toggle navigation"><Menu :size="18" /></button>
        <nav class="crumbs" aria-label="Breadcrumb">
          <RouterLink to="/">Home</RouterLink>
          <template v-if="$route.meta.section"><ChevronRight :size="14" /><span>{{ $route.meta.section }}</span></template>
          <template v-if="$route.name !== 'command'"><ChevronRight :size="14" /><strong>{{ $route.meta.title }}</strong></template>
        </nav>
        <form class="search" role="search" @submit.prevent="search">
          <Search :size="16" aria-hidden="true" />
          <input v-model="q" type="search" placeholder="Search requests or master records…" aria-label="Search requests or master records" />
        </form>
        <span class="pill tag-synthetic d-none d-xl-inline-flex" title="All data in this prototype is synthetic">Synthetic demo data</span>
        <NotificationBell />
        <PersonaSwitcher />
      </header>
      <main id="content"><slot /></main>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ChevronRight, ChevronsLeft, ChevronsRight, Database, FilePlus2, FileStack, Gauge, Globe2, History, Inbox, LayoutDashboard,
  Lightbulb, LineChart, Menu, Plug, Search, Settings, SlidersHorizontal, Workflow, Network, ShieldCheck,
} from 'lucide-vue-next'
import NotificationBell from './NotificationBell.vue'
import PersonaSwitcher from './PersonaSwitcher.vue'
import { useAuth } from '@/stores/auth'
import { useNotifications } from '@/stores/notifications'

const auth = useAuth()
const route = useRoute()
const router = useRouter()
const notes = useNotifications()
const q = ref('')
let stored = false
try { stored = localStorage.getItem('lives_one_sidebar') === '1' } catch { /* ignore */ }
const collapsed = ref(stored || window.innerWidth < 992)
function toggle() {
  collapsed.value = !collapsed.value
  try { localStorage.setItem('lives_one_sidebar', collapsed.value ? '1' : '0') } catch { /* ignore */ }
}

const ANALYTICS = ['SALES', 'EXECUTIVE', 'ADMIN', 'MDM_ANALYST', 'BU_HEAD', 'FINANCE']
const nav = computed(() => {
  const has = (...r) => auth.has(...r)
  return [
    { label: '', items: [{ to: '/', label: 'Command Centre', icon: LayoutDashboard, exact: true }] },
    { label: 'Smart MDM', items: [
      has('REQUESTOR', 'SALES', 'ADMIN') && { to: '/mdm/new', label: 'New Request', icon: FilePlus2 },
      { to: '/mdm/requests', label: 'My Requests', icon: FileStack },
      { to: '/mdm/records', label: 'Master Records', icon: Database },
    ].filter(Boolean) },
    { label: 'Flow Engine', items: [
      has('BU_HEAD', 'FINANCE', 'QRA', 'BUSINESS_SUPPORT') && { to: '/flow/inbox', label: 'Approval Inbox', icon: Inbox },
      { to: '/flow/tracker', label: 'Workflow Tracker', icon: Workflow },
      has('ADMIN', 'MDM_ANALYST', 'EXECUTIVE') && { to: '/flow/audit', label: 'Audit History', icon: History },
    ].filter(Boolean) },
    { label: 'Growth Intelligence', items: has(...ANALYTICS) ? [
      { to: '/growth/regional', label: 'Regional Overview', icon: Globe2 },
      { to: '/growth/data-quality', label: 'Data Quality & Mapping', icon: Network },
      { to: '/growth/forecasting', label: 'Demand Forecasting', icon: LineChart },
      has('SALES', 'EXECUTIVE', 'ADMIN', 'MDM_ANALYST') && { to: '/growth/opportunities', label: 'Growth Opportunities', icon: Lightbulb },
    ].filter(Boolean) : [] },
    { label: 'Impact', items: [{ to: '/impact', label: 'Business Impact', icon: Gauge }] },
        { label: 'Administration', items: [
      has('ADMIN') && { to: '/admin/forms', label: 'Form Configuration', icon: SlidersHorizontal },
      has('ADMIN') && { to: '/admin/approval-rules', label: 'Approval Rules', icon: ShieldCheck },
      has('ADMIN', 'MDM_ANALYST') && { to: '/admin/integrations', label: 'SAP & Notifications', icon: Plug },
    ].filter(Boolean) },
    { label: 'Account', items: [{ to: '/settings', label: 'Settings', icon: Settings }] },
  ]
})
function isActive(item) {
  return item.exact ? route.path === item.to : route.path.startsWith(item.to)
}
function search() {
  const term = q.value.trim()
  if (!term) return
  if (/^MDM-/i.test(term) || auth.has('REQUESTOR')) router.push({ path: auth.has('MDM_ANALYST', 'ADMIN', 'EXECUTIVE') ? '/flow/tracker' : '/mdm/requests', query: { q: term } })
  else router.push({ path: '/mdm/records', query: { q: term } })
  q.value = ''
}
onMounted(() => notes.start())
onBeforeUnmount(() => notes.stop())
</script>

<style scoped>
.shell { display: flex; min-height: 100vh; }
.sidebar { width: var(--sidebar-w); background: linear-gradient(180deg, #131f3d 0%, #101a33 100%); color: #c9d3e6; position: fixed; inset: 0 auto 0 0; display: flex; flex-direction: column; z-index: 30; transition: width .18s ease; }
.collapsed .sidebar { width: var(--sidebar-w-collapsed); }
.main { flex: 1; margin-left: var(--sidebar-w); min-width: 0; transition: margin .18s ease; }
.collapsed .main { margin-left: var(--sidebar-w-collapsed); }
.brand { display: flex; align-items: center; gap: .7rem; padding: 1.05rem 1.05rem .9rem; }
.logo { width: 36px; height: 36px; border-radius: 12px; background: linear-gradient(140deg, #818cf8, #4f46e5 60%, #0d9488); box-shadow: 0 8px 18px -8px rgba(99, 102, 241, .9); display: inline-flex; align-items: center; justify-content: center; flex: none; }
.logo span { width: 14px; height: 14px; border: 3px solid #fff; border-radius: 50%; }
.brand-text { display: flex; flex-direction: column; line-height: 1.1; }
.brand-text strong { color: #fff; letter-spacing: .08em; font-size: .95rem; }
.brand-text small { color: #8ea0c2; font-size: .7rem; margin-top: 2px; }
nav { flex: 1; overflow-y: auto; padding: .25rem .6rem; }
.group { margin-bottom: .55rem; }
.group-label { font-size: .66rem; text-transform: uppercase; letter-spacing: .09em; color: #7083a8; padding: .55rem .6rem .3rem; font-weight: 600; }
.nav-item { display: flex; align-items: center; gap: .7rem; padding: .55rem .7rem; border-radius: 12px; transition: background .15s, color .15s; color: #c9d3e6; font-weight: 500; font-size: .875rem; text-decoration: none; }
.nav-item:hover { background: rgba(255, 255, 255, .07); color: #fff; text-decoration: none; }
.nav-item.active { background: linear-gradient(135deg, #6366f1, #4f46e5); color: #fff; box-shadow: 0 10px 22px -12px rgba(99, 102, 241, 1); }
.nav-badge { margin-left: auto; background: #ec4899; color: #fff; border-radius: 999px; font-size: .7rem; padding: 0 .45rem; }
.collapse-btn { margin: .6rem; background: rgba(255, 255, 255, .04); border: 1px solid rgba(255, 255, 255, .08); color: #9fb0cf; border-radius: 12px; padding: .4rem; display: flex; align-items: center; gap: .5rem; justify-content: center; font-size: .78rem; }
.collapse-btn:hover { background: var(--navy-2); color: #fff; }
.topbar { height: var(--topbar-h); background: rgba(255, 255, 255, .8); backdrop-filter: saturate(160%) blur(10px); -webkit-backdrop-filter: saturate(160%) blur(10px); border-bottom: 1px solid rgba(232, 235, 243, .8); display: flex; align-items: center; gap: .75rem; padding: 0 1.25rem; position: sticky; top: 0; z-index: 20; }
.crumbs { display: flex; align-items: center; gap: .35rem; color: var(--muted); font-size: .84rem; min-width: 0; white-space: nowrap; overflow: hidden; }
.crumbs a { color: var(--muted); }
.crumbs strong { color: var(--text); font-weight: 600; }
.search { margin-left: auto; display: flex; align-items: center; gap: .45rem; background: var(--surface); border: 1px solid var(--border); border-radius: 999px; padding: 0 .9rem; height: 38px; box-shadow: 0 1px 2px rgba(16, 28, 53, .04); width: min(320px, 30vw); color: var(--muted); }
.search input { border: none; background: transparent; outline: none; width: 100%; font-size: .85rem; color: var(--text); }
.search:focus-within { border-color: var(--accent-2); box-shadow: var(--ring); }
@media (max-width: 991px) {
  .sidebar { width: var(--sidebar-w); transform: translateX(0); transition: transform .18s ease; }
  .collapsed .sidebar { transform: translateX(-100%); width: var(--sidebar-w); }
  .main, .collapsed .main { margin-left: 0; }
  .shell:not(.collapsed) .main::before { content: ''; position: fixed; inset: 0; background: rgba(16, 28, 53, .35); z-index: 25; }
  .search { display: none; }
}
</style>
