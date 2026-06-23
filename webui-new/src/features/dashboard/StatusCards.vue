<template>
  <div class="grid grid-cols-2 gap-4 lg:grid-cols-4">
    <Card v-for="metric in metrics" :key="metric.label">
      <CardHeader class="pb-2">
        <CardDescription>{{ metric.label }}</CardDescription>
      </CardHeader>
      <CardContent>
        <div class="text-2xl font-bold">{{ metric.value }}</div>
      </CardContent>
    </Card>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import type { DashboardStatus } from "@/api/services/dashboard"
import Card from "@/components/ui/card/Card.vue"
import CardContent from "@/components/ui/card/CardContent.vue"
import CardDescription from "@/components/ui/card/CardDescription.vue"
import CardHeader from "@/components/ui/card/CardHeader.vue"
import { formatDuration } from "@/utils/format"

const props = defineProps<{ status: DashboardStatus }>()

const metrics = computed(() => [
  { label: "Status", value: props.status.status },
  { label: "Uptime", value: formatDuration(props.status.uptime * 1000) },
  { label: "Plugins", value: `${props.status.plugins_count} loaded` },
  { label: "Adapters", value: props.status.adapters.length.toString() },
])
</script>
