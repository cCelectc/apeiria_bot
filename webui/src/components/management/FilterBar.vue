<script setup lang="ts">
withDefaults(defineProps<{
  compact?: boolean
}>(), {
  compact: false,
})
</script>

<template>
  <div class="workbench-filter-bar" :class="{ 'workbench-filter-bar--compact': compact }">
    <slot />
  </div>
</template>
