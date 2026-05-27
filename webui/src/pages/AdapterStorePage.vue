<script setup lang="ts">
import type {
  AdapterStoreCategoryItem,
  AdapterStoreItem,
  AdapterStoreSource,
  AdapterStoreTask,
} from '@/api/adapters'
import {
  ArrowLeft,
  ExternalLink,
  PackageOpen,
  RefreshCw,
  Search,
  UploadCloud,
} from '@lucide/vue'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import {
  getAdapterStoreItem,
  getAdapterStoreItems,
  getAdapterStoreSources,
  getAdapterStoreTask,
  installAdapterStoreItem,
  installManualAdapter,
  refreshAdapterStoreSources,
  uninstallAdapterStoreItem,
  updateAdapterStoreItem,
} from '@/api/adapters'
import { getErrorMessage } from '@/api/client'
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
import { Label } from '@/components/ui/label'
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

type AdapterActionMode = 'install' | 'manual-install' | 'update' | 'uninstall'

const ALL_STORE_OPTIONS = '__all__'
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const noticeStore = useNoticeStore()
const restartStore = useRestartStore()

const loading = ref(false)
const refreshingSources = ref(false)
const errorMessage = ref('')
const sources = ref<AdapterStoreSource[]>([])
const items = ref<AdapterStoreItem[]>([])
const categories = ref<AdapterStoreCategoryItem[]>([])
const totalItems = ref(0)
const selectedSource = ref('')
const selectedCategory = ref('')
const sortMode = ref<StoreSortMode>('default')
const currentPage = ref(1)
const search = ref('')
const uninstalledOnly = ref(true)
const actionDialogVisible = ref(false)
const manualInstallVisible = ref(false)
const actionPending = ref(false)
const taskDialogVisible = ref(false)
const selectedItem = ref<AdapterStoreItem | null>(null)
const activeTask = ref<AdapterStoreTask | null>(null)
const activeItem = ref<AdapterStoreItem | null>(null)
const actionMode = ref<AdapterActionMode>('install')
const manualRequirement = ref('')
const manualModuleName = ref('')
let taskPollTimer: number | null = null
let searchTimer: number | null = null
let syncingRouteState = false

