<template>
  <v-navigation-drawer
    v-model="drawer"
    class="app-drawer"
    :class="{ 'app-drawer--rail': rail }"
    permanent
    :rail="rail"
    :rail-width="56"
    :width="228"
  >
    <div class="app-drawer__hero">
      <div class="app-drawer__header">
        <v-list-item
          v-if="!rail"
          class="app-drawer__brand"
          nav
          prepend-icon="mdi-robot-happy"
          :subtitle="t('layout.subtitle')"
          :title="t('layout.brand')"
        />
        <v-btn
          class="app-drawer__toggle"
          :icon="rail ? 'mdi-chevron-right' : 'mdi-chevron-left'"
          size="small"
          variant="text"
          @click="rail = !rail"
        />
      </div>
      <v-divider />
    </div>

    <div class="app-drawer__nav">
      <div v-if="!rail" class="app-drawer__section-label">{{ t('layout.navigation') }}</div>
      <v-list v-model:opened="openedGroups" class="app-drawer__list" density="compact" nav>
        <template v-for="item in navItems" :key="item.key">
          <v-menu
            v-if="rail && item.children"
            location="end"
            offset="12"
            open-on-click
          >
            <template #activator="{ props }">
              <v-list-item
                v-bind="props"
                class="app-drawer__group-activator"
                :class="{ 'app-drawer__group-activator--active': isGroupActive(item) }"
                :prepend-icon="item.icon"
                rounded="lg"
                :title="item.title"
              />
            </template>
            <div class="app-drawer__rail-menu">
              <div class="app-drawer__rail-menu-title">{{ item.title }}</div>
              <v-list class="app-drawer__rail-menu-list" density="compact" nav>
                <v-list-item
                  v-for="child in item.children"
                  :key="child.to"
                  class="app-drawer__rail-menu-item"
                  :prepend-icon="child.icon"
                  rounded="lg"
                  :title="child.title"
                  :to="child.to"
                />
              </v-list>
            </div>
          </v-menu>
          <v-list-group
            v-else-if="item.children"
            class="app-drawer__group"
            :value="item.key"
          >
            <template #activator="{ props }">
              <v-list-item
                v-bind="props"
                class="app-drawer__group-activator"
                :prepend-icon="item.icon"
                rounded="lg"
                :title="item.title"
              />
            </template>
            <div class="app-drawer__group-panel">
              <v-list-item
                v-for="child in item.children"
                :key="child.to"
                class="app-drawer__child-item"
                :prepend-icon="child.icon"
                rounded="xl"
                :title="child.title"
                :to="child.to"
              />
            </div>
          </v-list-group>
          <v-list-item
            v-else
            :prepend-icon="item.icon"
            rounded="lg"
            :title="item.title"
            :to="item.to"
          />
        </template>
      </v-list>
    </div>

    <template #append>
      <div class="app-drawer__footer">
        <div v-if="!rail" class="app-drawer__section-label">{{ t('layout.systemSection') }}</div>
        <v-list class="app-drawer__list" density="compact" nav>
          <v-list-item
            prepend-icon="mdi-account-circle-outline"
            rounded="lg"
            :subtitle="currentRoleLabel"
            :title="authStore.principal?.username || t('layout.unknownUser')"
          />
          <v-menu location="top" offset="8">
            <template #activator="{ props }">
              <v-list-item
                v-bind="props"
                prepend-icon="mdi-translate"
                rounded="lg"
                :subtitle="currentLocaleLabel"
                :title="t('layout.language')"
              />
            </template>
            <v-list class="locale-menu" density="compact">
              <v-list-item
                :active="locale === 'zh_CN'"
                rounded="lg"
                :title="t('layout.chinese')"
                @click="setLocale('zh_CN')"
              />
              <v-list-item
                :active="locale === 'en_US'"
                rounded="lg"
                :title="t('layout.english')"
                @click="setLocale('en_US')"
              />
            </v-list>
          </v-menu>
          <v-list-item
            prepend-icon="mdi-theme-light-dark"
            rounded="lg"
            :subtitle="themeToggleSubtitle"
            :title="themeToggleLabel"
            @click="toggleTheme"
          />
          <v-list-item
            prepend-icon="mdi-logout"
            rounded="lg"
            :title="t('layout.logout')"
            @click="handleLogout"
          />
        </v-list>
      </div>
    </template>
  </v-navigation-drawer>

  <v-main class="app-main">
    <v-container class="app-container" fluid>
      <v-alert
        v-if="restartStore.hasPendingRestart"
        class="app-restart-banner"
        closable
        color="warning"
        density="comfortable"
        icon="mdi-restart-alert"
        variant="tonal"
        @click:close="restartStore.clearPending()"
      >
        <div class="app-restart-banner__content">
          <div class="app-restart-banner__text">
            <div class="font-weight-medium">
              {{ t('restart.bannerTitle', { count: restartStore.pendingCount }) }}
            </div>
            <div class="text-body-2">
              {{ t('restart.bannerDescription') }}
            </div>
            <div class="app-restart-banner__chips">
              <v-chip
                v-for="entry in restartEntries"
                :key="entry.id"
                size="small"
                variant="outlined"
              >
                {{ entry.summary }}
              </v-chip>
            </div>
          </div>
          <div class="app-restart-banner__actions">
            <v-btn
              color="warning"
              :loading="restarting"
              variant="tonal"
              @click="handleRestart"
            >
              {{ t('dashboard.restart') }}
            </v-btn>
            <v-btn
              :loading="reverting"
              variant="text"
              @click="handleRevertPendingChanges"
            >
              {{ t('restart.revert') }}
            </v-btn>
            <v-btn
              variant="text"
              @click="restartStore.clearPending()"
            >
              {{ t('restart.clear') }}
            </v-btn>
          </div>
        </div>
      </v-alert>

      <router-view />
    </v-container>
  </v-main>

  <v-snackbar
    v-model="noticeStore.visible"
    :color="noticeStore.color"
    location="top right"
    timeout="2400"
  >
    {{ noticeStore.message }}
  </v-snackbar>
