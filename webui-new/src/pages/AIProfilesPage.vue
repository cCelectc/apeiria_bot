<template>
  <div class="flex flex-col gap-6">
    <PageHeader title="AI Profiles" />
    <AiFeature />
  </div>
</template>

<script setup lang="ts">
import PageHeader from "@/components/PageHeader.vue"
import AiFeature from "@/features/ai-profiles/index.vue"
</script>
