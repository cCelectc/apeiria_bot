import type {
  AIModelBindingItem,
  AIModelProfileItem,
  AIProviderItem,
} from '@/api'
import { computed, reactive, ref } from 'vue'
import {
  getAIModelBindings,
  getAIModelProfiles,
  getAIProviders,
  getAIProviderTypes,
  upsertAIProvider,
} from '@/api'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'

interface ProviderFormState {
  provider_id: string
  name: string
  provider_type: string
  api_base: string
  api_key_env_name: string
  enabled: boolean
  default_model: string
}

function buildProviderSnapshot (form: ProviderFormState) {
  return JSON.stringify({
    provider_id: form.provider_id,
    name: form.name.trim(),
    provider_type: form.provider_type.trim(),
    api_base: form.api_base.trim(),
    api_key_env_name: form.api_key_env_name.trim(),
    enabled: form.enabled,
    default_model: form.default_model.trim(),
  })
}

export function useAIModelsTab (t: (key: string) => string) {
  const noticeStore = useNoticeStore()

  const providers = ref<AIProviderItem[]>([])
  const modelProfiles = ref<AIModelProfileItem[]>([])
  const modelBindings = ref<AIModelBindingItem[]>([])
  const savingProvider = ref(false)
  const providerTypes = ref<string[]>([])
  const providerBaseline = ref('')
  const providerSubmitAttempted = ref(false)
  const providerTouched = reactive({
    name: false,
    provider_type: false,
  })
  const providerForm = reactive<ProviderFormState>({
    provider_id: '',
    name: '',
    provider_type: 'openai_compatible',
    api_base: '',
    api_key_env_name: '',
    enabled: true,
    default_model: '',
  })

  const selectedProvider = computed(() => (
    providers.value.find(item => item.provider_id === providerForm.provider_id) ?? null
  ))

  const providerErrors = computed(() => ({
    name: providerForm.name.trim().length === 0 ? t('ai.providerNameRequired') : '',
    provider_type: providerForm.provider_type.trim().length === 0 ? t('ai.providerTypeRequired') : '',
  }))

  const displayedProviderErrors = computed(() => ({
    name: providerTouched.name || providerSubmitAttempted.value ? providerErrors.value.name : '',
    provider_type: providerTouched.provider_type || providerSubmitAttempted.value ? providerErrors.value.provider_type : '',
  }))

  const providerValid = computed(() => !providerErrors.value.name && !providerErrors.value.provider_type)
  const providerDirty = computed(() => buildProviderSnapshot(providerForm) !== providerBaseline.value)
  const isCreatingProvider = computed(() => providerForm.provider_id.length === 0)
  const canSaveProvider = computed(() => providerValid.value && providerDirty.value && !savingProvider.value)

  async function loadModelsData () {
    const [providersResponse, providerTypesResponse, profilesResponse, bindingsResponse] = await Promise.all([
      getAIProviders(),
      getAIProviderTypes(),
      getAIModelProfiles(),
      getAIModelBindings(),
    ])
    providers.value = providersResponse.data
    providerTypes.value = providerTypesResponse.data
    modelProfiles.value = profilesResponse.data
    modelBindings.value = bindingsResponse.data
    if (!providerForm.provider_id && providers.value.length > 0) {
      selectProvider(providers.value[0])
    }
  }

  function resetProviderValidation () {
    providerSubmitAttempted.value = false
    providerTouched.name = false
    providerTouched.provider_type = false
  }

  function syncProviderBaseline () {
    providerBaseline.value = buildProviderSnapshot(providerForm)
  }

  function touchProviderField (field: keyof typeof providerTouched) {
    providerTouched[field] = true
  }

  function selectProvider (item: AIProviderItem) {
    providerForm.provider_id = item.provider_id
    providerForm.name = item.name
    providerForm.provider_type = item.provider_type
    providerForm.api_base = item.api_base ?? ''
    providerForm.api_key_env_name = item.api_key_env_name ?? ''
    providerForm.enabled = item.enabled
    providerForm.default_model = item.default_model ?? ''
    syncProviderBaseline()
    resetProviderValidation()
  }

  function startCreateProvider () {
    providerForm.provider_id = ''
    providerForm.name = ''
    providerForm.provider_type = 'openai_compatible'
    providerForm.api_base = ''
    providerForm.api_key_env_name = ''
    providerForm.enabled = true
    providerForm.default_model = ''
    syncProviderBaseline()
    resetProviderValidation()
  }

  async function saveProvider () {
    providerSubmitAttempted.value = true
    if (!providerValid.value) {
      noticeStore.show(providerErrors.value.name || providerErrors.value.provider_type || t('ai.providerSaveFailed'), 'error')
      return
    }
    if (!providerDirty.value) {
      return
    }
    savingProvider.value = true
    try {
      const response = await upsertAIProvider({
        provider_id: providerForm.provider_id || null,
        name: providerForm.name.trim(),
        provider_type: providerForm.provider_type.trim(),
        api_base: providerForm.api_base.trim() || null,
        api_key_env_name: providerForm.api_key_env_name.trim() || null,
        enabled: providerForm.enabled,
        default_model: providerForm.default_model.trim() || null,
      })
      if (response.data) {
        await loadModelsData()
        selectProvider(response.data)
      }
      noticeStore.show(t('ai.providerSaved'), 'success')
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.providerSaveFailed')), 'error')
    } finally {
      savingProvider.value = false
    }
  }

  return {
    canSaveProvider,
    displayedProviderErrors,
    isCreatingProvider,
    loadModelsData,
    modelBindings,
    modelProfiles,
    providerDirty,
    providerForm,
    providerTypes,
    providers,
    saveProvider,
    savingProvider,
    selectProvider,
    selectedProvider,
    startCreateProvider,
    touchProviderField,
  }
}
