<script setup lang="ts">
import type { WorkbenchTone } from './types'
import { Badge } from '@/components/ui/badge'

withDefaults(defineProps<{
  label: string
  tone?: WorkbenchTone
}>(), {
  tone: 'default',
})
</script>

<template>
  <Badge
    :variant="tone === 'default' ? 'secondary' : 'outline'"
    class="workbench-status-badge"
    :class="`workbench-tone--${tone}`"
  >
    <span class="workbench-status-badge__dot" />
    {{ label }}
  </Badge>
</template>
