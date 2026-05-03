<template>
  <PageScaffold
    :error-message="errorMessage"
    :subtitle="t('ai.pageSubtitle.profiles')"
    :title="t('ai.personProfileTab')"
  >
    <template #actions>
      <v-btn :loading="loading" variant="tonal" @click="loadData">
        {{ t('common.refresh') }}
      </v-btn>
    </template>

    <v-card class="page-panel">
      <v-card-text>
        <AIPersonProfilesPanel
          v-model:edit-form="personProfileEditForm"
          :add-memory-point="addPersonMemoryPoint"
          :can-save-profile="canSavePersonProfile"
          :deleting-profile-id="deletingPersonProfileId"
          :load-profiles="loadPersonProfiles"
          :loading-profiles="loadingPersonProfiles"
          :person-profile-point-category-options="personProfilePointCategoryOptions"
          :profiles="personProfiles"
          :remove-memory-point="removePersonMemoryPoint"
          :remove-profile="removePersonProfile"
          :save-profile="savePersonProfile"
          :saving-profile="savingPersonProfile"
          :select-profile="selectPersonProfile"
          :selected-person-id="selectedPersonId"
          :selected-profile="selectedPersonProfile"
        />
      </v-card-text>
    </v-card>
  </PageScaffold>
</template>

<script setup lang="ts">
  import { onMounted } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { PageScaffold } from '@/components/workbench'
  import { useAIPersonProfilesTab } from '@/composables/useAIPersonProfilesTab'
  import AIPersonProfilesPanel from '@/views/ai/AIPersonProfilesPanel.vue'
  import {
    useAIPageLoader,
    usePersonProfilePointCategoryOptions,
  } from '@/views/ai/pageHelpers'

  const { t } = useI18n()
  const { errorMessage, loading, runPageLoad } = useAIPageLoader(() => t('ai.loadFailed'))
  const { personProfilePointCategoryOptions } = usePersonProfilePointCategoryOptions(t)

  const {
    addMemoryPoint: addPersonMemoryPoint,
    canSaveProfile: canSavePersonProfile,
    deletingProfileId: deletingPersonProfileId,
    editForm: personProfileEditForm,
    loadProfiles: loadPersonProfiles,
    loadingProfiles: loadingPersonProfiles,
    profiles: personProfiles,
    removeMemoryPoint: removePersonMemoryPoint,
    removeProfile: removePersonProfile,
    saveProfile: savePersonProfile,
    savingProfile: savingPersonProfile,
    selectProfile: selectPersonProfile,
    selectedPersonId,
    selectedProfile: selectedPersonProfile,
  } = useAIPersonProfilesTab(t)

  async function loadData () {
    await runPageLoad(loadPersonProfiles)
  }

  onMounted(() => {
    void loadData()
  })
</script>
