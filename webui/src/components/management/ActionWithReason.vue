<script setup lang="ts">
import type { Component } from 'vue'
import { computed } from 'vue'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'

let actionReasonIdSeed = 0

const props = withDefaults(defineProps<{
  disabled?: boolean
  icon?: Component
  label: string
  reason?: string
  size?: 'default' | 'sm' | 'lg' | 'icon' | 'icon-sm' | 'icon-lg'
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link'
}>(), {
  disabled: false,
  reason: '',
  size: 'sm',
  variant: 'ghost',
})

const emit = defineEmits<{
  activate: []
}>()

const actionReasonId = `management-action-reason-${++actionReasonIdSeed}`
const reasonId = computed(() => props.reason ? actionReasonId : undefined)

function handleActivate() {
  if (props.disabled) {
    return
  }
  emit('activate')
}
</script>

<template>
  <Tooltip v-if="disabled && reason">
    <TooltipTrigger as-child>
      <span
        class="management-action-with-reason"
        :aria-describedby="reasonId"
        :aria-label="`${label}: ${reason}`"
        aria-disabled="true"
        role="button"
        tabindex="0"
        @click.prevent
        @keydown.enter.prevent
        @keydown.space.prevent
      >
        <Button
          aria-hidden="true"
          disabled
          :size="size"
          tabindex="-1"
          :variant="variant"
        >
          <component v-if="icon" :is="icon" data-icon="inline-start" />
          {{ label }}
        </Button>
      </span>
    </TooltipTrigger>
    <TooltipContent :id="reasonId">
      {{ reason }}
    </TooltipContent>
  </Tooltip>
  <Button
    v-else
    :disabled="disabled"
    :size="size"
    :variant="variant"
    @click="handleActivate"
  >
    <component v-if="icon" :is="icon" data-icon="inline-start" />
    {{ label }}
  </Button>
</template>
