<script setup lang="ts">
import { ContactRound, Plus, RefreshCw, Save, Trash2 } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { getErrorMessage } from '@/api/client'
import {
  EmptyState,
  FormField,
  LoadingSkeleton,
  MetricStrip,
  PageScaffold,
  Panel,
  SelectableList,
  SelectableListItem,
  SplitPane,
  StatusBadge,
} from '@/components/management'
import type { WorkbenchMetricItem } from '@/components/management'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { useAIPersonProfilesTab } from '@/composables/useAIPersonProfilesTab'

const { t } = useI18n()
const errorMessage = ref('')
const search = ref('')
const {
  addMemoryPoint,
  canSaveProfile,
  deletingProfileId,
  editForm,
  loadProfiles,
  loadingProfiles,
  profiles,
  removeMemoryPoint,
  removeProfile,
  saveProfile,
  savingProfile,
  selectProfile,
  selectedPersonId,
  selectedProfile,
} = useAIPersonProfilesTab(t)

const categoryOptions = computed(() => [
  { label: t('ai.personProfileCategoryFact'), value: 'fact' },
  { label: t('ai.personProfileCategoryPreference'), value: 'preference' },
  { label: t('ai.personProfileCategoryRelationship'), value: 'relationship' },
  { label: t('ai.personProfileCategoryImpression'), value: 'impression' },
])
const filteredProfiles = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  if (!keyword) {
    return profiles.value
  }
  return profiles.value.filter(item => (
    `${item.platform} ${item.user_id} ${item.person_name ?? ''} ${item.nickname ?? ''}`
      .toLowerCase()
      .includes(keyword)
  ))
})
const personNameModel = computed({
  get: () => editForm.person_name ?? '',
  set: value => {
    editForm.person_name = value.trim() || null
  },
})
const nicknameModel = computed({
  get: () => editForm.nickname ?? '',
  set: value => {
    editForm.nickname = value.trim() || null
  },
})
const metrics = computed<WorkbenchMetricItem[]>(() => [
  {
    icon: ContactRound,
    key: 'profiles',
    label: t('ai.personProfileTab'),
    value: profiles.value.length,
  },
  {
    key: 'known',
    label: t('ai.personProfileKnown'),
    tone: 'success',
    value: profiles.value.filter(item => item.is_known).length,
  },
  {
    key: 'points',
    label: t('ai.personProfileMemoryPoints'),
    tone: 'info',
    value: profiles.value.reduce((count, item) => count + item.memory_points.length, 0),
  },
])

async function loadData() {
  errorMessage.value = ''
  try {
    await loadProfiles()
  } catch (error) {
    errorMessage.value = getErrorMessage(error, t('ai.personProfileLoadFailed'))
  }
}

function profileDisplayName(profile: NonNullable<typeof selectedProfile.value>) {
  return profile.nickname || profile.person_name || profile.user_id
}

onMounted(() => {
  void loadData()
})
</script>

