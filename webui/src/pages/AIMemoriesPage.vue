<script setup lang="ts">
import type { AIMemoryItem } from '@/api/ai'
import {
  Brain,
  CheckSquare,
  MessageSquare,
  RefreshCw,
  Save,
  Search,
  Trash2,
} from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { getErrorMessage } from '@/api/client'
import {
  EmptyState,
  FormField,
  LoadingSkeleton,
  MetricStrip,
  PageScaffold,
  Panel,
  SelectableList,
  SelectableListItem,
  SplitPane,
  StatusBadge,
} from '@/components/management'
import type { WorkbenchMetricItem } from '@/components/management'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { useAIMemoryTab } from '@/composables/useAIMemoryTab'

const { t } = useI18n()
const router = useRouter()
const errorMessage = ref('')
const {
  allMemoriesSelected,
  bulkActionLoading,
  bulkDelete,
  bulkSetLifecycle,
  canLoadMemories,
  canSaveEditedMemory,
  canSaveMemory,
  cancelEditMemory,
  clearSelection,
  deletingMemoryId,
  editingMemoryId,
  loadMemories,
  loadRecentTargets,
  loadingMemories,
  loadingRecentTargets,
  memories,
  memoryDraft,
  memoryEditDraft,
  memoryForm,
  recentTargets,
  removeMemory,
  setLifecycle,
  saveEditedMemory,
  saveMemory,
  savingEditedMemoryId,
  savingMemory,
  selectRecentTarget,
  selectedMemoryCount,
  selectedMemoryIds,
  selectedRecentTargetId,
  startEditMemory,
  toggleMemorySelection,
  toggleSelectAll,
  settingLifecycleId,
} = useAIMemoryTab(t)

const anchorTypeOptions = computed(() => [
  { label: t('ai.memoryAnchorScene'), value: 'scene' },
  { label: t('ai.scopeParticipant'), value: 'participant' },
  { label: t('ai.scopeUser'), value: 'user' },
])
const layerFilterOptions = computed(() => [
  { label: t('common.all'), value: '__all__' },
  { label: t('ai.memoryLayerOperator'), value: 'operator' },
  { label: t('ai.memoryLayerSummary'), value: 'summary' },
  { label: t('ai.memoryLayerLongTerm'), value: 'long_term' },
  { label: t('ai.memoryLayerKnowledge'), value: 'knowledge' },
])
const draftLayerOptions = computed(() => [
  { label: t('ai.memoryLayerLongTerm'), value: 'long_term' },
  { label: t('ai.memoryLayerKnowledge'), value: 'knowledge' },
  { label: t('ai.memoryLayerOperator'), value: 'operator' },
])
const kindOptions = [
  { label: 'fact', value: 'fact' },
  { label: 'preference', value: 'preference' },
  { label: 'relationship', value: 'relationship' },
  { label: 'note', value: 'note' },
]
const kindFilterOptions = computed(() => [
  { label: t('common.all'), value: '__all__' },
  ...kindOptions,
])
const memoryLimitOptions = [10, 20, 50, 100]
const memorySections = computed(() => {
  const knownLayers = [
    { title: t('ai.memoryLayerSummary'), value: 'summary' },
    { title: t('ai.memoryLayerLongTerm'), value: 'long_term' },
    { title: t('ai.memoryLayerKnowledge'), value: 'knowledge' },
    { title: t('ai.memoryLayerOperator'), value: 'operator' },
  ]
  const knownValues = new Set(knownLayers.map(item => item.value))
  const extraLayers = Array.from(new Set(
    memories.value
      .map(item => item.memory_layer)
      .filter(value => !knownValues.has(value)),
  )).map(value => ({ title: value, value }))
  return [...knownLayers, ...extraLayers].map(section => ({
    ...section,
    items: memories.value.filter(item => item.memory_layer === section.value),
  })).filter(section => section.items.length > 0)
})
const memoryTypeBreakdown = computed(() => {
  const counts = new Map<string, number>()
  for (const item of memories.value) {
    counts.set(item.memory_kind, (counts.get(item.memory_kind) ?? 0) + 1)
  }
  return Array.from(counts.entries()).map(([type, count]) => ({ count, type }))
})
const currentTargetLabel = computed(() => {
  if (!memoryForm.anchor_id.trim()) {
    return t('ai.selectMemoryTarget')
  }
  const anchorLabel = anchorTypeOptions.value.find(
    item => item.value === memoryForm.anchor_type,
  )?.label ?? memoryForm.anchor_type
  return `${anchorLabel} / ${memoryForm.anchor_id}`
})
const metrics = computed<WorkbenchMetricItem[]>(() => [
  {
    icon: Brain,
    key: 'memories',
    label: t('ai.memoryCount'),
    value: memories.value.length,
  },
  {
    key: 'selected',
    label: t('ai.memorySelectedCount'),
    tone: selectedMemoryCount.value > 0 ? 'info' : 'default',
    value: selectedMemoryCount.value,
  },
  {
    key: 'suppressed',
    label: t('ai.memorySuppressed'),
    tone: 'warning',
    value: memories.value.filter(item => item.lifecycle_state === 'suppressed').length,
  },
])

