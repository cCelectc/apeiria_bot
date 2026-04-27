import type { AIPersonMemoryPointItem, AIPersonProfileItem } from '@/api/ai'
import { computed, reactive, ref } from 'vue'
import {
  deleteAIPersonProfile,
  getAIPersonProfiles,
  updateAIPersonProfile,
} from '@/api/ai'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'

export function useAIPersonProfilesTab (t: (key: string) => string) {
  const noticeStore = useNoticeStore()

  const loadingProfiles = ref(false)
  const savingProfile = ref(false)
  const deletingProfileId = ref('')
  const profiles = ref<AIPersonProfileItem[]>([])
  const selectedPersonId = ref('')

  const editForm = reactive({
    person_name: '' as string | null,
    nickname: '' as string | null,
    memory_points: [] as AIPersonMemoryPointItem[],
  })

  const selectedProfile = computed(() =>
    profiles.value.find(item => item.person_id === selectedPersonId.value) ?? null,
  )

  const canSaveProfile = computed(() =>
    selectedPersonId.value.length > 0 && !savingProfile.value,
  )

  async function loadProfiles () {
    loadingProfiles.value = true
    try {
      const response = await getAIPersonProfiles({ limit: 100 })
      profiles.value = response.data
      if (!selectedPersonId.value && profiles.value.length > 0) {
        selectProfile(profiles.value[0])
      }
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.personProfileLoadFailed')), 'error')
    } finally {
      loadingProfiles.value = false
    }
  }

  function selectProfile (item: AIPersonProfileItem) {
    selectedPersonId.value = item.person_id
    editForm.person_name = item.person_name
    editForm.nickname = item.nickname
    editForm.memory_points = item.memory_points.map(point => ({ ...point }))
  }

  async function saveProfile () {
    if (!canSaveProfile.value) {
      return
    }
    savingProfile.value = true
    try {
      const response = await updateAIPersonProfile({
        person_id: selectedPersonId.value,
        person_name: editForm.person_name,
        nickname: editForm.nickname,
        memory_points: editForm.memory_points,
      })
      if (response.data) {
        profiles.value = profiles.value.map(item =>
          item.person_id === response.data?.person_id ? response.data : item,
        )
      }
      noticeStore.show(t('ai.personProfileSaved'), 'success')
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.personProfileSaveFailed')), 'error')
    } finally {
      savingProfile.value = false
    }
  }

  async function removeProfile (personId: string) {
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

  function removeMemoryPoint (index: number) {
    editForm.memory_points.splice(index, 1)
  }

  function addMemoryPoint () {
    editForm.memory_points.push({
      category: 'fact',
      content: '',
      confidence: 0.8,
      source_message_id: null,
    })
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
