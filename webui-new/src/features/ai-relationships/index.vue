<template>
  <Card>
    <CardHeader><CardTitle>Relationships</CardTitle><CardDescription>User-bot affinity scores</CardDescription></CardHeader>
    <CardContent>
      <Skeleton v-if="loading" class="h-64 w-full" />
      <div v-else-if="relationships && relationships.length > 0" class="flex flex-col gap-2">
        <div v-for="r in relationships" :key="r.user_id" class="rounded-md border p-3 text-sm">
          <div class="flex items-center justify-between">
            <span class="font-medium">{{ r.user_id }}</span>
            <StatusBadge :variant="(r.warmth ?? 0) > 0.5 ? 'success' : 'default'">
              Score: {{ r.score ?? '-' }}
            </StatusBadge>
          </div>
          <div class="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
            <span>Warmth: {{ r.warmth }}</span>
            <span>Initiative: {{ r.initiative_bias }}</span>
            <span v-if="r.mood_tags">Mood: {{ r.mood_tags }}</span>
          </div>
        </div>
      </div>
      <EmptyState v-else title="No relationships" />
    </CardContent>
  </Card>
</template>
<script setup lang="ts">
import { useRequest } from "@/composables/useRequest"
import { aiSessionsService } from "@/api/services/ai-sessions"
import Skeleton from "@/components/ui/skeleton/Skeleton.vue"
import Card from "@/components/ui/card/Card.vue"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import StatusBadge from "@/components/StatusBadge.vue"
import EmptyState from "@/components/EmptyState.vue"
const { data: relationships, loading } = useRequest("ai-relationships", () => aiSessionsService.getRelationships())
</script>
