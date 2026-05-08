<template>
  <PageScaffold
    :error-message="errorMessage"
    :subtitle="t('ai.pageSubtitle.knowledge')"
    :title="t('ai.knowledgeTab')"
  >
    <template #actions>
      <v-switch
        v-model="ragEnabled"
        color="primary"
        density="compact"
        hide-details
        :label="t('ai.knowledgeRagEnabled')"
        :loading="stateLoading"
        @update:model-value="saveRagState"
      />
      <v-btn :loading="loading" variant="tonal" @click="loadData">
        {{ t('common.refresh') }}
      </v-btn>
    </template>

    <div class="knowledge-page">
      <v-card class="page-panel">
        <v-card-title>{{ t('ai.knowledgeUpload') }}</v-card-title>
        <v-card-text class="knowledge-upload">
          <v-text-field
            v-model="uploadFileName"
            density="compact"
            :label="t('ai.knowledgeFileName')"
            placeholder="notes.md"
            variant="outlined"
          />
          <v-textarea
            v-model="uploadContent"
            auto-grow
            density="compact"
            :label="t('ai.knowledgeContent')"
            rows="4"
            variant="outlined"
          />
          <v-btn
            color="primary"
            :disabled="!canUpload"
            :loading="uploading"
            prepend-icon="mdi-upload"
            @click="uploadDocument"
          >
            {{ t('ai.knowledgeUpload') }}
          </v-btn>
        </v-card-text>
      </v-card>

      <v-card class="page-panel">
        <v-card-title>{{ t('ai.knowledgeDocuments') }}</v-card-title>
        <v-card-text>
          <v-table density="compact">
            <thead>
              <tr>
                <th>{{ t('ai.knowledgeSource') }}</th>
                <th>{{ t('ai.knowledgeStatus') }}</th>
                <th>{{ t('ai.knowledgeChunkCount') }}</th>
                <th>{{ t('ai.knowledgeUpdatedAt') }}</th>
                <th>{{ t('common.actions') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="documents.length === 0">
                <td colspan="5">{{ t('ai.knowledgeNoDocuments') }}</td>
              </tr>
              <tr
                v-for="document in documents"
                :key="document.document_id"
                :class="{ 'knowledge-row--active': selectedDocumentId === document.document_id }"
                @click="selectDocument(document.document_id)"
              >
                <td>
                  <div class="knowledge-source">{{ document.title }}</div>
                  <div class="knowledge-muted">{{ document.source_file_name }}</div>
                </td>
                <td><v-chip size="small" variant="tonal">{{ document.status }}</v-chip></td>
                <td>{{ document.chunk_count }}</td>
                <td>{{ formatDate(document.updated_at) }}</td>
                <td>
                  <v-btn
                    icon="mdi-refresh"
                    size="small"
                    :title="t('ai.knowledgeRebuild')"
                    variant="text"
                    @click.stop="rebuildDocument(document.document_id)"
                  />
                  <v-btn
                    icon="mdi-delete-outline"
                    size="small"
                    :title="t('common.delete')"
                    variant="text"
                    @click.stop="deleteDocument(document.document_id)"
                  />
                </td>
              </tr>
            </tbody>
          </v-table>
        </v-card-text>
      </v-card>

      <v-card class="page-panel">
        <v-card-title>{{ t('ai.knowledgeChunks') }}</v-card-title>
        <v-card-text>
          <div v-if="chunks.length === 0" class="knowledge-empty">
            {{ t('ai.knowledgeNoChunks') }}
          </div>
          <v-expansion-panels v-else density="compact" variant="accordion">
            <v-expansion-panel
              v-for="chunk in chunks"
              :key="chunk.chunk_id"
            >
              <v-expansion-panel-title>
                #{{ chunk.ordinal + 1 }} · {{ chunk.embedding_status }}
              </v-expansion-panel-title>
              <v-expansion-panel-text>
                <pre class="knowledge-chunk">{{ chunk.text }}</pre>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </v-card-text>
      </v-card>

      <v-card class="page-panel">
        <v-card-title>{{ t('ai.knowledgePreview') }}</v-card-title>
        <v-card-text class="knowledge-preview">
          <div class="knowledge-preview__controls">
            <v-text-field
              v-model="previewQuery"
              density="compact"
              :label="t('ai.knowledgePreviewQuery')"
              variant="outlined"
              @keyup.enter="previewRetrieval"
            />
            <v-text-field
              v-model.number="previewLimit"
              density="compact"
              :label="t('ai.knowledgePreviewLimit')"
              max="20"
              min="1"
              type="number"
              variant="outlined"
            />
            <v-btn
              :disabled="!previewQuery.trim()"
              :loading="previewing"
              prepend-icon="mdi-magnify"
              variant="tonal"
              @click="previewRetrieval"
            >
              {{ t('ai.knowledgePreview') }}
            </v-btn>
          </div>
          <div v-if="!previewResult" class="knowledge-empty">
            {{ t('ai.knowledgeNoPreview') }}
          </div>
          <div v-else class="knowledge-results">
            <v-chip size="small" variant="tonal">
              {{ t('ai.knowledgeRerank') }}: {{ previewResult.diagnostics.rerank_status }}
            </v-chip>
            <div
              v-for="item in previewResult.items"
              :key="item.chunk_id"
              class="knowledge-result"
            >
              <div class="knowledge-result__header">
                <strong>[{{ item.label }}] {{ item.title }}</strong>
                <span>{{ t('ai.knowledgeScore') }} {{ item.score.toFixed(3) }}</span>
              </div>
              <p>{{ item.excerpt }}</p>
            </div>
          </div>
        </v-card-text>
      </v-card>
    </div>
  </PageScaffold>
</template>

<script setup lang="ts">
  import type {
    AIKnowledgeChunkItem,
    AIKnowledgeDocumentItem,
    AIKnowledgeRetrievalResultItem,
  } from '@/api/ai/types'
  import { computed, onMounted, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import {
    deleteAIKnowledgeDocument,
    getAIKnowledgeChunks,
    getAIKnowledgeDocuments,
    getAIKnowledgeState,
    previewAIKnowledgeRetrieval,
    rebuildAIKnowledgeDocument,
    updateAIKnowledgeState,
    uploadAIKnowledgeDocument,
  } from '@/api/ai/knowledge'
  import { PageScaffold } from '@/components/workbench'
  import { useAIPageLoader } from '@/views/ai/pageHelpers'

  const { t } = useI18n()
  const { errorMessage, loading, runPageLoad } = useAIPageLoader(() => t('ai.loadFailed'))

  const ragEnabled = ref(false)
  const stateLoading = ref(false)
  const documents = ref<AIKnowledgeDocumentItem[]>([])
  const chunks = ref<AIKnowledgeChunkItem[]>([])
  const selectedDocumentId = ref('')
  const uploadFileName = ref('')
  const uploadContent = ref('')
  const uploading = ref(false)
  const previewQuery = ref('')
  const previewLimit = ref(4)
  const previewing = ref(false)
  const previewResult = ref<AIKnowledgeRetrievalResultItem | null>(null)

  const canUpload = computed(() => uploadFileName.value.trim() && uploadContent.value.trim())

  async function loadData () {
    await runPageLoad(async () => {
      const [stateResponse, documentsResponse] = await Promise.all([
        getAIKnowledgeState(),
        getAIKnowledgeDocuments(),
      ])
      ragEnabled.value = stateResponse.data.rag_enabled
      documents.value = documentsResponse.data
      if (selectedDocumentId.value) {
        await loadChunks(selectedDocumentId.value)
      }
    })
  }

  async function saveRagState () {
    stateLoading.value = true
    try {
      const response = await updateAIKnowledgeState(ragEnabled.value)
      ragEnabled.value = response.data.rag_enabled
    } catch {
      errorMessage.value = t('ai.knowledgeStateFailed')
    } finally {
      stateLoading.value = false
    }
  }

  async function uploadDocument () {
    uploading.value = true
    try {
      const response = await uploadAIKnowledgeDocument({
        source_file_name: uploadFileName.value.trim(),
        content: uploadContent.value,
      })
      uploadFileName.value = ''
      uploadContent.value = ''
      selectedDocumentId.value = response.data.document.document_id
      await loadData()
      await loadChunks(selectedDocumentId.value)
    } catch {
      errorMessage.value = t('ai.knowledgeUploadFailed')
    } finally {
      uploading.value = false
    }
  }

  async function selectDocument (documentId: string) {
    selectedDocumentId.value = documentId
    await loadChunks(documentId)
  }

  async function loadChunks (documentId: string) {
    const response = await getAIKnowledgeChunks(documentId)
    chunks.value = response.data
  }

  async function rebuildDocument (documentId: string) {
    try {
      await rebuildAIKnowledgeDocument(documentId)
      await loadData()
      if (selectedDocumentId.value === documentId) {
        await loadChunks(documentId)
      }
    } catch {
      errorMessage.value = t('ai.knowledgeRebuildFailed')
    }
  }

  async function deleteDocument (documentId: string) {
    try {
      await deleteAIKnowledgeDocument(documentId)
      if (selectedDocumentId.value === documentId) {
        selectedDocumentId.value = ''
        chunks.value = []
      }
      await loadData()
    } catch {
      errorMessage.value = t('ai.knowledgeDeleteFailed')
    }
  }

  async function previewRetrieval () {
    previewing.value = true
    try {
      const response = await previewAIKnowledgeRetrieval({
        query_text: previewQuery.value,
        limit: Number(previewLimit.value) || 4,
      })
      previewResult.value = response.data
    } catch {
      errorMessage.value = t('ai.knowledgePreviewFailed')
    } finally {
      previewing.value = false
    }
  }

  function formatDate (value: string) {
    return new Date(value).toLocaleString()
  }

  onMounted(() => {
    void loadData()
  })
</script>

<style scoped>
  .knowledge-page {
    display: grid;
    gap: 16px;
  }

  .knowledge-upload,
  .knowledge-preview {
    display: grid;
    gap: 12px;
  }

  .knowledge-preview__controls {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 140px auto;
    gap: 12px;
    align-items: start;
  }

  .knowledge-row--active {
    background: rgba(var(--v-theme-primary), 0.08);
  }

  .knowledge-source {
    font-weight: 600;
  }

  .knowledge-muted {
    color: rgba(var(--v-theme-on-surface), 0.62);
    font-size: 0.82rem;
  }

  .knowledge-empty {
    color: rgba(var(--v-theme-on-surface), 0.62);
    padding: 16px 0;
  }

  .knowledge-chunk {
    margin: 0;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .knowledge-results {
    display: grid;
    gap: 10px;
  }

  .knowledge-result {
    border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
    border-radius: 8px;
    padding: 12px;
  }

  .knowledge-result__header {
    display: flex;
    justify-content: space-between;
    gap: 12px;
  }

  @media (max-width: 760px) {
    .knowledge-preview__controls {
      grid-template-columns: 1fr;
    }
  }
</style>
