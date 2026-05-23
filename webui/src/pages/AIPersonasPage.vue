<script setup lang="ts">
import { CheckCircle2, MessagesSquare, Plus, RefreshCw, Save } from '@lucide/vue'
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
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { useAIPersonasTab } from '@/composables/useAIPersonasTab'

const { t } = useI18n()
defineProps<{
  embedded?: boolean
}>()
const errorMessage = ref('')
const search = ref('')
const {
  canSavePersona,
  displayedPersonaErrors,
  isCreatingPersona,
  loadPersonasData,
  loadingPersonas,
  personaBindings,
  personaForm,
  personas,
  savePersona,
  savingPersona,
  selectPersona,
  selectedPersonaBindingCount,
  startCreatePersona,
  touchPersonaField,
} = useAIPersonasTab(t)

const filteredPersonas = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  if (!keyword) {
    return personas.value
  }
  return personas.value.filter(item => (
    `${item.name} ${item.description} ${item.system_prompt}`.toLowerCase().includes(keyword)
  ))
})
const metrics = computed<WorkbenchMetricItem[]>(() => [
  {
    hint: t('ai.personaTitle'),
    icon: MessagesSquare,
    key: 'personas',
    label: t('ai.personasTab'),
    value: personas.value.length,
  },
  {
    icon: CheckCircle2,
    key: 'enabled',
    label: t('ai.enabled'),
    tone: 'success',
    value: personas.value.filter(item => item.enabled).length,
  },
  {
    key: 'bindings',
    label: t('ai.scopeBindings'),
    tone: 'info',
    value: personaBindings.value.length,
  },
])

async function loadData() {
  errorMessage.value = ''
  try {
    await loadPersonasData()
  } catch (error) {
    errorMessage.value = getErrorMessage(error, t('ai.loadFailed'))
  }
}

onMounted(() => {
  void loadData()
})
</script>

<template>
  <PageScaffold
    :embedded="embedded"
    :error-message="errorMessage"
    :subtitle="t('ai.pageSubtitle.personas')"
    :title="t('ai.personasTab')"
  >
    <template #actions>
      <Button :disabled="loadingPersonas" variant="secondary" @click="loadData">
        <RefreshCw :class="{ 'animate-spin': loadingPersonas }" :size="16" />
        {{ t('common.refresh') }}
      </Button>
      <Button @click="startCreatePersona">
        <Plus :size="16" />
        {{ t('ai.createPersona') }}
      </Button>
    </template>

    <MetricStrip :items="metrics" compact />

    <SplitPane wide-sidebar>
      <template #sidebar>
        <Panel :title="t('ai.personas')" :subtitle="t('ai.noPersonasHint')">
          <div class="ai-data-toolbar">
            <Input v-model="search" :placeholder="t('common.search')" />
          </div>

          <LoadingSkeleton v-if="loadingPersonas && personas.length === 0" :rows="5" />
          <EmptyState
            v-else-if="filteredPersonas.length === 0"
            :icon="MessagesSquare"
            :text="t('ai.noPersonasHint')"
            :title="t('ai.noPersonas')"
          >
            <template #actions>
              <Button variant="secondary" @click="startCreatePersona">
                <Plus :size="16" />
                {{ t('ai.createPersona') }}
              </Button>
            </template>
          </EmptyState>
          <SelectableList v-else>
            <SelectableListItem
              v-for="item in filteredPersonas"
              :key="item.persona_id"
              :active="item.persona_id === personaForm.persona_id"
              @click="selectPersona(item)"
            >
              <div class="ai-data-list-item">
                <div class="ai-data-list-item__main">
                  <strong>{{ item.name }}</strong>
                  <span>{{ item.description || t('common.none') }}</span>
                </div>
                <StatusBadge
                  :label="item.enabled ? t('ai.enabled') : t('ai.disabled')"
                  :tone="item.enabled ? 'success' : 'default'"
                />
              </div>
            </SelectableListItem>
          </SelectableList>
        </Panel>
      </template>

      <Panel
        :subtitle="t('ai.personaTemplateVariablesHint')"
        :title="isCreatingPersona ? t('ai.creatingPersona') : t('ai.editingPersona')"
      >
        <div class="ai-data-form">
          <div class="ai-data-form__meta">
            <Badge variant="secondary">
              {{ t('ai.scopeBindings') }}: {{ selectedPersonaBindingCount }}
            </Badge>
            <Badge variant="outline">
              {{ personaForm.persona_id || t('ai.createPersona') }}
            </Badge>
          </div>

          <FormField
            :error="displayedPersonaErrors.name"
            :label="t('ai.personaName')"
            required
          >
            <Input
              v-model="personaForm.name"
              :aria-invalid="Boolean(displayedPersonaErrors.name)"
              :disabled="savingPersona"
              @blur="touchPersonaField('name')"
            />
          </FormField>

          <FormField
            :error="displayedPersonaErrors.description"
            :label="t('ai.personaDescription')"
            required
          >
            <Input
              v-model="personaForm.description"
              :aria-invalid="Boolean(displayedPersonaErrors.description)"
              :disabled="savingPersona"
              @blur="touchPersonaField('description')"
            />
          </FormField>

          <FormField
            :error="displayedPersonaErrors.system_prompt"
            :helper="t('ai.personaTemplateVariablesHint')"
            :label="t('ai.personaSystemPrompt')"
            required
          >
            <Textarea
              v-model="personaForm.system_prompt"
              :aria-invalid="Boolean(displayedPersonaErrors.system_prompt)"
              class="min-h-40"
              :disabled="savingPersona"
              @blur="touchPersonaField('system_prompt')"
            />
          </FormField>

          <FormField
            :helper="t('ai.personaTemplateVariablesHint')"
            :label="t('ai.personaStylePrompt')"
          >
            <Textarea
              v-model="personaForm.style_prompt"
              class="min-h-32"
              :disabled="savingPersona"
            />
          </FormField>

          <div class="ai-data-switch-row">
            <div>
              <strong>{{ t('ai.personaEnabled') }}</strong>
              <span>{{ personaForm.enabled ? t('ai.enabled') : t('ai.disabled') }}</span>
            </div>
            <Switch v-model="personaForm.enabled" :disabled="savingPersona" />
          </div>

          <div class="ai-data-actions">
            <Button :disabled="!canSavePersona" @click="savePersona">
              <RefreshCw v-if="savingPersona" class="animate-spin" :size="16" />
              <Save v-else :size="16" />
              {{ t('common.save') }}
            </Button>
          </div>
        </div>
      </Panel>
    </SplitPane>
  </PageScaffold>
</template>
