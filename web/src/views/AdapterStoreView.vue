<template>
  <div class="page-view adapter-store-view">
    <div class="page-header">
      <div class="adapter-store-view__title-wrap">
        <v-btn
          icon="mdi-arrow-left"
          size="small"
          variant="text"
          @click="goBack"
        />
        <div>
          <h1 class="page-title">{{ t('adapterStore.title') }}</h1>
          <div class="text-body-2 text-medium-emphasis">
            {{ t('adapterStore.subtitle') }}
          </div>
        </div>
      </div>

      <div class="page-actions">
        <v-btn :loading="loading" variant="tonal" @click="loadStore">
          {{ t('common.refresh') }}
        </v-btn>
      </div>
    </div>

    <v-alert v-if="errorMessage" density="comfortable" type="error" variant="tonal">
      {{ errorMessage }}
    </v-alert>

    <v-card class="page-panel">
      <v-card-text class="d-flex flex-column ga-4">
        <div class="adapter-store-view__filters">
          <v-text-field
            v-model.trim="search"
            class="adapter-store-view__search"
            density="comfortable"
            hide-details
            :label="t('adapterStore.search')"
            prepend-inner-icon="mdi-magnify"
          />
          <v-select
            v-model="selectedSource"
            density="comfortable"
            hide-details
            item-title="label"
            item-value="value"
            :items="sourceOptions"
            :label="t('adapterStore.allSources')"
          />
          <v-select
            v-model="selectedCategory"
            density="comfortable"
            hide-details
            item-title="label"
            item-value="value"
            :items="categoryOptions"
            :label="t('adapterStore.category')"
          />
          <v-select
            v-model="sortMode"
            density="comfortable"
            hide-details
            item-title="label"
            item-value="value"
            :items="sortOptions"
            :label="t('adapterStore.sort')"
          />
          <v-switch
            v-model="uninstalledOnly"
            color="primary"
            hide-details
            :label="t('adapterStore.uninstalledOnly')"
          />
        </div>

        <div v-if="loading && items.length === 0" class="adapter-store-grid">
          <v-skeleton-loader
            v-for="index in 8"
            :key="index"
            class="adapter-store-card"
            type="article"
          />
        </div>

        <div v-else-if="items.length > 0" class="adapter-store-grid">
          <article
            v-for="item in items"
            :key="`${item.source_id}:${item.adapter_id}`"
            class="adapter-store-card"
          >
            <div class="adapter-store-card__header">
              <div>
                <h2 class="adapter-store-card__title">{{ item.name }}</h2>
                <div class="text-caption text-medium-emphasis">{{ item.module_name }}</div>
              </div>
              <v-chip v-if="item.is_official" color="warning" size="x-small" variant="tonal">
                {{ t('adapterStore.official') }}
              </v-chip>
            </div>

            <div class="text-body-2 text-medium-emphasis">
              {{ item.package_name }}
            </div>

            <p class="adapter-store-card__description">
              {{ item.description || t('adapterStore.noDescription') }}
            </p>

            <div class="adapter-store-card__chips">
              <v-chip
                v-if="item.is_installed"
                color="success"
                size="x-small"
                variant="tonal"
              >
                {{ t('adapterStore.installed') }}
              </v-chip>
              <v-chip
                v-if="item.is_registered"
                color="primary"
                size="x-small"
                variant="tonal"
              >
                {{ t('adapterStore.registered') }}
              </v-chip>
              <v-chip
                v-if="item.can_update"
                color="warning"
                size="x-small"
                variant="tonal"
              >
                {{ t('adapterStore.updateAvailable') }}
              </v-chip>
              <v-chip
                v-for="tag in item.tags.slice(0, 2)"
                :key="tag"
                size="x-small"
                variant="outlined"
              >
                {{ tag }}
              </v-chip>
            </div>

            <div class="adapter-store-card__meta text-caption text-medium-emphasis">
              <span>{{ t('adapterStore.source') }}: {{ item.source_name }}</span>
              <span v-if="item.author">{{ item.author }}</span>
              <span v-if="item.version">{{ item.version }}</span>
            </div>

            <div class="adapter-store-card__actions">
              <v-btn
                v-if="projectUrl(item)"
                :href="projectUrl(item)"
                rel="noopener noreferrer"
                target="_blank"
                variant="text"
              >
                {{ t('adapterStore.openProject') }}
              </v-btn>
              <v-spacer />
              <v-btn
                v-if="!item.is_installed"
                color="primary"
                :disabled="!authStore.isOwner || actionLocked"
                variant="tonal"
                @click="openActionDialog(item, 'install')"
              >
                {{ t('adapterStore.install') }}
              </v-btn>
              <v-btn
                v-if="item.can_update"
                color="primary"
                :disabled="!authStore.isOwner || actionLocked"
                variant="tonal"
                @click="openActionDialog(item, 'update')"
              >
                {{ t('adapterStore.update') }}
              </v-btn>
              <v-btn
                v-if="canUninstall(item)"
                color="warning"
                :disabled="!authStore.isOwner || actionLocked"
                variant="text"
                @click="openActionDialog(item, 'uninstall')"
              >
                {{ t('adapterStore.uninstall') }}
              </v-btn>
            </div>
          </article>
        </div>

        <div v-else class="adapter-store-view__empty">
          {{ t('adapterStore.empty') }}
        </div>

        <div v-if="pageCount > 1" class="d-flex justify-center">
          <v-pagination
            v-model="currentPage"
            :length="pageCount"
            rounded="circle"
            total-visible="7"
          />
        </div>
      </v-card-text>
    </v-card>

    <v-dialog v-model="actionDialogVisible" max-width="640">
      <v-card>
        <v-card-title>{{ actionDialogTitle }}</v-card-title>
        <v-card-text class="d-flex flex-column ga-3">
          <div v-if="selectedItem" class="d-flex flex-column ga-2">
            <div class="font-weight-medium">{{ selectedItem.name }}</div>
            <div class="text-body-2 text-medium-emphasis">{{ selectedItem.module_name }}</div>
            <div class="text-body-2">{{ t('adapterStore.packageName') }}: {{ selectedItem.package_name }}</div>
            <div class="text-body-2">{{ t('adapterStore.source') }}: {{ selectedItem.source_name }}</div>
          </div>
        </v-card-text>
        <v-card-actions>
          <v-btn variant="text" @click="actionDialogVisible = false">
            {{ t('common.cancel') }}
          </v-btn>
          <v-spacer />
          <v-btn color="primary" :loading="actionPending" @click="startAction">
            {{ actionDialogConfirmLabel }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="taskDialogVisible" max-width="840">
      <v-card>
        <v-card-title>{{ activeTask?.title || t('adapterStore.taskTitle') }}</v-card-title>
        <v-card-text class="d-flex flex-column ga-4">
          <div class="text-body-2 text-medium-emphasis">
            {{ taskStatusLabel }}
          </div>
          <v-progress-linear
            v-if="activeTask?.status === 'pending' || activeTask?.status === 'running'"
            color="primary"
            indeterminate
          />
          <div class="adapter-store-task-log">
            <pre>{{ activeTask?.logs || t('adapterStore.taskWaiting') }}</pre>
          </div>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="taskDialogVisible = false">
            {{ t('common.close') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
  import type { AdapterStoreCategoryItem, AdapterStoreItem, AdapterStoreSource, AdapterStoreTask } from '@/api/adapters'
  import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRouter } from 'vue-router'
  import {
    getAdapterStoreItem,
    getAdapterStoreItems,
    getAdapterStoreSources,
    getAdapterStoreTask,
    installAdapterStoreItem,
    uninstallAdapterStoreItem,
    updateAdapterStoreItem,
  } from '@/api/adapters'
  import { getErrorMessage } from '@/api/client'
  import { useAuthStore } from '@/stores/auth'
  import { useNoticeStore } from '@/stores/notice'
  import { useRestartStore } from '@/stores/restart'

  type AdapterActionMode = 'install' | 'update' | 'uninstall'

  const { t } = useI18n()
  const router = useRouter()
  const authStore = useAuthStore()
  const noticeStore = useNoticeStore()
  const restartStore = useRestartStore()

  const loading = ref(false)
  const errorMessage = ref('')
  const sources = ref<AdapterStoreSource[]>([])
  const items = ref<AdapterStoreItem[]>([])
  const categories = ref<AdapterStoreCategoryItem[]>([])
  const totalItems = ref(0)
  const selectedSource = ref('')
  const selectedCategory = ref('')
  const sortMode = ref<'default' | 'name' | 'updated'>('default')
  const currentPage = ref(1)
  const search = ref('')
  const uninstalledOnly = ref(true)
  const actionDialogVisible = ref(false)
  const actionPending = ref(false)
  const taskDialogVisible = ref(false)
  const selectedItem = ref<AdapterStoreItem | null>(null)
  const activeTask = ref<AdapterStoreTask | null>(null)
  const activeItem = ref<AdapterStoreItem | null>(null)
  const actionMode = ref<AdapterActionMode>('install')
  let taskPollTimer: number | null = null
  let searchTimer: number | null = null

  const sourceOptions = computed(() => [
    { value: '', label: t('adapterStore.allSources') },
    ...sources.value.map(item => ({
      value: item.source_id,
      label: item.name,
    })),
  ])
  const categoryOptions = computed(() => [
    { value: '', label: t('adapterStore.allCategories') },
    ...categories.value.map(item => ({
      value: item.value,
      label: `${item.value} (${item.count})`,
    })),
  ])
  const sortOptions = computed(() => [
    { value: 'default', label: t('adapterStore.sortDefault') },
    { value: 'updated', label: t('adapterStore.sortUpdated') },
    { value: 'name', label: t('adapterStore.sortName') },
  ])
  const pageSize = 16
  const pageCount = computed(() => Math.max(1, Math.ceil(totalItems.value / pageSize)))
  const actionDialogTitle = computed(() => {
    if (actionMode.value === 'update') return t('adapterStore.updateConfirmTitle')
    if (actionMode.value === 'uninstall') return t('adapterStore.uninstallConfirmTitle')
    return t('adapterStore.installConfirmTitle')
  })
  const actionDialogConfirmLabel = computed(() => {
    if (actionMode.value === 'update') return t('adapterStore.update')
    if (actionMode.value === 'uninstall') return t('adapterStore.uninstall')
    return t('adapterStore.install')
  })
  const actionLocked = computed(() => (
    actionPending.value
    || activeTask.value?.status === 'pending'
    || activeTask.value?.status === 'running'
  ))
  const taskStatusLabel = computed(() => {
    const status = activeTask.value?.status || ''
    const prefix = actionMode.value
    if (status === 'pending') {
      return t(`adapterStore.${prefix}Pending`)
    }
    if (status === 'running') {
      return t(`adapterStore.${prefix}Running`)
    }
    if (status === 'succeeded') {
      return t(`adapterStore.${prefix}Succeeded`)
    }
    if (status === 'failed') {
      return activeTask.value?.error || t(`adapterStore.${prefix}Failed`)
    }
    return ''
  })

  function goBack () {
    void router.push({ name: 'core', query: { section: 'adapters' } })
  }

  function canUninstall (item: AdapterStoreItem) {
    return Boolean(item.installed_package && item.is_registered)
  }

  function projectUrl (item: AdapterStoreItem) {
    const candidate = item.homepage || item.project_link || ''
    if (candidate.startsWith('http://') || candidate.startsWith('https://')) {
      return candidate
    }
    return ''
  }

  function openActionDialog (item: AdapterStoreItem, mode: AdapterActionMode) {
    if (actionLocked.value) return
    selectedItem.value = item
    actionMode.value = mode
    actionDialogVisible.value = true
    void loadItemDetail(item)
  }

  async function loadItemDetail (item: AdapterStoreItem) {
    try {
      const response = await getAdapterStoreItem(item.source_id, item.adapter_id)
      selectedItem.value = response.data
    } catch {
      selectedItem.value = item
    }
  }

  async function startAction () {
    if (!selectedItem.value) return
    actionPending.value = true
    activeItem.value = { ...selectedItem.value }
    try {
      let response
      if (actionMode.value === 'update') {
        response = await updateAdapterStoreItem({
          source_id: selectedItem.value.source_id,
          adapter_id: selectedItem.value.adapter_id,
          package_name: selectedItem.value.package_name,
          module_name: selectedItem.value.module_name,
        })
      } else if (actionMode.value === 'uninstall') {
        response = await uninstallAdapterStoreItem({
          package_name: selectedItem.value.installed_package || selectedItem.value.package_name,
          module_name: selectedItem.value.module_name,
        })
      } else {
        response = await installAdapterStoreItem({
          source_id: selectedItem.value.source_id,
          adapter_id: selectedItem.value.adapter_id,
          package_name: selectedItem.value.package_name,
          module_name: selectedItem.value.module_name,
        })
      }
      activeTask.value = response.data
      actionDialogVisible.value = false
      taskDialogVisible.value = true
      startTaskPolling(response.data.task_id)
    } catch (error) {
      noticeStore.show(
        getErrorMessage(error, t(`adapterStore.${actionMode.value}Failed`)),
        'error',
      )
      activeItem.value = null
    } finally {
      actionPending.value = false
    }
  }

  function startTaskPolling (taskId: string) {
    stopTaskPolling()
    taskPollTimer = window.setInterval(async () => {
      try {
        const response = await getAdapterStoreTask(taskId)
        activeTask.value = response.data
        if (response.data.status === 'succeeded' || response.data.status === 'failed') {
          stopTaskPolling()
          if (response.data.status === 'succeeded' && activeItem.value) {
            markRestartPending(activeItem.value, response.data)
            noticeStore.show(t(`adapterStore.${actionMode.value}Succeeded`), 'success')
            void loadStore()
          } else if (response.data.status === 'failed') {
            noticeStore.show(
              response.data.error || t(`adapterStore.${actionMode.value}Failed`),
              'error',
            )
          }
          activeItem.value = null
        }
      } catch (error) {
        stopTaskPolling()
        activeItem.value = null
        noticeStore.show(
          getErrorMessage(error, t(`adapterStore.${actionMode.value}Failed`)),
          'error',
        )
      }
    }, 1000)
  }

  function markRestartPending (item: AdapterStoreItem, task: AdapterStoreTask) {
    const resultModule = typeof task.result.module_name === 'string'
      ? task.result.module_name
      : item.module_name
    const resultRequirement = typeof task.result.requirement === 'string'
      ? task.result.requirement
      : item.installed_package || item.package_name

    if (actionMode.value === 'install') {
      restartStore.markPending({
        id: `adapter-store-install:${resultModule || resultRequirement}`,
        scope: 'core',
        summary: t('restart.pendingAdapterInstall', { name: item.name }),
        undo: {
          kind: 'adapter-install',
          packageName: resultRequirement,
          moduleName: resultModule,
        },
      })
      return
    }
    if (actionMode.value === 'update') {
      restartStore.markPending({
        id: `adapter-store-update:${resultModule || resultRequirement}`,
        scope: 'core',
        summary: t('restart.pendingAdapterUpdate', { name: item.name }),
      })
      return
    }
    restartStore.markPending({
      id: `adapter-store-uninstall:${resultModule || resultRequirement}`,
      scope: 'core',
      summary: t('restart.pendingAdapterUninstall', { name: item.name }),
    })
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
        getAdapterStoreSources(),
        getAdapterStoreItems({
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
      errorMessage.value = getErrorMessage(error, t('adapterStore.loadFailed'))
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
.adapter-store-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.adapter-store-view__title-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
}

.adapter-store-view__filters {
  display: grid;
  grid-template-columns: minmax(220px, 2fr) repeat(3, minmax(160px, 1fr)) auto;
  gap: 12px;
  align-items: center;
}

.adapter-store-view__search {
  min-width: 0;
}

.adapter-store-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.adapter-store-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: var(--shape-medium);
  background: rgba(var(--v-theme-on-surface), 0.02);
}

.adapter-store-card__header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: start;
}

.adapter-store-card__title {
  margin: 0;
  font-size: 1rem;
  line-height: 1.35;
}

.adapter-store-card__description {
  margin: 0;
  min-height: 44px;
  color: rgba(var(--v-theme-on-surface), 0.82);
}

.adapter-store-card__chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.adapter-store-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.adapter-store-card__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.adapter-store-view__empty {
  padding: 32px 16px;
  text-align: center;
  color: rgba(var(--v-theme-on-surface), 0.65);
}

.adapter-store-task-log {
  max-height: 360px;
  overflow: auto;
  padding: 12px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: var(--shape-medium);
  background: rgba(var(--v-theme-on-surface), 0.03);
}

.adapter-store-task-log pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 1120px) {
  .adapter-store-view__filters {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .adapter-store-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .adapter-store-view__filters,
  .adapter-store-grid {
    grid-template-columns: 1fr;
  }
}
</style>
