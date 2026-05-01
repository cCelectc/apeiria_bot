<template>
  <PageScaffold
    class="store-view"
    :error-message="errorMessage"
    :kicker="currentSourceLabel"
    :title="t('pluginStore.title')"
  >
    <ResourceWorkbench
      :count="totalItems"
      :empty="pagedItems.length === 0"
      empty-icon="mdi-store-search-outline"
      :empty-text="t('pluginStore.emptyHint')"
      :empty-title="t('pluginStore.empty')"
      icon="mdi-package-variant-closed"
      :loading="loading && pagedItems.length === 0"
      :title="t('pluginStore.allPlugins')"
    >
      <template #filters>
        <FilterBar
          :apply-label="t('common.applyFilters')"
          :close-label="t('common.close')"
          compact
          :overflow-label="t('common.filters')"
          :overflow-title="t('pluginStore.allPlugins')"
        >
          <template #filters>
            <v-text-field
              v-model.trim="search"
              class="store-search"
              density="comfortable"
              hide-details
              :label="t('pluginStore.search')"
              prepend-inner-icon="mdi-magnify"
            />
          </template>

          <template #summary>
            <v-chip size="small" variant="tonal">
              {{ currentSourceLabel }}
            </v-chip>

            <v-chip v-if="selectedCategory" size="small" variant="tonal">
              {{ selectedCategory }}
            </v-chip>

            <v-chip
              :color="uninstalledOnly ? 'primary' : undefined"
              size="small"
              variant="tonal"
            >
              {{ t('pluginStore.uninstalledOnly') }}
            </v-chip>
          </template>

          <template #overflow>
            <v-select
              v-model="selectedSource"
              density="comfortable"
              hide-details
              item-title="label"
              item-value="value"
              :items="sourceOptions"
              :label="t('pluginStore.allSources')"
            />

            <v-select
              v-model="selectedCategory"
              density="comfortable"
              hide-details
              item-title="label"
              item-value="value"
              :items="categoryOptions"
              :label="t('pluginStore.category')"
            />

            <v-select
              v-model="sortMode"
              density="comfortable"
              hide-details
              item-title="label"
              item-value="value"
              :items="sortOptions"
              :label="t('pluginStore.sort')"
            />

            <v-switch
              v-model="uninstalledOnly"
              color="primary"
              hide-details
              :label="t('pluginStore.uninstalledOnly')"
            />
          </template>
        </FilterBar>
      </template>

      <div class="store-grid">
        <article
          v-for="item in pagedItems"
          :key="`${item.source_id}:${item.plugin_id}`"
          class="store-card surface-gradient-card"
        >
          <div class="store-card__header">
            <div class="store-card__avatar">
              <img
                v-if="pluginIcon(item)"
                :alt="item.name"
                :src="pluginIcon(item) || undefined"
              >

              <v-icon v-else icon="mdi-puzzle-outline" />
            </div>

            <div class="store-card__meta">
              <div class="store-card__title-row">
                <h2 class="store-card__title">{{ item.name }}</h2>

                <v-chip
                  v-if="item.is_official"
                  color="warning"
                  size="x-small"
                  variant="flat"
                >
                  {{ t('pluginStore.official') }}
                </v-chip>

                <v-chip
                  v-if="item.is_installed"
                  color="success"
                  size="x-small"
                  variant="flat"
                >
                  {{ t('pluginStore.installed') }}
                </v-chip>
              </div>

              <div class="store-card__subline">
                <a
                  v-if="authorUrl(item) && item.author"
                  class="store-card__author store-card__author--link"
                  :href="authorUrl(item)"
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  {{ item.author }}
                </a>

                <span v-else-if="item.author" class="store-card__author">{{ item.author }}</span>
                <span v-if="item.version">{{ item.version }}</span>
                <span v-if="item.publish_time">{{ formatPublishTime(item.publish_time) }}</span>
              </div>

              <div class="store-card__module">{{ item.module_name }}</div>
            </div>
          </div>

          <p class="store-card__description">
            {{ item.description || t('pluginStore.noDescription') }}
          </p>

          <div class="store-card__tags">
            <v-chip
              v-for="tag in visibleTags(item)"
              :key="tag"
              size="small"
              variant="tonal"
            >
              {{ tag }}
            </v-chip>

            <v-chip
              v-if="hiddenTagCount(item) > 0"
              size="small"
              variant="tonal"
            >
              +{{ hiddenTagCount(item) }}
            </v-chip>
          </div>

          <div class="store-card__actions">
            <a
              v-if="externalProjectUrl(item)"
              class="store-card__link"
              :href="externalProjectUrl(item)"
              rel="noopener noreferrer"
              target="_blank"
            >
              <v-icon icon="mdi-github" start />
              {{ t('pluginStore.openProject') }}
            </a>

            <span v-else class="store-card__link store-card__link--muted">
              <v-icon icon="mdi-link-variant-off" start />
              {{ t('pluginStore.noProjectLink') }}
            </span>

            <v-btn
              color="primary"
              :disabled="(!item.can_update && item.is_installed) || actionLocked"
              variant="flat"
              @click="openActionDialog(item)"
            >
              {{ actionLabel(item) }}
            </v-btn>
          </div>
        </article>
      </div>
    </ResourceWorkbench>

    <div v-if="pageCount > 1" class="store-pagination">
      <v-pagination
        v-model="currentPage"
        :length="pageCount"
        total-visible="7"
      />
    </div>

    <v-dialog v-model="installDialogVisible" max-width="640">
      <v-card>
        <v-card-title>{{ dialogTitle }}</v-card-title>

        <v-card-text class="d-flex flex-column ga-4">
          <div v-if="selectedItem" class="d-flex flex-column ga-2">
            <div class="font-weight-medium">{{ selectedItem.name }}</div>
            <div class="text-body-2 text-medium-emphasis">{{ selectedItem.module_name }}</div>
            <div class="text-body-2">{{ t('pluginStore.packageName') }}: {{ selectedItem.package_name }}</div>
            <div class="text-body-2">{{ t('pluginStore.source') }}: {{ selectedItem.source_name }}</div>
          </div>
        </v-card-text>

        <v-card-actions>
          <v-btn variant="text" @click="installDialogVisible = false">{{ t('common.cancel') }}</v-btn>
          <v-spacer />

          <v-btn color="primary" :loading="installPending" @click="startAction">
            {{ dialogActionLabel }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <TaskDialog
      v-model="taskDialogVisible"
      :close-label="t('common.close')"
      :loading="activeTask?.status === 'pending' || activeTask?.status === 'running'"
      :logs="activeTask?.logs || ''"
      :status="taskStatusLabel"
      :title="activeTask?.title || taskDialogTitle"
      :waiting-text="taskWaitingLabel"
    />
  </PageScaffold>
</template>

<script setup lang="ts">
  import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { getErrorMessage } from '@/api/client'
  import {
    getPluginStoreItem,
    getPluginStoreItems,
    getPluginStoreSources,
    getPluginStoreTask,
    installPluginStoreItem,
    type PluginStoreCategoryItem,
    type PluginStoreItem,
    type PluginStoreSource,
    type PluginStoreTask,
    updatePluginStoreItem,
  } from '@/api/plugins'
  import {
    FilterBar,
    PageScaffold,
    ResourceWorkbench,
    TaskDialog,
  } from '@/components/workbench'
  import { useNoticeStore } from '@/stores/notice'
  import { useRestartStore } from '@/stores/restart'

  const { t, locale } = useI18n()
  const noticeStore = useNoticeStore()
  const restartStore = useRestartStore()
  const loading = ref(false)
  const errorMessage = ref('')
  const sources = ref<PluginStoreSource[]>([])
  const items = ref<PluginStoreItem[]>([])
  const categories = ref<PluginStoreCategoryItem[]>([])
  const totalItems = ref(0)
  const selectedSource = ref('')
  const selectedCategory = ref('')
  const sortMode = ref<'default' | 'name' | 'updated'>('default')
  const currentPage = ref(1)
  const search = ref('')
  const uninstalledOnly = ref(true)
  const installDialogVisible = ref(false)
  const taskDialogVisible = ref(false)
  const selectedItem = ref<PluginStoreItem | null>(null)
  const activeInstallItem = ref<PluginStoreItem | null>(null)
  const activeTask = ref<PluginStoreTask | null>(null)
  const activeTaskMode = ref<'install' | 'update'>('install')
  const installPending = ref(false)
  let taskPollTimer: number | null = null
  let searchTimer: number | null = null

  const currentSourceLabel = computed(() => {
    const matched = sources.value.find(item => item.source_id === selectedSource.value)
    return matched?.name || t('pluginStore.allSources')
  })
  const sourceOptions = computed(() => [
    { value: '', label: t('pluginStore.allSources') },
    ...sources.value.map(source => ({
      value: source.source_id,
      label: source.name,
    })),
  ])
  const taskStatusLabel = computed(() => {
    const status = activeTask.value?.status || ''
    if (status === 'pending') {
      return activeTaskMode.value === 'update'
        ? t('pluginStore.updatePending')
        : t('pluginStore.installPending')
    }
    if (status === 'running') {
      return activeTaskMode.value === 'update'
        ? t('pluginStore.updateRunning')
        : t('pluginStore.installRunning')
    }
    if (status === 'succeeded') {
      return activeTaskMode.value === 'update'
        ? t('pluginStore.updateSucceeded')
        : t('pluginStore.installSucceeded')
    }
    if (status === 'failed') {
      return activeTask.value?.error
        || (
          activeTaskMode.value === 'update'
            ? t('pluginStore.updateFailed')
            : t('pluginStore.installFailed')
        )
    }
    return ''
  })
  const dialogTitle = computed(() => (
    selectedItem.value?.can_update
      ? t('pluginStore.updateConfirmTitle')
      : t('pluginStore.installConfirmTitle')
  ))
  const dialogActionLabel = computed(() => (
    selectedItem.value?.can_update
      ? t('pluginStore.update')
      : t('pluginStore.install')
  ))
  const taskDialogTitle = computed(() => (
    activeTaskMode.value === 'update'
      ? t('pluginStore.updateTaskTitle')
      : t('pluginStore.installTaskTitle')
  ))
  const taskWaitingLabel = computed(() => (
    activeTaskMode.value === 'update'
      ? t('pluginStore.updateWaiting')
      : t('pluginStore.installWaiting')
  ))
  const actionLocked = computed(() => (
    installPending.value
    || activeTask.value?.status === 'pending'
    || activeTask.value?.status === 'running'
  ))
  const categoryOptions = computed(() => {
    return [
      { value: '', label: t('pluginStore.allCategories') },
      ...categories.value.map(item => ({
        value: item.value,
        label: `${item.value} (${item.count})`,
      })),
    ]
  })
  const sortOptions = computed(() => [
    { value: 'default', label: t('pluginStore.sortDefault') },
    { value: 'updated', label: t('pluginStore.sortUpdated') },
    { value: 'name', label: t('pluginStore.sortName') },
  ])
  const pageSize = 16
  const pageCount = computed(() => Math.max(1, Math.ceil(totalItems.value / pageSize)))
  const pagedItems = computed(() => items.value)

  function externalProjectUrl (item: PluginStoreItem) {
    const candidate = item.homepage || item.project_link || ''
    if (candidate.startsWith('http://') || candidate.startsWith('https://')) {
      return candidate
    }
    return ''
  }

  function pluginIcon (item: PluginStoreItem) {
    const candidates = ['icon', 'icon_url', 'logo', 'logo_url', 'avatar']
    for (const key of candidates) {
      const value = item.extra[key]
      if (typeof value === 'string' && value.startsWith('http')) {
        return value
      }
    }
    return ''
  }

  function authorUrl (item: PluginStoreItem) {
    return item.author_link || ''
  }

  function visibleTags (item: PluginStoreItem) {
    return item.tags.slice(0, 2)
  }

  function hiddenTagCount (item: PluginStoreItem) {
    return Math.max(item.tags.length - 2, 0)
  }

  function formatPublishTime (value: string) {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return ''
    return new Intl.DateTimeFormat(locale.value === 'zh_CN' ? 'zh-CN' : 'en-US', {
      year: 'numeric',
      month: 'numeric',
      day: 'numeric',
    }).format(date)
  }

  function actionLabel (item: PluginStoreItem) {
    if (item.can_update) return t('pluginStore.update')
    if (item.is_installed) return t('pluginStore.installed')
    return t('pluginStore.install')
  }

  async function openActionDialog (item: PluginStoreItem) {
    if (actionLocked.value) return
    selectedItem.value = item
    installDialogVisible.value = true
    try {
      const response = await getPluginStoreItem(item.source_id, item.plugin_id)
      selectedItem.value = response.data
    } catch {
      // Keep the existing item snapshot when detail loading fails.
    }
  }

  async function startAction () {
    if (!selectedItem.value) return
    activeInstallItem.value = { ...selectedItem.value }
    activeTaskMode.value = selectedItem.value.can_update ? 'update' : 'install'
    installPending.value = true
    try {
      const payload = {
        source_id: selectedItem.value.source_id,
        plugin_id: selectedItem.value.plugin_id,
        package_name: selectedItem.value.package_name,
        module_name: selectedItem.value.module_name,
      }
      const response = selectedItem.value.can_update
        ? await updatePluginStoreItem(payload)
        : await installPluginStoreItem(payload)
      activeTask.value = response.data
      installDialogVisible.value = false
      taskDialogVisible.value = true
      startTaskPolling(response.data.task_id)
    } catch (error) {
      activeInstallItem.value = null
      noticeStore.show(
        getErrorMessage(
          error,
          selectedItem.value.can_update
            ? t('pluginStore.updateFailed')
            : t('pluginStore.installFailed'),
        ),
        'error',
      )
    } finally {
      installPending.value = false
    }
  }

  function startTaskPolling (taskId: string) {
    stopTaskPolling()
    taskPollTimer = window.setInterval(async () => {
      try {
        const response = await getPluginStoreTask(taskId)
        activeTask.value = response.data
        if (response.data.status === 'succeeded' || response.data.status === 'failed') {
          stopTaskPolling()
          if (response.data.status === 'succeeded' && activeInstallItem.value) {
            if (activeTaskMode.value === 'install') {
              restartStore.markPending({
                id: `plugin-store-install:${activeInstallItem.value.module_name}`,
                scope: 'plugins',
                summary: t('pluginStore.pendingInstall', { name: activeInstallItem.value.name }),
                undo: {
                  kind: 'plugin-install',
                  packageName: activeInstallItem.value.package_name,
                  moduleName: activeInstallItem.value.module_name,
                },
              })
            } else {
              restartStore.markPending({
                id: `plugin-store-update:${activeInstallItem.value.module_name}`,
                scope: 'plugins',
                summary: t('pluginStore.pendingUpdate', { name: activeInstallItem.value.name }),
              })
            }
            noticeStore.show(
              activeTaskMode.value === 'update'
                ? t('pluginStore.updateSucceeded')
                : t('pluginStore.installSucceeded'),
              'success',
            )
            void loadStore()
          } else if (response.data.status === 'failed') {
            noticeStore.show(
              response.data.error || (
                activeTaskMode.value === 'update'
                  ? t('pluginStore.updateFailed')
                  : t('pluginStore.installFailed')
              ),
              'error',
            )
          }
          activeInstallItem.value = null
        }
      } catch (error) {
        stopTaskPolling()
        activeInstallItem.value = null
        noticeStore.show(
          getErrorMessage(
            error,
            activeTaskMode.value === 'update'
              ? t('pluginStore.updateFailed')
              : t('pluginStore.installFailed'),
          ),
          'error',
        )
      }
    }, 1000)
  }

  function stopTaskPolling () {
    if (taskPollTimer !== null) {
      window.clearInterval(taskPollTimer)
      taskPollTimer = null
    }
  }

  async function loadStore () {
    loading.value = true
    errorMessage.value = ''
    try {
      const [sourcesResponse, itemsResponse] = await Promise.all([
        getPluginStoreSources(),
        getPluginStoreItems({
          source: selectedSource.value || undefined,
          search: search.value || undefined,
          category: selectedCategory.value || undefined,
          sort: sortMode.value,
          uninstalled_only: uninstalledOnly.value || undefined,
          page: currentPage.value,
          per_page: pageSize,
        }),
      ])
      sources.value = sourcesResponse.data
      items.value = itemsResponse.data.items
      categories.value = itemsResponse.data.categories
      totalItems.value = itemsResponse.data.total
      if (
        selectedCategory.value
        && !itemsResponse.data.categories.some(item => item.value === selectedCategory.value)
      ) {
        selectedCategory.value = ''
      }
    } catch (error) {
      errorMessage.value = getErrorMessage(error, t('pluginStore.loadFailed'))
    } finally {
      loading.value = false
    }
  }

  function scheduleReload () {
    if (searchTimer !== null) {
      window.clearTimeout(searchTimer)
    }
    searchTimer = window.setTimeout(() => {
      void loadStore()
    }, 220)
  }

  watch([selectedSource, search, selectedCategory, sortMode, uninstalledOnly], () => {
    currentPage.value = 1
    scheduleReload()
  })

  watch(currentPage, (nextPage, previousPage) => {
    if (nextPage === previousPage) return
    void loadStore()
  })

  onMounted(() => {
    void loadStore()
  })

  onBeforeUnmount(() => {
    stopTaskPolling()
    if (searchTimer !== null) {
      window.clearTimeout(searchTimer)
      searchTimer = null
    }
  })
</script>

<style scoped>
.store-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.store-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  flex-wrap: wrap;
}

