import type { AIRecentTargetItem, AIRelationshipStateItem } from '@/api'
import { computed, reactive, ref } from 'vue'
import { getAIRelationshipState, getAIRelationshipStates, updateAIRelationshipScore } from '@/api'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'

export function useAIRelationshipTab (t: (key: string) => string) {
  const noticeStore = useNoticeStore()

  const loadingRelationships = ref(false)
  const savingRelationship = ref(false)
  const loadingSelectedRelationship = ref(false)
  const relationships = ref<AIRelationshipStateItem[]>([])
  const selectedAffinityId = ref('')
  const relationshipForm = reactive({
    limit: 50,
    score: 0,
  })

  const relationship = computed(() => (
    relationships.value.find(item => item.affinity_id === selectedAffinityId.value) ?? null
  ))

  async function loadRelationships () {
    loadingRelationships.value = true
    try {
      const response = await getAIRelationshipStates({ limit: relationshipForm.limit })
      relationships.value = response.data
      if ((!selectedAffinityId.value || !relationship.value) && relationships.value.length > 0) {
        selectRelationship(relationships.value[0])
      }
    } catch (error) {
      noticeStore.show(
        getErrorMessage(error, t('ai.relationshipLoadFailed')),
        'error',
      )
    } finally {
      loadingRelationships.value = false
    }
  }

  function selectRelationship (item: AIRelationshipStateItem) {
    selectedAffinityId.value = item.affinity_id
    relationshipForm.score = item.score
  }

  async function loadRelationshipForTarget (target: AIRecentTargetItem) {
    if (target.subject_type !== 'user' || !target.platform) {
      return
    }
    loadingSelectedRelationship.value = true
    try {
      const response = await getAIRelationshipState({
        platform: target.platform,
        user_id: target.subject_id,
        group_id: target.scope_type === 'group' ? target.scope_id ?? undefined : undefined,
      })
      const next = response.data
      const exists = relationships.value.some(item => item.affinity_id === next.affinity_id)
      relationships.value = exists
        ? relationships.value.map(item => item.affinity_id === next.affinity_id ? next : item)
        : [next, ...relationships.value]
      selectRelationship(next)
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.relationshipLoadFailed')), 'error')
    } finally {
      loadingSelectedRelationship.value = false
    }
  }

  async function saveRelationship () {
    if (!relationship.value) {
      noticeStore.show(t('ai.relationshipSaveFailed'), 'error')
      return
    }
    savingRelationship.value = true
    try {
      const response = await updateAIRelationshipScore({
        platform: relationship.value.platform,
        user_id: relationship.value.user_id,
        group_id: relationship.value.group_id,
        score: relationshipForm.score,
      })
      relationships.value = relationships.value.map(item => item.affinity_id === response.data.affinity_id ? response.data : item)
      selectRelationship(response.data)
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
    loadRelationshipForTarget,
    loadRelationships,
    loadingRelationships,
    loadingSelectedRelationship,
    relationship,
    relationshipForm,
    relationships,
    saveRelationship,
    savingRelationship,
    selectRelationship,
  }
}
