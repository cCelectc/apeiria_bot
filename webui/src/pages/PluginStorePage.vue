<script setup lang="ts">
import type {
  PluginStoreCategoryItem,
  PluginStoreItem,
  PluginStoreSource,
  PluginStoreTask,
} from '@/api/plugins'
import {
  ArrowLeft,
  ExternalLink,
  PackageOpen,
  RefreshCw,
  Search,
  Store,
} from '@lucide/vue'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { getErrorMessage } from '@/api/client'
import {
  getPluginStoreItem,
  getPluginStoreItems,
  getPluginStoreSources,
  getPluginStoreTask,
  installPluginStoreItem,
  refreshPluginStoreSources,
  updatePluginStoreItem,
} from '@/api/plugins'
import {
  EmptyState,
  FilterBar,
  LoadingSkeleton,
  PageScaffold,
  StatusBadge,
  TaskDialog,
} from '@/components/management'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { useAuthStore } from '@/stores/auth'
import { useNoticeStore } from '@/stores/notice'
import { useRestartStore } from '@/stores/restart'
import {
  hasActiveFeedbackFilters,
  resolveCollectionFeedback,
  taskStatusTone as resolveTaskStatusTone,
} from '@/utils/feedbackState'
import {
  buildStoreRouteQuery,
  normalizeStoreRouteState,
  storeRouteStateEquals,
  type StoreRouteState,
  type StoreSortMode,
} from '@/utils/storeRouteState'

type PluginStoreActionMode = 'install' | 'update'

const ALL_STORE_OPTIONS = '__all__'
const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const noticeStore = useNoticeStore()
const restartStore = useRestartStore()

const loading = ref(false)
const refreshingSources = ref(false)
const errorMessage = ref('')
const sources = ref<PluginStoreSource[]>([])
const items = ref<PluginStoreItem[]>([])
const categories = ref<PluginStoreCategoryItem[]>([])
const totalItems = ref(0)
const selectedSource = ref('')
const selectedCategory = ref('')
const sortMode = ref<StoreSortMode>('default')
const currentPage = ref(1)
const search = ref('')
const uninstalledOnly = ref(true)
const detailDialogVisible = ref(false)
const actionPending = ref(false)
const taskDialogVisible = ref(false)
const selectedItem = ref<PluginStoreItem | null>(null)
const activeTask = ref<PluginStoreTask | null>(null)
const activeItem = ref<PluginStoreItem | null>(null)
const actionMode = ref<PluginStoreActionMode>('install')
let taskPollTimer: number | null = null
let searchTimer: number | null = null
let syncingRouteState = false

