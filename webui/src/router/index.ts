import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import AppShell from "@/layouts/AppShell.vue";

declare module "vue-router" {
  interface RouteMeta {
    requiresAuth?: boolean;
  }
}

const LoginView = () => import("@/views/LoginView.vue");
const DashboardView = () => import("@/views/DashboardView.vue");
const PluginsView = () => import("@/views/PluginsView.vue");
const AdaptersView = () => import("@/views/AdaptersView.vue");
const StoreView = () => import("@/views/StoreView.vue");
const SettingsNonebotView = () => import("@/views/SettingsNonebotView.vue");
const SettingsApeiriaView = () => import("@/views/SettingsApeiriaView.vue");
const LogsView = () => import("@/views/LogsView.vue");
const WebchatView = () => import("@/views/WebchatView.vue");
const AccountView = () => import("@/views/AccountView.vue");

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/login",
      name: "login",
      component: LoginView,
    },
    {
      path: "/",
      component: AppShell,
      meta: { requiresAuth: true },
      children: [
        { path: "", name: "dashboard", component: DashboardView },
        { path: "plugins", name: "plugins", component: PluginsView },
        { path: "adapters", name: "adapters", component: AdaptersView },
        { path: "store", name: "store", component: StoreView },
        { path: "settings", redirect: { name: "settings-nonebot" } },
        {
          path: "settings/nonebot",
          name: "settings-nonebot",
          component: SettingsNonebotView,
        },
        {
          path: "settings/apeiria",
          name: "settings-apeiria",
          component: SettingsApeiriaView,
        },
        { path: "logs", name: "logs", component: LogsView },
        { path: "webchat", name: "webchat", component: WebchatView },
        { path: "account", name: "account", component: AccountView },
      ],
    },
  ],
});

router.beforeEach((to, _from) => {
  const auth = useAuthStore();
  const needsAuth = to.matched.some((r) => r.meta.requiresAuth === true);
  if (needsAuth && !auth.token) {
    return { name: "login" };
  }
  if (to.name === "login" && auth.token) {
    return { name: "dashboard" };
  }
});

export default router;
