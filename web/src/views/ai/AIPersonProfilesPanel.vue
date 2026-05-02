<template>
  <v-row>
    <v-col cols="12" lg="4">
      <div class="d-flex justify-space-between align-center mb-3">
        <div class="text-subtitle-1 font-weight-medium">
          {{ t('ai.personProfileListTitle') }}
        </div>
        <v-btn
          icon="mdi-refresh"
          :loading="loadingProfiles"
          size="small"
          variant="text"
          @click="loadProfiles"
        />
      </div>
      <v-sheet class="surface-gradient-card pa-2">
        <template v-if="profiles.length > 0">
          <v-list class="bg-transparent" density="comfortable" lines="two">
            <v-list-item
              v-for="item in profiles"
              :key="item.person_id"
              :active="selectedPersonId === item.person_id"
              @click="selectProfile(item)"
            >
              <v-list-item-title>
                {{ item.nickname || item.person_name || item.user_id }}
              </v-list-item-title>
              <v-list-item-subtitle>
                {{ item.platform }} · {{ item.user_id }}
              </v-list-item-subtitle>
              <template #append>
                <v-chip
                  :color="item.is_known ? 'success' : 'default'"
                  size="x-small"
                  variant="tonal"
                >
                  {{ item.is_known ? t('ai.personProfileKnown') : t('ai.personProfileUnknown') }}
                </v-chip>
              </template>
            </v-list-item>
          </v-list>
        </template>
        <div v-else class="pa-4">
          <div class="empty-state-text">{{ t('ai.personProfileEmpty') }}</div>
          <div class="empty-state-hint mt-2">{{ t('ai.personProfileEmptyHint') }}</div>
        </div>
      </v-sheet>
    </v-col>

    <v-col cols="12" lg="8">
      <template v-if="selectedProfile">
        <v-sheet class="surface-gradient-card pa-4">
          <div class="d-flex flex-wrap ga-2 mb-4">
            <v-chip color="primary" size="small" variant="tonal">
              {{ t('ai.personProfilePlatform') }}: {{ selectedProfile.platform }}
            </v-chip>
            <v-chip color="primary" size="small" variant="tonal">
              {{ t('ai.personProfileUserId') }}: {{ selectedProfile.user_id }}
            </v-chip>
            <v-chip v-if="selectedProfile.know_since" color="primary" size="small" variant="tonal">
              {{ t('ai.personProfileKnowSince') }}: {{ selectedProfile.know_since }}
            </v-chip>
            <v-chip color="primary" size="small" variant="tonal">
              {{ t('ai.personProfileLastInteraction') }}: {{ selectedProfile.last_interaction }}
            </v-chip>
          </div>

          <div class="workbench-form-grid workbench-form-grid--single">
            <label class="workbench-field">
              <span class="workbench-field__title">{{ t('ai.personProfileName') }}</span>
              <v-text-field
                v-model.trim="editForm.person_name"
                :aria-label="t('ai.personProfileName')"
                class="workbench-field__control"
                density="comfortable"
                hide-details
              />
            </label>
            <label class="workbench-field">
              <span class="workbench-field__title">{{ t('ai.personProfileNickname') }}</span>
              <v-text-field
                v-model.trim="editForm.nickname"
                :aria-label="t('ai.personProfileNickname')"
                class="workbench-field__control"
                density="comfortable"
                hide-details
              />
            </label>
          </div>

          <div class="mt-4">
            <div class="d-flex justify-space-between align-center mb-3">
              <div class="text-subtitle-2 font-weight-medium">
                {{ t('ai.personProfileMemoryPoints') }} · {{ editForm.memory_points.length }}
              </div>
              <v-btn color="primary" size="small" variant="tonal" @click="addMemoryPoint">
                {{ t('ai.personProfileAddPoint') }}
              </v-btn>
            </div>

            <div v-if="editForm.memory_points.length > 0" class="d-flex flex-column ga-3">
              <v-sheet
                v-for="(point, index) in editForm.memory_points"
                :key="index"
                class="surface-gradient-card pa-3"
              >
                <div class="person-profile-point-row">
                  <label class="workbench-field">
                    <span class="workbench-field__title">{{ t('ai.personProfilePointCategory') }}</span>
                    <v-select
                      v-model="point.category"
                      :aria-label="t('ai.personProfilePointCategory')"
                      class="workbench-field__control"
                      density="comfortable"
                      hide-details
                      :items="personProfilePointCategoryOptions"
                    />
                  </label>
                  <label class="workbench-field">
                    <span class="workbench-field__title">{{ t('ai.personProfilePointContent') }}</span>
                    <v-text-field
                      v-model.trim="point.content"
                      :aria-label="t('ai.personProfilePointContent')"
                      class="workbench-field__control"
                      density="comfortable"
                      hide-details
                    />
                  </label>
                  <label class="workbench-field">
                    <span class="workbench-field__title">{{ t('ai.personProfilePointConfidence') }}</span>
                    <v-text-field
                      v-model.number="point.confidence"
                      :aria-label="t('ai.personProfilePointConfidence')"
                      class="workbench-field__control"
                      density="comfortable"
                      hide-details
                      max="1"
                      min="0"
                      step="0.1"
                      type="number"
                    />
                  </label>
                  <v-btn
                    color="error"
                    icon="mdi-delete-outline"
                    size="small"
                    variant="text"
                    @click="removeMemoryPoint(index)"
                  />
                </div>
              </v-sheet>
            </div>
            <div v-else class="empty-state-hint">
              {{ t('ai.personProfileNoPoints') }}
            </div>
          </div>

          <div class="d-flex justify-end ga-3 mt-4">
            <v-btn
              color="error"
              :loading="deletingProfileId === selectedProfile.person_id"
              variant="text"
              @click="removeProfile(selectedProfile.person_id)"
            >
              {{ t('common.delete') }}
            </v-btn>
            <v-btn
              color="primary"
              :disabled="!canSaveProfile"
              :loading="savingProfile"
              @click="saveProfile"
            >
              {{ t('common.save') }}
            </v-btn>
          </div>
        </v-sheet>
      </template>
      <v-sheet v-else class="surface-gradient-card pa-4">
        <div class="empty-state-text">{{ t('ai.personProfileSelectHint') }}</div>
      </v-sheet>
    </v-col>
  </v-row>
