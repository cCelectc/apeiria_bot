import type { AIProfileItem } from '@/api/ai'
import { computed, reactive, ref } from 'vue'
import { deleteAIProfile, getAIProfiles, updateAIProfile } from '@/api/ai'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'

export interface ProfileEditFormState {
  display_name: string | null
  name_visibility: string
  preferred_name: string | null
  profile_enabled: boolean
}

export function useAIProfilesTab(t: (key: string) => string) {
  const noticeStore = useNoticeStore()

  const loadingProfiles = ref(false)
  const savingProfile = ref(false)
  const deletingProfileId = ref('')
  const profiles = ref<AIProfileItem[]>([])
  const selectedProfileId = ref('')
  const editForm = reactive<ProfileEditFormState>({
    display_name: null,
    name_visibility: 'public_allowed',
    preferred_name: null,
    profile_enabled: true,
  })

  const selectedProfile = computed(() => (
    profiles.value.find(item => item.profile_id === selectedProfileId.value) ?? null
  ))
  const canSaveProfile = computed(() => (
    selectedProfileId.value.length > 0
    && !savingProfile.value
  ))

  function selectProfile(item: AIProfileItem) {
    selectedProfileId.value = item.profile_id
    editForm.display_name = item.display_name
    editForm.preferred_name = item.preferred_name
    editForm.name_visibility = item.name_visibility
    editForm.profile_enabled = item.profile_enabled
  }

  async function loadProfiles() {
    loadingProfiles.value = true
    try {
      const response = await getAIProfiles({ limit: 100 })
      profiles.value = response.data
      const current = profiles.value.find(item => item.profile_id === selectedProfileId.value)
      if (current) {
        selectProfile(current)
      } else if (profiles.value.length > 0) {
        selectProfile(profiles.value[0])
      } else {
        selectedProfileId.value = ''
        editForm.display_name = null
        editForm.preferred_name = null
        editForm.name_visibility = 'public_allowed'
        editForm.profile_enabled = true
      }
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.profileLoadFailed')), 'error')
    } finally {
      loadingProfiles.value = false
    }
  }

  async function saveProfile() {
    if (!canSaveProfile.value) {
      return
    }
    savingProfile.value = true
    try {
      const response = await updateAIProfile({
        display_name: editForm.display_name?.trim() || null,
        name_source: 'manual',
        name_visibility: editForm.name_visibility,
        preferred_name: editForm.preferred_name?.trim() || null,
        profile_enabled: editForm.profile_enabled,
        profile_id: selectedProfileId.value,
      })
      if (response.data) {
        profiles.value = profiles.value.map(item => (
          item.profile_id === response.data?.profile_id ? response.data : item
        ))
        selectProfile(response.data)
      }
      noticeStore.show(t('ai.profileSaved'), 'success')
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.profileSaveFailed')), 'error')
    } finally {
      savingProfile.value = false
    }
  }

  async function removeProfile(profileId: string) {
    deletingProfileId.value = profileId
    try {
      await deleteAIProfile(profileId)
      profiles.value = profiles.value.filter(item => item.profile_id !== profileId)
      if (selectedProfileId.value === profileId) {
        selectedProfileId.value = ''
        if (profiles.value.length > 0) {
          selectProfile(profiles.value[0])
        }
      }
      noticeStore.show(t('ai.profileDeleted'), 'success')
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.profileDeleteFailed')), 'error')
    } finally {
      deletingProfileId.value = ''
    }
  }

  return {
    canSaveProfile,
    deletingProfileId,
    editForm,
    loadProfiles,
    loadingProfiles,
    profiles,
    removeProfile,
    saveProfile,
    savingProfile,
    selectProfile,
    selectedProfile,
    selectedProfileId,
  }
}
