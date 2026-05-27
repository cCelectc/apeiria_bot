import type { AISkillItem } from '@/api/ai'
import { ref } from 'vue'
import {
  getAISkills,
  reloadAISkills,
} from '@/api/ai'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'

export function useAISkillsTab(t: (key: string) => string) {
  const noticeStore = useNoticeStore()

  const skills = ref<AISkillItem[]>([])
  const loadingSkills = ref(false)
  const reloadingSkills = ref(false)

  async function loadSkillsData() {
    loadingSkills.value = true
    try {
      const skillsResponse = await getAISkills()
      skills.value = skillsResponse.data
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.loadFailed')), 'error')
    } finally {
      loadingSkills.value = false
    }
  }

  async function reloadSkillsData() {
    reloadingSkills.value = true
    try {
      const response = await reloadAISkills()
      skills.value = response.data
      await loadSkillsData()
      noticeStore.show(t('ai.skillsReloaded'), 'success')
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.skillsReloadFailed')), 'error')
    } finally {
      reloadingSkills.value = false
    }
  }

  return {
    loadSkillsData,
    loadingSkills,
    reloadSkillsData,
    reloadingSkills,
    skills,
  }
}