const pageSize = 16
const canUpdateStore = computed(() => authStore.isAuthenticated)
const pageCount = computed(() => Math.max(1, Math.ceil(totalItems.value / pageSize)))
const sourceOptions = computed(() => [
  { value: ALL_STORE_OPTIONS, label: t('pluginStore.allSources') },
  ...sources.value.map(item => ({
    value: item.source_id,
    label: item.name,
  })),
])
const currentSourceLabel = computed(() => {
  const matched = sources.value.find(item => item.source_id === selectedSource.value)
  return matched?.name || t('pluginStore.allSources')
})
const categoryOptions = computed(() => [
  { value: ALL_STORE_OPTIONS, label: t('pluginStore.allCategories') },
  ...categories.value.map(item => ({
    value: item.value,
    label: `${item.value} (${item.count})`,
  })),
])
const sortOptions = computed(() => [
  { value: 'default', label: t('pluginStore.sortDefault') },
  { value: 'updated', label: t('pluginStore.sortUpdated') },
  { value: 'name', label: t('pluginStore.sortName') },
])
const actionLocked = computed(() => (
  actionPending.value
  || activeTask.value?.status === 'pending'
  || activeTask.value?.status === 'queued'
  || activeTask.value?.status === 'running'
))
const taskIsRunning = computed(() =>
  activeTask.value?.status === 'pending'
  || activeTask.value?.status === 'queued'
  || activeTask.value?.status === 'running',
)
const taskFailed = computed(() => activeTask.value?.status === 'failed')
const taskStatusTone = computed(() => resolveTaskStatusTone(activeTask.value?.status))
const detailActionLabel = computed(() =>
  selectedItem.value ? actionLabel(selectedItem.value) : t('pluginStore.install'),
)
const detailTitle = computed(() =>
  selectedItem.value?.can_update
    ? t('pluginStore.updateConfirmTitle')
    : t('pluginStore.installConfirmTitle'),
)
const taskStatusLabel = computed(() => {
  const status = activeTask.value?.status || ''
  if (status === 'pending' || status === 'queued') {
    return actionMode.value === 'update'
      ? t('pluginStore.updatePending')
      : t('pluginStore.installPending')
  }
  if (status === 'running') {
    return actionMode.value === 'update'
      ? t('pluginStore.updateRunning')
      : t('pluginStore.installRunning')
  }
  if (status === 'succeeded') {
    return actionMode.value === 'update'
      ? t('pluginStore.updateSucceeded')
      : t('pluginStore.installSucceeded')
  }
  if (status === 'failed') {
    return activeTask.value?.error || (
      actionMode.value === 'update'
        ? t('pluginStore.updateFailed')
        : t('pluginStore.installFailed')
    )
  }
  return ''
})
const taskTitle = computed(() =>
  activeTask.value?.title || (
    actionMode.value === 'update'
      ? t('pluginStore.updateTaskTitle')
      : t('pluginStore.installTaskTitle')
  ),
)
const taskWaitingText = computed(() =>
  actionMode.value === 'update'
    ? t('pluginStore.updateWaiting')
    : t('pluginStore.installWaiting'),
)
const hasStoreFilters = computed(() =>
  hasActiveFeedbackFilters([
    search.value,
    storeFilterValue(selectedSource.value),
    storeFilterValue(selectedCategory.value),
    sortMode.value !== 'default',
    !uninstalledOnly.value,
  ]),
)
const storeFeedback = computed(() =>
  resolveCollectionFeedback({
    errorMessage: errorMessage.value,
    hasFilters: hasStoreFilters.value,
    loading: loading.value,
    totalCount: totalItems.value || items.value.length,
    visibleCount: items.value.length,
  }),
)

function goBack() {
  void router.push({ name: 'plugins' })
}

function projectUrl(item: PluginStoreItem) {
  const candidate = item.homepage || item.project_link || ''
  if (candidate.startsWith('http://') || candidate.startsWith('https://')) {
    return candidate
  }
  return ''
}

function authorUrl(item: PluginStoreItem) {
  const candidate = item.author_link || ''
  if (candidate.startsWith('http://') || candidate.startsWith('https://')) {
    return candidate
  }
  return ''
}

function pluginIcon(item: PluginStoreItem) {
  for (const key of ['icon', 'icon_url', 'logo', 'logo_url', 'avatar']) {
    const value = item.extra[key]
    if (typeof value === 'string' && value.startsWith('http')) {
      return value
    }
  }
  return ''
}

function visibleTags(item: PluginStoreItem) {
  return item.tags.slice(0, 3)
}

function hiddenTagCount(item: PluginStoreItem) {
  return Math.max(item.tags.length - 3, 0)
}

function formatPublishTime(value: string | null) {
  if (!value) {
    return ''
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return ''
  }
  return new Intl.DateTimeFormat(locale.value === 'zh_CN' ? 'zh-CN' : 'en-US', {
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
  }).format(date)
}

function actionLabel(item: PluginStoreItem) {
  if (item.can_update) {
    return t('pluginStore.update')
  }
  if (item.is_installed) {
    return t('pluginStore.installed')
  }
  return t('pluginStore.install')
}

function canActOnItem(item: PluginStoreItem) {
  return canUpdateStore.value && (!item.is_installed || item.can_update)
}

async function openDetailDialog(item: PluginStoreItem) {
  selectedItem.value = item
  detailDialogVisible.value = true
  try {
    selectedItem.value = (await getPluginStoreItem(item.source_id, item.plugin_id)).data
  } catch {
    selectedItem.value = item
  }
}

async function refreshSources() {
  refreshingSources.value = true
  try {
    sources.value = (await refreshPluginStoreSources({
      source_id: storeFilterValue(selectedSource.value),
    })).data
    noticeStore.show(t('pluginStore.sourcesRefreshed'), 'success')
    await loadStore()
  } catch (error) {
    noticeStore.show(getErrorMessage(error, t('pluginStore.sourceRefreshFailed')), 'error')
  } finally {
    refreshingSources.value = false
  }
}

