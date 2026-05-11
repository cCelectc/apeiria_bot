<script setup lang="ts">
import type { Component } from 'vue'
import { Info } from 'lucide-vue-next'
import { computed, markRaw, toRaw } from 'vue'
import { Button } from '@/components/ui/button'

defineEmits<{
  action: []
}>()

const props = withDefaults(defineProps<{
  actionLabel?: string
  icon?: Component
  text?: string
  title: string
}>(), {
  actionLabel: '',
  icon: () => Info,
  text: '',
})

const resolvedIcon = computed(() => markRaw(toRaw(props.icon)))
</script>

<template>
  <div class="workbench-empty-state">
    <div class="workbench-empty-state__icon">
      <component :is="resolvedIcon" :size="30" />
    </div>

    <div class="workbench-empty-state__content">
      <div class="workbench-empty-state__title">
        {{ title }}
      </div>
      <div v-if="text" class="workbench-empty-state__text">
        {{ text }}
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
