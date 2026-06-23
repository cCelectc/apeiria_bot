<template>
  <div class="flex flex-col gap-6">
    <div class="flex items-center justify-between">
      <div />
      <Button variant="outline" size="sm" @click="showCreate = true"><Plus class="size-4" /> New Persona</Button>
    </div>

    <Skeleton v-if="loading" class="h-64 w-full" />
    <div v-if="personas && !loading">
      <div v-for="p in personas" :key="String((p as Record<string,unknown>).id)" class="flex items-center justify-between rounded-md border p-3 mb-2 text-sm">
        <div>
          <span class="font-medium">{{ p.name }}</span>
          <span class="ml-2 text-xs text-muted-foreground">{{ p.description }}</span>
        </div>
        <div class="flex items-center gap-2">
          <StatusBadge :variant="p.enabled !== false ? 'success' : 'default'">{{ p.enabled !== false ? 'On' : 'Off' }}</StatusBadge>
          <Button variant="ghost" size="icon" class="size-8" @click="editPersona(p)"><Pencil class="size-4" /></Button>
        </div>
      </div>
    </div>

    <!-- Bindings -->
    <Card>
      <CardHeader class="flex-row items-center justify-between">
        <div><CardTitle>Persona Bindings</CardTitle><CardDescription>Map personas to sessions or users</CardDescription></div>
        <Button variant="outline" size="sm" :disabled="bindingsLoading" @click="loadBindings()">Refresh</Button>
      </CardHeader>
      <CardContent>
        <Skeleton v-if="bindingsLoading" class="h-32 w-full" />
        <div v-else-if="bindings && bindings.length > 0" class="flex flex-col gap-2">
          <div v-for="b in bindings" :key="String((b as Record<string,unknown>).id)" class="flex items-center justify-between rounded-md bg-muted px-3 py-2 text-sm">
            <span>{{ String((b as Record<string,unknown>).scope_type ?? '') }}: {{ String((b as Record<string,unknown>).scope_id ?? '') }}</span>
            <StatusBadge variant="default">{{ b.persona_id }}</StatusBadge>
          </div>
        </div>
        <EmptyState v-else title="No bindings" />
      </CardContent>
    </Card>

    <Dialog :open="showCreate" @update:open="showCreate = $event">
      <DialogContent class="sm:max-w-lg">
        <DialogHeader><DialogTitle>{{ editTarget ? 'Edit' : 'New' }} Persona</DialogTitle></DialogHeader>
        <form class="flex flex-col gap-4" @submit.prevent="doSave">
          <div class="flex flex-col gap-2"><Label>Name</Label><Input v-model="form.name" /></div>
          <div class="flex flex-col gap-2"><Label>Description</Label><Input v-model="form.description" /></div>
          <div class="flex flex-col gap-2"><Label>System Prompt</Label><Textarea v-model="form.system_prompt" rows="4" /></div>
          <div class="flex flex-col gap-2"><Label>Style Prompt</Label><Textarea v-model="form.style_prompt" rows="2" /></div>
          <DialogFooter>
            <Button variant="outline" type="button" @click="showCreate = false">Cancel</Button>
            <Button type="submit" :disabled="!form.name">Save</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue"
import { Plus, Pencil } from "@lucide/vue"
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
import { DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import Card from "@/components/ui/card/Card.vue"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import StatusBadge from "@/components/StatusBadge.vue"
import EmptyState from "@/components/EmptyState.vue"

const notice = useNoticeStore()
const { data: personas, loading, refresh } = useRequest("ai-personas", () => aiPersonasService.list())

const showCreate = ref(false)
const editTarget = ref<Record<string, unknown> | null>(null)
const form = reactive({ name: "", description: "", system_prompt: "", style_prompt: "" })

function editPersona(p: Record<string, unknown>) {
  editTarget.value = p
  form.name = (p.name as string) ?? ""
  form.description = (p.description as string) ?? ""
  form.system_prompt = (p.system_prompt as string) ?? ""
  form.style_prompt = (p.style_prompt as string) ?? ""
  showCreate.value = true
}

async function doSave() {
  try {
    await aiPersonasService.upsert({ ...form, id: editTarget.value?.id })
    showCreate.value = false
    editTarget.value = null
    refresh()
    notice.show("Persona saved", "success")
  } catch (err) { notice.show(getApiErrorMessage(err, "Failed"), "error") }
}

const bindings = ref<Record<string, unknown>[]>([])
const bindingsLoading = ref(false)
async function loadBindings() {
  bindingsLoading.value = true
  try { bindings.value = await aiPersonasService.getBindings() } catch { bindings.value = [] }
  finally { bindingsLoading.value = false }
}
</script>
