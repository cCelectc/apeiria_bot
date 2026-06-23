<template>
  <div class="flex flex-col gap-6">
    <PageHeader title="Core Settings" description="Bot runtime configuration" />
    <CoreSettings />
  </div>
</template>

<script setup lang="ts">
import PageHeader from "@/components/PageHeader.vue"
import CoreSettings from "@/features/core-settings/index.vue"
</script>
