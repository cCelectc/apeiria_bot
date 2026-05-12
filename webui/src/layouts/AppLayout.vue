<script setup lang="ts">
import type { Component } from 'vue'
import type { SupportedLocale } from '@/app/i18n'
import {
  Bot,
  Brain,
  Bug,
  CalendarClock,
  ChevronDown,
  ChevronsLeft,
  ChevronsRight,
  ContactRound,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  MessagesSquare,
  Moon,
  Network,
  PanelLeft,
  Plug,
  ScrollText,
  ServerCog,
  Settings,
  Shield,
  Store,
  Sun,
  UserCog,
  Wrench,
  X,
  BookOpenCheck,
  Languages,
  RefreshCw,
  Undo2,
} from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Separator } from '@/components/ui/separator'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { useRestartController } from '@/composables/useRestartController'
import { useAuthStore } from '@/stores/auth'
import { useRestartStore } from '@/stores/restart'
import { useThemeStore } from '@/stores/theme'
import { aiManagementPageDescriptors } from '@/router/aiRoutes'

interface NavLeaf {
  icon: Component
  key: string
  title: string
  to: string
}

interface NavGroup {
  children: NavLeaf[]
  icon: Component
  key: string
  title: string
}

type NavItem = NavLeaf | NavGroup

const iconMap: Record<string, Component> = {
  BookOpenCheck,
  Brain,
  Bug,
  CalendarClock,
  ContactRound,
  LayoutDashboard,
  MessageSquare,
  MessagesSquare,
  Network,
  ServerCog,
  Wrench,
}

const drawerOpen = ref(false)
const rail = ref(false)
const openedGroups = ref<string[]>([])
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
  {
    key: 'ai-group',
    icon: Brain,
    title: t('layout.aiGroup'),
    children: aiManagementPageDescriptors.map(item => ({
      icon: iconMap[item.icon] ?? Brain,
      key: item.page,
      title: t(item.titleKey),
      to: item.path,
    })),
  },
  {
    key: 'plugins-group',
    icon: Plug,
    title: t('layout.pluginsGroup'),
    children: [
      { key: 'plugins-config', icon: Plug, title: t('layout.plugins'), to: '/plugins/config' },
      { key: 'plugins-store', icon: Store, title: t('layout.pluginStore'), to: '/plugins/store' },
    ],
  },
  { key: 'chat', icon: MessageSquare, title: t('layout.chat'), to: '/chat' },
  {
    key: 'logs-group',
    icon: ScrollText,
    title: t('layout.logsGroup'),
    children: [
      { key: 'logs-live', icon: ScrollText, title: t('layout.logs'), to: '/logs' },
      { key: 'logs-history', icon: History, title: t('layout.logsHistory'), to: '/logs/history' },
    ],
  },
  {
    key: 'more-group',
    icon: PanelLeft,
    title: t('layout.moreGroup'),
    children: [
      { key: 'permissions', icon: Shield, title: t('layout.permissions'), to: '/permissions' },
    ],
  },
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
const currentRouteTitle = computed(() => {
  const titleKey = typeof route.meta.titleKey === 'string' ? route.meta.titleKey : ''
  return titleKey ? t(titleKey) : t('layout.defaultTitle')
})
const currentRoleLabel = computed(() => {
  if (authStore.role === 'owner') {
    return t('accounts.roles.owner')
  }
  return authStore.role || t('common.none')
})
const restartEntries = computed(() => restartStore.entries.slice(0, 3))
const sidebarWidthClass = computed(() => rail.value ? 'app-layout--rail' : 'app-layout--full')
const activeNavKey = computed(() => {
  const leaves = navItems.value.flatMap(item => isGroup(item) ? item.children : [item])
  return leaves
    .filter(item => routeMatches(item.to))
    .sort((left, right) => right.to.length - left.to.length)[0]?.key ?? ''
})

watch(
  () => route.path,
  nextPath => {
    const groups = new Set(openedGroups.value)
    if (nextPath.startsWith('/plugins')) {
      groups.add('plugins-group')
    }
    if (nextPath.startsWith('/ai')) {
      groups.add('ai-group')
    }
    if (nextPath.startsWith('/logs')) {
      groups.add('logs-group')
    }
    if (nextPath.startsWith('/permissions')) {
      groups.add('more-group')
    }
    openedGroups.value = Array.from(groups)
    drawerOpen.value = false
  },
  { immediate: true },
)

async function handleRestart() {
  if (!window.confirm(t('dashboard.restartConfirm'))) {
    return
  }
  await restartAndReload()
}

