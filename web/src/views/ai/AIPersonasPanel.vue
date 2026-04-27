<template>
  <v-row>
    <v-col cols="12" lg="4">
      <div class="d-flex justify-end mb-3">
        <v-btn color="primary" variant="tonal" @click="startCreatePersona">
          {{ t('ai.createPersona') }}
        </v-btn>
      </div>
      <v-sheet class="surface-gradient-card pa-2" rounded="lg">
        <template v-if="personas.length > 0">
          <v-list class="bg-transparent" density="comfortable" lines="two">
            <v-list-item
              v-for="item in personas"
              :key="item.persona_id"
              :active="item.persona_id === personaForm.persona_id"
              rounded="lg"
              @click="selectPersona(item)"
            >
              <v-list-item-title>{{ item.name }}</v-list-item-title>
              <v-list-item-subtitle>{{ item.description || t('common.none') }}</v-list-item-subtitle>
              <template #append>
                <v-chip :color="item.enabled ? 'success' : 'default'" size="small" variant="tonal">
                  {{ item.enabled ? t('ai.enabled') : t('ai.disabled') }}
                </v-chip>
              </template>
            </v-list-item>
          </v-list>
        </template>
        <div v-else class="pa-4">
          <div class="empty-state-text">{{ t('ai.noPersonas') }}</div>
          <div class="empty-state-hint mt-2">{{ t('ai.noPersonasHint') }}</div>
        </div>
      </v-sheet>
    </v-col>

    <v-col cols="12" lg="8">
      <v-sheet class="surface-gradient-card pa-4" rounded="lg">
        <div class="d-flex flex-wrap ga-2 mb-4">
          <v-chip color="primary" size="small" variant="tonal">
            {{ isCreatingPersona ? t('ai.creatingPersona') : t('ai.editingPersona') }}
          </v-chip>
          <v-chip color="primary" size="small" variant="tonal">
            {{ t('ai.scopeBindings') }}: {{ selectedPersonaBindingCount }}
          </v-chip>
        </div>

        <v-text-field
          v-model.trim="personaForm.name"
          density="comfortable"
          :disabled="savingPersona"
          :error-messages="displayedPersonaErrors.name ? [displayedPersonaErrors.name] : []"
          :label="t('ai.personaName')"
          @blur="touchPersonaField('name')"
        />
        <v-text-field
          v-model.trim="personaForm.description"
          class="mt-3"
          density="comfortable"
          :disabled="savingPersona"
          :error-messages="displayedPersonaErrors.description ? [displayedPersonaErrors.description] : []"
          :label="t('ai.personaDescription')"
          @blur="touchPersonaField('description')"
        />
        <v-textarea
          v-model.trim="personaForm.system_prompt"
          auto-grow
          class="mt-3"
          density="comfortable"
          :disabled="savingPersona"
          :error-messages="displayedPersonaErrors.system_prompt ? [displayedPersonaErrors.system_prompt] : []"
          :label="t('ai.personaSystemPrompt')"
          rows="5"
          @blur="touchPersonaField('system_prompt')"
        />
        <div class="mt-2 text-caption text-medium-emphasis">
          {{ t('ai.personaTemplateVariablesHint') }}
        </div>
        <v-textarea
          v-model.trim="personaForm.style_prompt"
          auto-grow
          class="mt-3"
          density="comfortable"
          :disabled="savingPersona"
          hide-details
          :label="t('ai.personaStylePrompt')"
          rows="4"
        />
        <div class="mt-2 text-caption text-medium-emphasis">
          {{ t('ai.personaTemplateVariablesHint') }}
        </div>
        <v-switch
          v-model="personaForm.enabled"
          class="mt-3"
          color="primary"
          density="comfortable"
          :disabled="savingPersona"
          hide-details
          :label="t('ai.personaEnabled')"
        />
        <div class="d-flex justify-end mt-4">
          <v-btn color="primary" :disabled="!canSavePersona" :loading="savingPersona" @click="savePersona">
            {{ t('common.save') }}
          </v-btn>
        </div>
      </v-sheet>
    </v-col>
  </v-row>
</template>

<script setup lang="ts">
  import type { AIPersonaBindingItem, AIPersonaItem } from '@/api/ai/types'
  import { computed } from 'vue'
  import { useI18n } from 'vue-i18n'

  interface PersonaFormState {
    persona_id: string
    name: string
    description: string
    system_prompt: string
    style_prompt: string
    enabled: boolean
  }

  const props = defineProps<{
    canSavePersona: boolean
    displayedPersonaErrors: {
      name: string
      description: string
      system_prompt: string
    }
    isCreatingPersona: boolean
    personaBindings: AIPersonaBindingItem[]
    personas: AIPersonaItem[]
    savePersona: () => void | Promise<void>
    savingPersona: boolean
    selectPersona: (item: AIPersonaItem) => void | Promise<void>
    startCreatePersona: () => void
    touchPersonaField: (
      field: 'name' | 'description' | 'system_prompt',
    ) => void
  }>()

  const personaForm = defineModel<PersonaFormState>('personaForm', { required: true })

  const { t } = useI18n()

  const selectedPersonaBindingCount = computed(() => props.personaBindings
    .filter(item => item.persona_id === personaForm.value.persona_id)
    .length)
</script>
