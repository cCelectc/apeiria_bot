<template>
  <div class="flex flex-col gap-6">
    <StatusCards v-if="status" :status="status" />
    <FeedbackAlert v-if="error" :message="error" variant="destructive" />
    <Skeleton v-if="loading" class="h-32 w-full" />
    <div v-if="status && !loading" class="grid gap-6 lg:grid-cols-2">
      <EventsFeed :events="events" />
      <BuildPanel :status="buildStatus" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { useRequest } from "@/composables/useRequest"
import { dashboardService } from "@/api/services/dashboard"
import StatusCards from "./StatusCards.vue"
import EventsFeed from "./EventsFeed.vue"
import BuildPanel from "./BuildPanel.vue"
import FeedbackAlert from "@/components/FeedbackAlert.vue"
import Skeleton from "@/components/ui/skeleton/Skeleton.vue"

const { data: status, loading: statusLoading, error: statusError } = useRequest(
  "dashboard-status",
  () => dashboardService.getStatus(),
  { staleTime: 15_000 },
)

const { data: eventsData } = useRequest(
  "dashboard-events",
  () => dashboardService.getEvents(),
  { staleTime: 30_000 },
)

const { data: buildStatusData } = useRequest(
  "dashboard-build",
  () => dashboardService.getWebUIBuildStatus(),
  { staleTime: 60_000 },
)

const loading = computed(() => statusLoading.value)
const error = computed(() => statusError.value)
const events = computed(() => eventsData.value?.items ?? [])
const buildStatus = computed(() => buildStatusData.value ?? {
  is_built: false,
  is_stale: false,
  can_build: false,
  build_tool: null,
  detail: null,
})
</script>
