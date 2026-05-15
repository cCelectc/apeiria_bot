import type {
  AIRecentTargetItem,
  AIRelationshipEventItem,
  AIRelationshipStateItem,
} from '@/api/ai'
import { computed, reactive, ref } from 'vue'
import {
  getAIRelationshipEvents,
  getAIRelationshipStates,
  updateAIRelationshipScore,
} from '@/api/ai'
import client, { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'

export interface RelationshipFormState {
  limit: number
  score: number
}

export function useAIRelationshipTab(t: (key: string) => string) {
  const noticeStore = useNoticeStore()
  let relationshipEventsRequestId = 0

  const loadingRelationships = ref(false)
  const savingRelationship = ref(false)
  const loadingSelectedRelationship = ref(false)
  const loadingRelationshipEvents = ref(false)
  const relationships = ref<AIRelationshipStateItem[]>([])
  const relationshipEvents = ref<AIRelationshipEventItem[]>([])
  const selectedAffinityId = ref('')
  const relationshipForm = reactive<RelationshipFormState>({
    limit: 50,
    score: 0,
  })

  const relationship = computed(() => (
    relationships.value.find(item => item.affinity_id === selectedAffinityId.value) ?? null
  ))

  async function loadRelationships() {
    loadingRelationships.value = true
    try {
      const response = await getAIRelationshipStates({ limit: relationshipForm.limit })
      relationships.value = response.data
      const current = relationships.value.find(item => item.affinity_id === selectedAffinityId.value)
      if (current) {
        await selectRelationship(current)
      } else if (relationships.value.length > 0) {
        await selectRelationship(relationships.value[0])
      }
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.relationshipLoadFailed')), 'error')
    } finally {
      loadingRelationships.value = false
    }
  }

  async function selectRelationship(item: AIRelationshipStateItem) {
    selectedAffinityId.value = item.affinity_id
    relationshipForm.score = item.score
    relationshipEvents.value = []
    await loadRelationshipEvents(item)
  }

  async function loadRelationshipForTarget(target: AIRecentTargetItem) {
    if (!target.platform) {
      return
    }
    const userId = target.user_id ?? (target.anchor_type === 'user' ? target.anchor_id : '')
    if (!userId) {
      return
    }
    loadingSelectedRelationship.value = true
    try {
      const response = await client.get<AIRelationshipStateItem>('/ai/relationships', {
        params: {
          platform: target.platform,
          user_id: userId,
        },
      })
      const next = response.data
      const exists = relationships.value.some(item => item.affinity_id === next.affinity_id)
      relationships.value = exists
        ? relationships.value.map(item => item.affinity_id === next.affinity_id ? next : item)
        : [next, ...relationships.value]
      await selectRelationship(next)
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.relationshipLoadFailed')), 'error')
    } finally {
      loadingSelectedRelationship.value = false
    }
  }

  async function saveRelationship() {
    if (!relationship.value) {
      noticeStore.show(t('ai.relationshipSaveFailed'), 'error')
      return
    }
    savingRelationship.value = true
    try {
      const response = await updateAIRelationshipScore({
        platform: relationship.value.platform,
        score: Number(relationshipForm.score),
        user_id: relationship.value.user_id,
      })
      const exists = relationships.value.some(item =>
        isSameRelationshipTarget(item, response.data),
      )
      relationships.value = exists
        ? relationships.value.map(item => (
            isSameRelationshipTarget(item, response.data) ? response.data : item
          ))
        : [response.data, ...relationships.value]
      await selectRelationship(response.data)
      noticeStore.show(t('ai.relationshipSaved'), 'success')
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.relationshipSaveFailed')), 'error')
    } finally {
      savingRelationship.value = false
    }
  }

  async function loadRelationshipEvents(item: AIRelationshipStateItem) {
    const requestId = ++relationshipEventsRequestId
    loadingRelationshipEvents.value = true
    try {
      const response = await getAIRelationshipEvents({
        limit: 20,
        platform: item.platform,
        user_id: item.user_id,
      })
      if (
        requestId !== relationshipEventsRequestId
        || selectedAffinityId.value !== item.affinity_id
      ) {
        return
      }
      relationshipEvents.value = response.data
    } catch (error) {
      if (
        requestId !== relationshipEventsRequestId
        || selectedAffinityId.value !== item.affinity_id
      ) {
        return
      }
      relationshipEvents.value = []
      noticeStore.show(getErrorMessage(error, t('ai.relationshipEventLoadFailed')), 'error')
    } finally {
      if (requestId === relationshipEventsRequestId) {
        loadingRelationshipEvents.value = false
      }
    }
  }

  return {
    loadRelationshipForTarget,
    loadRelationships,
    loadingRelationshipEvents,
    loadingRelationships,
    loadingSelectedRelationship,
    relationship,
    relationshipEvents,
    relationshipForm,
    relationships,
    saveRelationship,
    savingRelationship,
    selectRelationship,
  }
}

function isSameRelationshipTarget(
  left: AIRelationshipStateItem,
  right: AIRelationshipStateItem,
) {
  return (
    left.platform === right.platform
    && left.user_id === right.user_id
  )
}
