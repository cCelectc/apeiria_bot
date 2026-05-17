<script setup lang="ts">
import {
  MessageSquare,
  Network,
  RefreshCw,
  Save,
} from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
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
import { useAIMemoryTab } from '@/composables/useAIMemoryTab'
import { useAIRelationshipTab } from '@/composables/useAIRelationshipTab'

const { t } = useI18n()
const router = useRouter()
const errorMessage = ref('')
const {
  loadRecentTargets,
  loadingRecentTargets,
  recentTargets,
} = useAIMemoryTab(t)
const {
  loadRelationshipForTarget,
  loadRelationships,
  loadingRelationshipEvents,
  loadingRelationships,
  loadingSelectedRelationship,
  relationship,
  relationshipEvents,
  relationshipForm,
  relationships,
  saveRelationship,
  savingRelationship,
  selectRelationship,
} = useAIRelationshipTab(t)

const recentRelationshipTargets = computed(() => (
  recentTargets.value.filter(item => (
    (item.anchor_type === 'user' || item.anchor_type === 'participant')
    && !!item.platform
    && !!item.user_id
  ))
))
const relationshipMoodText = computed(() => {
  const tags = relationship.value?.effective_mood_tags ?? []
  return tags.length > 0 ? tags.join(', ') : t('common.none')
})
const relationshipSelectionLabel = computed(() => (
  relationship.value
    ? `${relationship.value.platform} / ${relationship.value.user_id}`
    : t('ai.selectRelationshipTarget')
))
const metrics = computed<WorkbenchMetricItem[]>(() => [
  {
    icon: Network,
    key: 'relationships',
    label: t('ai.relationshipTab'),
    value: relationships.value.length,
  },
  {
    key: 'score',
    label: t('ai.relationshipScore'),
    tone: relationship.value ? 'info' : 'default',
    value: relationship.value ? formatSigned(relationship.value.effective_score) : t('common.none'),
  },
  {
    key: 'events',
    label: t('ai.relationshipEvents'),
    value: relationshipEvents.value.length,
  },
])

async function loadData() {
  errorMessage.value = ''
  try {
    await Promise.all([
      loadRecentTargets(),
      loadRelationships(),
    ])
  } catch (error) {
    errorMessage.value = getErrorMessage(error, t('ai.relationshipLoadFailed'))
  }
}

function formatSigned(value: number) {
  return `${value >= 0 ? '+' : ''}${Math.round(value)}`
}

function formatEventType(value: string) {
  if (value === 'message') {
    return t('ai.relationshipEventMessage')
  }
  if (value === 'manual') {
    return t('ai.relationshipEventManual')
  }
  if (value === 'decay') {
    return t('ai.relationshipEventDecay')
  }
  return value
}

function openDebugConversations() {
  void router.push({ name: 'ai', query: { area: 'debug', debug: 'conversations' } })
}

function openChatView() {
  void router.push({ name: 'chat' })
}

onMounted(() => {
  void loadData()
})
</script>