</template>

<script setup lang="ts">
  import type { SupportedLocale } from '@/plugins/i18n'
  import { computed, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRoute, useRouter } from 'vue-router'
  import { useTheme } from 'vuetify'
  import { useRestartController } from '@/composables/useRestartController'
  import { useAuthStore } from '@/stores/auth'
  import { useNoticeStore } from '@/stores/notice'
  import { useRestartStore } from '@/stores/restart'

  const drawer = ref(true)
  const rail = ref(false)
  const openedGroups = ref<string[]>([])
  const { t, locale } = useI18n()
  const theme = useTheme()
  const router = useRouter()
  const route = useRoute()
  const authStore = useAuthStore()
  const noticeStore = useNoticeStore()
  const restartStore = useRestartStore()
  const { reverting, restarting, restartAndReload, revertPendingChanges } = useRestartController()

  const navItems = computed(() => [
    { key: 'dashboard', icon: 'mdi-view-dashboard', title: t('layout.dashboard'), to: '/dashboard' },
    { key: 'core', icon: 'mdi-cog-outline', title: t('layout.core'), to: '/core' },
    { key: 'ai', icon: 'mdi-robot-outline', title: t('layout.ai'), to: '/ai' },
    {
      key: 'plugins-group',
      icon: 'mdi-puzzle',
      title: t('layout.pluginsGroup'),
      children: [
        { icon: 'mdi-puzzle-outline', title: t('layout.plugins'), to: '/plugins/config' },
        { icon: 'mdi-storefront-outline', title: t('layout.pluginStore'), to: '/plugins/store' },
      ],
    },
    { key: 'chat', icon: 'mdi-chat-outline', title: t('layout.chat'), to: '/chat' },
    {
      key: 'logs-group',
      icon: 'mdi-text-box-outline',
      title: t('layout.logsGroup'),
      children: [
        { icon: 'mdi-text-box-outline', title: t('layout.logs'), to: '/logs' },
        { icon: 'mdi-history', title: t('layout.logsHistory'), to: '/logs/history' },
      ],
    },
    {
      key: 'more-group',
      icon: 'mdi-dots-horizontal-circle-outline',
      title: t('layout.moreGroup'),
      children: [
        { icon: 'mdi-shield-account', title: t('layout.permissions'), to: '/permissions' },
      ],
    },
    ...(authStore.isOwner
      ? [{ key: 'accounts', icon: 'mdi-account-cog-outline', title: t('layout.accounts'), to: '/accounts' }]
      : []),
  ])

  const themeToggleLabel = computed(() => theme.global.current.value.dark ? t('layout.toLight') : t('layout.toDark'))
  const themeToggleSubtitle = computed(() => theme.global.current.value.dark ? t('layout.darkTheme') : t('layout.lightTheme'))
  const currentLocaleLabel = computed(() => (
    locale.value === 'zh_CN' ? t('layout.chinese') : t('layout.english')
  ))
  const currentRoleLabel = computed(() => {
    if (authStore.role === 'owner') {
      return t('accounts.roles.owner')
    }
    return authStore.role || t('common.none')
  })
  const restartEntries = computed(() => restartStore.entries.slice(0, 3))

  watch(
    () => route.path,
    nextPath => {
      if (nextPath.startsWith('/plugins')) {
        openedGroups.value = Array.from(new Set([...openedGroups.value, 'plugins-group']))
      }
      if (nextPath.startsWith('/logs')) {
        openedGroups.value = Array.from(new Set([...openedGroups.value, 'logs-group']))
      }
      if (nextPath.startsWith('/permissions')) {
        openedGroups.value = Array.from(new Set([...openedGroups.value, 'more-group']))
      }
    },
    { immediate: true },
  )

  async function handleRestart () {
    if (!window.confirm(t('dashboard.restartConfirm'))) return
    await restartAndReload()
  }

  async function handleRevertPendingChanges () {
    if (!window.confirm(t('restart.revertConfirm'))) return
    await revertPendingChanges()
  }

  function toggleTheme () {
    const nextTheme = theme.global.current.value.dark ? 'light' : 'dark'
    theme.global.name.value = nextTheme
    localStorage.setItem('apeiria-theme', nextTheme)
  }

  function setLocale (nextLocale: SupportedLocale) {
    if (locale.value === nextLocale) {
      return
    }
    locale.value = nextLocale
    localStorage.setItem('apeiria-locale', locale.value)

    const titleKey = typeof route.meta.titleKey === 'string' ? route.meta.titleKey : ''
    document.title = titleKey
      ? t('layout.pageTitle', { page: t(titleKey) })
      : t('layout.defaultTitle')
    document.documentElement.lang = locale.value === 'zh_CN' ? 'zh-CN' : 'en-US'
  }

  function handleLogout () {
    restartStore.clearPending()
    authStore.logout()
    router.push('/login')
  }

  function isGroupActive (
    item: { children?: Array<{ to: string }> },
  ) {
    if (!item.children) {
      return false
    }
    return item.children.some(child => route.path.startsWith(child.to))
  }
