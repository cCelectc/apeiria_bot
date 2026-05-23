<script setup lang="ts">
import { AlertCircle, FolderOpen, Plus, RefreshCw, Save, Trash2 } from '@lucide/vue'
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  EmptyState,
  LoadingSkeleton,
  MetricStrip,
  PageScaffold,
  Panel,
  StatusBadge,
} from '@/components/management'
import type { WorkbenchMetricItem } from '@/components/management'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Field, FieldDescription, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import { usePluginLoadingRules } from '@/composables/usePluginLoadingRules'
import { useNoticeStore } from '@/stores/notice'
import { useRestartStore } from '@/stores/restart'

const { t } = useI18n()
const noticeStore = useNoticeStore()
const restartStore = useRestartStore()

const loadingRules = usePluginLoadingRules({
  noticeStore,
  restartStore,
  t: (key, params) => t(key, params || {}),
})

const metrics = computed<WorkbenchMetricItem[]>(() => [
  {
    key: 'modules',
    label: t('plugins.moduleSectionTitle'),
    value: `${loadingRules.loadedModuleCount.value}/${loadingRules.modules.value.length}`,
    icon: Plus,
    tone: 'info',
  },
  {
    key: 'dirs',
    label: t('plugins.dirSectionTitle'),
    value: `${loadingRules.availableDirCount.value}/${loadingRules.dirs.value.length}`,
    icon: FolderOpen,
    tone: loadingRules.availableDirCount.value === loadingRules.dirs.value.length
      ? 'success'
      : 'warning',
  },
])

function refreshRules() {
  void loadingRules.reload()
}

function saveRules() {
  void loadingRules.save()
}

onMounted(() => {
  void loadingRules.reload()
})
</script>

<template>
  <PageScaffold
    :error-message="loadingRules.errorMessage.value"
    :kicker="t('plugins.workbenchTitle')"
    :subtitle="t('plugins.configDescription')"
    :title="t('plugins.configTitle')"
  >
    <template #actions>
      <Button
        :disabled="loadingRules.saving.value || !loadingRules.hasPendingChanges.value"
        @click="saveRules"
      >
        <Save data-icon="inline-start" />
        {{ t('common.save') }}
      </Button>
      <Button
        :disabled="loadingRules.loading.value"
        variant="secondary"
        @click="refreshRules"
      >
        <RefreshCw
          :class="{ 'animate-spin': loadingRules.loading.value }"
          data-icon="inline-start"
        />
        {{ t('common.refresh') }}
      </Button>
    </template>

    <MetricStrip :items="metrics" />

    <Alert v-if="loadingRules.hasPendingChanges.value">
      <AlertCircle data-icon="inline-start" />
      <AlertDescription>{{ t('plugins.configDirDescription') }}</AlertDescription>
    </Alert>

    <Alert v-if="loadingRules.normalizationNotes.value.length > 0" variant="default">
      <AlertCircle data-icon="inline-start" />
      <AlertDescription>
        {{ loadingRules.normalizationNotes.value.join(' ') }}
      </AlertDescription>
    </Alert>

    <LoadingSkeleton
      v-if="loadingRules.loading.value && loadingRules.modules.value.length === 0"
      rows="8"
    />

    <div v-else class="plugin-loading-rules-grid">
      <Panel :subtitle="t('plugins.directConfigDescription')" :title="t('plugins.moduleSectionTitle')">
        <template #actions>
          <Button size="sm" variant="secondary" @click="loadingRules.addModuleRow">
            <Plus data-icon="inline-start" />
            {{ t('plugins.addModule') }}
          </Button>
        </template>

        <EmptyState
          v-if="loadingRules.moduleRows.value.length === 0"
          :title="t('plugins.emptyModules')"
        >
          <template #actions>
            <Button variant="secondary" @click="loadingRules.addModuleRow">
              <Plus data-icon="inline-start" />
              {{ t('plugins.addModule') }}
            </Button>
          </template>
        </EmptyState>

        <FieldGroup v-else class="plugin-loading-rules-list">
          <Field
            v-for="row in loadingRules.moduleRows.value"
            :key="row.id"
            class="plugin-loading-rules-row"
          >
            <FieldLabel class="sr-only" :for="row.id">
              {{ t('plugins.moduleInput') }}
            </FieldLabel>
            <Input
              :id="row.id"
              v-model="row.value"
              :placeholder="t('plugins.moduleInput')"
            />
            <FieldDescription v-if="loadingRules.moduleStatusSummary(row.value)">
              {{ loadingRules.moduleStatusSummary(row.value) }}
            </FieldDescription>
            <Button
              :aria-label="t('common.delete')"
              size="icon"
              type="button"
              variant="ghost"
              @click="loadingRules.removeModuleRow(row.id)"
            >
              <Trash2 />
            </Button>
          </Field>
        </FieldGroup>

        <Separator class="my-4" />

        <div class="plugin-loading-rules-status">
          <article
            v-for="item in loadingRules.modules.value"
            :key="item.name"
            class="plugin-loading-rules-status__item"
          >
            <span>{{ item.name }}</span>
            <StatusBadge
              :label="loadingRules.moduleStatusSummary(item.name)"
              :tone="item.is_loaded ? 'success' : item.is_importable ? 'info' : 'warning'"
            />
          </article>
        </div>
      </Panel>

      <Panel :subtitle="t('plugins.configDirDescription')" :title="t('plugins.dirSectionTitle')">
        <template #actions>
          <Button size="sm" variant="secondary" @click="loadingRules.addDirRow">
            <Plus data-icon="inline-start" />
            {{ t('plugins.addDir') }}
          </Button>
        </template>

        <EmptyState
          v-if="loadingRules.dirRows.value.length === 0"
          :title="t('plugins.emptyDirs')"
        >
          <template #actions>
            <Button variant="secondary" @click="loadingRules.addDirRow">
              <Plus data-icon="inline-start" />
              {{ t('plugins.addDir') }}
            </Button>
          </template>
        </EmptyState>

        <FieldGroup v-else class="plugin-loading-rules-list">
          <Field
            v-for="row in loadingRules.dirRows.value"
            :key="row.id"
            class="plugin-loading-rules-row"
          >
            <FieldLabel class="sr-only" :for="row.id">
              {{ t('plugins.dirInput') }}
            </FieldLabel>
            <Input
              :id="row.id"
              v-model="row.value"
              :placeholder="t('plugins.dirInput')"
            />
            <FieldDescription v-if="loadingRules.dirStatusSummary(row.value)">
              {{ loadingRules.dirStatusSummary(row.value) }}
            </FieldDescription>
            <Button
              :aria-label="t('common.delete')"
              size="icon"
              type="button"
              variant="ghost"
              @click="loadingRules.removeDirRow(row.id)"
            >
              <Trash2 />
            </Button>
          </Field>
        </FieldGroup>

        <Separator class="my-4" />

        <div class="plugin-loading-rules-status">
          <article
            v-for="item in loadingRules.dirs.value"
            :key="item.path"
            class="plugin-loading-rules-status__item"
          >
            <span>{{ item.path }}</span>
            <StatusBadge
              :label="loadingRules.dirStatusSummary(item.path)"
              :tone="item.exists ? (item.is_loaded ? 'success' : 'info') : 'warning'"
            />
          </article>
        </div>
      </Panel>
    </div>
  </PageScaffold>
</template>