function storeFilterValue(value: string) {
  return value && value !== ALL_STORE_OPTIONS ? value : undefined
}

function allOptionValue(value: string) {
  return value || ALL_STORE_OPTIONS
}

function currentStoreRouteState(): StoreRouteState {
  return {
    category: storeFilterValue(selectedCategory.value) || '',
    installedOnly: uninstalledOnly.value,
    page: currentPage.value,
    search: search.value.trim(),
    sort: sortMode.value,
    source: storeFilterValue(selectedSource.value) || '',
  }
}

async function syncStoreRouteQuery() {
  const nextQuery = buildStoreRouteQuery(currentStoreRouteState())
  const currentQuery = buildStoreRouteQuery(normalizeStoreRouteState(route.query))
  if (JSON.stringify(nextQuery) === JSON.stringify(currentQuery)) {
    return
  }
  await router.replace({ query: nextQuery })
}

function applyStoreRouteState(state: StoreRouteState) {
  syncingRouteState = true
  selectedSource.value = allOptionValue(state.source)
  selectedCategory.value = allOptionValue(state.category)
  sortMode.value = state.sort
  currentPage.value = state.page
  search.value = state.search
  uninstalledOnly.value = state.installedOnly
  void nextTick(() => {
    syncingRouteState = false
  })
}

function clearStoreFilters() {
  selectedSource.value = ALL_STORE_OPTIONS
  selectedCategory.value = ALL_STORE_OPTIONS
  sortMode.value = 'default'
  currentPage.value = 1
  search.value = ''
  uninstalledOnly.value = true
}

async function startAction() {
  if (!selectedItem.value || !canActOnItem(selectedItem.value)) {
    return
  }
  actionPending.value = true
  activeItem.value = { ...selectedItem.value }
  actionMode.value = selectedItem.value.can_update ? 'update' : 'install'
  try {
    const payload = {
      source_id: selectedItem.value.source_id,
      plugin_id: selectedItem.value.plugin_id,
      package_name: selectedItem.value.package_name,
      module_name: selectedItem.value.module_name,
    }
    const response = actionMode.value === 'update'
      ? await updatePluginStoreItem(payload)
      : await installPluginStoreItem(payload)
    activeTask.value = response.data
    detailDialogVisible.value = false
    taskDialogVisible.value = true
    startTaskPolling(response.data.task_id)
  } catch (error) {
    activeItem.value = null
    noticeStore.show(
      getErrorMessage(error, t(`pluginStore.${actionMode.value}Failed`)),
      'error',
    )
  } finally {
    actionPending.value = false
  }
}

function startTaskPolling(taskId: string) {
  stopTaskPolling()
  taskPollTimer = window.setInterval(async () => {
    try {
      const response = await getPluginStoreTask(taskId)
      activeTask.value = response.data
      if (response.data.status === 'succeeded' || response.data.status === 'failed') {
        stopTaskPolling()
        if (response.data.status === 'succeeded') {
          markRestartPending(activeItem.value, response.data)
          noticeStore.show(t(`pluginStore.${actionMode.value}Succeeded`), 'success')
          void loadStore()
        } else {
          noticeStore.show(
            response.data.error || t(`pluginStore.${actionMode.value}Failed`),
            'error',
          )
        }
        if (response.data.status === 'succeeded') {
          activeItem.value = null
        }
      }
    } catch (error) {
      stopTaskPolling()
      noticeStore.show(
        getErrorMessage(error, t(`pluginStore.${actionMode.value}Failed`)),
        'error',
      )
    }
  }, 1000)
}

function markRestartPending(item: PluginStoreItem | null, task: PluginStoreTask) {
  const moduleName = stringResult(task, 'module_name') || item?.module_name || ''
  const requirement = stringResult(task, 'requirement') || item?.package_name || ''
  const label = item?.name || moduleName || requirement

  if (actionMode.value === 'install') {
    restartStore.markPending({
      id: `plugin-store-install:${moduleName || requirement}`,
      scope: 'plugins',
      summary: t('pluginStore.pendingInstall', { name: label }),
      undo: {
        kind: 'plugin-install',
        packageName: requirement,
        moduleName,
      },
    })
    return
  }

  restartStore.markPending({
    id: `plugin-store-update:${moduleName || requirement}`,
    scope: 'plugins',
    summary: t('pluginStore.pendingUpdate', { name: label }),
  })
}