.store-hero__content {
  display: flex;
  flex: 1 1 520px;
  flex-direction: column;
  gap: 12px;
}

.store-hero__title-row {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.store-hero__title {
  margin: 0;
  font-size: clamp(2rem, 2.6vw, 2.5rem);
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.store-hero__chips {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.store-hero__actions {
  flex: 0 1 360px;
  width: min(100%, 360px);
}

.store-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.store-grid--loading :deep(.v-skeleton-loader__article) {
  border-radius: var(--shape-xlarge);
}

.store-card {
  display: flex;
  min-height: 220px;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  transition:
    transform var(--motion-base) var(--motion-ease),
    box-shadow var(--motion-base) var(--motion-ease),
    border-color var(--motion-base) var(--motion-ease);
}

.store-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--elevation-soft-hover);
}

.store-card:focus-within {
  box-shadow: var(--focus-ring), var(--elevation-soft);
}

.store-card__header {
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr);
  gap: 12px;
  align-items: flex-start;
}

.store-card__avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 52px;
  overflow: hidden;
  border-radius: var(--shape-medium);
  background: rgba(var(--v-theme-primary), 0.12);
  color: rgb(var(--v-theme-primary));
}

.store-card__avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.store-card__avatar :deep(.v-icon) {
  font-size: 24px;
}