async function handleRevertPendingChanges() {
  if (!window.confirm(t('restart.revertConfirm'))) {
    return
  }
  await revertPendingChanges()
}

function setLocale(nextLocale: SupportedLocale) {
  if (locale.value === nextLocale) {
    return
  }
  locale.value = nextLocale
  localStorage.setItem('apeiria-locale', nextLocale)
  document.documentElement.lang = nextLocale === 'zh_CN' ? 'zh-CN' : 'en-US'
}

function handleLogout() {
  restartStore.clearPending()
  authStore.logout()
  router.push('/login')
}

function isGroup(item: NavItem): item is NavGroup {
  return 'children' in item
}

function routeMatches(to: string) {
  const targetPath = to.replace(/\/+$/, '') || '/'
  const currentPath = route.path.replace(/\/+$/, '') || '/'
  return currentPath === targetPath || currentPath.startsWith(`${targetPath}/`)
}

function isLeafActive(item: NavLeaf) {
  return activeNavKey.value === item.key
}

function isGroupActive(item: NavGroup) {
  return item.children.some(child => routeMatches(child.to))
}

function toggleGroup(key: string) {
  openedGroups.value = openedGroups.value.includes(key)
    ? openedGroups.value.filter(item => item !== key)
    : [...openedGroups.value, key]
}

</script>

