import { createRouter, createWebHistory } from "vue-router"
import { useAuthStore } from "@/stores/auth"

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/login",
      name: "login",
      component: () => import("@/pages/LoginPage.vue"),
      meta: { requiresAuth: false },
    },
    {
      path: "/",
      component: () => import("@/components/AppShell.vue"),
      meta: { requiresAuth: true },
      children: [
        {
          path: "",
          redirect: "/dashboard",
        },
        {
          path: "dashboard",
          name: "dashboard",
          component: () => import("@/pages/OverviewPage.vue"),
          meta: { title: "Dashboard" },
        },
        {
          path: "config",
          children: [
            {
              path: "core",
              name: "core-settings",
              component: () => import("@/pages/CoreSettingsPage.vue"),
              meta: { title: "Core Settings" },
            },
            {
              path: "plugins",
              name: "plugins",
              component: () => import("@/pages/PluginsPage.vue"),
              meta: { title: "Plugins" },
            },
            {
              path: "store",
              name: "store",
              component: () => import("@/pages/StorePage.vue"),
              meta: { title: "Store" },
            },
            {
              path: "adapters",
              name: "adapters",
              component: () => import("@/pages/AdaptersPage.vue"),
              meta: { title: "Adapters" },
            },
            {
              path: "permissions",
              name: "permissions",
              component: () => import("@/pages/PermissionsPage.vue"),
              meta: { title: "Permissions" },
            },
            {
              path: "accounts",
              name: "accounts",
              component: () => import("@/pages/AccountsPage.vue"),
              meta: { title: "Accounts" },
            },
          ],
        },
        {
          path: "ai",
          children: [
            {
              path: "",
              redirect: "/ai/overview",
            },
            {
              path: "overview",
              name: "ai-overview",
              component: () => import("@/pages/AIOverviewPage.vue"),
              meta: { title: "AI Overview" },
            },
            {
              path: "models",
              name: "ai-models",
              component: () => import("@/pages/AIModelsPage.vue"),
              meta: { title: "Models" },
            },
            {
              path: "sessions",
              name: "ai-sessions",
              component: () => import("@/pages/AISessionsPage.vue"),
              meta: { title: "Sessions" },
            },
            {
              path: "memories",
              name: "ai-memories",
              component: () => import("@/pages/AIMemoriesPage.vue"),
              meta: { title: "Memories" },
            },
            {
              path: "knowledge",
              name: "ai-knowledge",
              component: () => import("@/pages/AIKnowledgePage.vue"),
              meta: { title: "Knowledge" },
            },
            {
              path: "personas",
              name: "ai-personas",
              component: () => import("@/pages/AIPersonasPage.vue"),
              meta: { title: "Personas" },
            },
            {
              path: "profiles",
              name: "ai-profiles",
              component: () => import("@/pages/AIProfilesPage.vue"),
              meta: { title: "Profiles" },
            },
            {
              path: "relationships",
              name: "ai-relationships",
              component: () => import("@/pages/AIRelationshipsPage.vue"),
              meta: { title: "Relationships" },
            },
            {
              path: "runtime",
              name: "ai-runtime",
              component: () => import("@/pages/AIRuntimeSettingsPage.vue"),
              meta: { title: "Runtime Settings" },
            },
            {
              path: "debug",
              name: "ai-debug",
              component: () => import("@/pages/AIDebugPage.vue"),
              meta: { title: "Debug" },
            },
          ],
        },
        {
          path: "ops",
          children: [
            {
              path: "chat",
              name: "chat",
              component: () => import("@/pages/ChatPage.vue"),
              meta: { title: "Chat" },
            },
            {
              path: "logs",
              name: "logs",
              component: () => import("@/pages/LogsPage.vue"),
              meta: { title: "Logs" },
            },
            {
              path: "update",
              name: "update",
              component: () => import("@/pages/UpdatePage.vue"),
              meta: { title: "Update" },
            },
          ],
        },
      ],
    },
  ],
})

router.beforeEach(async (to, _from, next) => {
  const auth = useAuthStore()

  if (to.meta.requiresAuth === false) {
    if (auth.isAuthenticated) {
      return next("/dashboard")
    }
    return next()
  }

  await auth.ensureInitialized("anonymous")

  if (!auth.isAuthenticated) {
    return next(`/login?redirect=${encodeURIComponent(to.fullPath)}`)
  }

  next()
})

export default router