async function loadData() {
  errorMessage.value = ''
  try {
    await loadRecentTargets()
    await loadMemories()
  } catch (error) {
    errorMessage.value = getErrorMessage(error, t('ai.loadFailed'))
  }
}

function formatScore(value: number) {
  return value.toFixed(2)
}

function memorySourceTurn(item: AIMemoryItem) {
  return item.source_message_id ? `${item.source_message_id.slice(0, 12)}...` : t('common.none')
}

function openDebugConversations() {
  void router.push({ name: 'ai', query: { area: 'debug', debug: 'conversations' } })
}

function openChatView() {
  void router.push({ name: 'chat' })
}

onMounted(() => {
  void loadData()
})
</script>

<template>
  <PageScaffold
    :error-message="errorMessage"
    :subtitle="t('ai.pageSubtitle.memories')"
    :title="t('ai.memoryTab')"
  >
    <template #actions>
      <Button :disabled="loadingRecentTargets || loadingMemories" variant="secondary" @click="loadData">
        <RefreshCw
          :class="{ 'animate-spin': loadingRecentTargets || loadingMemories }"
          :size="16"
        />
        {{ t('common.refresh') }}
      </Button>
    </template>

    <MetricStrip :items="metrics" compact />

    <SplitPane wide-sidebar>
      <template #sidebar>
        <Panel :title="t('ai.recentTargets')">
          <LoadingSkeleton v-if="loadingRecentTargets && recentTargets.length === 0" :rows="5" />
          <EmptyState
            v-else-if="recentTargets.length === 0"
            :icon="MessageSquare"
            :text="t('ai.noRecentTargetsHint')"
            :title="t('ai.noRecentTargets')"
          />
          <SelectableList v-else>
            <SelectableListItem
              v-for="item in recentTargets"
              :key="`${item.anchor_type}:${item.anchor_id}`"
              :active="selectedRecentTargetId === `${item.anchor_type}:${item.anchor_id}`"
              @click="selectRecentTarget(item)"
            >
              <div class="ai-data-list-item">
                <div class="ai-data-list-item__main">
                  <strong>{{ item.title }}</strong>
                  <span>{{ item.subtitle || item.anchor_id }}</span>
                </div>
                <Badge variant="secondary">{{ item.anchor_type }}</Badge>
              </div>
            </SelectableListItem>
          </SelectableList>
        </Panel>
      </template>

      <div class="ai-data-stack">
        <Panel :title="t('ai.advancedInput')" :subtitle="currentTargetLabel">
          <div class="ai-memory-filter-grid">
            <FormField :label="t('ai.memoryAnchorType')">
              <Select v-model="memoryForm.anchor_type">
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem
                      v-for="option in anchorTypeOptions"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </FormField>
            <FormField :label="t('ai.memoryAnchorId')">
              <Input v-model="memoryForm.anchor_id" />
            </FormField>
            <FormField :label="t('ai.memoryLayer')">
              <Select v-model="memoryForm.memory_layer">
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem
                      v-for="option in layerFilterOptions"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </FormField>
            <FormField :label="t('ai.memoryKind')">
              <Select v-model="memoryForm.memory_kind">
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem
                      v-for="option in kindFilterOptions"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </FormField>
            <FormField :label="t('ai.memoryQuery')">
              <Input v-model="memoryForm.query" />
            </FormField>
            <FormField :label="t('ai.memoryLimit')">
              <Select v-model="memoryForm.limit">
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem
                      v-for="option in memoryLimitOptions"
                      :key="option"
                      :value="option"
                    >
                      {{ option }}
                    </SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </FormField>
            <Button :disabled="!canLoadMemories || loadingMemories" @click="loadMemories">
              <RefreshCw v-if="loadingMemories" class="animate-spin" :size="16" />
              <Search v-else :size="16" />
              {{ t('ai.viewMemories') }}
            </Button>
          </div>
        </Panel>

        <Panel :title="t('ai.saveMemory')">
          <div class="ai-memory-create-grid">
            <FormField :label="t('ai.memoryLayer')">
              <Select v-model="memoryDraft.memory_layer">
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem
                      v-for="option in draftLayerOptions"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </FormField>
            <FormField :label="t('ai.memoryKind')">
              <Select v-model="memoryDraft.memory_kind">
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem
                      v-for="option in kindOptions"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </FormField>
            <FormField :label="t('ai.memoryContent')">
              <Textarea v-model="memoryDraft.content" class="min-h-20" />
            </FormField>
            <Button :disabled="!canSaveMemory" @click="saveMemory">
              <RefreshCw v-if="savingMemory" class="animate-spin" :size="16" />
              <Save v-else :size="16" />
              {{ t('ai.saveMemory') }}
            </Button>
          </div>
        </Panel>

        <Panel v-if="memories.length > 0">
          <template #actions>
            <Button size="sm" variant="secondary" @click="toggleSelectAll">
              <CheckSquare :size="15" />
              {{ allMemoriesSelected ? t('ai.memoryDeselectAll') : t('ai.memorySelectAll') }}
            </Button>
            <Button
              v-if="selectedMemoryCount > 0"
              :disabled="bulkActionLoading"
              size="sm"
              variant="secondary"
              @click="bulkSetLifecycle('suppressed')"
            >
              {{ t('ai.memoryBulkSuppress') }}
            </Button>
            <Button
              v-if="selectedMemoryCount > 0"
              :disabled="bulkActionLoading"
              size="sm"
              variant="secondary"
              @click="bulkSetLifecycle('active')"
            >
              {{ t('ai.memoryBulkActivate') }}
            </Button>
            <Button
              v-if="selectedMemoryCount > 0"
              :disabled="bulkActionLoading"
              size="sm"
              variant="destructive"
              @click="bulkDelete"
            >
              {{ t('ai.memoryBulkDelete') }}
            </Button>
            <Button v-if="selectedMemoryCount > 0" size="sm" variant="ghost" @click="clearSelection">
              {{ t('common.cancel') }}
            </Button>
          </template>

          <div class="ai-data-form__meta">
            <Badge variant="secondary">
              {{ t('ai.memoryTarget') }}: {{ currentTargetLabel }}
            </Badge>
            <Badge
              v-for="item in memoryTypeBreakdown"
              :key="item.type"
              variant="outline"
            >
              {{ item.type }}: {{ item.count }}
            </Badge>
          </div>
        </Panel>

        <LoadingSkeleton v-if="loadingMemories && memories.length === 0" :rows="6" />
        <EmptyState
          v-else-if="memories.length === 0"
          :icon="Brain"
          :text="canLoadMemories ? t('ai.memoryWorkingHint') : t('ai.selectMemoryTarget')"
          :title="canLoadMemories ? t('ai.noMemories') : t('ai.selectMemoryTarget')"
        >
          <template #actions>
            <Button variant="secondary" @click="openDebugConversations">
              {{ t('ai.goToDebug') }}
            </Button>
            <Button variant="ghost" @click="openChatView">
              {{ t('ai.goToChatView') }}
            </Button>
          </template>
        </EmptyState>

        <Panel
          v-for="section in memorySections"
          :key="section.value"
          :title="`${section.title} / ${section.items.length}`"
        >
          <div class="ai-memory-card-list">
            <article
              v-for="item in section.items"
              :key="item.memory_id"
              class="ai-memory-card"
            >
              <div class="ai-memory-card__header">
                <div class="ai-memory-card__badges">
                  <Checkbox
                    :checked="selectedMemoryIds.has(item.memory_id)"
                    @update:checked="() => toggleMemorySelection(item.memory_id)"
                  />
                  <Badge variant="secondary">{{ item.memory_kind }}</Badge>
                  <Badge variant="outline">{{ item.memory_layer }}</Badge>
                  <Badge variant="outline">{{ item.default_use_mode }}</Badge>
                  <StatusBadge
                    v-if="item.lifecycle_state !== 'active'"
                    :label="item.lifecycle_state"
                    tone="error"
                  />
                  <StatusBadge
                    v-if="!item.is_editable"
                    :label="t('ai.memoryReadOnly')"
                    tone="warning"
                  />
                </div>
                <span>{{ item.created_at }}</span>
              </div>

              <p class="ai-memory-card__content">{{ item.content }}</p>

              <div v-if="editingMemoryId === item.memory_id" class="ai-memory-edit">
                <FormField :label="t('ai.memoryContent')">
                  <Textarea v-model="memoryEditDraft.content" class="min-h-28" />
                </FormField>
                <div class="ai-data-grid-2">
                  <FormField :label="t('ai.memorySalience')">
                    <Input v-model="memoryEditDraft.salience" max="1" min="0" step="0.1" type="number" />
                  </FormField>
                  <FormField :label="t('ai.memoryConfidence')">
                    <Input v-model="memoryEditDraft.confidence" max="1" min="0" step="0.1" type="number" />
                  </FormField>
                </div>
              </div>

              <div class="ai-memory-card__meta">
                <span>{{ t('ai.memoryConfidence') }} {{ formatScore(item.confidence) }}</span>
                <span>{{ t('ai.memorySalience') }} {{ formatScore(item.salience) }}</span>
                <span>{{ t('ai.memoryLastRecalledAt') }} {{ item.last_recalled_at || t('common.none') }}</span>
                <span>{{ t('ai.memorySourceTurn') }} {{ memorySourceTurn(item) }}</span>
                <span>{{ t('ai.memoryGovernanceReason') }} {{ item.governance_reason || t('common.none') }}</span>
              </div>

              <div class="ai-memory-card__actions">
                <Button
                  :disabled="settingLifecycleId === item.memory_id"
                  size="sm"
                  variant="ghost"
                  @click="setLifecycle(
                    item.memory_id,
                    item.lifecycle_state === 'active' ? 'suppressed' : 'active',
                  )"
                >
                  <RefreshCw
                    v-if="settingLifecycleId === item.memory_id"
                    class="animate-spin"
                    :size="15"
                  />
                  {{ item.lifecycle_state === 'active' ? t('ai.memorySuppress') : t('ai.memoryActivate') }}
                </Button>
                <Button
                  v-if="editingMemoryId === item.memory_id"
                  size="sm"
                  variant="ghost"
                  @click="cancelEditMemory"
                >
                  {{ t('common.cancel') }}
                </Button>
                <Button
                  v-if="editingMemoryId === item.memory_id"
                  :disabled="!canSaveEditedMemory"
                  size="sm"
                  @click="saveEditedMemory"
                >
                  <RefreshCw
                    v-if="savingEditedMemoryId === item.memory_id"
                    class="animate-spin"
                    :size="15"
                  />
                  {{ t('ai.updateMemory') }}
                </Button>
                <Button
                  v-else
                  :disabled="!item.is_editable"
                  size="sm"
                  variant="secondary"
                  @click="startEditMemory(item)"
                >
                  {{ t('common.edit') }}
                </Button>
                <Button
                  :disabled="deletingMemoryId === item.memory_id"
                  size="sm"
                  variant="destructive"
                  @click="removeMemory(item.memory_id)"
                >
                  <RefreshCw
                    v-if="deletingMemoryId === item.memory_id"
                    class="animate-spin"
                    :size="15"
                  />
                  <Trash2 v-else :size="15" />
                  {{ t('common.delete') }}
                </Button>
              </div>
            </article>
          </div>
        </Panel>
      </div>
    </SplitPane>
  </PageScaffold>
</template>
