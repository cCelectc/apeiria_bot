<script setup lang="ts">
import {
  BookOpenCheck,
  FileText,
  RefreshCw,
  Search,
  Trash2,
  UploadCloud,
} from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
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
import type { WorkbenchMetricItem, WorkbenchTone } from '@/components/management'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { useAIKnowledgeTab } from '@/composables/useAIKnowledgeTab'

const { t } = useI18n()
const errorMessage = ref('')
const {
  canPreview,
  canUpload,
  chunks,
  deletingDocumentId,
  deleteDocument,
  documents,
  loadKnowledge,
  loadingChunks,
  loadingKnowledge,
  previewing,
  previewLimit,
  previewQuery,
  previewResult,
  previewRetrieval,
  rebuildingDocumentId,
  rebuildDocument,
  saveRagState,
  selectDocument,
  selectedDocument,
  selectedDocumentId,
  state,
  stateSaving,
  uploadContent,
  uploadDocument,
  uploadFileName,
  uploading,
} = useAIKnowledgeTab(t)

const limitOptions = [2, 4, 8, 12, 20]
const metrics = computed<WorkbenchMetricItem[]>(() => [
  {
    icon: BookOpenCheck,
    key: 'documents',
    label: t('ai.knowledgeDocuments'),
    value: state.value.document_count,
  },
  {
    key: 'chunks',
    label: t('ai.knowledgeChunks'),
    tone: 'info',
    value: state.value.chunk_count,
  },
  {
    key: 'rag',
    label: t('ai.knowledgeRagEnabled'),
    tone: state.value.rag_enabled ? 'success' : 'warning',
    value: state.value.rag_enabled ? t('ai.enabled') : t('ai.disabled'),
  },
])

async function loadData() {
  errorMessage.value = ''
  try {
    await loadKnowledge()
  } catch (error) {
    errorMessage.value = getErrorMessage(error, t('ai.loadFailed'))
  }
}

function statusTone(status: string): WorkbenchTone {
  if (status === 'ready' || status === 'completed') {
    return 'success'
  }
  if (status === 'failed' || status === 'error') {
    return 'error'
  }
  if (status === 'processing' || status === 'pending') {
    return 'info'
  }
  return 'default'
}

function formatScore(value: number | null) {
  return typeof value === 'number' ? value.toFixed(3) : t('common.none')
}

function formatDate(value: string) {
  return new Date(value).toLocaleString()
}

function handleRagToggle(value: boolean | 'indeterminate') {
  void saveRagState(value === true)
}

onMounted(() => {
  void loadData()
})
</script>

