<script setup lang="ts">
import { Skeleton } from '@/components/ui/skeleton'

withDefaults(defineProps<{
  busyLabel?: string
  rows?: string | number
}>(), {
  busyLabel: '',
  rows: 4,
})
</script>

<template>
  <div
    aria-busy="true"
    class="workbench-loading-skeleton"
    role="status"
  >
    <span v-if="busyLabel" class="sr-only">{{ busyLabel }}</span>
    <Skeleton
      v-for="index in Number(rows)"
      :key="index"
      class="workbench-loading-skeleton__row"
    />
  </div>
</template>
