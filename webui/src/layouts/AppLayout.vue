<script setup lang="ts">
import type { Component } from 'vue'
import type { SupportedLocale } from '@/app/i18n'
import {
  Bot,
  Brain,
  Cable,
  ChevronDown,
  Languages,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Moon,
  Plug,
  RefreshCw,
  ScrollText,
  Settings,
  Shield,
  ShoppingBag,
  Sun,
  Undo2,
  UploadCloud,
  UserCog,
  X,
} from '@lucide/vue'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarSeparator,
  SidebarTrigger,
} from '@/components/ui/sidebar'
import { logout as logoutSession } from '@/api/auth'
import { getStatus } from '@/api/dashboard'
import { getProjectUpdateStatus, refreshProjectUpdateStatus } from '@/api/projectUpdate'
import { useRestartController } from '@/composables/useRestartController'
import { useAuthStore } from '@/stores/auth'
import { useRestartStore } from '@/stores/restart'
import { useThemeStore } from '@/stores/theme'
import {
  hasProjectUpdateReleaseUpdate,
  shouldRefreshProjectUpdateRemote,
} from '@/utils/projectUpdateState'

interface NavItem {
  icon: Component
  key: string
  title: string
  to: string
}

type PendingConfirmAction = 'restart' | 'revert' | null

const pendingConfirmAction = ref<PendingConfirmAction>(null)
const sidebarOpen = ref(true)
const storeNavExpanded = ref(false)
const logsNavExpanded = ref(false)
const storeNavUserCollapsed = ref(false)
const logsNavUserCollapsed = ref(false)
const hasProjectReleaseUpdate = ref(false)
const { t, locale } = useI18n()
const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const restartStore = useRestartStore()
const themeStore = useThemeStore()
const { reverting, restarting, restartAndReload, revertPendingChanges } = useRestartController()

const navItems = computed<NavItem[]>(() => [
  { key: 'dashboard', icon: LayoutDashboard, title: t('layout.dashboard'), to: '/dashboard' },
  { key: 'core', icon: Settings, title: t('layout.core'), to: '/core' },
  { key: 'ai', icon: Brain, title: t('layout.aiWorkbench'), to: '/ai' },
  { key: 'plugins', icon: Plug, title: t('layout.pluginsWorkbench'), to: '/plugins' },
  { key: 'permissions', icon: Shield, title: t('layout.permissions'), to: '/permissions' },
  { key: 'chat', icon: MessageSquare, title: t('layout.chat'), to: '/chat' },
  ...(authStore.isOwner
    ? [{ key: 'accounts', icon: UserCog, title: t('layout.accounts'), to: '/accounts' }]
    : []),
])

const themeToggleLabel = computed(() =>
  themeStore.isDark ? t('layout.toLight') : t('layout.toDark'),
)
const currentLocaleLabel = computed(() =>
  locale.value === 'zh_CN' ? t('layout.chinese') : t('layout.english'),
)
const currentRoleLabel = computed(() => {
  if (authStore.role === 'owner') {
    return t('accounts.roles.owner')
  }
  return authStore.role || t('common.none')
})
const restartEntries = computed(() => restartStore.entries.slice(0, 3))
const confirmDialogOpen = computed({
  get: () => pendingConfirmAction.value !== null,
  set: value => {
    if (!value) {
      pendingConfirmAction.value = null
    }
  },
})
const confirmTitle = computed(() =>
  pendingConfirmAction.value === 'revert'
    ? t('restart.revert')
    : t('dashboard.restart'),
)
const confirmDescription = computed(() =>
  pendingConfirmAction.value === 'revert'
    ? t('restart.revertConfirm')
    : t('dashboard.restartConfirm'),
)
const confirmActionBusy = computed(() => {
  if (pendingConfirmAction.value === 'restart') {
    return restarting.value
  }
  if (pendingConfirmAction.value === 'revert') {
    return reverting.value
  }
  return false
})
const showProjectUpdateNotice = computed(() =>
  authStore.isOwner && hasProjectReleaseUpdate.value,
)