<template>
  <PageScaffold
    :error-message="errorMessage"
    :subtitle="t('ai.pageSubtitle.knowledge')"
    :title="t('ai.knowledgeTab')"
  >
    <template #actions>
      <div class="ai-data-switch-inline">
        <span>{{ t('ai.knowledgeRagEnabled') }}</span>
        <Switch
          :checked="state.rag_enabled"
          :disabled="stateSaving"
          @update:checked="handleRagToggle"
        />
      </div>
      <Button :disabled="loadingKnowledge" variant="secondary" @click="loadData">
        <RefreshCw :class="{ 'animate-spin': loadingKnowledge }" :size="16" />
        {{ t('common.refresh') }}
      </Button>
    </template>

    <MetricStrip :items="metrics" compact />

    <SplitPane wide-sidebar>
      <template #sidebar>
        <Panel :title="t('ai.knowledgeUpload')">
          <div class="ai-data-form">
            <FormField :label="t('ai.knowledgeFileName')" required>
              <Input v-model="uploadFileName" placeholder="notes.md" />
            </FormField>
            <FormField :label="t('ai.knowledgeContent')" required>
              <Textarea v-model="uploadContent" class="min-h-40" />
            </FormField>
            <Button :disabled="!canUpload" @click="uploadDocument">
              <RefreshCw v-if="uploading" class="animate-spin" :size="16" />
              <UploadCloud v-else :size="16" />
              {{ t('ai.knowledgeUpload') }}
            </Button>
          </div>
        </Panel>

        <Panel :title="t('ai.knowledgeDocuments')">
          <LoadingSkeleton v-if="loadingKnowledge && documents.length === 0" :rows="5" />
          <EmptyState
            v-else-if="documents.length === 0"
            :icon="FileText"
            :title="t('ai.knowledgeNoDocuments')"
          />
          <SelectableList v-else>
            <SelectableListItem
              v-for="document in documents"
              :key="document.document_id"
              :active="selectedDocumentId === document.document_id"
              @click="selectDocument(document.document_id)"
            >
              <div class="ai-data-list-item">
                <div class="ai-data-list-item__main">
                  <strong>{{ document.title }}</strong>
                  <span>{{ document.source_file_name }}</span>
                </div>
                <StatusBadge
                  :label="document.status"
                  :tone="statusTone(document.status)"
                />
              </div>
            </SelectableListItem>
          </SelectableList>
        </Panel>
      </template>

      <div class="ai-data-stack">
        <Panel
          :subtitle="selectedDocument?.source_file_name || t('ai.knowledgeNoChunks')"
          :title="selectedDocument?.title || t('ai.knowledgeChunks')"
        >
          <template v-if="selectedDocument" #actions>
            <Button
              :disabled="rebuildingDocumentId === selectedDocument.document_id"
              size="sm"
              variant="secondary"
              @click="rebuildDocument(selectedDocument.document_id)"
            >
              <RefreshCw
                :class="{ 'animate-spin': rebuildingDocumentId === selectedDocument.document_id }"
                :size="15"
              />
              {{ t('ai.knowledgeRebuild') }}
            </Button>
            <Button
              :disabled="deletingDocumentId === selectedDocument.document_id"
              size="sm"
              variant="destructive"
              @click="deleteDocument(selectedDocument.document_id)"
            >
              <RefreshCw
                v-if="deletingDocumentId === selectedDocument.document_id"
                class="animate-spin"
                :size="15"
              />
              <Trash2 v-else :size="15" />
              {{ t('common.delete') }}
            </Button>
          </template>

          <div v-if="selectedDocument" class="ai-data-form__meta">
            <Badge variant="secondary">
              {{ t('ai.knowledgeChunkCount') }}: {{ selectedDocument.chunk_count }}
            </Badge>
            <Badge variant="outline">
              {{ t('ai.knowledgeUpdatedAt') }}: {{ formatDate(selectedDocument.updated_at) }}
            </Badge>
            <Badge v-if="selectedDocument.last_error" variant="destructive">
              {{ selectedDocument.last_error }}
            </Badge>
          </div>

          <LoadingSkeleton v-if="loadingChunks" :rows="5" />
          <EmptyState
            v-else-if="chunks.length === 0"
            :icon="FileText"
            :title="t('ai.knowledgeNoChunks')"
          />
          <div v-else class="ai-knowledge-chunk-list">
            <article
              v-for="chunk in chunks"
              :key="chunk.chunk_id"
              class="ai-knowledge-chunk"
            >
              <div class="ai-knowledge-chunk__header">
                <strong>#{{ chunk.ordinal + 1 }}</strong>
                <div>
                  <Badge variant="secondary">
                    {{ chunk.embedding_status }}
                  </Badge>
                  <Badge variant="outline">
                    {{ chunk.char_count }}
                  </Badge>
                </div>
              </div>
              <pre>{{ chunk.text }}</pre>
            </article>
          </div>
        </Panel>

        <Panel :title="t('ai.knowledgePreview')" :subtitle="t('ai.knowledgeNoPreview')">
          <div class="ai-knowledge-preview-controls">
            <FormField :label="t('ai.knowledgePreviewQuery')">
              <Input
                v-model="previewQuery"
                @keyup.enter="previewRetrieval"
              />
            </FormField>
            <FormField :label="t('ai.knowledgePreviewLimit')">
              <Select v-model="previewLimit">
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem
                    v-for="option in limitOptions"
                    :key="option"
                    :value="option"
                  >
                    {{ option }}
                  </SelectItem>
                </SelectContent>
              </Select>
            </FormField>
            <Button :disabled="!canPreview" @click="previewRetrieval">
              <RefreshCw v-if="previewing" class="animate-spin" :size="16" />
              <Search v-else :size="16" />
              {{ t('ai.knowledgePreview') }}
            </Button>
          </div>

          <EmptyState
            v-if="!previewResult"
            :icon="Search"
            :title="t('ai.knowledgeNoPreview')"
          />
          <div v-else class="ai-knowledge-results">
            <div class="ai-data-form__meta">
              <Badge variant="secondary">
                {{ t('ai.knowledgeRerank') }}: {{ previewResult.diagnostics.rerank_status }}
              </Badge>
              <Badge variant="outline">
                {{ t('ai.knowledgePreviewLimit') }}: {{ previewResult.diagnostics.selected_count }}
              </Badge>
              <Badge v-if="previewResult.diagnostics.degradation_reason" variant="outline">
                {{ previewResult.diagnostics.degradation_reason }}
              </Badge>
            </div>

            <article
              v-for="item in previewResult.items"
              :key="item.chunk_id"
              class="ai-knowledge-result"
            >
              <div class="ai-knowledge-result__header">
                <strong>[{{ item.label }}] {{ item.title }}</strong>
                <div>
                  <Badge variant="secondary">
                    {{ t('ai.knowledgeScore') }} {{ formatScore(item.score) }}
                  </Badge>
                  <Badge variant="outline">
                    {{ t('ai.knowledgeRerank') }} {{ formatScore(item.rerank_score) }}
                  </Badge>
                </div>
              </div>
              <p>{{ item.excerpt }}</p>
            </article>
          </div>
        </Panel>
      </div>
    </SplitPane>
  </PageScaffold>
</template>
