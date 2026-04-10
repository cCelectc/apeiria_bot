import type {
  AICapabilityItem,
  AICapabilityPreviewItem,
  AIToolItem,
  AIToolPolicyBindingItem,
  AIToolPolicyPreviewItem,
} from '@/api'
import { reactive, ref } from 'vue'
import {
  createAIToolPolicyBinding,
  deleteAIToolPolicyBinding,
  getAICapabilities,
  getAIToolPolicyBindings,
  getAITools,
  previewAICapability,
  previewAIToolPolicy,
  updateAIToolPolicyBinding,
} from '@/api'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'

export function useAIToolsTab (t: (key: string) => string) {
  const noticeStore = useNoticeStore()

  const saving = ref(false)
  const previewingPolicy = ref(false)
  const previewingCapability = ref(false)

  const tools = ref<AIToolItem[]>([])
  const capabilities = ref<AICapabilityItem[]>([])
  const bindings = ref<AIToolPolicyBindingItem[]>([])
  const policyPreview = ref<AIToolPolicyPreviewItem | null>(null)
  const capabilityPreview = ref<AICapabilityPreviewItem | null>(null)

  const editingBindingId = ref('')
  const capabilityPreviewName = ref('help.show')

  const bindingForm = reactive({
    scope_type: 'global',
    scope_id: '__global__',
    allow_read_only_tools: true,
    capability_mode: 'off',
  })

  const previewForm = reactive({
    scope_type: 'private',
    is_tome: false,
    allow_read_only_tools: true,
    capability_mode: 'off',
  })

  async function loadToolsData () {
    const [toolsResponse, capabilitiesResponse, bindingsResponse] = await Promise.all([
      getAITools(),
      getAICapabilities(),
      getAIToolPolicyBindings(),
    ])
    tools.value = toolsResponse.data
    capabilities.value = capabilitiesResponse.data
    bindings.value = bindingsResponse.data
    if (!capabilityPreviewName.value && capabilities.value.length > 0) {
      capabilityPreviewName.value = capabilities.value[0].capability_name
    }
  }

  async function submitBinding (reload: () => Promise<void>) {
    saving.value = true
    try {
      const action = editingBindingId.value
        ? updateAIToolPolicyBinding({
            binding_id: editingBindingId.value,
            allow_read_only_tools: bindingForm.allow_read_only_tools,
            capability_mode: bindingForm.capability_mode,
          })
        : createAIToolPolicyBinding({
            scope_type: bindingForm.scope_type,
            scope_id: bindingForm.scope_id,
            allow_read_only_tools: bindingForm.allow_read_only_tools,
            capability_mode: bindingForm.capability_mode,
          })
      await action
      noticeStore.show(t('ai.bindingSaved'), 'success')
      resetBindingForm()
      await reload()
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.bindingSaveFailed')), 'error')
    } finally {
      saving.value = false
    }
  }

  function editBinding (item: AIToolPolicyBindingItem) {
    editingBindingId.value = item.binding_id
    bindingForm.scope_type = item.scope_type
    bindingForm.scope_id = item.scope_id
    bindingForm.allow_read_only_tools = item.allow_read_only_tools
    bindingForm.capability_mode = item.capability_mode
  }

  function resetBindingForm () {
    editingBindingId.value = ''
    bindingForm.scope_type = 'global'
    bindingForm.scope_id = '__global__'
    bindingForm.allow_read_only_tools = true
    bindingForm.capability_mode = 'off'
  }

  async function removeBinding (bindingId: string, reload: () => Promise<void>) {
    try {
      await deleteAIToolPolicyBinding(bindingId)
      noticeStore.show(t('ai.bindingDeleted'), 'success')
      if (editingBindingId.value === bindingId) {
        resetBindingForm()
      }
      await reload()
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.bindingDeleteFailed')), 'error')
    }
  }

  async function runPolicyPreview () {
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

  async function runCapabilityPreview () {
    previewingCapability.value = true
    try {
      const response = await previewAICapability({
        capability_name: capabilityPreviewName.value,
        ...previewForm,
      })
      capabilityPreview.value = response.data
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.previewFailed')), 'error')
    } finally {
      previewingCapability.value = false
    }
  }

  return {
    bindingForm,
    bindings,
    capabilities,
    capabilityPreview,
    capabilityPreviewName,
    editingBindingId,
    loadToolsData,
    policyPreview,
    previewForm,
    previewingCapability,
    previewingPolicy,
    removeBinding,
    resetBindingForm,
    runCapabilityPreview,
    runPolicyPreview,
    saving,
    submitBinding,
    tools,
    editBinding,
  }
}
