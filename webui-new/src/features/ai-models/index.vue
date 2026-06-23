<template>
  <div class="flex flex-col gap-6">
    <div class="flex items-center justify-between">
      <div />
      <Button @click="showCreateSource = true"><Plus class="size-4" /> Add Source</Button>
    </div>

    <Skeleton v-if="loading" class="h-64 w-full" />

    <div v-if="sources && !loading" class="grid gap-4">
      <Card v-for="src in sources" :key="src.source_id">
        <CardHeader class="flex-row items-center justify-between pb-2">
          <div>
            <CardTitle>{{ src.name }}</CardTitle>
            <CardDescription>{{ src.provider }}</CardDescription>
          </div>
          <div class="flex items-center gap-2">
            <StatusBadge :variant="src.enabled !== false ? 'success' : 'default'">
              {{ src.enabled !== false ? 'Enabled' : 'Disabled' }}
            </StatusBadge>
            <Button variant="outline" size="sm" @click="fetchModels(src)">Fetch Models</Button>
            <Button variant="ghost" size="icon" class="size-8" @click="confirmDeleteSource(src)">
              <Trash class="size-4 text-destructive" />
            </Button>
          </div>
        </CardHeader>
      </Card>
    </div>

    <EmptyState v-if="sources && sources.length === 0" title="No AI sources" description="Add an AI provider to get started." />

    <!-- Create Source Dialog -->
    <Dialog :open="showCreateSource" @update:open="showCreateSource = $event">
      <DialogContent class="sm:max-w-md">
        <DialogHeader><DialogTitle>Add AI Source</DialogTitle></DialogHeader>
        <form class="flex flex-col gap-4" @submit.prevent="doCreateSource">
          <div class="flex flex-col gap-2">
            <Label>Source ID</Label>
            <Input v-model="srcForm.source_id" placeholder="e.g. openai" />
          </div>
          <div class="flex flex-col gap-2">
            <Label>Name</Label>
            <Input v-model="srcForm.name" placeholder="e.g. OpenAI" />
          </div>
          <div class="flex flex-col gap-2">
            <Label>Provider</Label>
            <Input v-model="srcForm.provider" placeholder="e.g. openai" />
          </div>
          <div class="flex flex-col gap-2">
            <Label>API Base</Label>
            <Input v-model="srcForm.api_base" placeholder="https://api.openai.com/v1" />
          </div>
          <div class="flex flex-col gap-2">
            <Label>API Key</Label>
            <Input v-model="srcForm.api_key" type="password" placeholder="sk-..." />
          </div>
          <DialogFooter>
            <Button variant="outline" type="button" @click="showCreateSource = false">Cancel</Button>
            <Button type="submit" :disabled="!srcForm.source_id">Create</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>

    <!-- Delete Confirm -->
    <ConfirmDialog
      :open="showDeleteConfirm"
      title="Delete Source"
      :description="`Delete AI source '${deleteTarget?.name}'?`"
      confirm-label="Delete"
      @update:open="showDeleteConfirm = $event"
      @confirm="doDeleteSource"
      @cancel="showDeleteConfirm = false"
    />
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue"
import { Plus, Trash } from "@lucide/vue"
import { useRequest } from "@/composables/useRequest"
import { aiModelsService, type AISource } from "@/api/services/ai-models"
import { getApiErrorMessage } from "@/api/client"
import { useNoticeStore } from "@/stores/notice"
import Button from "@/components/ui/button/Button.vue"
import Input from "@/components/ui/input/Input.vue"
import Label from "@/components/ui/label/Label.vue"
import Skeleton from "@/components/ui/skeleton/Skeleton.vue"
import Dialog from "@/components/ui/dialog/Dialog.vue"
import DialogContent from "@/components/ui/dialog/DialogContent.vue"
import DialogFooter from "@/components/ui/dialog/DialogFooter.vue"
import DialogHeader from "@/components/ui/dialog/DialogHeader.vue"
import DialogTitle from "@/components/ui/dialog/DialogTitle.vue"
import Card from "@/components/ui/card/Card.vue"
import CardDescription from "@/components/ui/card/CardDescription.vue"
import CardHeader from "@/components/ui/card/CardHeader.vue"
import CardTitle from "@/components/ui/card/CardTitle.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import EmptyState from "@/components/EmptyState.vue"
import ConfirmDialog from "@/components/ConfirmDialog.vue"

const notice = useNoticeStore()
const { data: sources, loading, refresh } = useRequest("ai-sources", () => aiModelsService.getSources())

const showCreateSource = ref(false)
const srcForm = reactive({ source_id: "", name: "", provider: "", api_base: "", api_key: "" })

async function doCreateSource() {
  try {
    await aiModelsService.createSource({ ...srcForm })
    showCreateSource.value = false
    for (const k of Object.keys(srcForm)) delete (srcForm as Record<string, unknown>)[k]
    refresh()
    notice.show("Source created", "success")
  } catch (err) {
    notice.show(getApiErrorMessage(err, "Failed"), "error")
  }
}

const showDeleteConfirm = ref(false)
const deleteTarget = ref<AISource | null>(null)

function confirmDeleteSource(src: AISource) {
  deleteTarget.value = src
  showDeleteConfirm.value = true
}

async function doDeleteSource() {
  if (!deleteTarget.value) return
  try {
    await aiModelsService.deleteSource(deleteTarget.value.source_id)
    showDeleteConfirm.value = false
    refresh()
    notice.show("Source deleted", "success")
  } catch (err) {
    notice.show(getApiErrorMessage(err, "Failed"), "error")
  }
}

async function fetchModels(src: AISource) {
  try {
    await aiModelsService.fetchModels(src.source_id)
    notice.show("Models fetched", "success")
  } catch (err) {
    notice.show(getApiErrorMessage(err, "Failed to fetch models"), "error")
  }
}
</script>
