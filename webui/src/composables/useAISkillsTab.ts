import type { AICapabilityItem, AISkillItem } from '@/api/ai'
import { ref } from 'vue'
import { getAICapabilities, getAISkills } from '@/api/ai'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'

export function useAISkillsTab(t: (key: string) => string) {
  const noticeStore = useNoticeStore()

  const skills = ref<AISkillItem[]>([])
  const capabilities = ref<AICapabilityItem[]>([])
  const loadingSkills = ref(false)

  async function loadSkillsData() {
    loadingSkills.value = true
    try {
      const [skillsResponse, capabilitiesResponse] = await Promise.all([
        getAISkills(),
        getAICapabilities(),
      ])
      skills.value = skillsResponse.data
      capabilities.value = capabilitiesResponse.data
    } catch (error) {
      noticeStore.show(getErrorMessage(error, t('ai.loadFailed')), 'error')
    } finally {
      loadingSkills.value = false
    }
  }

  return {
    capabilities,
    loadSkillsData,
    loadingSkills,
    skills,
  }
}
