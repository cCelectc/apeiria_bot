import { createRouter, createWebHistory } from 'vue-router'
import { CAP_ACCOUNT_MANAGE, CAP_CONTROL_PANEL } from '@/constants/access'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { requiresAuth: false, titleKey: 'login.submit' },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/RegisterView.vue'),
    meta: { requiresAuth: false, titleKey: 'register.submit' },
  },
  {
    path: '/',
    component: () => import('@/layouts/AppLayout.vue'),
    meta: { requiresAuth: true, requiredCapability: CAP_CONTROL_PANEL },
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', name: 'dashboard', component: () => import('@/views/DashboardView.vue'), meta: { titleKey: 'dashboard.title' } },
      { path: 'core', name: 'core', component: () => import('@/views/CoreView.vue'), meta: { titleKey: 'core.title' } },
      { path: 'core/adapters/store', name: 'adapters-store', component: () => import('@/views/AdapterStoreView.vue'), meta: { titleKey: 'adapterStore.title' } },
      { path: 'ai', name: 'ai', redirect: '/ai/overview', meta: { titleKey: 'ai.title' } },
      { path: 'ai/overview', name: 'ai-overview', component: () => import('@/views/ai/AIOverviewPage.vue'), meta: { titleKey: 'ai.overviewTitle' } },
      { path: 'ai/models', name: 'ai-models', component: () => import('@/views/ai/AIModelsPage.vue'), meta: { titleKey: 'ai.modelsTitle' } },
      { path: 'ai/personas', name: 'ai-personas', component: () => import('@/views/ai/AIPersonasPage.vue'), meta: { titleKey: 'ai.personasTab' } },
      { path: 'ai/knowledge', name: 'ai-knowledge', component: () => import('@/views/ai/AIKnowledgePage.vue'), meta: { titleKey: 'ai.knowledgeTab' } },
      { path: 'ai/memories', name: 'ai-memories', component: () => import('@/views/ai/AIMemoriesPage.vue'), meta: { titleKey: 'ai.memoryTab' } },
      { path: 'ai/relationships', name: 'ai-relationships', component: () => import('@/views/ai/AIRelationshipsPage.vue'), meta: { titleKey: 'ai.relationshipTab' } },
      { path: 'ai/profiles', name: 'ai-profiles', component: () => import('@/views/ai/AIPersonProfilesPage.vue'), meta: { titleKey: 'ai.personProfileTab' } },
      { path: 'ai/skills', name: 'ai-skills', component: () => import('@/views/ai/AISkillsPage.vue'), meta: { titleKey: 'ai.skillsTab' } },
      { path: 'ai/debug', name: 'ai-debug', component: () => import('@/views/ai/AIDebugPage.vue'), meta: { titleKey: 'ai.debugTab' } },
      { path: 'plugins', redirect: '/plugins/config' },
      { path: 'plugins/config', name: 'plugins', component: () => import('@/views/PluginsView.vue'), meta: { titleKey: 'plugins.title' } },
      { path: 'plugins/store', name: 'plugins-store', component: () => import('@/views/PluginStoreView.vue'), meta: { titleKey: 'pluginStore.title' } },
      { path: 'permissions', name: 'permissions', component: () => import('@/views/PermissionsView.vue'), meta: { titleKey: 'permissions.title' } },
      { path: 'logs', name: 'logs', component: () => import('@/views/LogsView.vue'), meta: { titleKey: 'logs.liveTitle' } },
      { path: 'logs/history', name: 'logs-history', component: () => import('@/views/LogHistoryView.vue'), meta: { titleKey: 'logs.historyTitle' } },
      { path: 'chat', name: 'chat', component: () => import('@/views/ChatView.vue'), meta: { titleKey: 'chat.title' } },
      {
        path: 'accounts',
        name: 'accounts',
        component: () => import('@/views/AccountsView.vue'),
        meta: { titleKey: 'accounts.title', requiredCapability: CAP_ACCOUNT_MANAGE },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async to => {
  const authStore = useAuthStore()
  const token = authStore.token || localStorage.getItem('token')
  if (to.meta.requiresAuth !== false && !token) {
    return { name: 'login' }
  }

  if (token && !authStore.isAuthenticated) {
    await authStore.ensureInitialized()
  }

  if (to.meta.requiresAuth !== false && !authStore.isAuthenticated) {
    return { name: 'login' }
  }

  const requiredCapability = typeof to.meta.requiredCapability === 'string'
    ? to.meta.requiredCapability
    : ''
  if (requiredCapability && !authStore.capabilities.includes(requiredCapability)) {
    authStore.handleForbidden()
    return { name: 'login' }
  }

  if ((to.name === 'login' || to.name === 'register') && authStore.isAuthenticated) {
    return { name: 'dashboard' }
  }

  return undefined
})

export default router
