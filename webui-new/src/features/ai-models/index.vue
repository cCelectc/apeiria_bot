<template>
  <div class="flex flex-col gap-6">
    <div class="flex items-center justify-between">
      <div />
      <Button @click="showCreateSource = true"><Plus class="size-4" /> Add Source</Button>
    </div>

    <Skeleton v-if="sourcesLoading" class="h-64 w-full" />

    <div v-if="sources && !sourcesLoading" class="grid gap-4">
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
    <EmptyState v-if="sources && sources.length === 0" title="No AI sources" />

    <!-- AI Profiles & Routes tabs -->
    <Tabs v-model="configTab" class="w-full">
      <TabsList>
        <TabsTrigger value="profiles">Model Profiles</TabsTrigger>
        <TabsTrigger value="routes">Model Routes</TabsTrigger>
      </TabsList>
      <TabsContent value="profiles" class="mt-4">
        <Card>
          <CardHeader class="flex-row items-center justify-between">
            <CardTitle>Model Profiles</CardTitle>
            <Button variant="outline" size="sm" :disabled="profilesLoading" @click="loadProfiles()">Refresh</Button>
          </CardHeader>
          <CardContent>
            <Skeleton v-if="profilesLoading" class="h-32 w-full" />
            <div v-else-if="profiles && profiles.length > 0" class="flex flex-col gap-2">
              <div v-for="p in profiles" :key="String((p as Record<string,unknown>).id)" class="flex items-center justify-between rounded-md border p-2 text-sm">
                <div>
                  <span class="font-medium">{{ p.name || p.id }}</span>
                  <span class="ml-2 text-xs text-muted-foreground">task: {{ String((p as Record<string,unknown>).task_class ?? '') }}</span>
                </div>
                <StatusBadge variant="default">{{ p.priority }}</StatusBadge>
              </div>
            </div>
            <EmptyState v-else title="No profiles" />
          </CardContent>
        </Card>
      </TabsContent>
      <TabsContent value="routes" class="mt-4">
        <Card>
          <CardHeader class="flex-row items-center justify-between">
            <CardTitle>Model Routes</CardTitle>
            <Button variant="outline" size="sm" :disabled="routesLoading" @click="loadRoutes()">Refresh</Button>
          </CardHeader>
          <CardContent>
            <Skeleton v-if="routesLoading" class="h-32 w-full" />
            <EmptyState v-else title="Model routes" description="Route configuration coming soon." />
          </CardContent>
        </Card>
      </TabsContent>
    </Tabs>

    <!-- Create Source Dialog -->
    <Dialog :open="showCreateSource" @update:open="showCreateSource = $event">
      <DialogContent class="sm:max-w-md">
        <DialogHeader><DialogTitle>Add AI Source</DialogTitle></DialogHeader>
        <form class="flex flex-col gap-4" @submit.prevent="doCreateSource">
          <div class="flex flex-col gap-2"><Label>Source ID</Label><Input v-model="srcForm.source_id" /></div>
          <div class="flex flex-col gap-2"><Label>Name</Label><Input v-model="srcForm.name" /></div>
          <div class="flex flex-col gap-2"><Label>Provider</Label><Input v-model="srcForm.provider" /></div>
          <div class="flex flex-col gap-2"><Label>API Base</Label><Input v-model="srcForm.api_base" /></div>
          <div class="flex flex-col gap-2"><Label>API Key</Label><Input v-model="srcForm.api_key" type="password" /></div>
          <DialogFooter>
            <Button variant="outline" type="button" @click="showCreateSource = false">Cancel</Button>
            <Button type="submit" :disabled="!srcForm.source_id">Create</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>

    <ConfirmDialog :open="showDeleteConfirm" title="Delete Source" :description="'Delete ' + deleteTarget?.name + '?'"
      confirm-label="Delete" @update:open="showDeleteConfirm = $event" @confirm="doDeleteSource" @cancel="showDeleteConfirm = false" />
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue"
import { Plus, Trash } from "@lucide/vue"
import { useRequest } from "@/composables/useRequest"
import { aiModelsService, type AISource } from "@/api/services/ai-models"
import client from "@/api/client"
import { getApiErrorMessage } from "@/api/client"
import { useNoticeStore } from "@/stores/notice"
import Button from "@/components/ui/button/Button.vue"
import Input from "@/components/ui/input/Input.vue"
import Label from "@/components/ui/label/Label.vue"
import Skeleton from "@/components/ui/skeleton/Skeleton.vue"
import Dialog from "@/components/ui/dialog/Dialog.vue"
import { DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import Tabs from "@/components/ui/tabs/Tabs.vue"
import { TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import Card from "@/components/ui/card/Card.vue"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import StatusBadge from "@/components/StatusBadge.vue"
import EmptyState from "@/components/EmptyState.vue"
import ConfirmDialog from "@/components/ConfirmDialog.vue"

const notice = useNoticeStore()
const configTab = ref("profiles")
const { data: sources, loading: sourcesLoading, refresh } = useRequest("ai-sources", () => aiModelsService.getSources())

const showCreateSource = ref(false)
const srcForm = reactive({ source_id: "", name: "", provider: "", api_base: "", api_key: "" })

async function doCreateSource() {
  try { await aiModelsService.createSource({ ...srcForm }); showCreateSource.value = false; refresh(); notice.show("Source created", "success") }
  catch (err) { notice.show(getApiErrorMessage(err, "Failed"), "error") }
}

const showDeleteConfirm = ref(false)
const deleteTarget = ref<AISource | null>(null)
function confirmDeleteSource(src: AISource) { deleteTarget.value = src; showDeleteConfirm.value = true }
async function doDeleteSource() {
  if (!deleteTarget.value) return
  try { await aiModelsService.deleteSource(deleteTarget.value.source_id); showDeleteConfirm.value = false; refresh(); notice.show("Deleted", "success") }
  catch (err) { notice.show(getApiErrorMessage(err, "Failed"), "error") }
}
async function fetchModels(src: AISource) {
  try { await aiModelsService.fetchModels(src.source_id); notice.show("Models fetched", "success") }
  catch (err) { notice.show(getApiErrorMessage(err, "Failed"), "error") }
}

// Profiles
const profiles = ref<Record<string, unknown>[] | null>(null)
const profilesLoading = ref(false)
async function loadProfiles() { profilesLoading.value = true; try { profiles.value = await client.get("/ai/model-profiles").then(r => r.data) } finally { profilesLoading.value = false } }

// Routes
const routes = ref<Record<string, unknown>[] | null>(null)
const routesLoading = ref(false)
async function loadRoutes() { routesLoading.value = true; try { routes.value = await client.get("/ai/model-routes").then(r => r.data) } finally { routesLoading.value = false } }
</script>
