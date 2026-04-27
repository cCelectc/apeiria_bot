<template>
  <div class="d-flex flex-column ga-4">
    <div class="d-flex flex-wrap ga-2">
      <v-chip color="primary" size="small" variant="tonal">
        {{ t('ai.skills') }}: {{ skills.length }}
      </v-chip>
      <v-chip color="primary" size="small" variant="tonal">
        {{ t('ai.capabilities') }}: {{ capabilities.length }}
      </v-chip>
      <v-chip color="primary" size="small" variant="tonal">
        {{ t('ai.skillReadOnly') }}: {{ readonlySkillCount }}
      </v-chip>
    </div>

    <div v-if="skills.length > 0" class="skill-card-grid">
      <v-sheet
        v-for="item in skills"
        :key="item.name"
        class="surface-gradient-card pa-4"
        rounded="lg"
      >
        <div class="d-flex flex-wrap justify-space-between ga-3">
          <div>
            <div class="text-subtitle-1 font-weight-medium">{{ item.display_name || item.name }}</div>
            <div class="text-body-2 text-medium-emphasis mt-1">
              {{ item.display_description || item.description || t('common.none') }}
            </div>
          </div>
          <v-chip color="primary" size="small" variant="tonal">
            {{ item.risk_label || item.risk_level }}
          </v-chip>
        </div>

        <div class="d-flex flex-wrap ga-2 mt-3">
          <v-chip :color="item.read_only ? 'success' : 'default'" size="small" variant="tonal">
            {{ t('ai.skillReadOnly') }}: {{ item.read_only ? t('ai.enabled') : t('ai.disabled') }}
          </v-chip>
          <v-chip :color="item.concurrency_safe ? 'success' : 'default'" size="small" variant="tonal">
            {{ t('ai.skillConcurrencySafe') }}: {{ item.concurrency_safe ? t('ai.enabled') : t('ai.disabled') }}
          </v-chip>
          <v-chip :color="item.is_capability_bridge ? 'success' : 'default'" size="small" variant="tonal">
            {{ t('ai.skillCapabilityBridge') }}: {{ item.is_capability_bridge ? t('ai.enabled') : t('ai.disabled') }}
          </v-chip>
        </div>

        <div class="mt-4">
          <div class="text-body-2 text-medium-emphasis mb-2">{{ t('ai.linkedCapabilities') }}</div>
          <div v-if="skillCapabilitiesFor(item.name).length > 0" class="d-flex flex-wrap ga-2">
            <v-chip
              v-for="capability in skillCapabilitiesFor(item.name)"
              :key="`${item.name}-${capability}`"
              color="primary"
              size="small"
              variant="tonal"
            >
              {{ capability }}
            </v-chip>
          </div>
          <div v-else class="empty-state-text">
            {{ t('ai.noCapabilities') }}
          </div>
        </div>
      </v-sheet>
    </div>

    <v-sheet v-else class="surface-gradient-card pa-4" rounded="lg">
      <div class="empty-state-text">{{ t('ai.noSkills') }}</div>
    </v-sheet>
  </div>
</template>

<script setup lang="ts">
  import type { AICapabilityItem, AISkillItem } from '@/api/ai'
  import { computed } from 'vue'
  import { useI18n } from 'vue-i18n'

  const props = defineProps<{
    capabilities: AICapabilityItem[]
    skills: AISkillItem[]
  }>()

  const { t } = useI18n()

  const readonlySkillCount = computed(() => props.skills.filter(item => item.read_only).length)

  const skillCapabilitiesByTool = computed(() => {
    const map = new Map<string, string[]>()
    for (const item of props.capabilities) {
      const list = map.get(item.bound_tool_name) ?? []
      list.push(item.capability_name)
      map.set(item.bound_tool_name, list)
    }
    return map
  })

  function skillCapabilitiesFor (toolName: string) {
    return skillCapabilitiesByTool.value.get(toolName) ?? []
  }
</script>
