<template>
  <Card>
    <CardHeader class="flex-row items-center justify-between">
      <div><CardTitle>Knowledge Base</CardTitle><CardDescription>RAG knowledge documents</CardDescription></div>
      <Button variant="outline" size="sm" @click="showUpload=true"><Plus class="size-4"/>Upload</Button>
    </CardHeader>
    <CardContent>
      <Skeleton v-if="loading" class="h-64 w-full" />
      <DataTable v-else-if="docs && docs.length > 0"
        :columns="[{key:'source_file_name',label:'Name'},{key:'status',label:'Status'}]"
        :rows="docs as unknown as Record<string,unknown>[]" />
      <EmptyState v-else title="No documents" description="Upload a document to the knowledge base." />
    </CardContent>
  </Card>

  <Dialog :open="showUpload" @update:open="showUpload=$event">
    <DialogContent class="sm:max-w-md">
      <DialogHeader><DialogTitle>Upload Document</DialogTitle></DialogHeader>
      <form class="flex flex-col gap-4" @submit.prevent="doUpload">
        <div class="flex flex-col gap-2"><Label>Filename</Label><Input v-model="uploadName" placeholder="document.txt"/></div>
        <div class="flex flex-col gap-2"><Label>Content</Label><Textarea v-model="uploadContent" rows="8"/></div>
        <DialogFooter>
          <Button variant="outline" type="button" @click="showUpload=false">Cancel</Button>
          <Button type="submit" :disabled="!uploadName||!uploadContent">Upload</Button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>
</template>
<script setup lang="ts">
import { ref } from "vue"
import { Plus } from "@lucide/vue"
import { useRequest } from "@/composables/useRequest"
import { aiKnowledgeService } from "@/api/services/ai-knowledge"
import { getApiErrorMessage } from "@/api/client"
import { useNoticeStore } from "@/stores/notice"
import Button from "@/components/ui/button/Button.vue"
import Input from "@/components/ui/input/Input.vue"
import Label from "@/components/ui/label/Label.vue"
import Textarea from "@/components/ui/textarea/Textarea.vue"
import Skeleton from "@/components/ui/skeleton/Skeleton.vue"
import Dialog from "@/components/ui/dialog/Dialog.vue"
import {DialogContent,DialogFooter,DialogHeader,DialogTitle} from "@/components/ui/dialog"
import Card from "@/components/ui/card/Card.vue"
import {CardContent,CardDescription,CardHeader,CardTitle} from "@/components/ui/card"
import DataTable from "@/components/DataTable.vue"
import EmptyState from "@/components/EmptyState.vue"
const notice=useNoticeStore()
const {data:docs,loading,refresh}=useRequest("ai-knowledge",()=>aiKnowledgeService.listDocuments())
const showUpload=ref(false)
const uploadName=ref("")
const uploadContent=ref("")
async function doUpload(){
  try{await aiKnowledgeService.upload(uploadName.value,uploadContent.value);showUpload.value=false;refresh();notice.show("Document uploaded","success")}
  catch(err){notice.show(getApiErrorMessage(err,"Failed"),"error")}
}
</script>
