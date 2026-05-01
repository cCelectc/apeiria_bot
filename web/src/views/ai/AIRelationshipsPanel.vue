<template>
  <v-row>
    <v-col cols="12" lg="4">
      <v-sheet class="surface-gradient-card pa-2">
        <div class="d-flex align-center justify-space-between px-2 py-2">
          <div class="text-body-2 text-medium-emphasis">{{ t('ai.recentTargets') }}</div>
          <v-btn
            icon="mdi-refresh"
            :loading="loadingRecentTargets || loadingSelectedRelationship"
            size="small"
            variant="text"
            @click="loadRecentTargets"
          />
        </div>
        <template v-if="recentRelationshipTargets.length > 0">
          <v-list class="bg-transparent" density="comfortable" lines="two">
            <v-list-item
              v-for="item in recentRelationshipTargets"
              :key="`${item.anchor_type}:${item.anchor_id}`"
              @click="loadRelationshipForTarget(item)"
            >
              <v-list-item-title>{{ item.title }}</v-list-item-title>
              <v-list-item-subtitle>{{ item.subtitle || item.anchor_id }}</v-list-item-subtitle>
            </v-list-item>
          </v-list>
        </template>
        <div v-else class="pa-4">
          <div class="empty-state-text">{{ t('ai.noRecentTargets') }}</div>
          <div class="empty-state-hint mt-2">{{ t('ai.noRecentTargetsHint') }}</div>
        </div>
      </v-sheet>
    </v-col>

    <v-col cols="12" lg="8">
      <v-sheet class="surface-gradient-card pa-4">
        <div v-if="relationship" class="d-flex flex-column ga-4">
          <div class="d-flex flex-wrap ga-2">
            <v-chip color="primary" size="small" variant="tonal">
              {{ t('ai.relationshipTarget') }}: {{ relationshipSelectionLabel }}
            </v-chip>
            <v-chip color="primary" size="small" variant="tonal">
              {{ t('ai.relationshipPlatform') }}: {{ relationship.platform }}
            </v-chip>
            <v-chip color="primary" size="small" variant="tonal">
              {{ t('ai.relationshipGroupId') }}: {{ relationship.group_id || t('common.none') }}
            </v-chip>
          </div>

          <div class="relationship-meta-grid text-body-2">
            <div>
              <span class="text-medium-emphasis">{{ t('ai.relationshipScore') }}</span>
              <div class="mt-1">{{ relationship.effective_score.toFixed(1) }}</div>
            </div>
            <div>
              <span class="text-medium-emphasis">{{ t('ai.relationshipProjectedTone') }}</span>
              <div class="mt-1">{{ relationship.effective_projected_tone || t('common.none') }}</div>
            </div>
            <div>
              <span class="text-medium-emphasis">{{ t('ai.relationshipMoodTags') }}</span>
              <div class="mt-1">{{ relationshipMoodText }}</div>
            </div>
            <div>
              <span class="text-medium-emphasis">{{ t('ai.relationshipLastEventAt') }}</span>
              <div class="mt-1">{{ relationship.last_event_at || t('common.none') }}</div>
            </div>
            <div>
              <span class="text-medium-emphasis">{{ t('ai.relationshipLastDecayAt') }}</span>
              <div class="mt-1">{{ relationship.last_decay_at || t('common.none') }}</div>
            </div>
            <div>
              <span class="text-medium-emphasis">{{ t('ai.relationshipWarmthBias') }}</span>
              <div class="mt-1">{{ formatSignedRelationshipValue(relationship.effective_warmth_bias) }}</div>
            </div>
            <div>
              <span class="text-medium-emphasis">{{ t('ai.relationshipInitiativeBias') }}</span>
              <div class="mt-1">{{ formatSignedRelationshipValue(relationship.effective_initiative_bias) }}</div>
            </div>
          </div>

          <div>
            <div class="text-body-2 text-medium-emphasis mb-2">{{ t('ai.relationshipStyleModulation') }}</div>
            <div v-if="relationship.effective_style_modulation.length > 0" class="d-flex flex-wrap ga-2">
              <v-chip
                v-for="line in relationship.effective_style_modulation"
                :key="`${relationship.affinity_id}-${line}`"
                color="primary"
                size="small"
                variant="tonal"
              >
                {{ line }}
              </v-chip>
            </div>
            <div v-else class="empty-state-hint">
              {{ t('common.none') }}
            </div>
          </div>

          <div>
            <div class="text-body-2 text-medium-emphasis mb-2">{{ t('ai.relationshipScore') }}</div>
            <v-slider
              v-model="relationshipForm.score"
              color="primary"
              hide-details
              max="1"
              min="-1"
              step="0.1"
              thumb-label
            />
          </div>

          <div class="d-flex justify-end">
            <v-btn color="primary" :loading="savingRelationship" @click="saveRelationship">
              {{ t('ai.saveRelationship') }}
            </v-btn>
          </div>

          <div>
            <div class="d-flex align-center justify-space-between mb-2">
              <div class="text-body-2 text-medium-emphasis">{{ t('ai.relationshipEvents') }}</div>
              <v-btn
                icon="mdi-refresh"
                :loading="loadingRelationshipEvents"
                size="small"
                variant="text"
                @click="selectRelationship(relationship)"
              />
            </div>
            <v-list
              v-if="relationshipEvents.length > 0"
              class="bg-transparent relation-event-list"
              density="comfortable"
              lines="three"
            >
              <v-list-item
                v-for="event in relationshipEvents"
                :key="event.event_id"
              >
                <v-list-item-title class="d-flex flex-wrap ga-2 align-center">
                  <span>{{ formatRelationshipEventType(event.event_type) }}</span>
                  <v-chip color="primary" size="x-small" variant="tonal">
                    {{ formatSignedRelationshipValue(event.score_delta) }}
                  </v-chip>
                  <v-chip color="default" size="x-small" variant="tonal">
                    {{ t('ai.relationshipScoreAfter') }}: {{ event.score_after.toFixed(2) }}
                  </v-chip>
                </v-list-item-title>
                <v-list-item-subtitle class="mt-1">
                  {{ event.reason || t('common.none') }}
                </v-list-item-subtitle>
                <template #append>
                  <div class="text-caption text-medium-emphasis text-right">
                    <div>{{ event.created_at }}</div>
                    <div>{{ event.mood_tag || t('common.none') }}</div>
                  </div>
                </template>
              </v-list-item>
            </v-list>
            <div v-else class="empty-state-hint">
              {{ loadingRelationshipEvents ? t('common.loading') : t('ai.noRelationshipEvents') }}
            </div>
          </div>
        </div>
        <div v-else>
          <div class="empty-state-text mb-3">
            {{ t('ai.selectRelationshipTarget') }}
          </div>
          <div class="d-flex flex-wrap ga-3">
            <v-btn color="primary" variant="tonal" @click="openDebugConversations">
              {{ t('ai.goToDebug') }}
            </v-btn>
            <v-btn variant="text" @click="openChatView">
              {{ t('ai.goToChatView') }}
            </v-btn>
          </div>
        </div>
      </v-sheet>
    </v-col>
  </v-row>
