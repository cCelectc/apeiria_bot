<template>
  <v-chip
    class="workbench-status-badge"
    :color="color"
    :prepend-icon="icon || undefined"
    :size="size"
    variant="tonal"
  >
    {{ label }}
  </v-chip>
</template>

<script setup lang="ts">
  withDefaults(defineProps<{
    label: string
    color?: string
    icon?: string
    size?: 'x-small' | 'small' | 'default' | 'large' | 'x-large'
  }>(), {
    color: 'default',
    icon: '',
    size: 'small',
  })
</script>

<style scoped>
.workbench-status-badge {
  font-weight: 650;
  letter-spacing: 0;
}
</style>