</script>

<style scoped>
.app-restart-banner {
  margin-bottom: 16px;
}

.app-restart-banner__content {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.app-restart-banner__text {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  flex: 1 1 420px;
}

.app-restart-banner__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.app-restart-banner__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.app-drawer {
  position: relative;
  background: rgb(var(--v-theme-surface));
  box-shadow: inset -1px 0 0 rgba(var(--v-theme-outline-variant), 0.72);
}

.app-drawer__hero {
  position: sticky;
  top: 0;
  z-index: 2;
  background: rgb(var(--v-theme-surface));
}

.app-drawer__header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 6px 6px;
}

.app-drawer__toggle {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  margin-top: 2px;
}

.app-drawer__brand {
  flex: 1;
  min-width: 0;
}

.app-drawer__brand:deep(.v-list-item) {
  padding-inline: 4px !important;
}

.app-drawer__brand:deep(.v-list-item__prepend) {
  margin-inline-end: 10px !important;
}

.app-drawer__brand:deep(.v-list-item-title) {
  display: -webkit-box;
  overflow: hidden;
  font-size: 0.98rem;
  line-height: 1.08;
  white-space: normal;
  word-break: break-word;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.app-drawer__brand:deep(.v-list-item-subtitle) {
  overflow: hidden;
  line-height: 1.05;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-drawer__nav,
.app-drawer__footer {
  padding: 6px 6px;
}

.app-drawer__list {
  padding: 0;
  background: transparent;
}

.app-drawer__group-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 4px 0 2px 8px;
  padding: 6px 6px 4px 8px;
}

.app-drawer__group-panel::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: var(--shape-large);
  background: rgba(var(--v-theme-primary), 0.06);
}

.app-drawer__group-activator:deep(.v-list-item-title) {
  font-weight: 500;
}

