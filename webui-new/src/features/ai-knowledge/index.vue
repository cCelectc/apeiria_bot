<template>
  <Card>
    <CardHeader class="flex-row items-center justify-between">
      <div><CardTitle>Knowledge Base</CardTitle><CardDescription>RAG knowledge documents</CardDescription></div>
      <Button variant="outline" size="sm" @click="showUpload = true"><Plus class="size-4" /> Upload</Button>
    </CardHeader>
    <CardContent>
      <Skeleton v-if="loading" class="h-48 w-full" />
      <div v-else-if="docs && docs.length > 0" class="flex flex-col gap-3">
        <div v-for="d in docs" :key="d.id" class="flex items-center justify-between rounded-md border p-3 text-sm">
          <div class="min-w-0 flex-1">
            <span class="font-medium truncate">{{ d.source_file_name }}</span>
            <span class="ml-2 text-xs text-muted-foreground">{{ d.chunk_count ?? 0 }} chunks</span>
          </div>
          <div class="flex items-center gap-1 ml-2 shrink-0">
            <Button variant="ghost" size="sm" @click="viewChunks(d.id)">Chunks</Button>
            <Button variant="ghost" size="sm" @click="rebuildDoc(d.id)">Rebuild</Button>
            <Button variant="ghost" size="icon" class="size-8" @click="deleteDoc(d.id)">
              <Trash class="size-4 text-destructive" />
            </Button>
          </div>
        </div>
      </div>
      <EmptyState v-else title="No documents" />
    </CardContent>
  </Card>

  <!-- Retrieval Preview -->
  <Card>
    <CardHeader><CardTitle>Retrieval Preview</CardTitle></CardHeader>
    <CardContent>
      <div class="flex items-center gap-2">
        <Input v-model="retrievalQuery" placeholder="Enter query to test retrieval..." class="flex-1" @keydown.enter="doRetrieval" />
        <Button :disabled="!retrievalQuery || retrievalLoading" @click="doRetrieval">Search</Button>
      </div>
      <div v-if="retrievalResults" class="mt-4 flex flex-col gap-2">
        <div v-for="(r, i) in retrievalResults" :key="i" class="rounded-md border p-2 text-sm">
          <div class="flex items-center justify-between text-xs text-muted-foreground">
            <span>{{ r.document_id }}</span>
            <Badge variant="outline">Score: {{ Number(r.score).toFixed(3) }}</Badge>
          </div>
          <p class="mt-1">{{ String(r.content).slice(0, 300) }}</p>
        </div>
      </div>
    </CardContent>
  </Card>

  <!-- Chunks Dialog -->
  <Dialog :open="showChunks" @update:open="showChunks = $event">
    <DialogContent class="sm:max-w-xl">
      <DialogHeader><DialogTitle>Document Chunks</DialogTitle></DialogHeader>
      <Skeleton v-if="chunksLoading" class="h-48 w-full" />
      <div v-else class="flex flex-col gap-2 max-h-96 overflow-auto">
        <div v-for="(c, i) in chunks" :key="i" class="rounded-md border p-2 text-xs">
          <span class="text-muted-foreground">#{{ i + 1 }}</span>
          <p class="mt-1">{{ String(c.content).slice(0, 500) }}</p>
        </div>
        <EmptyState v-if="!chunks || chunks.length === 0" title="No chunks" />
      </div>
    </DialogContent>
  </Dialog>

  <!-- Upload Dialog -->
  <Dialog :open="showUpload" @update:open="showUpload = $event">
    <DialogContent class="sm:max-w-md">
      <DialogHeader><DialogTitle>Upload Document</DialogTitle></DialogHeader>
      <form class="flex flex-col gap-4" @submit.prevent="doUpload">
        <div class="flex flex-col gap-2"><Label>Filename</Label><Input v-model="uploadName" placeholder="document.txt" /></div>
        <div class="flex flex-col gap-2"><Label>Content</Label><Textarea v-model="uploadContent" rows="8" /></div>
        <DialogFooter>
          <Button variant="outline" type="button" @click="showUpload = false">Cancel</Button>
          <Button type="submit" :disabled="!uploadName || !uploadContent">Upload</Button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { Plus, Trash } from "@lucide/vue"
import { useRequest } from "@/composables/useRequest"
import { aiKnowledgeService } from "@/api/services/ai-knowledge"
import { getApiErrorMessage } from "@/api/client"
import { useNoticeStore } from "@/stores/notice"
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
import Card from "@/components/ui/card/Card.vue"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import EmptyState from "@/components/EmptyState.vue"

const notice = useNoticeStore()
const { data: docs, loading, refresh } = useRequest("ai-knowledge", () => aiKnowledgeService.listDocuments())

// Upload
const showUpload = ref(false)
const uploadName = ref("")
const uploadContent = ref("")

async function doUpload() {
  try {
    await aiKnowledgeService.upload(uploadName.value, uploadContent.value)
    showUpload.value = false
    uploadName.value = ""
    uploadContent.value = ""
    refresh()
    notice.show("Document uploaded", "success")
  } catch (err) { notice.show(getApiErrorMessage(err, "Failed"), "error") }
}

// Chunks
const showChunks = ref(false)
const chunks = ref<Record<string, unknown>[]>([])
const chunksLoading = ref(false)

async function viewChunks(id: string) {
  showChunks.value = true
  chunksLoading.value = true
  try { chunks.value = await aiKnowledgeService.getChunks(id) } catch { chunks.value = [] }
  finally { chunksLoading.value = false }
}

async function rebuildDoc(id: string) {
  try { await aiKnowledgeService.rebuild(id); notice.show("Rebuilding...", "success") }
  catch (err) { notice.show(getApiErrorMessage(err, "Failed"), "error") }
}

async function deleteDoc(id: string) {
  try { await aiKnowledgeService.deleteDocument(id); refresh(); notice.show("Deleted", "success") }
  catch (err) { notice.show(getApiErrorMessage(err, "Failed"), "error") }
}

// Retrieval
const retrievalQuery = ref("")
const retrievalLoading = ref(false)
const retrievalResults = ref<Record<string, unknown>[] | null>(null)

async function doRetrieval() {
  retrievalLoading.value = true
  try { retrievalResults.value = await aiKnowledgeService.retrievalPreview(retrievalQuery.value) as unknown as Record<string, unknown>[]
  } catch { retrievalResults.value = null }
  finally { retrievalLoading.value = false }
}
</script>
