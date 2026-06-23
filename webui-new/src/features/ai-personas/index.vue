<template>
  <Card>
    <CardHeader class="flex-row items-center justify-between">
      <div><CardTitle>AI Personas</CardTitle><CardDescription>Bot personality configurations</CardDescription></div>
      <Button variant="outline" size="sm" @click="showCreate=true"><Plus class="size-4"/>New Persona</Button>
    </CardHeader>
    <CardContent>
      <Skeleton v-if="loading" class="h-64 w-full" />
      <DataTable v-else-if="personas && personas.length > 0"
        :columns="[{key:'name',label:'Name'},{key:'description',label:'Description'},{key:'enabled',label:'Enabled'}]"
        :rows="personas as unknown as Record<string,unknown>[]" />
      <EmptyState v-else title="No personas" />
    </CardContent>
  </Card>

  <Dialog :open="showCreate" @update:open="showCreate=$event">
    <DialogContent class="sm:max-w-lg">
      <DialogHeader><DialogTitle>New Persona</DialogTitle></DialogHeader>
      <form class="flex flex-col gap-4" @submit.prevent="doCreate">
        <div class="flex flex-col gap-2"><Label>Name</Label><Input v-model="form.name" placeholder="e.g. friendly"/></div>
        <div class="flex flex-col gap-2"><Label>Description</Label><Input v-model="form.description"/></div>
        <div class="flex flex-col gap-2"><Label>System Prompt</Label><Textarea v-model="form.system_prompt" rows="4"/></div>
        <DialogFooter>
          <Button variant="outline" type="button" @click="showCreate=false">Cancel</Button>
          <Button type="submit" :disabled="!form.name">Create</Button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>
</template>
<script setup lang="ts">
import { reactive, ref } from "vue"
import { Plus } from "@lucide/vue"
import { useRequest } from "@/composables/useRequest"
import { aiPersonasService } from "@/api/services/ai-personas"
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
const {data:personas,loading,refresh}=useRequest("ai-personas",()=>aiPersonasService.list())
const showCreate=ref(false)
const form=reactive({name:"",description:"",system_prompt:"",style_prompt:""})
async function doCreate(){
  try{await aiPersonasService.upsert({...form});showCreate.value=false;refresh();notice.show("Persona created","success")}
  catch(err){notice.show(getApiErrorMessage(err,"Failed"),"error")}
}
</script>
