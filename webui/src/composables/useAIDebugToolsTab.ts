import type {
  AICapabilityItem,
  AICapabilityPreviewItem,
  AIToolIntentPreviewItem,
  AIToolPolicyBindingItem,
  AIToolPolicyPreviewItem,
} from '@/api/ai'
import { reactive, ref } from 'vue'
import {
  createAIToolPolicyBinding,
  deleteAIToolPolicyBinding,
  getAICapabilities,
  getAIToolPolicyBindings,
  previewAICapability,
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
  const previewingCapability = ref(false)
  const previewingIntents = ref(false)
  const loadingTools = ref(false)
  const capabilities = ref<AICapabilityItem[]>([])
  const bindings = ref<AIToolPolicyBindingItem[]>([])
  const policyPreview = ref<AIToolPolicyPreviewItem | null>(null)
  const capabilityPreview = ref<AICapabilityPreviewItem | null>(null)
  const intentPreview = ref<AIToolIntentPreviewItem[]>([])
  const editingBindingId = ref('')
  const capabilityPreviewName = ref('')

  const bindingForm = reactive({
    allow_read_only_tools: true,
    capability_mode: 'off',
    scope_id: '__global__',
    scope_type: 'global',
  })
  const previewForm = reactive({
    allow_read_only_tools: true,
    capability_mode: 'off',
    is_tome: false,
    scope_type: 'private',
  })
  const intentPreviewForm = reactive({
    message_text: '',
  })

  async function loadDebugToolsData() {
    loadingTools.value = true
    try {
      const [capabilitiesResponse, bindingsResponse] = await Promise.all([
        getAICapabilities(),
        getAIToolPolicyBindings(),
      ])
      capabilities.value = capabilitiesResponse.data
      bindings.value = bindingsResponse.data
      if (!capabilityPreviewName.value && capabilities.value.length > 0) {
        capabilityPreviewName.value = capabilities.value[0].capability_name
      }
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
            allow_read_only_tools: bindingForm.allow_read_only_tools,
            binding_id: editingBindingId.value,
            capability_mode: bindingForm.capability_mode,
          })
        : createAIToolPolicyBinding({
            allow_read_only_tools: bindingForm.allow_read_only_tools,
            capability_mode: bindingForm.capability_mode,
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
    bindingForm.allow_read_only_tools = item.allow_read_only_tools
    bindingForm.capability_mode = item.capability_mode
    bindingForm.scope_id = item.scope_id
    bindingForm.scope_type = item.scope_type
  }

  function resetBindingForm() {
    editingBindingId.value = ''
    bindingForm.allow_read_only_tools = true
    bindingForm.capability_mode = 'off'
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

  async function runCapabilityPreview() {
    if (!capabilityPreviewName.value) {
      return
    }
    previewingCapability.value = true
    try {
      const response = await previewAICapability({
        ...previewForm,
        capability_name: capabilityPreviewName.value,
      })
      capabilityPreview.value = response.data
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.previewFailed')), 'error')
    } finally {
      previewingCapability.value = false
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
    capabilities,
    capabilityPreview,
    capabilityPreviewName,
    editBinding,
    editingBindingId,
    intentPreview,
    intentPreviewForm,
    loadDebugToolsData,
    loadingTools,
    policyPreview,
    previewForm,
    previewingCapability,
    previewingIntents,
    previewingPolicy,
    removeBinding,
    resetBindingForm,
    runCapabilityPreview,
    runIntentPreview,
    runPolicyPreview,
    saving,
    submitBinding,
  }
}
