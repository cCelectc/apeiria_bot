import type { RouteRecordRaw } from 'vue-router'
import { createRouter, createWebHistory } from 'vue-router'
import { CAP_ACCOUNT_MANAGE, CAP_CONTROL_PANEL } from '@/constants/access'
import { useAuthStore } from '@/stores/auth'
import { aiManagementPageDescriptors } from './aiRoutes'

const PlaceholderPage = () => import('@/pages/PlaceholderPage.vue')

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/pages/LoginPage.vue'),
    meta: { requiresAuth: false, titleKey: 'login.submit' },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/pages/RegisterPage.vue'),
    meta: { requiresAuth: false, titleKey: 'register.submit' },
  },
  {
    path: '/',
    component: () => import('@/layouts/AppLayout.vue'),
    meta: { requiresAuth: true, requiredCapability: CAP_CONTROL_PANEL },
    children: [
      { path: '', redirect: '/dashboard' },
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('@/pages/DashboardPage.vue'),
        meta: { titleKey: 'dashboard.title' },
      },
      {
        path: 'core',
        name: 'core',
        component: () => import('@/pages/CorePage.vue'),
        meta: { titleKey: 'core.title' },
      },
      {
        path: 'core/adapters/store',
        name: 'adapters-store',
        component: () => import('@/pages/AdapterStorePage.vue'),
        meta: { titleKey: 'adapterStore.title' },
      },
      { path: 'ai', name: 'ai', redirect: '/ai/overview', meta: { titleKey: 'ai.title' } },
      {
        path: 'ai/overview',
        name: 'ai-overview',
        component: () => import('@/pages/AIOverviewPage.vue'),
        meta: { titleKey: 'ai.overviewTitle' },
      },
      {
        path: 'ai/models',
        name: 'ai-models',
        component: () => import('@/pages/AIModelsPage.vue'),
        meta: { titleKey: 'ai.modelsTitle' },
      },
      {
        path: 'ai/knowledge',
        name: 'ai-knowledge',
        component: () => import('@/pages/AIKnowledgePage.vue'),
        meta: { titleKey: 'ai.knowledgeTab' },
      },
      {
        path: 'ai/personas',
        name: 'ai-personas',
        component: () => import('@/pages/AIPersonasPage.vue'),
        meta: { titleKey: 'ai.personasTab' },
      },
      {
        path: 'ai/memories',
        name: 'ai-memories',
        component: () => import('@/pages/AIMemoriesPage.vue'),
        meta: { titleKey: 'ai.memoryTab' },
      },
      {
        path: 'ai/relationships',
        name: 'ai-relationships',
        component: () => import('@/pages/AIRelationshipsPage.vue'),
        meta: { titleKey: 'ai.relationshipTab' },
      },
      {
        path: 'ai/profiles',
        name: 'ai-profiles',
        component: () => import('@/pages/AIPersonProfilesPage.vue'),
        meta: { titleKey: 'ai.personProfileTab' },
      },
      {
        path: 'ai/future-tasks',
        name: 'ai-future-tasks',
        component: () => import('@/pages/AIFutureTasksPage.vue'),
        meta: { titleKey: 'ai.futureTaskTab' },
      },
      {
        path: 'ai/skills',
        name: 'ai-skills',
        component: () => import('@/pages/AISkillsPage.vue'),
        meta: { titleKey: 'ai.skillsTab' },
      },
      {
        path: 'ai/debug',
        name: 'ai-debug',
        component: () => import('@/pages/AIDebugPage.vue'),
        meta: { titleKey: 'ai.debugTab' },
      },
      ...aiManagementPageDescriptors
        .filter(item => ![
          'overview',
          'models',
          'knowledge',
          'personas',
          'memories',
          'relationships',
          'profiles',
          'futureTasks',
          'skills',
          'debug',
        ].includes(item.page))
        .map(item => ({
          path: item.path.replace(/^\//, ''),
          name: item.routeName,
          component: PlaceholderPage,
          meta: { titleKey: item.titleKey },
        })),
      { path: 'plugins', redirect: '/plugins/config' },
      {
        path: 'plugins/config',
        name: 'plugins',
        component: () => import('@/pages/PluginsPage.vue'),
        meta: { titleKey: 'plugins.title' },
      },
      {
        path: 'plugins/store',
        name: 'plugins-store',
        component: () => import('@/pages/PluginStorePage.vue'),
        meta: { titleKey: 'pluginStore.title' },
      },
      {
        path: 'permissions',
        name: 'permissions',
        component: () => import('@/pages/PermissionsPage.vue'),
        meta: { titleKey: 'permissions.title' },
      },
      {
        path: 'logs',
        name: 'logs',
        component: () => import('@/pages/LogsPage.vue'),
        meta: { titleKey: 'logs.liveTitle' },
      },
      {
        path: 'logs/history',
        name: 'logs-history',
        component: () => import('@/pages/LogHistoryPage.vue'),
        meta: { titleKey: 'logs.historyTitle' },
      },
      {
        path: 'chat',
        name: 'chat',
        component: () => import('@/pages/ChatPage.vue'),
        meta: { titleKey: 'chat.title' },
      },
      {
        path: 'accounts',
        name: 'accounts',
        component: () => import('@/pages/AccountsPage.vue'),
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
  const isPublicRoute = to.meta.requiresAuth === false

  if (!isPublicRoute && !token) {
    return { name: 'login' }
  }

  if (token && !authStore.isAuthenticated) {
    await authStore.ensureInitialized()
  }

  if (!isPublicRoute && !authStore.isAuthenticated) {
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
