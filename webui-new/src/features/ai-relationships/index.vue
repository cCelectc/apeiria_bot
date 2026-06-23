<template>
  <Card>
    <CardHeader><CardTitle>Relationships</CardTitle><CardDescription>User-bot affinity scores</CardDescription></CardHeader>
    <CardContent>
      <Skeleton v-if="loading" class="h-64 w-full" />
      <div v-else-if="relationships && relationships.length > 0" class="flex flex-col gap-2">
        <div v-for="r in relationships" :key="r.user_id" class="rounded-md border p-3 text-sm">
          <div class="flex items-center justify-between">
            <span class="font-medium">{{ r.user_id }}</span>
            <div class="flex items-center gap-2">
              <StatusBadge :variant="(r.warmth ?? 0) > 0.5 ? 'success' : 'default'">Score: {{ r.score }}</StatusBadge>
              <Button variant="ghost" size="icon" class="size-8" @click="adjustScore(r)"><Pencil class="size-4" /></Button>
            </div>
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

  <Dialog :open="showAdjust" @update:open="showAdjust = $event">
    <DialogContent class="sm:max-w-sm">
      <DialogHeader><DialogTitle>Adjust Score for {{ adjustTarget?.user_id }}</DialogTitle></DialogHeader>
      <div class="flex flex-col gap-4">
        <div class="flex flex-col gap-2"><Label>New Score</Label><Input v-model="adjustForm.score" type="number" min="0" max="1" step="0.1" /></div>
        <div class="flex flex-col gap-2"><Label>Reason</Label><Input v-model="adjustForm.reason" /></div>
        <Button @click="doAdjust">Save</Button>
      </div>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue"
import { Pencil } from "@lucide/vue"
import { useRequest } from "@/composables/useRequest"
import client from "@/api/client"
import { useNoticeStore } from "@/stores/notice"
import { getApiErrorMessage } from "@/api/client"
import { aiSessionsService } from "@/api/services/ai-sessions"
import Button from "@/components/ui/button/Button.vue"
import Input from "@/components/ui/input/Input.vue"
import Label from "@/components/ui/label/Label.vue"
import Skeleton from "@/components/ui/skeleton/Skeleton.vue"
import Dialog from "@/components/ui/dialog/Dialog.vue"
import { DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import Card from "@/components/ui/card/Card.vue"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import StatusBadge from "@/components/StatusBadge.vue"
import EmptyState from "@/components/EmptyState.vue"

const notice = useNoticeStore()
const { data: relationships, loading, refresh } = useRequest("ai-relationships", () => aiSessionsService.getRelationships())

const showAdjust = ref(false)
const adjustTarget = ref<Record<string, unknown> | null>(null)
const adjustForm = reactive({ score: "0.5", reason: "" })

function adjustScore(r: Record<string, unknown>) {
  adjustTarget.value = r
  adjustForm.score = String(r.score ?? 0.5)
  adjustForm.reason = ""
  showAdjust.value = true
}

async function doAdjust() {
  if (!adjustTarget.value) return
  try {
    await client.patch("/ai/relationships", { user_id: adjustTarget.value.user_id, session_id: adjustTarget.value.session_id, score: parseFloat(adjustForm.score), reason: adjustForm.reason })
    showAdjust.value = false
    refresh()
    notice.show("Score updated", "success")
  } catch (err) { notice.show(getApiErrorMessage(err, "Failed"), "error") }
}
</script>