function routeMatches(to: string) {
  const targetPath = to.replace(/\/+$/, '') || '/'
  const currentPath = route.path.replace(/\/+$/, '') || '/'
  return currentPath === targetPath || currentPath.startsWith(`${targetPath}/`)
}

const storeNavItems = computed<NavItem[]>(() => [
  { key: 'plugin-store', icon: ShoppingBag, title: t('layout.pluginStore'), to: '/store/plugins' },
  { key: 'adapter-store', icon: Cable, title: t('layout.adapterStore'), to: '/store/adapters' },
])

const storeRouteActive = computed(() =>
  storeNavItems.value.some(item => routeMatches(item.to)),
)
const storeNavVisible = computed(() =>
  storeRouteActive.value ? !storeNavUserCollapsed.value : storeNavExpanded.value,
)

const logsNavItems = computed<NavItem[]>(() => [
  { key: 'logs-live', icon: ScrollText, title: t('layout.logs'), to: '/logs/live' },
  { key: 'logs-history', icon: ScrollText, title: t('layout.logsHistory'), to: '/logs/history' },
])

const logsRouteActive = computed(() =>
  logsNavItems.value.some(item => routeMatches(item.to)),
)
const logsNavVisible = computed(() =>
  logsRouteActive.value ? !logsNavUserCollapsed.value : logsNavExpanded.value,
)

function toggleStoreNav() {
  if (storeRouteActive.value) {
    storeNavUserCollapsed.value = !storeNavUserCollapsed.value
    return
  }
  storeNavExpanded.value = !storeNavExpanded.value
}

function toggleLogsNav() {
  if (logsRouteActive.value) {
    logsNavUserCollapsed.value = !logsNavUserCollapsed.value
    return
  }
  logsNavExpanded.value = !logsNavExpanded.value
}

function setLocale(nextLocale: SupportedLocale) {
  if (locale.value === nextLocale) {
    return
  }
  locale.value = nextLocale
  localStorage.setItem('apeiria-locale', nextLocale)
  document.documentElement.lang = nextLocale === 'zh_CN' ? 'zh-CN' : 'en-US'
}

async function handleLogout() {
  restartStore.clearPending()
  try {
    await logoutSession()
  } catch {
    // Local logout still clears browser state when the server is unreachable.
  }
  authStore.logout()
  await router.push('/login')
}

function requestRestart() {
  pendingConfirmAction.value = 'restart'
}

function requestRevertPendingChanges() {
  if (restartStore.hasReversiblePending) {
    pendingConfirmAction.value = 'revert'
  }
}

async function refreshProjectUpdateNotice() {
  if (!authStore.isOwner) {
    hasProjectReleaseUpdate.value = false
    return
  }

  try {
    const response = await getProjectUpdateStatus()
    let nextStatus = response.data
    if (shouldRefreshProjectUpdateRemote(response.data.remote_refresh)) {
      const refreshResponse = await refreshProjectUpdateStatus()
      nextStatus = refreshResponse.data
    }
    hasProjectReleaseUpdate.value = hasProjectUpdateReleaseUpdate(nextStatus)
  } catch {
    hasProjectReleaseUpdate.value = false
  }
}

async function syncRestartReminderWithRuntime() {
  if (!authStore.isOwner) {
    return
  }

  try {
    const response = await getStatus()
    restartStore.syncRuntimeUptime(response.data.uptime)
  } catch {
    // Keep local reminders when the runtime status cannot be checked.
  }
}

async function runConfirmedAction() {
  const action = pendingConfirmAction.value
  pendingConfirmAction.value = null

  if (action === 'restart') {
    await restartAndReload()
    return
  }

  if (action === 'revert') {
    await revertPendingChanges()
  }
}

watch(storeRouteActive, active => {
  if (!active) {
    storeNavUserCollapsed.value = false
  }
})

watch(logsRouteActive, active => {
  if (!active) {
    logsNavUserCollapsed.value = false
  }
})

watch(
  () => authStore.isOwner,
  () => {
    void refreshProjectUpdateNotice()
    void syncRestartReminderWithRuntime()
  },
  { immediate: true },
)
</script>

