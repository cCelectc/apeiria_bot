<template>
  <v-row>
    <v-col cols="12" lg="4">
      <v-sheet class="surface-gradient-card pa-2" rounded="lg">
        <div class="d-flex align-center justify-space-between px-2 py-2">
          <div class="text-body-2 text-medium-emphasis">{{ t('ai.recentTargets') }}</div>
          <v-btn
            icon="mdi-refresh"
            :loading="loadingRecentTargets"
            size="small"
            variant="text"
            @click="loadRecentTargets"
          />
        </div>
        <template v-if="recentTargets.length > 0">
          <v-list class="bg-transparent" density="comfortable" lines="two">
            <v-list-item
              v-for="item in recentTargets"
              :key="`${item.anchor_type}:${item.anchor_id}`"
              :active="selectedRecentTargetId === `${item.anchor_type}:${item.anchor_id}`"
              rounded="lg"
              @click="selectRecentTarget(item)"
            >
              <v-list-item-title>{{ item.title }}</v-list-item-title>
              <v-list-item-subtitle>{{ item.subtitle || item.anchor_id }}</v-list-item-subtitle>
              <template #append>
                <v-chip color="primary" size="small" variant="tonal">
                  {{
                    item.anchor_type === 'scene'
                      ? t('ai.memoryAnchorScene')
                      : item.anchor_type === 'participant'
                        ? t('ai.scopeParticipant')
                        : t('ai.scopeUser')
                  }}
                </v-chip>
              </template>
            </v-list-item>
          </v-list>
        </template>
        <div v-else class="pa-4">
          <div class="empty-state-text">{{ t('ai.noRecentTargets') }}</div>
          <div class="empty-state-hint mt-2">{{ t('ai.noRecentTargetsHint') }}</div>
        </div>
      </v-sheet>
    </v-col>

    <v-col class="d-flex flex-column ga-4" cols="12" lg="8">
      <v-expansion-panels variant="accordion">
        <v-expansion-panel>
          <v-expansion-panel-title>{{ t('ai.advancedInput') }}</v-expansion-panel-title>
          <v-expansion-panel-text>
            <div class="ai-binding-form ai-memory-toolbar pt-2">
              <v-select
                v-model="memoryForm.anchor_type"
                density="comfortable"
                hide-details
                :items="memorySubjectOptions"
                :label="t('ai.memoryAnchorType')"
              />
              <v-select
                v-model="memoryForm.memory_layer"
                density="comfortable"
                hide-details
                :items="memoryDomainOptions"
                :label="t('ai.memoryLayer')"
              />
              <v-text-field
                v-model.trim="memoryForm.anchor_id"
                density="comfortable"
                hide-details
                :label="t('ai.memoryAnchorId')"
              />
              <v-text-field
                v-model.trim="memoryForm.query"
                density="comfortable"
                hide-details
                :label="t('ai.memoryQuery')"
              />
              <v-select
                v-model="memoryForm.memory_kind"
                density="comfortable"
                hide-details
                :items="memoryTypeFilterOptions"
                :label="t('ai.memoryKind')"
              />
              <v-select
                v-model="memoryForm.limit"
                density="comfortable"
                hide-details
                :items="memoryLimitOptions"
                :label="t('ai.memoryLimit')"
              />
            </div>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>

      <div class="d-flex flex-wrap ga-2 justify-space-between align-center">
        <div class="d-flex flex-wrap ga-2">
          <v-chip color="primary" size="small" variant="tonal">
            {{ t('ai.memoryTarget') }}: {{ memoryTargetLabel }}
          </v-chip>
          <v-chip color="primary" size="small" variant="tonal">
            {{ t('ai.memoryCount') }}: {{ memories.length }}
          </v-chip>
          <v-chip
            v-for="item in memoryTypeBreakdown"
            :key="item.memoryType"
            color="primary"
            size="small"
            variant="tonal"
          >
            {{ item.memoryType }}: {{ item.count }}
          </v-chip>
        </div>

        <v-btn
          color="primary"
          :disabled="!canLoadMemories"
          :loading="loadingMemories"
          @click="loadMemories"
        >
          {{ t('ai.viewMemories') }}
        </v-btn>
      </div>

      <div v-if="memories.length > 0" class="d-flex flex-wrap ga-2 align-center">
        <v-btn size="small" variant="tonal" @click="toggleSelectAll">
          {{ allMemoriesSelected ? t('ai.memoryDeselectAll') : t('ai.memorySelectAll') }}
        </v-btn>
        <template v-if="selectedMemoryCount > 0">
          <v-chip color="primary" size="small" variant="tonal">
            {{ t('ai.memorySelectedCount') }}: {{ selectedMemoryCount }}
          </v-chip>
          <v-btn
            color="error"
            :loading="bulkActionLoading"
            size="small"
            variant="tonal"
            @click="bulkDelete"
          >
            {{ t('ai.memoryBulkDelete') }}
          </v-btn>
          <v-btn
            :loading="bulkActionLoading"
            size="small"
            variant="tonal"
            @click="bulkSetIgnored(true)"
          >
            {{ t('ai.memoryBulkIgnore') }}
          </v-btn>
          <v-btn
            :loading="bulkActionLoading"
            size="small"
            variant="tonal"
            @click="bulkSetIgnored(false)"
          >
            {{ t('ai.memoryBulkUnignore') }}
          </v-btn>
          <v-btn size="small" variant="text" @click="clearSelection">
            {{ t('common.cancel') }}
          </v-btn>
        </template>
      </div>

      <v-sheet class="surface-gradient-card pa-4" rounded="lg">
        <div class="ai-binding-form ai-memory-toolbar">
          <v-select
            v-model="memoryDraft.memory_layer"
            density="comfortable"
            hide-details
            :items="memoryDraftLayerOptions"
            :label="t('ai.memoryLayer')"
          />
          <v-select
            v-model="memoryDraft.memory_kind"
            density="comfortable"
            hide-details
            :items="memoryTypeOptions"
            :label="t('ai.memoryKind')"
          />
          <v-textarea
            v-model.trim="memoryDraft.content"
            auto-grow
            density="comfortable"
            hide-details
            :label="t('ai.memoryContent')"
            rows="2"
          />
          <v-btn
            color="primary"
            :disabled="!canSaveMemory"
            :loading="savingMemory"
            @click="saveMemory"
          >
            {{ t('ai.saveMemory') }}
          </v-btn>
        </div>
      </v-sheet>

      <v-sheet class="surface-gradient-card pa-4" rounded="lg">
        <div class="text-subtitle-2 font-weight-medium">
          {{ t('ai.memoryLayerWorking') }}
        </div>
        <div class="empty-state-hint mt-2">
          {{ t('ai.memoryWorkingHint') }}
        </div>
      </v-sheet>

      <div v-if="memories.length > 0" class="d-flex flex-column ga-4">
        <v-sheet
          v-for="section in memoryLayerSections"
          :key="section.layer"
          class="surface-gradient-card pa-4"
          rounded="lg"
        >
          <div class="text-subtitle-2 font-weight-medium mb-3">
            {{ section.title }} · {{ section.items.length }}
          </div>

          <div v-if="section.items.length === 0" class="empty-state-hint">
            {{ t('ai.noMemories') }}
          </div>

          <div v-else class="memory-card-list">
            <v-sheet
              v-for="item in section.items"
              :key="item.memory_id"
              class="surface-gradient-card pa-4"
              rounded="lg"
            >
              <div class="d-flex flex-wrap justify-space-between ga-3">
                <div class="d-flex flex-wrap ga-2 align-center">
                  <v-checkbox
                    density="compact"
                    hide-details
                    :model-value="selectedMemoryIds.has(item.memory_id)"
                    @update:model-value="toggleMemorySelection(item.memory_id)"
                  />
                  <v-chip color="primary" size="small" variant="tonal">
                    {{ item.memory_kind }}
                  </v-chip>
                  <v-chip color="primary" size="small" variant="tonal">
                    {{ item.memory_layer }}
                  </v-chip>
                  <v-chip v-if="!item.is_editable" color="warning" size="small" variant="tonal">
                    {{ t('ai.memoryReadOnly') }}
                  </v-chip>
                  <v-chip v-if="item.is_ignored" color="error" size="small" variant="tonal">
                    {{ t('ai.memoryIgnored') }}
                  </v-chip>
                  <v-chip color="primary" size="small" variant="tonal">
                    {{ t('ai.memoryConfidence') }}: {{ formatMemoryScore(item.confidence) }}
                  </v-chip>
                  <v-chip color="primary" size="small" variant="tonal">
                    {{ t('ai.memorySalience') }}: {{ formatMemoryScore(item.salience) }}
                  </v-chip>
                </div>
                <div class="text-caption text-medium-emphasis">
                  {{ t('ai.memoryCreatedAt') }}: {{ item.created_at }}
                </div>
              </div>

              <div class="text-body-1 mt-3 memory-content-text">{{ item.content }}</div>
              <div v-if="editingMemoryId === item.memory_id" class="d-flex flex-column ga-3 mt-3">
                <v-textarea
                  v-model.trim="memoryEditDraft.content"
                  auto-grow
                  density="comfortable"
                  hide-details
                  :label="t('ai.memoryContent')"
                  rows="3"
                />
                <div class="ai-binding-form">
                  <v-text-field
                    v-model.number="memoryEditDraft.salience"
                    density="comfortable"
                    hide-details
                    :label="t('ai.memorySalience')"
                    max="1"
                    min="0"
                    step="0.1"
                    type="number"
                  />
                  <v-text-field
                    v-model.number="memoryEditDraft.confidence"
                    density="comfortable"
                    hide-details
                    :label="t('ai.memoryConfidence')"
                    max="1"
                    min="0"
                    step="0.1"
                    type="number"
                  />
                </div>
              </div>

              <div class="d-flex flex-wrap ga-4 mt-3 text-caption text-medium-emphasis">
                <span>{{ t('ai.memoryLastRecalledAt') }}: {{ item.last_recalled_at || t('common.none') }}</span>
                <span>{{ t('ai.memorySourceTurn') }}: {{ formatMemorySourceTurn(item.source_message_id) }}</span>
              </div>

              <div class="d-flex justify-end mt-3">
                <v-btn
                  :loading="togglingIgnoredId === item.memory_id"
                  size="small"
                  variant="text"
                  @click="toggleIgnored(item.memory_id)"
                >
                  {{ item.is_ignored ? t('ai.memoryUnignore') : t('ai.memoryIgnore') }}
                </v-btn>
                <v-btn
                  v-if="editingMemoryId === item.memory_id"
                  variant="text"
                  @click="cancelEditMemory"
                >
                  {{ t('common.cancel') }}
                </v-btn>
                <v-btn
                  v-if="editingMemoryId === item.memory_id"
                  color="primary"
                  :disabled="!canSaveEditedMemory"
                  :loading="savingEditedMemoryId === item.memory_id"
                  size="small"
                  variant="text"
                  @click="saveEditedMemory"
                >
                  {{ t('ai.updateMemory') }}
                </v-btn>
                <v-btn
                  v-else
                  color="primary"
                  :disabled="!item.is_editable"
                  size="small"
                  variant="text"
                  @click="startEditMemory(item)"
                >
                  {{ t('common.edit') }}
                </v-btn>
                <v-btn
                  color="error"
                  :loading="deletingMemoryId === item.memory_id"
                  size="small"
                  variant="text"
                  @click="removeMemory(item.memory_id)"
                >
                  {{ t('common.delete') }}
                </v-btn>
              </div>
            </v-sheet>
          </div>
        </v-sheet>
      </div>

      <v-sheet v-else class="surface-gradient-card pa-4" rounded="lg">
        <div class="empty-state-text mb-3">
          {{ canLoadMemories ? t('ai.noMemories') : t('ai.selectMemoryTarget') }}
        </div>
        <div class="d-flex flex-wrap ga-3">
          <v-btn color="primary" variant="tonal" @click="openDebugConversations">
            {{ t('ai.goToDebug') }}
          </v-btn>
          <v-btn variant="text" @click="openChatView">
            {{ t('ai.goToChatView') }}
          </v-btn>
        </div>
      </v-sheet>
    </v-col>
  </v-row>
