<script setup lang="ts">
import Panel from './Panel.vue'

withDefaults(defineProps<{
  subtitle?: string
  title?: string
}>(), {
  subtitle: '',
  title: '',
})
</script>

<template>
  <Panel class="workbench-detail-panel" :subtitle="subtitle" :title="title">
    <template v-if="$slots.actions" #actions>
      <slot name="actions" />
    </template>
    <slot />
  </Panel>
</template>
