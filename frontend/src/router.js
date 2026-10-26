import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '@/stores/auth'

const routes = [
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { public: true, title: 'Sign in' } },
  { path: '/', name: 'command', component: () => import('@/views/CommandCentre.vue'), meta: { title: 'Command Centre' } },
  { path: '/mdm/new', name: 'mdm-new', component: () => import('@/views/mdm/NewRequest.vue'), meta: { title: 'New Request', section: 'Smart MDM' } },
  { path: '/mdm/requests', name: 'mdm-requests', component: () => import('@/views/mdm/MyRequests.vue'), meta: { title: 'My Requests', section: 'Smart MDM' } },
  { path: '/mdm/requests/:id', name: 'mdm-request', component: () => import('@/views/mdm/RequestDetail.vue'), meta: { title: 'Request', section: 'Smart MDM' } },
  { path: '/mdm/records', name: 'mdm-records', component: () => import('@/views/mdm/MasterRecords.vue'), meta: { title: 'Master Records', section: 'Smart MDM' } },
  { path: '/flow/inbox', name: 'flow-inbox', component: () => import('@/views/flow/ApprovalInbox.vue'), meta: { title: 'Approval Inbox', section: 'Flow Engine' } },
  { path: '/flow/tracker', name: 'flow-tracker', component: () => import('@/views/flow/WorkflowTracker.vue'), meta: { title: 'Workflow Tracker', section: 'Flow Engine' } },
  { path: '/flow/audit', name: 'flow-audit', component: () => import('@/views/flow/AuditHistory.vue'), meta: { title: 'Audit History', section: 'Flow Engine', roles: ['ADMIN', 'MDM_ANALYST', 'EXECUTIVE'] } },
  { path: '/growth/regional', name: 'growth-regional', component: () => import('@/views/growth/RegionalOverview.vue'), meta: { title: 'Regional Overview', section: 'Growth Intelligence', roles: ['SALES', 'EXECUTIVE', 'ADMIN', 'MDM_ANALYST', 'BU_HEAD', 'FINANCE'] } },
  { path: '/growth/data-quality', name: 'growth-dq', component: () => import('@/views/growth/DataQuality.vue'), meta: { title: 'Data Quality & Mapping', section: 'Growth Intelligence', roles: ['SALES', 'EXECUTIVE', 'ADMIN', 'MDM_ANALYST', 'BU_HEAD', 'FINANCE'] } },
  { path: '/growth/forecasting', name: 'growth-forecast', component: () => import('@/views/growth/DemandForecasting.vue'), meta: { title: 'Demand Forecasting', section: 'Growth Intelligence', roles: ['SALES', 'EXECUTIVE', 'ADMIN', 'MDM_ANALYST', 'BU_HEAD', 'FINANCE'] } },
  { path: '/growth/opportunities', name: 'growth-opps', component: () => import('@/views/growth/GrowthOpportunities.vue'), meta: { title: 'Growth Opportunities', section: 'Growth Intelligence', roles: ['SALES', 'EXECUTIVE', 'ADMIN', 'MDM_ANALYST'] } },
  { path: '/impact', name: 'impact', component: () => import('@/views/BusinessImpact.vue'), meta: { title: 'Business Impact' } },
  { path: '/admin/forms', name: 'admin-forms', component: () => import('@/views/admin/FormConfiguration.vue'), meta: { title: 'Form Configuration', section: 'Administration', roles: ['ADMIN'] } },
  { path: '/admin/approval-rules', name: 'admin-rules', component: () => import('@/views/admin/ApprovalRules.vue'), meta: { title: 'Approval Rules', section: 'Administration', roles: ['ADMIN'] } },
  { path: '/admin/integrations', name: 'admin-integrations', component: () => import('@/views/admin/Integrations.vue'),meta: { title: 'SAP & Notifications', section: 'Administration', roles: ['ADMIN', 'MDM_ANALYST'] } },
  { path: '/settings', name: 'settings', component: () => import('@/views/SettingsView.vue'), meta: { title: 'Settings' } },
  { path: '/:pathMatch(.*)*', name: 'notfound', component: () => import('@/views/NotFound.vue'), meta: { title: 'Not found' } },
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
