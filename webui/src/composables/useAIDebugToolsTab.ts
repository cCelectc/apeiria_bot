import type {
  AIToolIntentPreviewItem,
  AIToolPolicyBindingItem,
  AIToolPolicyPreviewItem,
} from '@/api/ai'
import { reactive, ref } from 'vue'
import {
  createAIToolPolicyBinding,
  deleteAIToolPolicyBinding,
  getAIToolPolicyBindings,
  previewAIToolIntents,
  previewAIToolPolicy,
  updateAIToolPolicyBinding,
} from '@/api/ai'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'

export function useAIDebugToolsTab(t: (key: string) => string) {
  const noticeStore = useNoticeStore()

  const saving = ref(false)
  const previewingPolicy = ref(false)
  const previewingIntents = ref(false)
  const loadingTools = ref(false)
  const bindings = ref<AIToolPolicyBindingItem[]>([])
  const policyPreview = ref<AIToolPolicyPreviewItem | null>(null)
  const intentPreview = ref<AIToolIntentPreviewItem[]>([])
  const editingBindingId = ref('')

  const bindingForm = reactive({
    allowed_level: 'none',
    scope_id: '__global__',
    scope_type: 'global',
  })
  const previewForm = reactive({
    allowed_level: 'none',
    is_tome: false,
    scope_type: 'private',
  })
  const intentPreviewForm = reactive({
    message_text: '',
  })

  async function loadDebugToolsData() {
    loadingTools.value = true
    try {
      const bindingsResponse = await getAIToolPolicyBindings()
      bindings.value = bindingsResponse.data
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.loadFailed')), 'error')
    } finally {
      loadingTools.value = false
    }
  }

  async function submitBinding() {
    saving.value = true
    try {
      const action = editingBindingId.value
        ? updateAIToolPolicyBinding({
            allowed_level: bindingForm.allowed_level,
            binding_id: editingBindingId.value,
          })
        : createAIToolPolicyBinding({
            allowed_level: bindingForm.allowed_level,
            scope_id: bindingForm.scope_id.trim(),
            scope_type: bindingForm.scope_type,
          })
      await action
      noticeStore.show(t('ai.bindingSaved'), 'success')
      resetBindingForm()
      await loadDebugToolsData()
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.bindingSaveFailed')), 'error')
    } finally {
      saving.value = false
    }
  }

  function editBinding(item: AIToolPolicyBindingItem) {
    editingBindingId.value = item.binding_id
    bindingForm.allowed_level = item.allowed_level
    bindingForm.scope_id = item.scope_id
    bindingForm.scope_type = item.scope_type
  }

  function resetBindingForm() {
    editingBindingId.value = ''
    bindingForm.allowed_level = 'none'
    bindingForm.scope_id = '__global__'
    bindingForm.scope_type = 'global'
  }

  async function removeBinding(bindingId: string) {
    try {
      await deleteAIToolPolicyBinding(bindingId)
      noticeStore.show(t('ai.bindingDeleted'), 'success')
      if (editingBindingId.value === bindingId) {
        resetBindingForm()
      }
      await loadDebugToolsData()
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.bindingDeleteFailed')), 'error')
    }
  }

  async function runPolicyPreview() {
    previewingPolicy.value = true
    try {
      const response = await previewAIToolPolicy(previewForm)
      policyPreview.value = response.data
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.previewFailed')), 'error')
    } finally {
      previewingPolicy.value = false
    }
  }

  async function runIntentPreview() {
    if (!intentPreviewForm.message_text.trim()) {
      return
    }
    previewingIntents.value = true
    try {
      const response = await previewAIToolIntents({
        ...previewForm,
        message_text: intentPreviewForm.message_text.trim(),
      })
      intentPreview.value = response.data
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.previewFailed')), 'error')
    } finally {
      previewingIntents.value = false
    }
  }

  return {
    bindingForm,
    bindings,
    editBinding,
    editingBindingId,
    intentPreview,
    intentPreviewForm,
    loadDebugToolsData,
    loadingTools,
    policyPreview,
    previewForm,
    previewingIntents,
    previewingPolicy,
    removeBinding,
    resetBindingForm,
    runIntentPreview,
    runPolicyPreview,
    saving,
    submitBinding,
  }
}
