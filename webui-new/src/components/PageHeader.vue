<template>
  <div class="flex items-center justify-between border-b pb-4 mb-2">
    <div>
      <h1 class="text-2xl font-semibold tracking-tight">{{ title }}</h1>
      <p v-if="description" class="text-sm text-muted-foreground mt-1">{{ description }}</p>
    </div>
    <div class="flex items-center gap-3">
      <Badge v-if="restartPending" variant="secondary">
        Restart required
      </Badge>
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { useNoticeStore } from "@/stores/notice"
import Badge from "@/components/ui/badge/Badge.vue"

defineProps<{
  title: string
  description?: string
}>()

const notice = useNoticeStore()
const restartPending = computed(() => notice.pendingRestart)
</script>
