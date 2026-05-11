import type {
  AIKnowledgeChunkItem,
  AIKnowledgeDocumentItem,
  AIKnowledgeRetrievalResultItem,
  AIKnowledgeStateItem,
} from '@/api/ai'
import { computed, ref } from 'vue'
import {
  deleteAIKnowledgeDocument,
  getAIKnowledgeChunks,
  getAIKnowledgeDocuments,
  getAIKnowledgeState,
  previewAIKnowledgeRetrieval,
  rebuildAIKnowledgeDocument,
  updateAIKnowledgeState,
  uploadAIKnowledgeDocument,
} from '@/api/ai'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'

export function useAIKnowledgeTab(t: (key: string) => string) {
  const noticeStore = useNoticeStore()

  const state = ref<AIKnowledgeStateItem>({
    chunk_count: 0,
    document_count: 0,
    rag_enabled: false,
  })
  const documents = ref<AIKnowledgeDocumentItem[]>([])
  const chunks = ref<AIKnowledgeChunkItem[]>([])
  const selectedDocumentId = ref('')
  const uploadFileName = ref('')
  const uploadContent = ref('')
  const previewQuery = ref('')
  const previewLimit = ref(4)
  const previewResult = ref<AIKnowledgeRetrievalResultItem | null>(null)
  const loadingKnowledge = ref(false)
  const stateSaving = ref(false)
  const uploading = ref(false)
  const loadingChunks = ref(false)
  const rebuildingDocumentId = ref('')
  const deletingDocumentId = ref('')
  const previewing = ref(false)

  const selectedDocument = computed(() => (
    documents.value.find(item => item.document_id === selectedDocumentId.value) ?? null
  ))
  const canUpload = computed(() => (
    uploadFileName.value.trim().length > 0
    && uploadContent.value.trim().length > 0
    && !uploading.value
  ))
  const canPreview = computed(() => (
    previewQuery.value.trim().length > 0
    && !previewing.value
  ))

  async function loadKnowledge() {
    loadingKnowledge.value = true
    try {
      const [stateResponse, documentsResponse] = await Promise.all([
        getAIKnowledgeState(),
        getAIKnowledgeDocuments(),
      ])
      state.value = stateResponse.data
      documents.value = documentsResponse.data
      if (
        selectedDocumentId.value
        && !documents.value.some(item => item.document_id === selectedDocumentId.value)
      ) {
        selectedDocumentId.value = ''
        chunks.value = []
      }
      if (!selectedDocumentId.value && documents.value.length > 0) {
        await selectDocument(documents.value[0].document_id)
      } else if (selectedDocumentId.value) {
        await loadChunks(selectedDocumentId.value)
      }
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.loadFailed')), 'error')
    } finally {
      loadingKnowledge.value = false
    }
  }

  async function saveRagState(nextValue: boolean) {
    stateSaving.value = true
    try {
      const response = await updateAIKnowledgeState(nextValue)
      state.value = response.data
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.knowledgeStateFailed')), 'error')
    } finally {
      stateSaving.value = false
    }
  }

  async function uploadDocument() {
    if (!canUpload.value) {
      return
    }
    uploading.value = true
    try {
      const response = await uploadAIKnowledgeDocument({
        content: uploadContent.value,
        source_file_name: uploadFileName.value.trim(),
      })
      uploadContent.value = ''
      uploadFileName.value = ''
      selectedDocumentId.value = response.data.document.document_id
      chunks.value = response.data.chunks
      await loadKnowledge()
      noticeStore.show(t('ai.knowledgeUploadSaved'), 'success')
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.knowledgeUploadFailed')), 'error')
    } finally {
      uploading.value = false
    }
  }

  async function selectDocument(documentId: string) {
    selectedDocumentId.value = documentId
    await loadChunks(documentId)
  }

  async function loadChunks(documentId: string) {
    loadingChunks.value = true
    try {
      const response = await getAIKnowledgeChunks(documentId)
      if (selectedDocumentId.value === documentId) {
        chunks.value = response.data
      }
    } catch (error) {
      chunks.value = []
      noticeStore.show(getErrorMessage(error, t('ai.loadFailed')), 'error')
    } finally {
      loadingChunks.value = false
    }
  }

  async function rebuildDocument(documentId: string) {
    rebuildingDocumentId.value = documentId
    try {
      await rebuildAIKnowledgeDocument(documentId)
      await loadKnowledge()
      noticeStore.show(t('ai.knowledgeRebuild'), 'success')
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.knowledgeRebuildFailed')), 'error')
    } finally {
      rebuildingDocumentId.value = ''
    }
  }

  async function deleteDocument(documentId: string) {
    deletingDocumentId.value = documentId
    try {
      await deleteAIKnowledgeDocument(documentId)
      if (selectedDocumentId.value === documentId) {
        selectedDocumentId.value = ''
        chunks.value = []
      }
      await loadKnowledge()
      noticeStore.show(t('ai.knowledgeDeleteSaved'), 'success')
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.knowledgeDeleteFailed')), 'error')
    } finally {
      deletingDocumentId.value = ''
    }
  }

  async function previewRetrieval() {
    if (!canPreview.value) {
      return
    }
    previewing.value = true
    try {
      const response = await previewAIKnowledgeRetrieval({
        limit: Math.min(20, Math.max(1, Number(previewLimit.value) || 4)),
        query_text: previewQuery.value.trim(),
      })
      previewResult.value = response.data
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.knowledgePreviewFailed')), 'error')
    } finally {
      previewing.value = false
    }
  }

  return {
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
  }
}
