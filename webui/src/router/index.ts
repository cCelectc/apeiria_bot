import type { RouteRecordRaw } from 'vue-router'
import { createRouter, createWebHistory } from 'vue-router'
import { CAP_ACCOUNT_MANAGE, CAP_CONTROL_PANEL } from '@/constants/access'
import { useAuthStore } from '@/stores/auth'
import { buildAuthRedirect } from '@/utils/routeRedirect'

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
        path: 'store/plugins',
        name: 'plugin-store',
        component: () => import('@/pages/PluginStorePage.vue'),
        meta: { titleKey: 'pluginStore.title' },
      },
      {
        path: 'store/adapters',
        name: 'adapter-store',
        component: () => import('@/pages/AdapterStorePage.vue'),
        meta: { titleKey: 'adapterStore.title' },
      },
      {
        path: 'ai',
        name: 'ai',
        component: () => import('@/pages/AIWorkbenchPage.vue'),
        meta: { titleKey: 'ai.title' },
      },
      {
        path: 'plugins',
        name: 'plugins',
        component: () => import('@/pages/PluginsWorkbenchPage.vue'),
        meta: { titleKey: 'plugins.workbenchTitle' },
      },
      {
        path: 'permissions',
        name: 'permissions',
        component: () => import('@/pages/PermissionsPage.vue'),
        meta: { titleKey: 'permissions.title' },
      },
      {
        path: 'logs/live',
        name: 'logs-live',
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
  const isPublicRoute = to.meta.requiresAuth === false

  if (!authStore.isAuthenticated) {
    await authStore.ensureInitialized({ unauthorizedStatus: 'anonymous' })
  }

  if (!isPublicRoute && !authStore.isAuthenticated) {
    return {
      name: 'login',
      query: { redirect: buildAuthRedirect(to.fullPath) },
    }
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