</template>

<script setup lang="ts">
  import type { AIMemoryItem, AIRecentTargetItem } from '@/api'
  import { computed } from 'vue'
  import { useI18n } from 'vue-i18n'

  interface MemoryFormState {
    anchor_type: string
    anchor_id: string
    memory_layer: string
    memory_kind: string
    query: string
    limit: number
  }

  interface MemoryDraftState {
    memory_layer: string
    memory_kind: string
    content: string
  }

  interface MemoryEditDraftState {
    content: string
    salience: number
    confidence: number
  }

  const props = defineProps<{
    allMemoriesSelected: boolean
    bulkActionLoading: boolean
    canLoadMemories: boolean
    canSaveEditedMemory: boolean
    canSaveMemory: boolean
    cancelEditMemory: () => void
    clearSelection: () => void
    deletingMemoryId: string
    editingMemoryId: string
    loadMemories: () => void | Promise<void>
    loadRecentTargets: () => void | Promise<void>
    loadingMemories: boolean
    loadingRecentTargets: boolean
    memories: AIMemoryItem[]
    openChatView: () => void | Promise<void>
    openDebugConversations: () => void
    recentTargets: AIRecentTargetItem[]
    removeMemory: (memoryId: string) => void | Promise<void>
    saveEditedMemory: () => void | Promise<void>
    saveMemory: () => void | Promise<void>
    savingEditedMemoryId: string
    savingMemory: boolean
    selectedMemoryCount: number
    selectedMemoryIds: Set<string>
    selectedRecentTargetId: string
    selectRecentTarget: (item: AIRecentTargetItem) => void | Promise<void>
    startEditMemory: (item: AIMemoryItem) => void
    toggleIgnored: (memoryId: string) => void | Promise<void>
    toggleMemorySelection: (memoryId: string) => void
    toggleSelectAll: () => void
    togglingIgnoredId: string
    bulkDelete: () => void | Promise<void>
    bulkSetIgnored: (ignored: boolean) => void | Promise<void>
  }>()

  const memoryForm = defineModel<MemoryFormState>('memoryForm', { required: true })
  const memoryDraft = defineModel<MemoryDraftState>('memoryDraft', { required: true })
  const memoryEditDraft = defineModel<MemoryEditDraftState>('memoryEditDraft', { required: true })

  const { t } = useI18n()

  const memorySubjectOptions = computed(() => [
    { title: t('ai.memoryAnchorScene'), value: 'scene' },
    { title: t('ai.scopeUser'), value: 'user' },
    { title: t('ai.scopeParticipant'), value: 'participant' },
  ])

  const memoryDomainOptions = computed(() => [
    { title: t('common.all'), value: '' },
    { title: t('ai.memoryLayerOperator'), value: 'operator' },
    { title: t('ai.memoryLayerSummary'), value: 'summary' },
    { title: t('ai.memoryLayerLongTerm'), value: 'long_term' },
    { title: t('ai.memoryLayerKnowledge'), value: 'knowledge' },
  ])

  const memoryDraftLayerOptions = computed(() => [
    { title: t('ai.memoryLayerLongTerm'), value: 'long_term' },
    { title: t('ai.memoryLayerKnowledge'), value: 'knowledge' },
    { title: t('ai.memoryLayerOperator'), value: 'operator' },
  ])

  const memoryTypeOptions = computed(() => [
    { title: 'fact', value: 'fact' },
    { title: 'preference', value: 'preference' },
    { title: 'relationship', value: 'relationship' },
    { title: 'note', value: 'note' },
  ])

  const memoryTypeFilterOptions = computed(() => [
    { title: t('common.all'), value: '' },
    ...memoryTypeOptions.value,
  ])

  const memoryLimitOptions = [10, 20, 50, 100]

  const memoryTargetLabel = computed(() => {
    if (!memoryForm.value.anchor_id.trim()) {
      return t('ai.selectMemoryTarget')
    }
    const subjectLabel = memorySubjectOptions.value.find(
      item => item.value === memoryForm.value.anchor_type,
    )?.title ?? memoryForm.value.anchor_type
    return `${subjectLabel} · ${memoryForm.value.anchor_id}`
  })

  const memoryTypeBreakdown = computed(() => {
    const counts = new Map<string, number>()
    for (const item of props.memories) {
      counts.set(item.memory_kind, (counts.get(item.memory_kind) ?? 0) + 1)
    }
    return Array.from(counts.entries()).map(([memoryType, count]) => ({ memoryType, count }))
  })

  const memoryLayerSections = computed(() => [
    {
      layer: 'summary',
      title: t('ai.memoryLayerSummary'),
      items: props.memories.filter(item => item.memory_layer === 'summary'),
    },
    {
      layer: 'long_term',
      title: t('ai.memoryLayerLongTerm'),
      items: props.memories.filter(item => item.memory_layer === 'long_term'),
    },
    {
      layer: 'knowledge',
      title: t('ai.memoryLayerKnowledge'),
      items: props.memories.filter(item => item.memory_layer === 'knowledge'),
    },
    {
      layer: 'operator',
      title: t('ai.memoryLayerOperator'),
      items: props.memories.filter(item => item.memory_layer === 'operator'),
    },
  ])

  function formatMemoryScore (value: number) {
    return value.toFixed(2)
  }

  function formatMemorySourceTurn (sourceMessageId: string | null) {
    if (!sourceMessageId) {
      return t('common.none')
    }
    return `${sourceMessageId.slice(0, 12)}...`
  }
</script>
