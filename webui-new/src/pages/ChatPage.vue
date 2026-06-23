<template>
  <div class="flex flex-col gap-6">
    <PageHeader title="Chat" description="WebSocket chat interface" />
    <ChatFeature />
  </div>
</template>

<script setup lang="ts">
import PageHeader from "@/components/PageHeader.vue"
import ChatFeature from "@/features/chat/index.vue"
</script>