const pageSize = 16
const pageCount = computed(() => Math.max(1, Math.ceil(totalItems.value / pageSize)))
const sourceOptions = computed(() => [
  { value: ALL_STORE_OPTIONS, label: t('adapterStore.allSources') },
  ...sources.value.map(item => ({
    value: item.source_id,
    label: item.name,
  })),
])
const currentSourceLabel = computed(() => {
  const matched = sources.value.find(item => item.source_id === selectedSource.value)
  return matched?.name || t('adapterStore.allSources')
})
const categoryOptions = computed(() => [
  { value: ALL_STORE_OPTIONS, label: t('adapterStore.allCategories') },
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
const canSubmitManualInstall = computed(() => manualRequirement.value.trim().length > 0)
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
const actionDialogTitle = computed(() => {
  if (actionMode.value === 'update') {
    return t('adapterStore.updateConfirmTitle')
  }
  if (actionMode.value === 'uninstall') {
    return t('adapterStore.uninstallConfirmTitle')
  }
  return t('adapterStore.installConfirmTitle')
})
const actionDialogConfirmLabel = computed(() => {
  if (actionMode.value === 'update') {
    return t('adapterStore.update')
  }
  if (actionMode.value === 'uninstall') {
    return t('adapterStore.uninstall')
  }
  return t('adapterStore.install')
})
const taskStatusLabel = computed(() => {
  const status = activeTask.value?.status || ''
  const prefix = actionMode.value === 'manual-install' ? 'install' : actionMode.value
  if (status === 'pending' || status === 'queued') {
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
  void router.push({ name: 'core' })
}

function canUninstall(item: AdapterStoreItem) {
  return Boolean(item.installed_package && item.is_registered)
}

function projectUrl(item: AdapterStoreItem) {
  const candidate = item.homepage || item.project_link || ''
  if (candidate.startsWith('http://') || candidate.startsWith('https://')) {
    return candidate
  }
  return ''
}

function openActionDialog(item: AdapterStoreItem, mode: Exclude<AdapterActionMode, 'manual-install'>) {
  if (actionLocked.value) {
    return
  }
  selectedItem.value = item
  actionMode.value = mode
  actionDialogVisible.value = true
  void loadItemDetail(item)
}

function openManualInstallDialog() {
  if (actionLocked.value) {
    return
  }
  manualRequirement.value = ''
  manualModuleName.value = ''
  manualInstallVisible.value = true
}

async function loadItemDetail(item: AdapterStoreItem) {
  try {
    const response = await getAdapterStoreItem(item.source_id, item.adapter_id)
    selectedItem.value = response.data
  } catch {
    selectedItem.value = item
  }
}

async function refreshSources() {
  refreshingSources.value = true
  try {
    sources.value = (await refreshAdapterStoreSources({
      source_id: storeFilterValue(selectedSource.value),
    })).data
    noticeStore.show(t('adapterStore.sourcesRefreshed'), 'success')
    await loadStore()
  } catch (error) {
    noticeStore.show(getErrorMessage(error, t('adapterStore.sourceRefreshFailed')), 'error')
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

async function submitManualInstall() {
  const requirement = manualRequirement.value.trim()
  if (!requirement) {
    return
  }
  actionPending.value = true
  actionMode.value = 'manual-install'
  try {
    const response = await installManualAdapter({
      requirement,
      module_name: manualModuleName.value.trim() || undefined,
    })
    activeTask.value = response.data
    activeItem.value = null
    manualInstallVisible.value = false
    taskDialogVisible.value = true
    startTaskPolling(response.data.task_id, { requirement })
  } catch (error) {
    noticeStore.show(getErrorMessage(error, t('adapterStore.installFailed')), 'error')
  } finally {
    actionPending.value = false
  }
}

async function startAction() {
  if (!selectedItem.value) {
    return
  }
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

function startTaskPolling(taskId: string, manualContext?: { requirement: string }) {
  stopTaskPolling()
  taskPollTimer = window.setInterval(async () => {
    try {
      const response = await getAdapterStoreTask(taskId)
      activeTask.value = response.data
      if (response.data.status === 'succeeded' || response.data.status === 'failed') {
        stopTaskPolling()
        if (response.data.status === 'succeeded') {
          markRestartPending(activeItem.value, response.data, manualContext)
          noticeStore.show(t(`adapterStore.${taskMessagePrefix()}Succeeded`), 'success')
          void loadStore()
        } else {
          noticeStore.show(
            response.data.error || t(`adapterStore.${taskMessagePrefix()}Failed`),
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
        getErrorMessage(error, t(`adapterStore.${taskMessagePrefix()}Failed`)),
        'error',
      )
    }
  }, 1000)
}

function taskMessagePrefix() {
  return actionMode.value === 'manual-install' ? 'install' : actionMode.value
}

function markRestartPending(
  item: AdapterStoreItem | null,
  task: AdapterStoreTask,
  manualContext?: { requirement: string },
) {
  const resultModule = typeof task.result.module_name === 'string'
    ? task.result.module_name
    : item?.module_name || manualModuleName.value.trim()
  const resultRequirement = typeof task.result.requirement === 'string'
    ? task.result.requirement
    : item?.installed_package || item?.package_name || manualContext?.requirement || ''
  const label = item?.name || resultModule || resultRequirement

  if (actionMode.value === 'install' || actionMode.value === 'manual-install') {
    restartStore.markPending({
      id: `adapter-store-install:${resultModule || resultRequirement}`,
      scope: 'core',
      summary: t('restart.pendingAdapterInstall', { name: label }),
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
      summary: t('restart.pendingAdapterUpdate', { name: label }),
    })
    return
  }
  restartStore.markPending({
    id: `adapter-store-uninstall:${resultModule || resultRequirement}`,
    scope: 'core',
    summary: t('restart.pendingAdapterUninstall', { name: label }),
  })
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
      getAdapterStoreSources(),
      getAdapterStoreItems({
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
    errorMessage.value = getErrorMessage(error, t('adapterStore.loadFailed'))
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
    class="store-page store-page--adapters"
    :aria-busy="storeFeedback.ariaBusy"
    :error-message="errorMessage"
    :kicker="t('layout.systemSection')"
    :retry-label="t('feedback.retry')"
    :subtitle="t('adapterStore.description')"
    :title="t('adapterStore.title')"
    @retry="loadStore"
  >
    <template #actions>
      <Button variant="ghost" @click="goBack">
        <ArrowLeft :size="16" />
        {{ t('common.back') }}
      </Button>
      <Button
        :disabled="refreshingSources"
        variant="secondary"
        @click="refreshSources"
      >
        <RefreshCw :class="{ 'animate-spin': refreshingSources }" :size="16" />
        {{ t('adapterStore.refreshSources') }}
      </Button>
      <Button
        :disabled="!authStore.isAuthenticated || actionLocked"
        @click="openManualInstallDialog"
      >
        <UploadCloud :size="16" />
        {{ t('adapterStore.manualInstall') }}
      </Button>
    </template>

    <FilterBar compact>
      <div v-if="storeFeedback.isRefreshing" class="workbench-refresh-status">
        <RefreshCw class="animate-spin" data-icon="inline-start" />
        {{ t('feedback.refreshing') }}
      </div>

      <div class="adapter-store-filter">
        <div class="adapter-store-search">
          <Search :size="16" />
          <Input
            v-model.trim="search"
            :aria-label="t('adapterStore.search')"
            :placeholder="t('adapterStore.search')"
          />
        </div>

        <Select v-model="selectedSource">
          <SelectTrigger class="adapter-store-filter__select">
            <SelectValue :placeholder="t('adapterStore.allSources')" />
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
          <SelectTrigger class="adapter-store-filter__select">
            <SelectValue :placeholder="t('adapterStore.allCategories')" />
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
          <SelectTrigger class="adapter-store-filter__select">
            <SelectValue :placeholder="t('adapterStore.sort')" />
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

        <label class="adapter-store-filter__switch">
          <Switch v-model="uninstalledOnly" />
          <span>{{ t('adapterStore.uninstalledOnly') }}</span>
        </label>
      </div>

      <div class="adapter-store-filter-summary">
        <Badge variant="secondary">
          {{ currentSourceLabel }}
        </Badge>
        <Badge v-if="storeFilterValue(selectedCategory)" variant="outline">
          {{ storeFilterValue(selectedCategory) }}
        </Badge>
        <Badge variant="outline">
          {{ t('adapterStore.totalCount', { count: totalItems }) }}
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
      :icon="PackageOpen"
      :text="storeFeedback.emptyCause === 'filtered' ? '' : t('adapterStore.emptyHint')"
      :title="storeFeedback.emptyCause === 'filtered' ? '' : t('adapterStore.empty')"
      @action="clearStoreFilters"
    />

    <div v-else class="adapter-store-grid">
      <article
        v-for="item in items"
        :key="`${item.source_id}:${item.adapter_id}`"
        class="adapter-store-card"
      >
        <div class="adapter-store-card__header">
          <div class="adapter-store-card__identity">
            <h2>{{ item.name }}</h2>
            <p>{{ item.module_name }}</p>
          </div>

          <StatusBadge
            v-if="item.is_official"
            :label="t('adapterStore.official')"
            tone="warning"
          />
        </div>

        <div class="adapter-store-card__package">
          {{ item.package_name }}
        </div>

        <p class="adapter-store-card__description">
          {{ item.description || t('adapterStore.noDescription') }}
        </p>

        <div class="adapter-store-card__chips">
          <StatusBadge
            v-if="item.is_installed"
            :label="t('adapterStore.installed')"
            tone="success"
          />
          <StatusBadge
            v-if="item.is_registered"
            :label="t('adapterStore.registered')"
            tone="info"
          />
          <StatusBadge
            v-if="item.can_update"
            :label="t('adapterStore.updateAvailable')"
            tone="warning"
          />
          <Badge v-for="tag in item.tags.slice(0, 2)" :key="tag" variant="outline">
            {{ tag }}
          </Badge>
        </div>

        <div class="adapter-store-card__meta">
          <span>{{ t('adapterStore.source') }}: {{ item.source_name }}</span>
          <span v-if="item.author">{{ item.author }}</span>
          <span v-if="item.version">{{ item.version }}</span>
        </div>

        <div class="adapter-store-card__actions">
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
            {{ t('adapterStore.openProject') }}
          </Button>
          <span class="adapter-store-card__action-spacer" />
          <Button
            v-if="!item.is_installed"
            :disabled="!authStore.isAuthenticated || actionLocked"
            size="sm"
            @click="openActionDialog(item, 'install')"
          >
            {{ t('adapterStore.install') }}
          </Button>
          <Button
            v-if="item.can_update"
            :disabled="!authStore.isAuthenticated || actionLocked"
            size="sm"
            variant="secondary"
            @click="openActionDialog(item, 'update')"
          >
            {{ t('adapterStore.update') }}
          </Button>
          <Button
            v-if="canUninstall(item)"
            :disabled="!authStore.isAuthenticated || actionLocked"
            size="sm"
            variant="ghost"
            @click="openActionDialog(item, 'uninstall')"
          >
            {{ t('adapterStore.uninstall') }}
          </Button>
        </div>
      </article>
    </div>

    <div v-if="pageCount > 1" class="adapter-store-pagination">
      <Button
        :disabled="currentPage <= 1"
        variant="secondary"
        @click="currentPage -= 1"
      >
        {{ t('common.previous') }}
      </Button>
      <span>{{ t('adapterStore.pageLabel', { current: currentPage, total: pageCount }) }}</span>
      <Button
        :disabled="currentPage >= pageCount"
        variant="secondary"
        @click="currentPage += 1"
      >
        {{ t('common.next') }}
      </Button>
    </div>

    <Dialog v-model:open="actionDialogVisible">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{{ actionDialogTitle }}</DialogTitle>
          <DialogDescription>{{ t('adapterStore.actionRestartHint') }}</DialogDescription>
        </DialogHeader>

        <div v-if="selectedItem" class="adapter-store-action-summary">
          <div>
            <strong>{{ selectedItem.name }}</strong>
            <span>{{ selectedItem.module_name }}</span>
          </div>
          <div>{{ t('adapterStore.packageName') }}: {{ selectedItem.package_name }}</div>
          <div>{{ t('adapterStore.source') }}: {{ selectedItem.source_name }}</div>
        </div>

        <DialogFooter>
          <Button variant="ghost" @click="actionDialogVisible = false">
            {{ t('common.cancel') }}
          </Button>
          <Button :disabled="actionPending" @click="startAction">
            {{ actionDialogConfirmLabel }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="manualInstallVisible">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{{ t('adapterStore.manualInstall') }}</DialogTitle>
          <DialogDescription>{{ t('adapterStore.manualInstallHint') }}</DialogDescription>
        </DialogHeader>

        <div class="adapter-store-manual-form">
          <div class="adapter-store-form-field">
            <Label for="manual-adapter-requirement">
              {{ t('adapterStore.manualRequirement') }}
            </Label>
            <Input
              id="manual-adapter-requirement"
              v-model.trim="manualRequirement"
              :placeholder="t('adapterStore.manualRequirementPlaceholder')"
            />
          </div>

          <div class="adapter-store-form-field">
            <Label for="manual-adapter-module">
              {{ t('adapterStore.manualModuleName') }}
            </Label>
            <Input
              id="manual-adapter-module"
              v-model.trim="manualModuleName"
              :placeholder="t('adapterStore.manualModulePlaceholder')"
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" @click="manualInstallVisible = false">
            {{ t('common.cancel') }}
          </Button>
          <Button
            :disabled="!canSubmitManualInstall || actionPending"
            @click="submitManualInstall"
          >
            {{ t('adapterStore.install') }}
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
      :retry-label="taskFailed && activeItem ? t('taskDialog.retry') : ''"
      :status="taskStatusLabel"
      :status-tone="taskStatusTone"
      :steps="activeTask?.steps || []"
      :title="activeTask?.title || t('adapterStore.taskTitle')"
      :waiting-text="t('adapterStore.taskWaiting')"
      @retry="activeItem && openActionDialog(activeItem, actionMode === 'uninstall' ? 'uninstall' : actionMode === 'update' ? 'update' : 'install')"
    />
  </PageScaffold>
</template>
