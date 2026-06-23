<template>
  <Card>
    <CardHeader class="flex-row items-center justify-between">
      <div><CardTitle>AI Profiles</CardTitle><CardDescription>User profile management</CardDescription></div>
      <Button variant="outline" size="sm" :disabled="loading" @click="refresh()">
        <RotateCw class="size-4" /> Refresh
      </Button>
    </CardHeader>
    <CardContent>
      <Skeleton v-if="loading" class="h-64 w-full" />
      <div v-else-if="profiles && profiles.length > 0" class="flex flex-col gap-2">
        <div v-for="p in profiles" :key="p.id" class="flex items-center justify-between rounded-md border p-3 text-sm">
          <div>
            <span class="font-medium">{{ p.display_name || p.id }}</span>
            <span class="ml-2 text-muted-foreground">{{ p.preferred_name || '-' }}</span>
          </div>
          <StatusBadge :variant="p.enabled !== false ? 'success' : 'default'">
            {{ p.enabled !== false ? 'Active' : 'Disabled' }}
          </StatusBadge>
        </div>
      </div>
      <EmptyState v-else title="No profiles" />
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import { RotateCw } from "@lucide/vue"
import { useRequest } from "@/composables/useRequest"
import { aiSessionsService } from "@/api/services/ai-sessions"
import Button from "@/components/ui/button/Button.vue"
import Skeleton from "@/components/ui/skeleton/Skeleton.vue"
import Card from "@/components/ui/card/Card.vue"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import StatusBadge from "@/components/StatusBadge.vue"
import EmptyState from "@/components/EmptyState.vue"

const { data: profiles, loading, refresh } = useRequest("ai-profiles", () => aiSessionsService.getProfiles())
</script>
