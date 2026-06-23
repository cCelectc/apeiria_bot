<template>
  <Card>
    <CardHeader class="flex-row items-center justify-between">
      <div><CardTitle>Project Update</CardTitle><CardDescription>Git-based update management</CardDescription></div>
      <Button variant="outline" size="sm" :disabled="statusLoading" @click="doRefresh">Check for updates</Button>
    </CardHeader>
    <CardContent>
      <Skeleton v-if="statusLoading" class="h-32 w-full" />
      <div v-else-if="status" class="flex flex-col gap-3 text-sm">
        <div class="flex gap-4">
          <span class="text-muted-foreground">Branch:</span>
          <span class="font-medium">{{ status.active_branch || '-' }}</span>
        </div>
        <div class="flex gap-4">
          <span class="text-muted-foreground">Commit:</span>
          <span class="font-mono text-xs">{{ status.head_sha?.slice(0, 8) || '-' }}</span>
        </div>
        <Button v-if="status.updates_available" variant="default" size="sm" class="w-fit mt-2">
          Update Available
        </Button>
      </div>
      <EmptyState v-else title="No status" />
    </CardContent>
  </Card>
</template>
<script setup lang="ts">
import { useRequest } from "@/composables/useRequest"
import { updateService } from "@/api/services/update"
import { useNoticeStore } from "@/stores/notice"
import Button from "@/components/ui/button/Button.vue"
import Skeleton from "@/components/ui/skeleton/Skeleton.vue"
import Card from "@/components/ui/card/Card.vue"
import {CardContent,CardDescription,CardHeader,CardTitle} from "@/components/ui/card"
import EmptyState from "@/components/EmptyState.vue"
const notice=useNoticeStore()
const {data:status,loading:statusLoading,refresh}=useRequest("update-status",()=>updateService.getStatus())
async function doRefresh(){await updateService.refresh();refresh();notice.show("Status refreshed","success")}
</script>