<template>
  <div class="app-layout" :class="sidebarWidthClass">
    <aside class="app-sidebar">
      <div class="app-sidebar__header">
        <div v-if="!rail" class="app-brand">
          <span class="app-brand__mark">
            <Bot :size="19" />
          </span>
          <span>
            <strong>{{ t('layout.brand') }}</strong>
            <small>{{ t('layout.subtitle') }}</small>
          </span>
        </div>
        <Button
          class="app-sidebar__rail-toggle"
          size="icon"
          :title="rail ? t('layout.navigation') : t('common.close')"
          variant="ghost"
          @click="rail = !rail"
        >
          <ChevronsRight v-if="rail" :size="17" />
          <ChevronsLeft v-else :size="17" />
        </Button>
      </div>

      <Separator />

      <nav class="app-nav" :aria-label="t('layout.navigation')">
        <template v-for="item in navItems" :key="item.key">
          <div v-if="isGroup(item)" class="app-nav__group">
            <DropdownMenu v-if="rail">
              <DropdownMenuTrigger as-child>
                <button
                  class="app-nav__item app-nav__item--rail"
                  :class="{ 'app-nav__item--group-active': isGroupActive(item) }"
                  :title="item.title"
                  type="button"
                >
                  <component :is="item.icon" :size="17" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="start"
                class="app-nav__rail-menu"
                side="right"
                :side-offset="10"
              >
                <DropdownMenuLabel class="app-nav__rail-menu-title">
                  {{ item.title }}
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  v-for="child in item.children"
                  :key="child.to"
                  as-child
                >
                  <RouterLink
                    class="app-nav__rail-link"
                    :class="{ 'app-nav__rail-link--active': isLeafActive(child) }"
                    :to="child.to"
                  >
                    <component :is="child.icon" :size="15" />
                    <span>{{ child.title }}</span>
                  </RouterLink>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <button
              v-else
              class="app-nav__item"
              :class="{
                'app-nav__item--open': openedGroups.includes(item.key) || isGroupActive(item),
              }"
              type="button"
              @click="toggleGroup(item.key)"
            >
                <component :is="item.icon" :size="17" />
                <span>{{ item.title }}</span>
                <ChevronDown
                  class="app-nav__chevron"
                  :class="{ 'app-nav__chevron--open': openedGroups.includes(item.key) }"
                  :size="14"
                />
              </button>
            <div v-if="!rail && openedGroups.includes(item.key)" class="app-nav__children">
              <RouterLink
                v-for="child in item.children"
                :key="child.to"
                class="app-nav__child"
                :class="{ 'app-nav__child--active': isLeafActive(child) }"
                :to="child.to"
              >
                <component :is="child.icon" :size="15" />
                <span>{{ child.title }}</span>
              </RouterLink>
            </div>
          </div>
          <RouterLink
            v-else
            class="app-nav__item"
            :class="{ 'app-nav__item--active': isLeafActive(item) }"
            :to="item.to"
          >
            <component :is="item.icon" :size="17" />
            <span v-if="!rail">{{ item.title }}</span>
          </RouterLink>
        </template>
      </nav>

      <div class="app-sidebar__footer">
        <div v-if="!rail" class="app-user">
          <div class="app-user__avatar">
            {{ (authStore.principal?.username || '?').slice(0, 1).toUpperCase() }}
          </div>
          <div>
            <strong>{{ authStore.principal?.username || t('layout.unknownUser') }}</strong>
            <small>{{ currentRoleLabel }}</small>
          </div>
        </div>
        <div class="app-sidebar__controls">
          <DropdownMenu>
            <DropdownMenuTrigger as-child>
              <Button size="icon" :title="t('layout.language')" variant="ghost">
                <Languages :size="17" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>{{ currentLocaleLabel }}</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem @click="setLocale('zh_CN')">
                {{ t('layout.chinese') }}
              </DropdownMenuItem>
              <DropdownMenuItem @click="setLocale('en_US')">
                {{ t('layout.english') }}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button size="icon" :title="themeToggleLabel" variant="ghost" @click="themeStore.toggleTheme()">
            <Sun v-if="themeStore.isDark" :size="17" />
            <Moon v-else :size="17" />
          </Button>
          <Button size="icon" :title="t('layout.logout')" variant="ghost" @click="handleLogout">
            <LogOut :size="17" />
          </Button>
        </div>
      </div>
    </aside>

    <div class="app-main">
      <header class="app-topbar">
        <Button class="md:hidden" size="icon" variant="ghost" @click="drawerOpen = true">
          <Menu :size="18" />
        </Button>
        <div class="app-topbar__title">
          <span>{{ currentRouteTitle }}</span>
          <small>{{ t('layout.brand') }}</small>
        </div>
        <Badge variant="secondary">
          {{ currentLocaleLabel }}
        </Badge>
      </header>

      <main class="app-content">
        <Alert v-if="restartStore.hasPendingRestart" class="restart-banner">
          <RefreshCw :size="17" />
          <AlertTitle>{{ t('restart.bannerTitle', { count: restartStore.pendingCount }) }}</AlertTitle>
          <AlertDescription>
            <p>{{ t('restart.bannerDescription') }}</p>
            <div class="restart-banner__entries">
              <Badge v-for="entry in restartEntries" :key="entry.id" variant="outline">
                {{ entry.summary }}
              </Badge>
            </div>
            <div class="restart-banner__actions">
              <Button :disabled="restarting" size="sm" variant="secondary" @click="handleRestart">
                <RefreshCw :size="14" />
                {{ t('dashboard.restart') }}
              </Button>
              <Button :disabled="reverting" size="sm" variant="ghost" @click="handleRevertPendingChanges">
                <Undo2 :size="14" />
                {{ t('restart.revert') }}
              </Button>
              <Button size="sm" variant="ghost" @click="restartStore.clearPending()">
                <X :size="14" />
                {{ t('restart.clear') }}
              </Button>
            </div>
          </AlertDescription>
        </Alert>

        <RouterView />
      </main>
    </div>

    <Sheet v-model:open="drawerOpen">
      <SheetContent class="mobile-sheet" side="left">
        <SheetHeader>
          <SheetTitle>{{ t('layout.navigation') }}</SheetTitle>
        </SheetHeader>
        <nav class="app-nav app-nav--mobile">
          <template v-for="item in navItems" :key="item.key">
            <div v-if="isGroup(item)" class="app-nav__group">
              <button
                class="app-nav__item"
                :class="{ 'app-nav__item--group-active': isGroupActive(item) }"
                type="button"
                @click="toggleGroup(item.key)"
              >
                <component :is="item.icon" :size="17" />
                <span>{{ item.title }}</span>
                <ChevronDown
                  class="app-nav__chevron"
                  :class="{ 'app-nav__chevron--open': openedGroups.includes(item.key) }"
                  :size="14"
                />
              </button>
              <div v-if="openedGroups.includes(item.key)" class="app-nav__children">
                <RouterLink
                  v-for="child in item.children"
                  :key="child.to"
                  class="app-nav__child"
                  :class="{ 'app-nav__child--active': isLeafActive(child) }"
                  :to="child.to"
                >
                  <component :is="child.icon" :size="15" />
                  <span>{{ child.title }}</span>
                </RouterLink>
              </div>
            </div>
            <RouterLink
              v-else
              class="app-nav__item"
              :class="{ 'app-nav__item--active': isLeafActive(item) }"
              :to="item.to"
            >
              <component :is="item.icon" :size="17" />
              <span>{{ item.title }}</span>
            </RouterLink>
          </template>
        </nav>
      </SheetContent>
    </Sheet>

  </div>
</template>
