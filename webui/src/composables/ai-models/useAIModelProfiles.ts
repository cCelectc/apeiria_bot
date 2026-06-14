import type {
  AIModelBindingItem,
  AIModelProfileItem,
  AISourceModelItem,
} from '@/api/ai'
import { computed, reactive, ref, type Ref } from 'vue'
import {
  getAIModelBindings,
  getAIModelProfiles,
  upsertAIModelProfile,
} from '@/api/ai'
import { getErrorMessage } from '@/api/client'
import {
  buildProfileSnapshot,
  type ProfileFormState,
} from '@/composables/aiModels/formState'
import type { AIWorkflowOperationResult, AIWorkflowResultStage } from '@/utils/aiSetupWorkflow'
import type { NoticeLevel, ProfileTouchedField } from './helpers'

export interface ProfileRouteHooks {
  syncActiveRouteSelection: () => void
}

export function useAIModelProfiles(
  t: (key: string, params?: Record<string, unknown>) => string,
  notifyFn: (message: string, level: NoticeLevel) => void,
  reportWorkflowFn: (stage: AIWorkflowResultStage, result: AIWorkflowOperationResult) => void,
  configuredSourceModelIds: Ref<Set<string>>,
  sourceModels: Ref<AISourceModelItem[]>,
  isChatCapability: Ref<boolean>,
) {
  const modelProfiles = ref<AIModelProfileItem[]>([])
  const modelBindings = ref<AIModelBindingItem[]>([])

  const savingProfile = ref(false)
  const profileBaseline = ref('')
  const profileSubmitAttempted = ref(false)

  const profileTouched = reactive<Record<ProfileTouchedField, boolean>>({
    model_id: false,
    name: false,
  })

  const profileForm = reactive<ProfileFormState>({
    enabled: true,
    model_id: '',
    name: '',
    priority: 100,
    profile_id: '',
    task_class: 'reply_default',
  })

  const routeHooks: ProfileRouteHooks = {
    syncActiveRouteSelection: () => {},
  }

  function setRouteHooks(hooks: ProfileRouteHooks) {
    Object.assign(routeHooks, hooks)
  }

  const filteredModelProfiles = computed(() => modelProfiles.value.filter(
    item => configuredSourceModelIds.value.has(item.model_id),
  ))
  const modelProfileCount = computed(() => filteredModelProfiles.value.length)
  const isCreatingProfile = computed(() => profileForm.profile_id.length === 0)

  const profileErrors = computed(() => ({
    model_id: profileForm.model_id.trim().length === 0
      ? t('ai.modelProfileModelRequired')
      : '',
    name: profileForm.name.trim().length === 0
      ? t('ai.modelProfileNameRequired')
      : '',
  }))
  const displayedProfileErrors = computed(() => ({
    model_id: profileTouched.model_id || profileSubmitAttempted.value
      ? profileErrors.value.model_id
      : '',
    name: profileTouched.name || profileSubmitAttempted.value
      ? profileErrors.value.name
      : '',
  }))
  const profileValid = computed(() => (
    !profileErrors.value.model_id && !profileErrors.value.name
  ))
  const profileDirty = computed(() => (
    buildProfileSnapshot(profileForm) !== profileBaseline.value
  ))
  const canSaveProfile = computed(() => (
    isChatCapability.value
    && profileValid.value
    && profileDirty.value
    && !savingProfile.value
  ))

  const profileModelOptions = computed(() => sourceModels.value.map(item => ({
    title: item.display_name,
    value: item.model_id,
  })))
  const selectedModelBindingCount = computed(() => (
    modelBindings.value.filter(item => item.profile_id === profileForm.profile_id).length
  ))

  function resetProfileValidation() {
    profileSubmitAttempted.value = false
    profileTouched.model_id = false
    profileTouched.name = false
  }

  function syncProfileBaseline() {
    profileBaseline.value = buildProfileSnapshot(profileForm)
  }

  function touchProfileField(field: ProfileTouchedField) {
    profileTouched[field] = true
  }

  function selectModelProfile(item: AIModelProfileItem) {
    Object.assign(profileForm, {
      enabled: item.enabled,
      model_id: item.model_id,
      name: item.name,
      priority: item.priority,
      profile_id: item.profile_id,
      task_class: item.task_class,
    })
    syncProfileBaseline()
    resetProfileValidation()
  }

  function startCreateModelProfile() {
    Object.assign(profileForm, {
      enabled: true,
      model_id: sourceModels.value[0]?.model_id ?? '',
      name: '',
      priority: 100,
      profile_id: '',
      task_class: 'reply_default',
    })
    syncProfileBaseline()
    resetProfileValidation()
  }

  function syncActiveProfileSelection() {
    if (!isChatCapability.value) {
      startCreateModelProfile()
      routeHooks.syncActiveRouteSelection()
      return
    }
    const current = filteredModelProfiles.value.find(
      item => item.profile_id === profileForm.profile_id,
    )
    if (current) {
      selectModelProfile(current)
      routeHooks.syncActiveRouteSelection()
      return
    }
    if (filteredModelProfiles.value.length > 0) {
      selectModelProfile(filteredModelProfiles.value[0])
      routeHooks.syncActiveRouteSelection()
      return
    }
    startCreateModelProfile()
    routeHooks.syncActiveRouteSelection()
  }

  async function saveModelProfile() {
    profileSubmitAttempted.value = true
    if (!profileValid.value) {
      const message = profileErrors.value.name
        || profileErrors.value.model_id
        || t('ai.modelProfileSaveFailed')
      reportWorkflowFn('profile', { message, status: 'error' })
      notifyFn(message, 'error')
      return
    }
    if (!profileDirty.value) {
      return
    }
    savingProfile.value = true
    try {
      const response = await upsertAIModelProfile({
        enabled: profileForm.enabled,
        model_id: profileForm.model_id,
        name: profileForm.name.trim(),
        priority: profileForm.priority,
        profile_id: profileForm.profile_id || null,
        task_class: profileForm.task_class,
      })
      if (response.data) {
        const profilesResponse = await getAIModelProfiles()
        modelProfiles.value = profilesResponse.data
        selectModelProfile(response.data)
      }
      const message = t('ai.modelProfileSaved')
      reportWorkflowFn('profile', { message, status: 'success' })
      notifyFn(message, 'success')
    } catch (error) {
      const message = getErrorMessage(error, t('ai.modelProfileSaveFailed'))
      reportWorkflowFn('profile', { message, status: 'error' })
      notifyFn(message, 'error')
    } finally {
      savingProfile.value = false
    }
  }

  return {
    canSaveProfile,
    displayedProfileErrors,
    filteredModelProfiles,
    isCreatingProfile,
    modelBindings,
    modelProfileCount,
    modelProfiles,
    profileForm,
    profileModelOptions,
    profileValid,
    savingProfile,
    selectedModelBindingCount,

    saveModelProfile,
    selectModelProfile,
    startCreateModelProfile,
    syncActiveProfileSelection,
    touchProfileField,

    setRouteHooks,
  }
}