</template>

<script setup lang="ts">
  import type { AIPersonMemoryPointItem, AIPersonProfileItem } from '@/api/ai/types'
  import { useI18n } from 'vue-i18n'

  interface PersonProfileEditFormState {
    person_name: string | null
    nickname: string | null
    memory_points: AIPersonMemoryPointItem[]
  }

  defineProps<{
    addMemoryPoint: () => void
    canSaveProfile: boolean
    deletingProfileId: string
    loadProfiles: () => void | Promise<void>
    loadingProfiles: boolean
    personProfilePointCategoryOptions: Array<{
      title: string
      value: string
    }>
    profiles: AIPersonProfileItem[]
    removeMemoryPoint: (index: number) => void
    removeProfile: (personId: string) => void | Promise<void>
    saveProfile: () => void | Promise<void>
    savingProfile: boolean
    selectProfile: (item: AIPersonProfileItem) => void
    selectedPersonId: string
    selectedProfile: AIPersonProfileItem | null
  }>()

  const editForm = defineModel<PersonProfileEditFormState>('editForm', { required: true })

  const { t } = useI18n()
</script>

<style scoped>
.person-profile-point-row {
  display: grid;
  gap: 12px;
  align-items: end;
  grid-template-columns: minmax(120px, 160px) minmax(0, 1fr) minmax(92px, 120px) auto;
}

@media (max-width: 960px) {
  .person-profile-point-row {
    grid-template-columns: 1fr;
  }
}
</style>
