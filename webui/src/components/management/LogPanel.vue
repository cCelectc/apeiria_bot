<script setup lang="ts">
import Panel from './Panel.vue'

withDefaults(defineProps<{
  logs?: string
  title?: string
}>(), {
  logs: '',
  title: '',
})
</script>

<template>
  <Panel class="workbench-log-panel" :title="title">
    <pre>{{ logs }}</pre>
  </Panel>
</template>
