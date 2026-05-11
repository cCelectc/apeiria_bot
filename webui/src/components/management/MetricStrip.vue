<script setup lang="ts">
import type { WorkbenchMetricItem } from './types'
import { computed, markRaw, toRaw } from 'vue'
import {
  Card,
  CardContent,
} from '@/components/ui/card'

const props = withDefaults(defineProps<{
  compact?: boolean
  items: WorkbenchMetricItem[]
}>(), {
  compact: false,
})

const displayItems = computed(() =>
  props.items.map(item => ({
    ...item,
    icon: item.icon ? markRaw(toRaw(item.icon)) : undefined,
  })),
)
</script>

<template>
  <div class="workbench-metric-strip" :class="{ 'workbench-metric-strip--compact': compact }">
    <Card
      v-for="item in displayItems"
      :key="item.key"
      class="workbench-metric-strip__item"
    >
      <CardContent class="workbench-metric-strip__content">
        <div class="workbench-metric-strip__label">
          {{ item.label }}
        </div>

        <div class="workbench-metric-strip__value-row">
          <div class="workbench-metric-strip__value">
            {{ item.value }}
          </div>

          <div
            v-if="item.icon"
            class="workbench-metric-strip__icon"
            :class="item.tone ? `workbench-tone--${item.tone}` : undefined"
          >
            <component :is="item.icon" :size="22" />
          </div>
        </div>

        <div v-if="item.hint" class="workbench-metric-strip__hint">
          {{ item.hint }}
        </div>
      </CardContent>
    </Card>
  </div>
</template>
