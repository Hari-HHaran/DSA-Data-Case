import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '@/stores/auth'

const routes = [
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { public: true, title: 'Sign in' } },
  { path: '/', name: 'command', component: () => import('@/views/CommandCentre.vue'), meta: { title: 'Home' } },
  { path: '/mdm/new', name: 'mdm-new', component: () => import('@/views/mdm/NewRequest.vue'), meta: { title: 'New request', section: 'Requests' } },
  { path: '/mdm/requests', name: 'mdm-requests', component: () => import('@/views/mdm/MyRequests.vue'), meta: { title: 'My requests', section: 'Requests' } },
  { path: '/mdm/requests/:id', name: 'mdm-request', component: () => import('@/views/mdm/RequestDetail.vue'), meta: { title: 'Request', section: 'Requests' } },
  { path: '/mdm/records', name: 'mdm-records', component: () => import('@/views/mdm/MasterRecords.vue'), meta: { title: 'Existing records', section: 'Requests' } },
  { path: '/flow/inbox', name: 'flow-inbox', component: () => import('@/views/flow/ApprovalInbox.vue'), meta: { title: 'Approval inbox', section: 'Approvals' } },
  { path: '/flow/tracker', name: 'flow-tracker', component: () => import('@/views/flow/WorkflowTracker.vue'), meta: { title: 'Track requests', section: 'Approvals' } },
  { path: '/flow/audit', name: 'flow-audit', component: () => import('@/views/flow/AuditHistory.vue'), meta: { title: 'Activity history', section: 'Approvals', roles: ['ADMIN', 'MDM_ANALYST', 'EXECUTIVE'] } },
  { path: '/growth/regional', name: 'growth-regional', component: () => import('@/views/growth/RegionalOverview.vue'), meta: { title: 'Sales by country', section: 'Sales insights', roles: ['SALES', 'EXECUTIVE', 'ADMIN', 'MDM_ANALYST', 'BU_HEAD', 'FINANCE'] } },
  { path: '/growth/data-quality', redirect: '/mdm/records?tab=mapping' }, // old link: page removed
  { path: '/growth/forecasting', name: 'growth-forecast', component: () => import('@/views/growth/DemandForecasting.vue'), meta: { title: 'Sales forecast', section: 'Sales insights', roles: ['SALES', 'EXECUTIVE', 'ADMIN', 'MDM_ANALYST', 'BU_HEAD', 'FINANCE'] } },
  { path: '/growth/opportunities', name: 'growth-opps', component: () => import('@/views/growth/GrowthOpportunities.vue'), meta: { title: 'Sales opportunities', section: 'Sales insights', roles: ['SALES', 'EXECUTIVE', 'ADMIN', 'MDM_ANALYST'] } },
  { path: '/admin/forms', name: 'admin-forms', component: () => import('@/views/admin/FormConfiguration.vue'), meta: { title: 'Request forms', section: 'Setup', roles: ['ADMIN'] } },
  { path: '/admin/approval-rules', name: 'admin-rules', component: () => import('@/views/admin/ApprovalRules.vue'), meta: { title: 'Approval rules', section: 'Setup', roles: ['ADMIN'] } },
  { path: '/admin/integrations', name: 'admin-integrations', component: () => import('@/views/admin/Integrations.vue'),meta: { title: 'SAP & email status', section: 'Setup', roles: ['ADMIN', 'MDM_ANALYST'] } },
  { path: '/settings', name: 'settings', component: () => import('@/views/SettingsView.vue'), meta: { title: 'Settings' } },
  { path: '/:pathMatch(.*)*', name: 'notfound', component: () => import('@/views/NotFound.vue'), meta: { title: 'Page not found' } },
]

const router = createRouter({ history: createWebHistory(), routes, scrollBehavior: () => ({ top: 0 }) })

router.beforeEach(async (to) => {
  const auth = useAuth()
  if (!auth.ready) await auth.init()
  if (to.meta.public) return true
  if (!auth.isAuthed) return { name: 'login', query: { next: to.fullPath } }
  if (to.meta.roles && !auth.has(...to.meta.roles)) return { name: 'command', query: { denied: to.meta.title } }
  return true
})
router.afterEach((to) => { document.title = `${to.meta.title || 'LIVES ONE'} · LIVES ONE` })

export default router