.app-drawer__group-activator--active {
  background: rgb(var(--v-theme-secondary-container)) !important;
  color: rgb(var(--v-theme-on-secondary-container)) !important;
}

.app-drawer__rail-menu {
  min-width: 188px;
  padding: 8px;
  border: 1px solid rgba(var(--v-theme-outline), 0.12);
  border-radius: var(--shape-large);
  background: rgb(var(--v-theme-surface));
  box-shadow: var(--elevation-flyout);
}

.app-drawer__rail-menu-title {
  padding: 4px 8px 8px;
  color: rgba(var(--v-theme-on-surface), 0.56);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.app-drawer__rail-menu-list {
  padding: 0;
  background: transparent;
}

.app-drawer__rail-menu-item {
  min-height: 40px;
}

.app-drawer__child-item {
  position: relative;
  z-index: 1;
  margin-inline-start: 0;
  min-height: 44px;
  padding-inline-start: 8px;
  color: rgba(var(--v-theme-on-surface), 0.86);
  background: transparent;
}

.app-drawer__group :deep(.v-list-group__items) {
  margin-top: 2px;
  padding: 0;
}

.app-drawer__group :deep(.v-list-group__header .v-list-item) {
  min-height: 46px;
  transition:
    background-color var(--motion-fast) var(--motion-ease),
    color var(--motion-fast) var(--motion-ease);
}

.app-drawer__group :deep(.v-list-group__header .v-list-item:hover) {
  background: rgba(var(--v-theme-primary), 0.08);
}

.app-drawer__group :deep(.v-list-group__header .v-list-item:focus-visible) {
  outline: none;
  box-shadow: inset var(--focus-ring);
}

.app-drawer__group :deep(.v-list-group__items .v-list-item) {
  opacity: 0.96;
  transition:
    background-color var(--motion-fast) var(--motion-ease),
    color var(--motion-fast) var(--motion-ease),
    opacity var(--motion-fast) var(--motion-ease);
}

.app-drawer__group :deep(.v-list-group__items .v-list-item:hover) {
  opacity: 1;
  background: rgba(var(--v-theme-primary), 0.08);
}

.app-drawer__group :deep(.v-list-group__items .v-list-item:focus-visible) {
  outline: none;
  box-shadow: inset var(--focus-ring);
}

.app-drawer__child-item:deep(.v-list-item__prepend) {
  opacity: 0.72;
}

.app-drawer__child-item:deep(.v-list-item-title) {
  overflow: hidden;
  font-size: 0.98rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-drawer__child-item:deep(.v-list-item__content) {
  min-width: 0;
}

.app-drawer__child-item:deep(.v-list-item--active) {
  background: rgba(var(--v-theme-primary), 0.14);
  color: rgb(var(--v-theme-primary));
}

.app-drawer__child-item:deep(.v-list-item--active .v-list-item__prepend) {
  opacity: 1;
}

.app-drawer--rail .app-drawer__child-item {
  margin-inline-start: 0;
  padding-inline-start: 0;
}

.app-drawer--rail .app-drawer__group-panel {
  display: none;
}

.app-drawer__section-label {
  padding: 4px 10px 6px;
  color: rgba(var(--v-theme-on-surface), 0.46);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.app-drawer__section-label--spaced {
  margin-top: 6px;
}

.app-drawer__footer {
  padding-top: 10px;
  padding-bottom: 8px;
  box-shadow: inset 0 1px 0 rgba(var(--v-theme-outline-variant), 0.52);
}

.app-drawer--rail .app-drawer__header {
  justify-content: center;
  align-items: center;
  padding: 6px 0 4px;
}

.app-drawer--rail .app-drawer__brand {
  display: none;
}

.app-drawer--rail .app-drawer__toggle {
  margin-top: 0;
}

.app-drawer--rail .app-drawer__nav,
.app-drawer--rail .app-drawer__footer {
  padding-left: 0;
  padding-right: 0;
}

.app-main {
  min-height: 100vh;
  background: rgb(var(--v-theme-background));
  transition:
    background-color var(--motion-base) var(--motion-ease),
    color var(--motion-base) var(--motion-ease);
}

.app-container {
  padding: var(--page-gutter);
}

.locale-menu {
  min-width: 144px;
}

@media (max-width: 960px) {
  .app-container {
    padding: 16px;
  }
}
</style>
