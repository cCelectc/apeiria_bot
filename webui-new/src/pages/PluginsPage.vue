<template>
  <div class="flex flex-col gap-6">
    <PageHeader title="Plugins" />
    <PluginsFeature />
  </div>
</template>

<script setup lang="ts">
import PageHeader from "@/components/PageHeader.vue"
import PluginsFeature from "@/features/plugins/index.vue"
</script>
