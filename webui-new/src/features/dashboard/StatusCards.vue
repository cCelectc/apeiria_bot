<template>
  <div class="grid grid-cols-2 gap-4 lg:grid-cols-4">
    <Card v-for="metric in metrics" :key="metric.label">
      <CardContent class="pt-6">
        <div class="flex flex-col gap-3">
          <div
            :class="metric.iconBg"
            class="flex size-10 items-center justify-center rounded-xl"
          >
            <component :is="metric.icon" :class="metric.iconColor" class="size-5" />
          </div>
          <div>
            <div class="text-sm text-muted-foreground">{{ metric.label }}</div>
            <div class="text-2xl font-bold tracking-tight">{{ metric.value }}</div>
          </div>
        </div>
      </CardContent>
    </Card>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import type { DashboardStatus } from "@/api/services/dashboard"
import {
  Activity,
  Clock,
  Package,
  Cable,
} from "@lucide/vue"
import Card from "@/components/ui/card/Card.vue"
import CardContent from "@/components/ui/card/CardContent.vue"
import { formatDuration } from "@/utils/format"

const props = defineProps<{ status: DashboardStatus }>()

const metrics = computed(() => [
  {
    label: "Status",
    value: props.status.status,
    icon: Activity,
    iconBg: "bg-blue-100 dark:bg-blue-900/40",
    iconColor: "text-blue-600 dark:text-blue-400",
  },
  {
    label: "Uptime",
    value: formatDuration(props.status.uptime * 1000),
    icon: Clock,
    iconBg: "bg-emerald-100 dark:bg-emerald-900/40",
    iconColor: "text-emerald-600 dark:text-emerald-400",
  },
  {
    label: "Plugins",
    value: `${props.status.plugins_count} loaded`,
    icon: Package,
    iconBg: "bg-violet-100 dark:bg-violet-900/40",
    iconColor: "text-violet-600 dark:text-violet-400",
  },
  {
    label: "Adapters",
    value: props.status.adapters.length.toString(),
    icon: Cable,
    iconBg: "bg-amber-100 dark:bg-amber-900/40",
    iconColor: "text-amber-600 dark:text-amber-400",
  },
])
</script>