<template>
  <SidebarProvider v-model:open="sidebarOpen">
    <a class="app-shell-skip-link" href="#app-main-content">
      {{ t('layout.skipToContent') }}
    </a>
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <div class="app-shell-brand">
          <div class="app-shell-brand__identity">
            <div class="app-shell-brand__mark">
              <Bot />
            </div>
            <div class="app-shell-brand__text">
              <strong>{{ t('layout.brand') }}</strong>
              <span>{{ t('layout.subtitle') }}</span>
            </div>
          </div>
          <SidebarTrigger class="app-shell-brand__toggle" />
        </div>
      </SidebarHeader>

      <SidebarSeparator />

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>{{ t('layout.navigation') }}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem v-for="item in navItems" :key="item.key">
                <SidebarMenuButton
                  as-child
                  :is-active="routeMatches(item.to)"
                  :tooltip="item.title"
                >
                  <RouterLink :to="item.to">
                    <component :is="item.icon" />
                    <span>{{ item.title }}</span>
                  </RouterLink>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <DropdownMenu v-if="!sidebarOpen">
                  <DropdownMenuTrigger as-child>
                    <SidebarMenuButton
                      :is-active="storeRouteActive"
                      :tooltip="t('layout.store')"
                    >
                      <ShoppingBag />
                      <span>{{ t('layout.store') }}</span>
                    </SidebarMenuButton>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start" side="right">
                    <DropdownMenuLabel>{{ t('layout.store') }}</DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    <DropdownMenuGroup>
                      <DropdownMenuItem
                        v-for="item in storeNavItems"
                        :key="item.key"
                        @click="router.push(item.to)"
                      >
                        <component :is="item.icon" />
                        <span>{{ item.title }}</span>
                      </DropdownMenuItem>
                    </DropdownMenuGroup>
                  </DropdownMenuContent>
                </DropdownMenu>
                <SidebarMenuButton
                  v-else
                  :is-active="storeRouteActive"
                  :tooltip="t('layout.store')"
                  @click="toggleStoreNav"
                >
                  <ShoppingBag />
                  <span>{{ t('layout.store') }}</span>
                  <ChevronDown
                    class="app-shell-store-caret"
                    :class="{ 'app-shell-store-caret--open': storeNavVisible }"
                  />
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem
                v-for="item in storeNavItems"
                v-show="storeNavVisible"
                :key="item.key"
                class="app-shell-store-item"
              >
                <SidebarMenuButton
                  as-child
                  :is-active="routeMatches(item.to)"
                  :tooltip="item.title"
                >
                  <RouterLink :to="item.to">
                    <component :is="item.icon" />
                    <span>{{ item.title }}</span>
                  </RouterLink>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <DropdownMenu v-if="!sidebarOpen">
                  <DropdownMenuTrigger as-child>
                    <SidebarMenuButton
                      :is-active="logsRouteActive"
                      :tooltip="t('layout.logsGroup')"
                    >
                      <ScrollText />
                      <span>{{ t('layout.logsGroup') }}</span>
                    </SidebarMenuButton>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start" side="right">
                    <DropdownMenuLabel>{{ t('layout.logsGroup') }}</DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    <DropdownMenuGroup>
                      <DropdownMenuItem
                        v-for="item in logsNavItems"
                        :key="item.key"
                        @click="router.push(item.to)"
                      >
                        <component :is="item.icon" />
                        <span>{{ item.title }}</span>
                      </DropdownMenuItem>
                    </DropdownMenuGroup>
                  </DropdownMenuContent>
                </DropdownMenu>
                <SidebarMenuButton
                  v-else
                  :is-active="logsRouteActive"
                  :tooltip="t('layout.logsGroup')"
                  @click="toggleLogsNav"
                >
                  <ScrollText />
                  <span>{{ t('layout.logsGroup') }}</span>
                  <ChevronDown
                    class="app-shell-store-caret"
                    :class="{ 'app-shell-store-caret--open': logsNavVisible }"
                  />
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem
                v-for="item in logsNavItems"
                v-show="logsNavVisible"
                :key="item.key"
                class="app-shell-store-item"
              >
                <SidebarMenuButton
                  as-child
                  :is-active="routeMatches(item.to)"
                  :tooltip="item.title"
                >
                  <RouterLink :to="item.to">
                    <component :is="item.icon" />
                    <span>{{ item.title }}</span>
                  </RouterLink>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarSeparator />

      <SidebarFooter>
        <div class="app-shell-user">
          <div class="app-shell-user__avatar">
            {{ (authStore.principal?.username || '?').slice(0, 1).toUpperCase() }}
          </div>
          <div class="app-shell-user__text">
            <strong>{{ authStore.principal?.username || t('layout.unknownUser') }}</strong>
            <span>{{ currentRoleLabel }}</span>
          </div>
          <Badge
            v-if="showProjectUpdateNotice"
            as="button"
            class="app-shell-update-notice"
            type="button"
            variant="outline"
            @click="router.push('/update')"
          >
            {{ t('layout.projectUpdateAvailable') }}
          </Badge>
        </div>

        <div class="app-shell-controls">
          <DropdownMenu>
            <DropdownMenuTrigger as-child>
              <Button size="icon" :title="t('layout.language')" variant="ghost">
                <Languages data-icon="inline-start" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>{{ currentLocaleLabel }}</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuGroup>
                <DropdownMenuItem @click="setLocale('zh_CN')">
                  {{ t('layout.chinese') }}
                </DropdownMenuItem>
                <DropdownMenuItem @click="setLocale('en_US')">
                  {{ t('layout.english') }}
                </DropdownMenuItem>
              </DropdownMenuGroup>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button
            v-if="authStore.isOwner"
            size="icon"
            :title="t('layout.projectUpdate')"
            variant="ghost"
            @click="router.push('/update')"
          >
            <UploadCloud data-icon="inline-start" />
          </Button>
          <Button size="icon" :title="themeToggleLabel" variant="ghost" @click="themeStore.toggleTheme()">
            <Sun v-if="themeStore.isDark" data-icon="inline-start" />
            <Moon v-else data-icon="inline-start" />
          </Button>
          <Button size="icon" :title="t('layout.logout')" variant="ghost" @click="handleLogout">
            <LogOut data-icon="inline-start" />
          </Button>
        </div>
      </SidebarFooter>

      <SidebarRail />
    </Sidebar>

    <SidebarInset>
      <main id="app-main-content" class="app-shell-content" tabindex="-1">
        <Alert v-if="restartStore.hasPendingRestart" class="restart-banner">
          <RefreshCw />
          <AlertTitle>{{ t('restart.bannerTitle', { count: restartStore.pendingCount }) }}</AlertTitle>
          <AlertDescription>
            <p>{{ t('restart.bannerDescription') }}</p>
            <div class="restart-banner__entries">
              <Badge v-for="entry in restartEntries" :key="entry.id" variant="outline">
                {{ entry.summary }}
              </Badge>
            </div>
            <div class="restart-banner__actions">
              <Button :disabled="restarting" size="sm" variant="secondary" @click="requestRestart">
                <RefreshCw data-icon="inline-start" />
                {{ t('dashboard.restart') }}
              </Button>
              <Button
                v-if="restartStore.hasReversiblePending"
                :disabled="reverting"
                size="sm"
                variant="ghost"
                @click="requestRevertPendingChanges"
              >
                <Undo2 data-icon="inline-start" />
                {{ t('restart.revert') }}
              </Button>
              <Button size="sm" variant="ghost" @click="restartStore.clearPending()">
                <X data-icon="inline-start" />
                {{ t('restart.clear') }}
              </Button>
            </div>
          </AlertDescription>
        </Alert>

        <RouterView />
      </main>
    </SidebarInset>

    <AlertDialog v-model:open="confirmDialogOpen">
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{{ confirmTitle }}</AlertDialogTitle>
          <AlertDialogDescription>{{ confirmDescription }}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{{ t('common.cancel') }}</AlertDialogCancel>
          <Button :disabled="confirmActionBusy" @click="runConfirmedAction">
            {{ t('common.confirm') }}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </SidebarProvider>
</template>
