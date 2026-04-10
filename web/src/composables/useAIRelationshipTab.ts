import type { AIRelationshipStateItem } from '@/api'
import { reactive, ref } from 'vue'
import { getAIRelationshipState, updateAIRelationshipScore } from '@/api'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'

export function useAIRelationshipTab (t: (key: string) => string) {
  const noticeStore = useNoticeStore()

  const loadingRelationship = ref(false)
  const savingRelationship = ref(false)
  const relationship = ref<AIRelationshipStateItem | null>(null)
  const relationshipForm = reactive({
    platform: 'onebot12',
    user_id: '',
    group_id: '',
    score: 0,
  })

  async function loadRelationship () {
    loadingRelationship.value = true
    try {
      const response = await getAIRelationshipState({
        platform: relationshipForm.platform,
        user_id: relationshipForm.user_id,
        group_id: relationshipForm.group_id || undefined,
      })
      relationship.value = response.data
      relationshipForm.score = response.data.score
    } catch (error) {
      noticeStore.show(
        getErrorMessage(error, t('ai.relationshipLoadFailed')),
        'error',
      )
    } finally {
      loadingRelationship.value = false
    }
  }

  async function saveRelationship () {
    savingRelationship.value = true
    try {
      const response = await updateAIRelationshipScore({
        platform: relationshipForm.platform,
        user_id: relationshipForm.user_id,
        group_id: relationshipForm.group_id || null,
        score: relationshipForm.score,
      })
      relationship.value = response.data
      noticeStore.show(t('ai.relationshipSaved'), 'success')
    } catch (error) {
      noticeStore.show(
        getErrorMessage(error, t('ai.relationshipSaveFailed')),
        'error',
      )
    } finally {
      savingRelationship.value = false
    }
  }

  return {
    loadRelationship,
    loadingRelationship,
    relationship,
    relationshipForm,
    saveRelationship,
    savingRelationship,
  }
}
