<template>
  <Card>
    <CardHeader>
      <CardTitle>Recent Events</CardTitle>
      <CardDescription v-if="events.length === 0">No recent events</CardDescription>
    </CardHeader>
    <CardContent v-if="events.length > 0">
      <div class="flex flex-col gap-1">
        <div
          v-for="(evt, i) in events"
          :key="i"
          class="flex items-center gap-3 rounded-md px-3 py-2 text-sm"
          :class="evt.level === 'ERROR' ? 'bg-destructive/10' : 'bg-muted/50'"
        >
          <StatusBadge :variant="evt.level === 'ERROR' ? 'error' : 'warning'" class="shrink-0">
            {{ evt.level }}
          </StatusBadge>
          <span class="truncate">{{ evt.message }}</span>
          <span class="ml-auto shrink-0 text-xs text-muted-foreground">
            {{ evt.source }}
          </span>
        </div>
      </div>
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import type { DashboardEventItem } from "@/api/services/dashboard"
import Card from "@/components/ui/card/Card.vue"
import CardContent from "@/components/ui/card/CardContent.vue"
import CardDescription from "@/components/ui/card/CardDescription.vue"
import CardHeader from "@/components/ui/card/CardHeader.vue"
import CardTitle from "@/components/ui/card/CardTitle.vue"
import StatusBadge from "@/components/StatusBadge.vue"

defineProps<{ events: DashboardEventItem[] }>()
</script>