<template>
  <PageScaffold
    :error-message="errorMessage"
    :subtitle="t('ai.pageSubtitle.profiles')"
    :title="t('ai.personProfileTab')"
  >
    <template #actions>
      <Button :disabled="loadingProfiles" variant="secondary" @click="loadData">
        <RefreshCw :class="{ 'animate-spin': loadingProfiles }" :size="16" />
        {{ t('common.refresh') }}
      </Button>
    </template>

    <MetricStrip :items="metrics" compact />

    <SplitPane wide-sidebar>
      <template #sidebar>
        <Panel :title="t('ai.personProfileListTitle')">
          <div class="ai-data-toolbar">
            <Input v-model="search" :placeholder="t('common.search')" />
          </div>

          <LoadingSkeleton v-if="loadingProfiles && profiles.length === 0" :rows="5" />
          <EmptyState
            v-else-if="filteredProfiles.length === 0"
            :icon="ContactRound"
            :text="t('ai.personProfileEmptyHint')"
            :title="t('ai.personProfileEmpty')"
          />
          <SelectableList v-else>
            <SelectableListItem
              v-for="item in filteredProfiles"
              :key="item.person_id"
              :active="selectedPersonId === item.person_id"
              @click="selectProfile(item)"
            >
              <div class="ai-data-list-item">
                <div class="ai-data-list-item__main">
                  <strong>{{ item.nickname || item.person_name || item.user_id }}</strong>
                  <span>{{ item.platform }} / {{ item.user_id }}</span>
                </div>
                <StatusBadge
                  :label="item.is_known ? t('ai.personProfileKnown') : t('ai.personProfileUnknown')"
                  :tone="item.is_known ? 'success' : 'default'"
                />
              </div>
            </SelectableListItem>
          </SelectableList>
        </Panel>
      </template>

      <Panel v-if="selectedProfile" :title="profileDisplayName(selectedProfile)">
        <div class="ai-data-form">
          <div class="ai-data-form__meta">
            <Badge variant="secondary">
              {{ t('ai.personProfilePlatform') }}: {{ selectedProfile.platform }}
            </Badge>
            <Badge variant="secondary">
              {{ t('ai.personProfileUserId') }}: {{ selectedProfile.user_id }}
            </Badge>
            <Badge v-if="selectedProfile.know_since" variant="outline">
              {{ t('ai.personProfileKnowSince') }}: {{ selectedProfile.know_since }}
            </Badge>
            <Badge variant="outline">
              {{ t('ai.personProfileLastInteraction') }}: {{ selectedProfile.last_interaction }}
            </Badge>
          </div>

          <div class="ai-data-grid-2">
            <FormField :label="t('ai.personProfileName')">
              <Input v-model="personNameModel" />
            </FormField>
            <FormField :label="t('ai.personProfileNickname')">
              <Input v-model="nicknameModel" />
            </FormField>
          </div>

          <div class="ai-section-header">
            <div>
              <h2>{{ t('ai.personProfileMemoryPoints') }}</h2>
              <p>{{ editForm.memory_points.length }} {{ t('common.itemsPerPage') }}</p>
            </div>
            <Button size="sm" variant="secondary" @click="addMemoryPoint">
              <Plus :size="15" />
              {{ t('ai.personProfileAddPoint') }}
            </Button>
          </div>

          <div v-if="editForm.memory_points.length > 0" class="ai-memory-point-list">
            <div
              v-for="(point, index) in editForm.memory_points"
              :key="`${index}-${point.category}`"
              class="ai-memory-point-row"
            >
              <FormField :label="t('ai.personProfilePointCategory')">
                <Select v-model="point.category">
                  <SelectTrigger>
                    <SelectValue :placeholder="t('ai.personProfilePointCategory')" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem
                      v-for="option in categoryOptions"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </FormField>
              <FormField :label="t('ai.personProfilePointContent')">
                <Textarea v-model="point.content" class="min-h-20" />
              </FormField>
              <FormField :label="t('ai.personProfilePointConfidence')">
                <Input v-model="point.confidence" max="1" min="0" step="0.1" type="number" />
              </FormField>
              <Button
                :title="t('common.delete')"
                size="icon"
                variant="ghost"
                @click="removeMemoryPoint(index)"
              >
                <Trash2 :size="16" />
              </Button>
            </div>
          </div>
          <EmptyState
            v-else
            :icon="ContactRound"
            :title="t('ai.personProfileNoPoints')"
          />

          <div class="ai-data-actions">
            <Button
              :disabled="deletingProfileId === selectedProfile.person_id"
              variant="destructive"
              @click="removeProfile(selectedProfile.person_id)"
            >
              <RefreshCw
                v-if="deletingProfileId === selectedProfile.person_id"
                class="animate-spin"
                :size="16"
              />
              <Trash2 v-else :size="16" />
              {{ t('common.delete') }}
            </Button>
            <Button :disabled="!canSaveProfile" @click="saveProfile">
              <RefreshCw v-if="savingProfile" class="animate-spin" :size="16" />
              <Save v-else :size="16" />
              {{ t('common.save') }}
            </Button>
          </div>
        </div>
      </Panel>
      <Panel v-else>
        <EmptyState
          :icon="ContactRound"
          :text="t('ai.personProfileEmptyHint')"
          :title="t('ai.personProfileSelectHint')"
        />
      </Panel>
    </SplitPane>
  </PageScaffold>
</template>