</template>

<script setup lang="ts">
  import type {
    AIRecentTargetItem,
    AIRelationshipEventItem,
    AIRelationshipStateItem,
  } from '@/api/ai/types'
  import { computed } from 'vue'
  import { useI18n } from 'vue-i18n'

  interface RelationshipFormState {
    limit: number
    score: number
  }

  const props = defineProps<{
    loadRecentTargets: () => void | Promise<void>
    loadRelationshipForTarget: (target: AIRecentTargetItem) => void | Promise<void>
    loadingRecentTargets: boolean
    loadingRelationshipEvents: boolean
    loadingSelectedRelationship: boolean
    openChatView: () => void | Promise<void>
    openDebugConversations: () => void
    recentTargets: AIRecentTargetItem[]
    relationship: AIRelationshipStateItem | null
    relationshipEvents: AIRelationshipEventItem[]
    saveRelationship: () => void | Promise<void>
    savingRelationship: boolean
    selectRelationship: (item: AIRelationshipStateItem) => void | Promise<void>
  }>()

  const relationshipForm = defineModel<RelationshipFormState>('relationshipForm', { required: true })

  const { t } = useI18n()

  const recentRelationshipTargets = computed(() => (
    props.recentTargets.filter(item => (
      (item.anchor_type === 'user' || item.anchor_type === 'participant')
      && !!item.platform
      && !!item.user_id
    ))
  ))

  const relationshipSelectionLabel = computed(() => {
    if (!props.relationship) {
      return t('ai.selectRelationshipTarget')
    }
    return props.relationship.user_id
  })

  const relationshipMoodText = computed(() => {
    const tags = props.relationship?.effective_mood_tags ?? []
    if (tags.length === 0) {
      return t('common.none')
    }
    return tags.join('、')
  })

  function formatSignedRelationshipValue (value: number) {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}`
  }

  function formatRelationshipEventType (value: string) {
    if (value === 'message') {
      return t('ai.relationshipEventMessage')
    }
    if (value === 'manual') {
      return t('ai.relationshipEventManual')
    }
    if (value === 'absence_decay') {
      return t('ai.relationshipEventDecay')
    }
    return value
  }
</script>
