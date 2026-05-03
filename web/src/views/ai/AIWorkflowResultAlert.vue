<template>
  <v-alert
    v-if="result"
    class="ai-workflow-result"
    density="compact"
    :type="result.status"
    variant="tonal"
  >
    <div class="ai-workflow-result__message">{{ result.message }}</div>
    <pre v-if="result.detail" class="ai-workflow-result__detail">{{ result.detail }}</pre>
  </v-alert>
</template>

<script setup lang="ts">
  import type { AIWorkflowOperationResult } from '@/composables/aiModels/setupWorkflow'

  defineProps<{
    result: AIWorkflowOperationResult | null
  }>()
</script>

<style scoped>
.ai-workflow-result {
  margin-top: 12px;
}

.ai-workflow-result__message {
  line-height: 1.55;
}

.ai-workflow-result__detail {
  max-height: 140px;
  margin: 8px 0 0;
  overflow: auto;
  color: rgba(var(--v-theme-on-surface), 0.76);
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.78rem;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