.store-card__meta {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.store-card__title-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.store-card__title {
  margin: 0;
  font-size: 0.96rem;
  line-height: 1.2;
  font-weight: 800;
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.store-card__subline,
.store-card__module {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.82rem;
}

.store-card__author {
  color: rgb(var(--v-theme-primary));
  font-weight: 600;
}

.store-card__author--link {
  text-decoration: none;
}

.store-card__author--link:hover {
  text-decoration: underline;
}

.store-card__author--link:focus-visible {
  outline: none;
  text-decoration: underline;
}

.store-card__description {
  margin: 0;
  color: rgba(var(--v-theme-on-surface), 0.74);
  font-size: 0.88rem;
  line-height: 1.42;
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}

.store-card__tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: auto;
}

.store-card__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: auto;
}

.store-card__actions :deep(.v-btn) {
  border-radius: var(--shape-medium) !important;
  min-height: 36px;
  padding-inline: 16px;
  transition:
    background-color var(--motion-fast) var(--motion-ease),
    box-shadow var(--motion-fast) var(--motion-ease),
    color var(--motion-fast) var(--motion-ease);
}

.store-card__actions :deep(.v-btn:not(.v-btn--disabled):hover) {
  box-shadow: var(--elevation-soft-press);
}

.store-card__actions :deep(.v-btn:focus-visible) {
  box-shadow: var(--focus-ring);
}

.store-card__link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 36px;
  padding: 0 12px;
  border-radius: var(--shape-medium);
  color: rgb(var(--v-theme-primary));
  text-decoration: none;
  font-weight: 700;
  font-size: 0.9rem;
  transition:
    background-color var(--motion-fast) var(--motion-ease),
    color var(--motion-fast) var(--motion-ease);
}

.store-card__link:hover {
  background: rgba(var(--v-theme-primary), 0.14);
}

.store-card__link:focus-visible {
  outline: none;
  background: rgba(var(--v-theme-primary), 0.14);
  box-shadow: var(--focus-ring);
}

.store-card__link--muted {
  color: rgba(var(--v-theme-on-surface), 0.44);
}

.store-card__link--muted:hover {
  background: transparent;
}

.store-pagination {
  display: flex;
  justify-content: center;
  padding-top: 4px;
}

@media (max-width: 960px) {
  .store-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .store-hero__actions {
    width: 100%;
  }

  .store-select,
  .store-search {
    width: 100%;
  }
}

@media (max-width: 640px) {
  .store-grid {
    grid-template-columns: 1fr;
  }
}
</style>
