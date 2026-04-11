import type { AICapabilityItem, AISkillItem } from '@/api'
import { ref } from 'vue'
import { getAICapabilities, getAISkills } from '@/api'

export function useAISkillsTab () {
  const skills = ref<AISkillItem[]>([])
  const capabilities = ref<AICapabilityItem[]>([])

  async function loadSkillsData () {
    const [skillsResponse, capabilitiesResponse] = await Promise.all([
      getAISkills(),
      getAICapabilities(),
    ])
    skills.value = skillsResponse.data
    capabilities.value = capabilitiesResponse.data
  }

  return {
    capabilities,
    loadSkillsData,
    skills,
  }
}
