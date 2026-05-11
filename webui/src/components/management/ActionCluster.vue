<script setup lang="ts">
withDefaults(defineProps<{
  align?: 'start' | 'end' | 'between'
  wrap?: boolean
}>(), {
  align: 'end',
  wrap: true,
})
</script>

<template>
  <div
    class="workbench-action-cluster"
    :class="[
      `workbench-action-cluster--${align}`,
      { 'workbench-action-cluster--nowrap': !wrap },
    ]"
  >
    <slot />
  </div>
</template>
