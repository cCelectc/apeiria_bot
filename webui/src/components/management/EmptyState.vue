<script setup lang="ts">
import type { Component } from 'vue'
import type { WorkbenchEmptyCause } from './types'
import { FilterX, Info, ListRestart, MousePointerSquareDashed } from 'lucide-vue-next'
import { computed, markRaw, toRaw } from 'vue'
import { useI18n } from 'vue-i18n'
import { Button } from '@/components/ui/button'

defineEmits<{
  action: []
}>()

const props = withDefaults(defineProps<{
  actionLabel?: string
  cause?: WorkbenchEmptyCause
  compact?: boolean
  icon?: Component
  text?: string
  title?: string
}>(), {
  actionLabel: '',
  cause: 'no-data',
  compact: false,
  icon: () => Info,
  text: '',
  title: '',
})

const { t } = useI18n()

const causeMeta = computed(() => {
  if (props.cause === 'filtered') {
    return {
      icon: FilterX,
      text: t('feedback.emptyFilteredDescription'),
      title: t('feedback.emptyFilteredTitle'),
    }
  }
  if (props.cause === 'selection-required') {
    return {
      icon: MousePointerSquareDashed,
      text: t('feedback.emptySelectionDescription'),
      title: t('feedback.emptySelectionTitle'),
    }
  }
  if (props.cause === 'pending') {
    return {
      icon: ListRestart,
      text: t('feedback.emptyPendingDescription'),
      title: t('feedback.emptyPendingTitle'),
    }
  }
  return {
    icon: Info,
    text: t('feedback.emptyNoDataDescription'),
    title: t('feedback.emptyNoDataTitle'),
  }
})

const hasCustomIcon = computed(() => props.icon !== Info)
const resolvedIcon = computed(() =>
  markRaw(toRaw(hasCustomIcon.value ? props.icon : causeMeta.value.icon)),
)
const resolvedText = computed(() => props.text || causeMeta.value.text)
const resolvedTitle = computed(() => props.title || causeMeta.value.title)
</script>

<template>
  <div
    class="workbench-empty-state"
    :class="{ 'workbench-empty-state--compact': compact }"
    :data-empty-cause="cause"
  >
    <div class="workbench-empty-state__icon">
      <component :is="resolvedIcon" :size="30" />
    </div>

    <div class="workbench-empty-state__content">
      <div class="workbench-empty-state__title">
        {{ resolvedTitle }}
      </div>
      <div v-if="resolvedText" class="workbench-empty-state__text">
        {{ resolvedText }}
      </div>
    </div>

    <div v-if="$slots.actions || actionLabel" class="workbench-empty-state__actions">
      <slot name="actions">
        <Button v-if="actionLabel" variant="secondary" @click="$emit('action')">
          {{ actionLabel }}
        </Button>
      </slot>
    </div>
  </div>
</template>
