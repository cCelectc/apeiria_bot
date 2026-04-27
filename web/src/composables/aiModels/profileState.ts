import type {
  AIModelBindingItem,
  AIModelProfileItem,
  AISourceModelItem,
} from '@/api/ai'
import { computed, type ComputedRef, reactive, ref, type Ref } from 'vue'
import { getAIModelProfiles, upsertAIModelProfile } from '@/api/ai'
import { getErrorMessage } from '@/api/client'
import {
  buildProfileSnapshot,
  type ProfileFormState,
} from './formState'

type NoticeLevel = 'error' | 'success' | 'warning'
type ProfileTouchedField = 'model_id' | 'name'

interface UseAIModelProfileStateOptions {
  t: (key: string, params?: Record<string, unknown>) => string
  notify: (message: string, level: NoticeLevel) => void
  currentSourceCapability: Readonly<ComputedRef<string>>
  sourceModels: Ref<AISourceModelItem[]>
  modelProfiles: Ref<AIModelProfileItem[]>
  modelBindings: Ref<AIModelBindingItem[]>
}

export function useAIModelProfileState ({
  t,
  notify,
  currentSourceCapability,
  sourceModels,
  modelProfiles,
  modelBindings,
}: UseAIModelProfileStateOptions) {
  const savingProfile = ref(false)

  const profileBaseline = ref('')
  const profileSubmitAttempted = ref(false)
  const profileTouched = reactive<Record<ProfileTouchedField, boolean>>({
    name: false,
    model_id: false,
  })

  const profileForm = reactive<ProfileFormState>({
    profile_id: '',
    name: '',
    model_id: '',
    task_class: 'reply_default',
    priority: 100,
    enabled: true,
    fallback_profile_id: '',
  })

  const isChatCapability = computed(() => (
    currentSourceCapability.value === 'chat_completion'
  ))
  const configuredSourceModelIds = computed(() => (
    new Set(sourceModels.value.map(item => item.model_id))
  ))
  const filteredModelProfiles = computed(() => modelProfiles.value.filter(
    item => configuredSourceModelIds.value.has(item.model_id),
  ))
  const modelProfileCount = computed(() => filteredModelProfiles.value.length)
  const selectedModelProfile = computed(() => (
    filteredModelProfiles.value.find(
      item => item.profile_id === profileForm.profile_id,
    )
    ?? null
  ))
  const selectedModelBindingCount = computed(() => modelBindings.value.length)

  const profileErrors = computed(() => ({
    name:
      profileForm.name.trim().length === 0
        ? t('ai.modelProfileNameRequired')
        : '',
    model_id:
      profileForm.model_id.trim().length === 0
        ? t('ai.modelProfileModelRequired')
        : '',
  }))

  const displayedProfileErrors = computed(() => ({
    name:
      profileTouched.name || profileSubmitAttempted.value
        ? profileErrors.value.name
        : '',
    model_id:
      profileTouched.model_id || profileSubmitAttempted.value
        ? profileErrors.value.model_id
        : '',
  }))

  const profileValid = computed(() => (
    !profileErrors.value.name && !profileErrors.value.model_id
  ))
  const profileDirty = computed(() => (
    buildProfileSnapshot(profileForm) !== profileBaseline.value
  ))
  const isCreatingProfile = computed(() => profileForm.profile_id.length === 0)
  const canSaveProfile = computed(() => (
    isChatCapability.value
    && profileValid.value
    && profileDirty.value
    && !savingProfile.value
  ))
  const taskClassOptions = computed(() => [
    { title: t('ai.modelTaskClassReplyDefault'), value: 'reply_default' },
    { title: t('ai.modelTaskClassReplyRoleplay'), value: 'reply_roleplay' },
    {
      title: t('ai.modelTaskClassToolOrchestration'),
      value: 'tool_orchestration',
    },
    {
      title: t('ai.modelTaskClassMemoryExtraction'),
      value: 'memory_extraction',
    },
    { title: t('ai.modelTaskClassPlannerLight'), value: 'planner_light' },
    {
      title: t('ai.modelTaskClassReasoningHeavy'),
      value: 'reasoning_heavy',
    },
  ])
  const profileModelOptions = computed(() => sourceModels.value.map(item => ({
    title: item.display_name,
    value: item.model_id,
  })))
  const fallbackProfileOptions = computed(() => filteredModelProfiles.value
    .filter(item => item.profile_id !== profileForm.profile_id)
    .map(item => ({
      title: item.name,
      value: item.profile_id,
    })))

  function resetProfileValidation () {
    profileSubmitAttempted.value = false
    profileTouched.name = false
    profileTouched.model_id = false
  }

  function syncProfileBaseline () {
    profileBaseline.value = buildProfileSnapshot(profileForm)
  }

  function touchProfileField (field: ProfileTouchedField) {
    profileTouched[field] = true
  }

  function selectModelProfile (item: AIModelProfileItem) {
    profileForm.profile_id = item.profile_id
    profileForm.name = item.name
    profileForm.model_id = item.model_id
    profileForm.task_class = item.task_class
    profileForm.priority = item.priority
    profileForm.enabled = item.enabled
    profileForm.fallback_profile_id = item.fallback_profile_id ?? ''
    syncProfileBaseline()
    resetProfileValidation()
  }

  function startCreateModelProfile () {
    profileForm.profile_id = ''
    profileForm.name = ''
    profileForm.model_id = sourceModels.value[0]?.model_id ?? ''
    profileForm.task_class = 'reply_default'
    profileForm.priority = 100
    profileForm.enabled = true
    profileForm.fallback_profile_id = ''
    syncProfileBaseline()
    resetProfileValidation()
  }

  function syncActiveProfileSelection () {
    if (!isChatCapability.value) {
      startCreateModelProfile()
      return
    }
    const current = filteredModelProfiles.value.find(
      item => item.profile_id === profileForm.profile_id,
    )
    if (current) {
      selectModelProfile(current)
      return
    }
    if (filteredModelProfiles.value.length > 0) {
      selectModelProfile(filteredModelProfiles.value[0])
      return
    }
    startCreateModelProfile()
  }

  async function saveModelProfile () {
    profileSubmitAttempted.value = true
    if (!profileValid.value) {
      notify(
        profileErrors.value.name
        || profileErrors.value.model_id
        || t('ai.modelProfileSaveFailed'),
        'error',
      )
      return
    }
    if (!profileDirty.value) {
      return
    }
    savingProfile.value = true
    try {
      const response = await upsertAIModelProfile({
        profile_id: profileForm.profile_id || null,
        name: profileForm.name.trim(),
        model_id: profileForm.model_id,
        task_class: profileForm.task_class,
        priority: profileForm.priority,
        enabled: profileForm.enabled,
        fallback_profile_id: profileForm.fallback_profile_id || null,
      })
      if (response.data) {
        const profilesResponse = await getAIModelProfiles()
        modelProfiles.value = profilesResponse.data
        selectModelProfile(response.data)
      }
      notify(t('ai.modelProfileSaved'), 'success')
    } catch (error) {
      notify(getErrorMessage(error, t('ai.modelProfileSaveFailed')), 'error')
    } finally {
      savingProfile.value = false
    }
  }

  return {
    canSaveProfile,
    displayedProfileErrors,
    fallbackProfileOptions,
    filteredModelProfiles,
    isChatCapability,
    isCreatingProfile,
    modelProfileCount,
    profileForm,
    profileModelOptions,
    saveModelProfile,
    savingProfile,
    selectModelProfile,
    selectedModelBindingCount,
    selectedModelProfile,
    startCreateModelProfile,
    syncActiveProfileSelection,
    taskClassOptions,
    touchProfileField,
  }
}
