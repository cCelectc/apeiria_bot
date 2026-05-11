<script setup lang="ts">
import { Skeleton } from '@/components/ui/skeleton'

withDefaults(defineProps<{
  rows?: string | number
}>(), {
  rows: 4,
})
</script>

<template>
  <div class="workbench-loading-skeleton">
    <Skeleton
      v-for="index in Number(rows)"
      :key="index"
      class="workbench-loading-skeleton__row"
    />
  </div>
</template>
