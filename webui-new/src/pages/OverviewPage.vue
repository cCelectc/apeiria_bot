<template>
  <div class="flex flex-col gap-6">
    <PageHeader title="Dashboard" description="Bot health and activity overview" />
    <Dashboard />
  </div>
</template>

<script setup lang="ts">
import PageHeader from "@/components/PageHeader.vue"
import Dashboard from "@/features/dashboard/index.vue"
</script>
