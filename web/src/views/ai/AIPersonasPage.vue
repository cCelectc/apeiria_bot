<template>
  <PageScaffold
    :error-message="errorMessage"
    :subtitle="t('ai.pageSubtitle.personas')"
    :title="t('ai.personasTab')"
  >
    <template #actions>
      <v-btn :loading="loading" variant="tonal" @click="loadData">
        {{ t('common.refresh') }}
      </v-btn>
    </template>

    <v-card class="page-panel">
      <v-card-text>
        <AIPersonasPanel
          v-model:persona-form="personaForm"
          :can-save-persona="canSavePersona"
          :displayed-persona-errors="displayedPersonaErrors"
          :is-creating-persona="isCreatingPersona"
          :persona-bindings="personaBindings"
          :personas="personas"
          :save-persona="savePersona"
          :saving-persona="savingPersona"
          :select-persona="selectPersona"
          :start-create-persona="startCreatePersona"
          :touch-persona-field="touchPersonaField"
        />
      </v-card-text>
    </v-card>
  </PageScaffold>
</template>

<script setup lang="ts">
  import { onMounted } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { PageScaffold } from '@/components/workbench'
  import { useAIPersonasTab } from '@/composables/useAIPersonasTab'
  import AIPersonasPanel from '@/views/ai/AIPersonasPanel.vue'
  import { useAIPageLoader } from '@/views/ai/pageHelpers'

  const { t } = useI18n()
  const { errorMessage, loading, runPageLoad } = useAIPageLoader(() => t('ai.loadFailed'))

  const {
    canSavePersona,
    displayedPersonaErrors,
    isCreatingPersona,
    loadPersonasData,
    personaBindings,
    personaForm,
    personas,
    savePersona,
    savingPersona,
    selectPersona,
    startCreatePersona,
    touchPersonaField,
  } = useAIPersonasTab(t)

  async function loadData () {
    await runPageLoad(loadPersonasData)
  }

  onMounted(() => {
    void loadData()
  })
</script>
