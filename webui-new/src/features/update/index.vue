<template>
  <div class="flex flex-col gap-6">
    <Card>
      <CardHeader class="flex-row items-center justify-between">
        <div><CardTitle>Project Update</CardTitle><CardDescription>Git-based update management</CardDescription></div>
        <div class="flex items-center gap-2">
          <Button variant="outline" size="sm" :disabled="statusLoading" @click="doRefresh">Check for updates</Button>
          <Button variant="outline" size="sm" :disabled="!status" @click="doPlan">Preview Plan</Button>
        </div>
      </CardHeader>
      <CardContent>
        <Skeleton v-if="statusLoading" class="h-32 w-full" />
        <div v-else-if="status" class="flex flex-col gap-3 text-sm">
          <div class="flex gap-4"><span class="text-muted-foreground">Branch:</span><span class="font-medium">{{ status.active_branch || '-' }}</span></div>
          <div class="flex gap-4"><span class="text-muted-foreground">Commit:</span><span class="font-mono text-xs">{{ status.head_sha?.slice(0, 8) || '-' }}</span></div>
          <Badge v-if="status.updates_available" variant="default">Updates Available</Badge>
        </div>
        <EmptyState v-else title="No status" />
      </CardContent>
    </Card>

    <!-- Plan Dialog -->
    <Dialog :open="showPlan" @update:open="showPlan = $event">
      <DialogContent class="sm:max-w-lg">
        <DialogHeader><DialogTitle>Update Plan</DialogTitle></DialogHeader>
        <Skeleton v-if="planLoading" class="h-48 w-full" />
        <div v-else class="flex flex-col gap-2 text-sm">
          <pre class="rounded-md bg-muted p-3 font-mono text-xs whitespace-pre-wrap">{{ planText || 'No changes detected.' }}</pre>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="showPlan = false">Close</Button>
          <Button :disabled="!planText" @click="doUpdate">Execute Update</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- Task Dialog -->
    <TaskDialog :open="showTask" title="Update Progress" :steps="taskSteps" @update:open="showTask = false" />
  </div>
</template>
<script setup lang="ts">
import { ref } from "vue"
import { useRequest } from "@/composables/useRequest"
import { updateService } from "@/api/services/update"
import { useNoticeStore } from "@/stores/notice"
import Button from "@/components/ui/button/Button.vue"
import Skeleton from "@/components/ui/skeleton/Skeleton.vue"
import Badge from "@/components/ui/badge/Badge.vue"
import Dialog from "@/components/ui/dialog/Dialog.vue"
import { DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import Card from "@/components/ui/card/Card.vue"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import EmptyState from "@/components/EmptyState.vue"
import TaskDialog, { type TaskStep } from "@/components/TaskDialog.vue"
const notice = useNoticeStore()
const { data: status, loading: statusLoading, refresh } = useRequest("update-status", () => updateService.getStatus())
async function doRefresh() { await updateService.refresh(); refresh(); notice.show("Status refreshed", "success") }
const showPlan = ref(false); const planLoading = ref(false); const planText = ref("")
async function doPlan() { planLoading.value = true; showPlan.value = true
  try { planText.value = JSON.stringify(await updateService.plan(), null, 2) }
  catch { planText.value = "Failed to load plan" }
  finally { planLoading.value = false }
}
const showTask = ref(false); const taskSteps = ref<TaskStep[]>([{ label: "Planning", status: "pending" }, { label: "Updating", status: "pending" }])
async function doUpdate() {
  showPlan.value = false; showTask.value = true; taskSteps.value[0].status = "running"
  try { await updateService.createTask({ update: true }); taskSteps.value[0].status = "done"; taskSteps.value[1].status = "done"; notice.show("Update started", "success") }
  catch { taskSteps.value[0].status = "failed" }
}
</script>
