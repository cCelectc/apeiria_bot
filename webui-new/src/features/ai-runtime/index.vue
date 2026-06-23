<template>
  <Card>
    <CardHeader class="flex-row items-center justify-between">
      <div><CardTitle>AI Runtime Settings</CardTitle><CardDescription>Tune AI behavior parameters</CardDescription></div>
      <Button variant="outline" size="sm" :disabled="loading" @click="refresh()">Refresh</Button>
    </CardHeader>
    <CardContent>
      <Skeleton v-if="loading" class="h-64 w-full" />
      <EmptyState v-else title="Runtime settings" description="Configure AI thresholds and limits here." />
    </CardContent>
  </Card>
</template>
<script setup lang="ts">
import { useRequest } from "@/composables/useRequest"
import client from "@/api/client"
import Button from "@/components/ui/button/Button.vue"
import Skeleton from "@/components/ui/skeleton/Skeleton.vue"
import Card from "@/components/ui/card/Card.vue"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import EmptyState from "@/components/EmptyState.vue"
const { loading, refresh } = useRequest("ai-runtime", () => client.get("/ai/settings").then(r => r.data))
</script>