function stringResult(task: PluginStoreTask, key: string) {
  const value = task.result[key]
  return typeof value === 'string' ? value : ''
}

function stopTaskPolling() {
  if (taskPollTimer !== null) {
    window.clearInterval(taskPollTimer)
    taskPollTimer = null
  }
}

async function loadStore() {
  loading.value = true
  if (items.value.length === 0) {
    errorMessage.value = ''
  }
  try {
    const [sourcesResponse, itemsResponse] = await Promise.all([
      getPluginStoreSources(),
      getPluginStoreItems({
        source: storeFilterValue(selectedSource.value),
        search: search.value || undefined,
        category: storeFilterValue(selectedCategory.value),
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
      && selectedCategory.value !== ALL_STORE_OPTIONS
      && !itemsResponse.data.categories.some(item => item.value === selectedCategory.value)
    ) {
      selectedCategory.value = ALL_STORE_OPTIONS
    }
  } catch (error) {
    errorMessage.value = getErrorMessage(error, t('pluginStore.loadFailed'))
  } finally {
    loading.value = false
  }
}

function scheduleReload() {
  if (searchTimer !== null) {
    window.clearTimeout(searchTimer)
  }
  searchTimer = window.setTimeout(() => {
    void loadStore()
  }, 220)
}

watch([selectedSource, search, selectedCategory, sortMode, uninstalledOnly], () => {
  if (syncingRouteState) {
    return
  }
  currentPage.value = 1
  void syncStoreRouteQuery()
  scheduleReload()
})

watch(currentPage, (nextPage, previousPage) => {
  if (syncingRouteState) {
    return
  }
  if (nextPage === previousPage) {
    return
  }
  void syncStoreRouteQuery()
  void loadStore()
})

watch(() => route.query, query => {
  const nextState = normalizeStoreRouteState(query)
  if (storeRouteStateEquals(nextState, currentStoreRouteState())) {
    return
  }
  applyStoreRouteState(nextState)
  void loadStore()
})

onMounted(() => {
  applyStoreRouteState(normalizeStoreRouteState(route.query))
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

<template>
  <PageScaffold
    class="store-page store-page--plugins"
    :aria-busy="storeFeedback.ariaBusy"
    :error-message="errorMessage"
    :kicker="currentSourceLabel"
    :retry-label="t('feedback.retry')"
    :subtitle="t('pluginStore.warning')"
    :title="t('pluginStore.title')"
    @retry="loadStore"
  >
    <template #actions>
      <Button variant="ghost" @click="goBack">
        <ArrowLeft :size="16" />
        {{ t('pluginStore.backToPlugins') }}
      </Button>
      <Button
        :disabled="refreshingSources"
        variant="secondary"
        @click="refreshSources"
      >
        <RefreshCw :class="{ 'animate-spin': refreshingSources }" :size="16" />
        {{ t('pluginStore.refreshSources') }}
      </Button>
    </template>

    <FilterBar compact>
      <div v-if="storeFeedback.isRefreshing" class="workbench-refresh-status">
        <RefreshCw class="animate-spin" data-icon="inline-start" />
        {{ t('feedback.refreshing') }}
      </div>

      <div class="plugin-store-filter">
        <div class="plugin-store-search">
          <Search :size="16" />
          <Input
            v-model.trim="search"
            :aria-label="t('pluginStore.search')"
            :placeholder="t('pluginStore.search')"
          />
        </div>

        <Select v-model="selectedSource">
          <SelectTrigger class="plugin-store-filter__select">
            <SelectValue :placeholder="t('pluginStore.allSources')" />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectItem
                v-for="option in sourceOptions"
                :key="option.value || 'all'"
                :value="option.value"
              >
                {{ option.label }}
              </SelectItem>
            </SelectGroup>
          </SelectContent>
        </Select>

        <Select v-model="selectedCategory">
          <SelectTrigger class="plugin-store-filter__select">
            <SelectValue :placeholder="t('pluginStore.allCategories')" />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectItem
                v-for="option in categoryOptions"
                :key="option.value || 'all'"
                :value="option.value"
              >
                {{ option.label }}
              </SelectItem>
            </SelectGroup>
          </SelectContent>
        </Select>

        <Select v-model="sortMode">
          <SelectTrigger class="plugin-store-filter__select">
            <SelectValue :placeholder="t('pluginStore.sort')" />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectItem
                v-for="option in sortOptions"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}
              </SelectItem>
            </SelectGroup>
          </SelectContent>
        </Select>

        <label class="plugin-store-filter__switch">
          <Switch v-model="uninstalledOnly" />
          <span>{{ t('pluginStore.uninstalledOnly') }}</span>
        </label>
      </div>

      <div class="plugin-store-filter-summary">
        <Badge variant="secondary">
          {{ currentSourceLabel }}
        </Badge>
        <Badge v-if="storeFilterValue(selectedCategory)" variant="outline">
          {{ storeFilterValue(selectedCategory) }}
        </Badge>
        <Badge variant="outline">
          {{ t('pluginStore.totalCount', { count: totalItems }) }}
        </Badge>
      </div>
    </FilterBar>

    <LoadingSkeleton
      v-if="storeFeedback.isInitialLoading"
      :busy-label="t('common.loading')"
      rows="8"
    />
    <EmptyState
      v-else-if="storeFeedback.showEmpty"
      :action-label="storeFeedback.emptyCause === 'filtered' ? t('feedback.clearFilters') : ''"
      :cause="storeFeedback.emptyCause || 'no-data'"
      :icon="Store"
      :text="storeFeedback.emptyCause === 'filtered' ? '' : t('pluginStore.emptyHint')"
      :title="storeFeedback.emptyCause === 'filtered' ? '' : t('pluginStore.empty')"
      @action="clearStoreFilters"
    />

    <div v-else class="plugin-store-grid">
      <article
        v-for="item in items"
        :key="`${item.source_id}:${item.plugin_id}`"
        class="plugin-store-card"
      >
        <div class="plugin-store-card__header">
          <div class="plugin-store-card__icon">
            <img
              v-if="pluginIcon(item)"
              :alt="item.name"
              :src="pluginIcon(item)"
            >
            <PackageOpen v-else :size="23" />
          </div>

          <div class="plugin-store-card__identity">
            <div class="plugin-store-card__title-row">
              <h2>{{ item.name }}</h2>
              <StatusBadge
                v-if="item.is_official"
                :label="t('pluginStore.official')"
                tone="warning"
              />
              <StatusBadge
                v-if="item.is_installed"
                :label="t('pluginStore.installed')"
                tone="success"
              />
              <StatusBadge
                v-if="item.can_update"
                :label="t('plugins.updateAvailable')"
                tone="warning"
              />
            </div>
            <p>{{ item.module_name }}</p>
          </div>
        </div>

        <div class="plugin-store-card__package">
          {{ item.package_name }}
        </div>

        <p class="plugin-store-card__description">
          {{ item.description || t('pluginStore.noDescription') }}
        </p>

        <div class="plugin-store-card__chips">
          <Badge v-for="tag in visibleTags(item)" :key="tag" variant="outline">
            {{ tag }}
          </Badge>
          <Badge v-if="hiddenTagCount(item) > 0" variant="secondary">
            +{{ hiddenTagCount(item) }}
          </Badge>
        </div>

        <div class="plugin-store-card__meta">
          <span>{{ t('pluginStore.source') }}: {{ item.source_name }}</span>
          <a
            v-if="authorUrl(item) && item.author"
            :href="authorUrl(item)"
            rel="noopener noreferrer"
            target="_blank"
          >
            {{ item.author }}
          </a>
          <span v-else-if="item.author">{{ item.author }}</span>
          <span v-if="item.version">{{ item.version }}</span>
          <span v-if="formatPublishTime(item.publish_time)">
            {{ formatPublishTime(item.publish_time) }}
          </span>
        </div>

        <div class="plugin-store-card__actions">
          <Button
            v-if="projectUrl(item)"
            as="a"
            :href="projectUrl(item)"
            rel="noopener noreferrer"
            size="sm"
            target="_blank"
            variant="ghost"
          >
            <ExternalLink :size="15" />
            {{ t('pluginStore.openProject') }}
          </Button>
          <span v-else class="plugin-store-card__muted-link">
            {{ t('pluginStore.noProjectLink') }}
          </span>

          <span class="plugin-store-card__action-spacer" />
          <Button
            size="sm"
            variant="secondary"
            @click="openDetailDialog(item)"
          >
            {{ t('common.details') }}
          </Button>
          <Button
            :disabled="!canActOnItem(item) || actionLocked"
            size="sm"
            @click="openDetailDialog(item)"
          >
            {{ actionLabel(item) }}
          </Button>
        </div>
      </article>
    </div>

    <div v-if="pageCount > 1" class="plugin-store-pagination">
      <Button
        :disabled="currentPage <= 1"
        variant="secondary"
        @click="currentPage -= 1"
      >
        {{ t('common.previous') }}
      </Button>
      <span>{{ t('pluginStore.pageLabel', { current: currentPage, total: pageCount }) }}</span>
      <Button
        :disabled="currentPage >= pageCount"
        variant="secondary"
        @click="currentPage += 1"
      >
        {{ t('common.next') }}
      </Button>
    </div>

    <Dialog v-model:open="detailDialogVisible">
      <DialogContent class="plugin-store-detail-dialog">
        <DialogHeader>
          <DialogTitle>{{ detailTitle }}</DialogTitle>
          <DialogDescription>{{ t('plugins.settingsRestartHint') }}</DialogDescription>
        </DialogHeader>

        <div v-if="selectedItem" class="plugin-store-detail">
          <div class="plugin-store-detail__header">
            <div class="plugin-store-card__icon">
              <img
                v-if="pluginIcon(selectedItem)"
                :alt="selectedItem.name"
                :src="pluginIcon(selectedItem)"
              >
              <PackageOpen v-else :size="23" />
            </div>
            <div>
              <h2>{{ selectedItem.name }}</h2>
              <p>{{ selectedItem.module_name }}</p>
            </div>
          </div>

          <p class="plugin-store-detail__description">
            {{ selectedItem.description || t('pluginStore.noDescription') }}
          </p>

          <div class="plugin-store-detail__grid">
            <div>
              <span>{{ t('pluginStore.packageName') }}</span>
              <strong>{{ selectedItem.package_name }}</strong>
            </div>
            <div>
              <span>{{ t('pluginStore.source') }}</span>
              <strong>{{ selectedItem.source_name }}</strong>
            </div>
            <div v-if="selectedItem.version">
              <span>{{ t('pluginStore.version') }}</span>
              <strong>{{ selectedItem.version }}</strong>
            </div>
            <div v-if="selectedItem.author">
              <span>{{ t('pluginStore.author') }}</span>
              <strong>{{ selectedItem.author }}</strong>
            </div>
          </div>

          <div class="plugin-store-detail__chips">
            <StatusBadge
              v-if="selectedItem.is_official"
              :label="t('pluginStore.official')"
              tone="warning"
            />
            <StatusBadge
              v-if="selectedItem.is_installed"
              :label="t('pluginStore.installed')"
              tone="success"
            />
            <StatusBadge
              v-if="selectedItem.is_registered"
              :label="t('pluginStore.registered')"
              tone="info"
            />
            <StatusBadge
              v-if="selectedItem.can_update"
              :label="t('plugins.updateAvailable')"
              tone="warning"
            />
            <Badge v-for="tag in selectedItem.tags" :key="tag" variant="outline">
              {{ tag }}
            </Badge>
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" @click="detailDialogVisible = false">
            {{ t('common.cancel') }}
          </Button>
          <Button
            v-if="selectedItem"
            :disabled="!canActOnItem(selectedItem) || actionPending"
            @click="startAction"
          >
            {{ detailActionLabel }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <TaskDialog
      v-model="taskDialogVisible"
      :binding-value="activeTask?.binding_value"
      :close-label="t('common.close')"
      :current-phase="activeTask?.current_phase"
      :current-phase-label="activeTask?.current_phase_label"
      :diagnostics="activeTask?.diagnostics || []"
      :loading="taskIsRunning"
      :logs="activeTask?.logs || ''"
      :operation="activeTask?.operation"
      :queue-position="activeTask?.queue_position"
      :raw-status="activeTask?.status"
      :requirement="activeTask?.requirement"
      :resource-kind="activeTask?.resource_kind"
      :restart-required="activeTask?.restart_required"
      :retry-label="taskFailed ? t('taskDialog.retry') : ''"
      :status="taskStatusLabel"
      :status-tone="taskStatusTone"
      :steps="activeTask?.steps || []"
      :title="taskTitle"
      :waiting-text="taskWaitingText"
      @retry="activeItem && openDetailDialog(activeItem)"
    />
  </PageScaffold>
</template>
