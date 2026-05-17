<script setup lang="ts">
import { ContactRound, RefreshCw, Save, Trash2 } from 'lucide-vue-next'
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
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useAIProfilesTab } from '@/composables/useAIProfilesTab'

const { t } = useI18n()
const errorMessage = ref('')
const search = ref('')
const {
  canSaveProfile,
  deletingProfileId,
  editForm,
  loadProfiles,
  loadingProfiles,
  profiles,
  removeProfile,
  saveProfile,
  savingProfile,
  selectProfile,
  selectedProfile,
  selectedProfileId,
} = useAIProfilesTab(t)

const visibilityOptions = computed(() => [
  { label: t('ai.profileVisibilityPublic'), value: 'public_allowed' },
  { label: t('ai.profileVisibilityPrivate'), value: 'private_only' },
  { label: t('ai.profileVisibilityDisabled'), value: 'disabled' },
])
const filteredProfiles = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  if (!keyword) {
    return profiles.value
  }
  return profiles.value.filter(item => (
    `${item.platform} ${item.user_id} ${item.display_name ?? ''} ${item.preferred_name ?? ''}`
      .toLowerCase()
      .includes(keyword)
  ))
})
const displayNameModel = computed({
  get: () => editForm.display_name ?? '',
  set: value => {
    editForm.display_name = value.trim() || null
  },
})
const preferredNameModel = computed({
  get: () => editForm.preferred_name ?? '',
  set: value => {
    editForm.preferred_name = value.trim() || null
  },
})
const metrics = computed<WorkbenchMetricItem[]>(() => [
  {
    icon: ContactRound,
    key: 'profiles',
    label: t('ai.profileTab'),
    value: profiles.value.length,
  },
  {
    key: 'enabled',
    label: t('ai.profileEnabled'),
    tone: 'success',
    value: profiles.value.filter(item => item.profile_enabled).length,
  },
  {
    key: 'private_names',
    label: t('ai.profileVisibilityPrivate'),
    tone: 'info',
    value: profiles.value.filter(item => item.name_visibility === 'private_only').length,
  },
])

async function loadData() {
  errorMessage.value = ''
  try {
    await loadProfiles()
  } catch (error) {
    errorMessage.value = getErrorMessage(error, t('ai.profileLoadFailed'))
  }
}

function profileDisplayName(profile: NonNullable<typeof selectedProfile.value>) {
  return profile.preferred_name || profile.display_name || profile.user_id
}

onMounted(() => {
  void loadData()
})
</script>

<template>
  <PageScaffold
    :error-message="errorMessage"
    :subtitle="t('ai.pageSubtitle.profiles')"
    :title="t('ai.profileTab')"
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
        <Panel :title="t('ai.profileListTitle')">
          <div class="ai-data-toolbar">
            <Input v-model="search" :placeholder="t('common.search')" />
          </div>

          <LoadingSkeleton v-if="loadingProfiles && profiles.length === 0" :rows="5" />
          <EmptyState
            v-else-if="filteredProfiles.length === 0"
            :icon="ContactRound"
            :text="t('ai.profileEmptyHint')"
            :title="t('ai.profileEmpty')"
          />
          <SelectableList v-else>
            <SelectableListItem
              v-for="item in filteredProfiles"
              :key="item.profile_id"
              :active="selectedProfileId === item.profile_id"
              @click="selectProfile(item)"
            >
              <div class="ai-data-list-item">
                <div class="ai-data-list-item__main">
                  <strong>{{ item.preferred_name || item.display_name || item.user_id }}</strong>
                  <span>{{ item.platform }} / {{ item.user_id }}</span>
                </div>
                <StatusBadge
                  :label="item.profile_enabled ? t('ai.profileEnabled') : t('ai.profileDisabled')"
                  :tone="item.profile_enabled ? 'success' : 'default'"
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
              {{ t('ai.profilePlatform') }}: {{ selectedProfile.platform }}
            </Badge>
            <Badge variant="secondary">
              {{ t('ai.profileUserId') }}: {{ selectedProfile.user_id }}
            </Badge>
            <Badge variant="outline">
              {{ t('ai.profileLastInteraction') }}: {{ selectedProfile.last_interaction_at }}
            </Badge>
            <Badge variant="outline">
              {{ t('ai.profileNameSource') }}: {{ selectedProfile.name_source || t('common.none') }}
            </Badge>
          </div>

          <div class="ai-data-grid-2">
            <FormField :label="t('ai.profileDisplayName')">
              <Input v-model="displayNameModel" />
            </FormField>
            <FormField :label="t('ai.profilePreferredName')">
              <Input v-model="preferredNameModel" />
            </FormField>
          </div>

          <div class="ai-data-grid-2">
            <FormField :label="t('ai.profileNameVisibility')">
              <Select v-model="editForm.name_visibility">
                <SelectTrigger>
                  <SelectValue :placeholder="t('ai.profileNameVisibility')" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem
                      v-for="option in visibilityOptions"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </FormField>
            <FormField :label="t('ai.profileEnabled')">
              <label class="ai-checkbox-row">
                <Checkbox v-model:checked="editForm.profile_enabled" />
                <span>{{ t('ai.profileEnabled') }}</span>
              </label>
            </FormField>
          </div>

          <div class="ai-data-actions">
            <Button
              :disabled="deletingProfileId === selectedProfile.profile_id"
              variant="destructive"
              @click="removeProfile(selectedProfile.profile_id)"
            >
              <RefreshCw
                v-if="deletingProfileId === selectedProfile.profile_id"
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
          :text="t('ai.profileEmptyHint')"
          :title="t('ai.profileSelectHint')"
        />
      </Panel>
    </SplitPane>
  </PageScaffold>
</template>
