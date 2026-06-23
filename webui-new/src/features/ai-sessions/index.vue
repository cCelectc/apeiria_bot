<template>
  <Card>
    <CardHeader class="flex-row items-center justify-between">
      <div>
        <CardTitle>AI Sessions</CardTitle>
        <CardDescription>Managed conversation sessions</CardDescription>
      </div>
      <Button variant="outline" size="sm" :disabled="loading" @click="refresh()">Refresh</Button>
    </CardHeader>
    <CardContent>
      <Skeleton v-if="loading" class="h-64 w-full" />
      <DataTable v-else-if="sessions && sessions.length > 0"
        :columns="[{key:'id',label:'ID'},{key:'platform',label:'Platform'},{key:'ai_enabled',label:'AI'}]"
        :rows="sessions as unknown as Record<string,unknown>[]" />
      <EmptyState v-else title="No sessions" description="AI sessions will appear here." />
    </CardContent>
  </Card>
</template>
<script setup lang="ts">
import { useRequest } from "@/composables/useRequest"
import { aiSessionsService } from "@/api/services/ai-sessions"
import Button from "@/components/ui/button/Button.vue"
import Skeleton from "@/components/ui/skeleton/Skeleton.vue"
import Card from "@/components/ui/card/Card.vue"
import {CardContent,CardDescription,CardHeader,CardTitle} from "@/components/ui/card"
import DataTable from "@/components/DataTable.vue"
import EmptyState from "@/components/EmptyState.vue"
const {data:sessions,loading,refresh}=useRequest("ai-sessions",()=>aiSessionsService.list())
</script>
