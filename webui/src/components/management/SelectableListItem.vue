<script setup lang="ts">
withDefaults(defineProps<{
  active?: boolean
  disabled?: boolean
}>(), {
  active: false,
  disabled: false,
})
</script>

<template>
  <button
    class="workbench-selectable-list__item"
    :class="{ 'workbench-selectable-list__item--active': active }"
    :disabled="disabled"
    type="button"
  >
    <slot />
  </button>
</template>
