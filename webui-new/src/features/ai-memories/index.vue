<template>
  <div class="flex flex-col gap-6">
    <div class="flex items-center justify-between">
      <FilterBar v-model="search" placeholder="Search memories..." :filters="filterDefs" @filter-change="onFilter" />
      <div class="flex items-center gap-2">
        <Button variant="outline" size="sm" @click="bulkArchive">
          <Archive class="size-4" /> Archive Selected
        </Button>
        <Button variant="outline" size="sm" @click="showCreate = true">
          <Plus class="size-4" /> Add Memory
        </Button>
      </div>
    </div>

    <Skeleton v-if="loading" class="h-64 w-full" />
    <div v-else-if="memories && memories.length > 0" class="flex flex-col gap-2">
      <div v-for="m in memories" :key="m.id" class="flex items-start justify-between rounded-md border p-3 text-sm">
        <div class="flex-1 min-w-0">
          <p class="truncate">{{ m.content }}</p>
          <div class="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
            <Badge variant="outline">{{ m.layer }}</Badge>
            <Badge variant="outline">{{ m.kind }}</Badge>
            <span>Salience: {{ m.salience }}</span>
            <span>Confidence: {{ m.confidence }}</span>
          </div>
        </div>
        <div class="flex items-center gap-1 ml-2 shrink-0">
          <Button variant="ghost" size="icon" class="size-8" @click="archiveOne(m.id)"><Archive class="size-4" /></Button>
          <Button variant="ghost" size="icon" class="size-8" @click="deleteOne(m.id)"><Trash class="size-4 text-destructive" /></Button>
        </div>
      </div>
    </div>
    <EmptyState v-else title="No memories" description="Create a memory or adjust filters." />

    <!-- Create Memory Dialog -->
    <Dialog :open="showCreate" @update:open="showCreate = $event">
      <DialogContent class="sm:max-w-md">
        <DialogHeader><DialogTitle>Add Memory</DialogTitle></DialogHeader>
        <form class="flex flex-col gap-4" @submit.prevent="doCreate">
          <div class="flex flex-col gap-2">
            <Label>Content</Label>
            <Textarea v-model="form.content" rows="3" placeholder="Memory content..." />
          </div>
          <div class="grid grid-cols-2 gap-2">
            <div class="flex flex-col gap-2">
              <Label>Layer</Label>
              <Input v-model="form.layer" placeholder="e.g. user" />
            </div>
            <div class="flex flex-col gap-2">
              <Label>Kind</Label>
              <Input v-model="form.kind" placeholder="e.g. fact" />
            </div>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <div class="flex flex-col gap-2">
              <Label>Salience (0-1)</Label>
              <Input v-model="form.salience" type="number" min="0" max="1" step="0.1" />
            </div>
            <div class="flex flex-col gap-2">
              <Label>Confidence (0-1)</Label>
              <Input v-model="form.confidence" type="number" min="0" max="1" step="0.1" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" type="button" @click="showCreate = false">Cancel</Button>
            <Button type="submit" :disabled="!form.content">Create</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue"
import { useRequest } from "@/composables/useRequest"
import { aiMemoriesService } from "@/api/services/ai-memories"
import { getApiErrorMessage } from "@/api/client"
import { useNoticeStore } from "@/stores/notice"
import { Plus, Archive, Trash } from "@lucide/vue"
import Button from "@/components/ui/button/Button.vue"
import Input from "@/components/ui/input/Input.vue"
import Label from "@/components/ui/label/Label.vue"
import Textarea from "@/components/ui/textarea/Textarea.vue"
import Skeleton from "@/components/ui/skeleton/Skeleton.vue"
import Badge from "@/components/ui/badge/Badge.vue"
import Dialog from "@/components/ui/dialog/Dialog.vue"
import DialogContent from "@/components/ui/dialog/DialogContent.vue"
import DialogFooter from "@/components/ui/dialog/DialogFooter.vue"
import DialogHeader from "@/components/ui/dialog/DialogHeader.vue"
import DialogTitle from "@/components/ui/dialog/DialogTitle.vue"
import FilterBar from "@/components/FilterBar.vue"
import EmptyState from "@/components/EmptyState.vue"

const notice = useNoticeStore()
const search = ref("")
const filterDefs = [
  { key: "layer", label: "Layer", value: "", options: [
    { label: "All", value: "" }, { label: "User", value: "user" }, { label: "Session", value: "session" }
  ]},
]

const { data: memories, loading, refresh } = useRequest("ai-memories", () => aiMemoriesService.list({ query: search.value }))

function onFilter(_key: string, _value: string) {
  refresh()
}

// Create
const showCreate = ref(false)
const form = reactive({ content: "", layer: "user", kind: "fact", salience: "0.5", confidence: "0.8" })

async function doCreate() {
  try {
    await aiMemoriesService.create({ ...form, salience: parseFloat(form.salience), confidence: parseFloat(form.confidence) })
    showCreate.value = false
    refresh()
    notice.show("Memory created", "success")
  } catch (err) {
    notice.show(getApiErrorMessage(err, "Failed"), "error")
  }
}

async function archiveOne(id: string) {
  try {
    await aiMemoriesService.setLifecycle({ memory_id: id, lifecycle: "archived" })
    refresh()
    notice.show("Memory archived", "success")
  } catch (err) {
    notice.show(getApiErrorMessage(err, "Failed"), "error")
  }
}

async function deleteOne(id: string) {
  try {
    await aiMemoriesService.remove(id)
    refresh()
    notice.show("Memory deleted", "success")
  } catch (err) {
    notice.show(getApiErrorMessage(err, "Failed"), "error")
  }
}

async function bulkArchive() {
  notice.show("Bulk archive not yet implemented", "warning")
}
</script>
