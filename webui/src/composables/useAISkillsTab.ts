import type { AISkillItem } from '@/api/ai'
import { ref } from 'vue'
import { getAISkills } from '@/api/ai'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'

export function useAISkillsTab(t: (key: string) => string) {
  const noticeStore = useNoticeStore()

  const skills = ref<AISkillItem[]>([])
  const loadingSkills = ref(false)

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

  return {
    loadSkillsData,
    loadingSkills,
    skills,
  }
}