<template>
  <PageScaffold
    :error-message="errorMessage"
    :subtitle="t('ai.pageSubtitle.relationships')"
    :title="t('ai.relationshipTab')"
  >
    <template #actions>
      <Button :disabled="loadingRelationships || loadingRecentTargets" variant="secondary" @click="loadData">
        <RefreshCw
          :class="{ 'animate-spin': loadingRelationships || loadingRecentTargets }"
          :size="16"
        />
        {{ t('common.refresh') }}
      </Button>
    </template>

    <MetricStrip :items="metrics" compact />

    <SplitPane wide-sidebar>
      <template #sidebar>
        <Panel :title="t('ai.recentTargets')" :subtitle="t('ai.noRecentTargetsHint')">
          <LoadingSkeleton v-if="loadingRecentTargets && recentRelationshipTargets.length === 0" :rows="5" />
          <EmptyState
            v-else-if="recentRelationshipTargets.length === 0"
            :icon="MessageSquare"
            :text="t('ai.noRecentTargetsHint')"
            :title="t('ai.noRecentTargets')"
          />
          <SelectableList v-else>
            <SelectableListItem
              v-for="item in recentRelationshipTargets"
              :key="`${item.anchor_type}:${item.anchor_id}`"
              :disabled="loadingSelectedRelationship"
              @click="loadRelationshipForTarget(item)"
            >
              <div class="ai-data-list-item">
                <div class="ai-data-list-item__main">
                  <strong>{{ item.title }}</strong>
                  <span>{{ item.subtitle || item.anchor_id }}</span>
                </div>
                <Badge variant="secondary">{{ item.platform }}</Badge>
              </div>
            </SelectableListItem>
          </SelectableList>
        </Panel>

        <Panel :title="t('ai.relationshipStateTitle')">
          <LoadingSkeleton v-if="loadingRelationships && relationships.length === 0" :rows="4" />
          <EmptyState
            v-else-if="relationships.length === 0"
            :icon="Network"
            :title="t('ai.noRelationships')"
          />
          <SelectableList v-else>
            <SelectableListItem
              v-for="item in relationships"
              :key="item.affinity_id"
              :active="relationship?.affinity_id === item.affinity_id"
              @click="selectRelationship(item)"
            >
              <div class="ai-data-list-item">
                <div class="ai-data-list-item__main">
                  <strong>{{ item.user_id }}</strong>
                  <span>{{ item.platform }}</span>
                </div>
                <StatusBadge
                  :label="formatSigned(item.effective_score)"
                  :tone="item.effective_score >= 0 ? 'success' : 'warning'"
                />
              </div>
            </SelectableListItem>
          </SelectableList>
        </Panel>
      </template>

      <div class="ai-data-stack">
        <Panel v-if="relationship" :title="t('ai.relationshipStateTitle')" :subtitle="relationshipSelectionLabel">
          <div class="ai-data-form">
            <div class="ai-data-form__meta">
              <Badge variant="secondary">
                {{ t('ai.relationshipPlatform') }}: {{ relationship.platform }}
              </Badge>
              <Badge variant="secondary">
                {{ t('ai.relationshipUserId') }}: {{ relationship.user_id }}
              </Badge>
            </div>

            <div class="ai-relationship-grid">
              <div>
                <span>{{ t('ai.relationshipScore') }}</span>
                <strong>{{ formatSigned(relationship.effective_score) }}</strong>
              </div>
              <div>
                <span>{{ t('ai.relationshipProjectedTone') }}</span>
                <strong>{{ relationship.effective_projected_tone || t('common.none') }}</strong>
              </div>
              <div>
                <span>{{ t('ai.relationshipMoodTags') }}</span>
                <strong>{{ relationshipMoodText }}</strong>
              </div>
              <div>
                <span>{{ t('ai.relationshipLastEventAt') }}</span>
                <strong>{{ relationship.last_event_at || t('common.none') }}</strong>
              </div>
              <div>
                <span>{{ t('ai.relationshipWarmthBias') }}</span>
                <strong>{{ formatSigned(relationship.effective_warmth_bias) }}</strong>
              </div>
              <div>
                <span>{{ t('ai.relationshipInitiativeBias') }}</span>
                <strong>{{ formatSigned(relationship.effective_initiative_bias) }}</strong>
              </div>
            </div>

            <div class="ai-data-form__meta">
              <Badge
                v-for="line in relationship.effective_style_modulation"
                :key="line"
                variant="outline"
              >
                {{ line }}
              </Badge>
              <Badge v-if="relationship.effective_style_modulation.length === 0" variant="outline">
                {{ t('ai.relationshipStyleModulation') }}: {{ t('common.none') }}
              </Badge>
            </div>

            <div class="ai-relationship-score-editor">
              <FormField :label="t('ai.relationshipScore')">
                <Input v-model="relationshipForm.score" max="100" min="-100" step="1" type="number" />
              </FormField>
              <Button :disabled="savingRelationship" @click="saveRelationship">
                <RefreshCw v-if="savingRelationship" class="animate-spin" :size="16" />
                <Save v-else :size="16" />
                {{ t('ai.saveRelationship') }}
              </Button>
            </div>
          </div>
        </Panel>
        <Panel v-else>
          <EmptyState
            :icon="Network"
            :text="t('ai.noRelationshipLoaded')"
            :title="t('ai.selectRelationshipTarget')"
          >
            <template #actions>
              <Button variant="secondary" @click="openDebugConversations">
                {{ t('ai.goToDebug') }}
              </Button>
              <Button variant="ghost" @click="openChatView">
                {{ t('ai.goToChatView') }}
              </Button>
            </template>
          </EmptyState>
        </Panel>

        <Panel :title="t('ai.relationshipEvents')">
          <LoadingSkeleton v-if="loadingRelationshipEvents" :rows="4" />
          <EmptyState
            v-else-if="relationshipEvents.length === 0"
            :icon="Network"
            :title="t('ai.noRelationshipEvents')"
          />
          <div v-else class="ai-event-list">
            <article
              v-for="event in relationshipEvents"
              :key="event.event_id"
              class="ai-event-row"
            >
              <div>
                <strong>{{ formatEventType(event.event_type) }}</strong>
                <p>{{ event.reason || t('common.none') }}</p>
              </div>
              <div class="ai-event-row__meta">
                <Badge variant="secondary">{{ formatSigned(event.score_delta) }}</Badge>
                <Badge variant="outline">
                  {{ t('ai.relationshipScoreAfter') }}: {{ formatSigned(event.score_after) }}
                </Badge>
                <span>{{ event.created_at }}</span>
              </div>
            </article>
          </div>
        </Panel>
      </div>
    </SplitPane>
  </PageScaffold>
</template>
