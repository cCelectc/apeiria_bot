import type {
  AIPersonMemoryPointItem,
  AIPersonProfileItem,
} from '@/api/ai'
import { computed, reactive, ref } from 'vue'
import {
  deleteAIPersonProfile,
  getAIPersonProfiles,
  updateAIPersonProfile,
} from '@/api/ai'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'

export interface PersonProfileEditFormState {
  memory_points: AIPersonMemoryPointItem[]
  nickname: string | null
  person_name: string | null
}

export function useAIPersonProfilesTab(t: (key: string) => string) {
  const noticeStore = useNoticeStore()

  const loadingProfiles = ref(false)
  const savingProfile = ref(false)
  const deletingProfileId = ref('')
  const profiles = ref<AIPersonProfileItem[]>([])
  const selectedPersonId = ref('')
  const editForm = reactive<PersonProfileEditFormState>({
    memory_points: [],
    nickname: null,
    person_name: null,
  })

  const selectedProfile = computed(() => (
    profiles.value.find(item => item.person_id === selectedPersonId.value) ?? null
  ))
  const canSaveProfile = computed(() => (
    selectedPersonId.value.length > 0
    && !savingProfile.value
  ))

  function selectProfile(item: AIPersonProfileItem) {
    selectedPersonId.value = item.person_id
    editForm.memory_points = item.memory_points.map(point => ({ ...point }))
    editForm.nickname = item.nickname
    editForm.person_name = item.person_name
  }

  async function loadProfiles() {
    loadingProfiles.value = true
    try {
      const response = await getAIPersonProfiles({ limit: 100 })
      profiles.value = response.data
      const current = profiles.value.find(item => item.person_id === selectedPersonId.value)
      if (current) {
        selectProfile(current)
      } else if (profiles.value.length > 0) {
        selectProfile(profiles.value[0])
      } else {
        selectedPersonId.value = ''
        editForm.memory_points = []
        editForm.nickname = null
        editForm.person_name = null
      }
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.personProfileLoadFailed')), 'error')
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
      const response = await updateAIPersonProfile({
        memory_points: editForm.memory_points.map(point => ({
          category: point.category,
          confidence: clamp01(Number(point.confidence)),
          content: point.content.trim(),
          source_message_id: point.source_message_id,
        })),
        nickname: editForm.nickname?.trim() || null,
        person_id: selectedPersonId.value,
        person_name: editForm.person_name?.trim() || null,
      })
      if (response.data) {
        profiles.value = profiles.value.map(item => (
          item.person_id === response.data?.person_id ? response.data : item
        ))
        selectProfile(response.data)
      }
      noticeStore.show(t('ai.personProfileSaved'), 'success')
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.personProfileSaveFailed')), 'error')
    } finally {
      savingProfile.value = false
    }
  }

  async function removeProfile(personId: string) {
    deletingProfileId.value = personId
    try {
      await deleteAIPersonProfile(personId)
      profiles.value = profiles.value.filter(item => item.person_id !== personId)
      if (selectedPersonId.value === personId) {
        selectedPersonId.value = ''
        if (profiles.value.length > 0) {
          selectProfile(profiles.value[0])
        }
      }
      noticeStore.show(t('ai.personProfileDeleted'), 'success')
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.personProfileDeleteFailed')), 'error')
    } finally {
      deletingProfileId.value = ''
    }
  }

  function addMemoryPoint() {
    editForm.memory_points.push({
      category: 'fact',
      confidence: 0.8,
      content: '',
      source_message_id: null,
    })
  }

  function removeMemoryPoint(index: number) {
    editForm.memory_points.splice(index, 1)
  }

  return {
    addMemoryPoint,
    canSaveProfile,
    deletingProfileId,
    editForm,
    loadProfiles,
    loadingProfiles,
    profiles,
    removeMemoryPoint,
    removeProfile,
    saveProfile,
    savingProfile,
    selectProfile,
    selectedPersonId,
    selectedProfile,
  }
}

function clamp01(value: number) {
  if (!Number.isFinite(value)) {
    return 0
  }
  return Math.min(1, Math.max(0, value))
}
