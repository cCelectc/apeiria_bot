<template>
  <div class="flex flex-col gap-6">
    <Card>
      <CardHeader class="flex-row items-center justify-between">
        <div><CardTitle>AI Profiles</CardTitle><CardDescription>User profile management</CardDescription></div>
        <Button variant="outline" size="sm" :disabled="loading" @click="refresh()"><RotateCw class="size-4" /> Refresh</Button>
      </CardHeader>
      <CardContent>
        <Skeleton v-if="loading" class="h-64 w-full" />
        <div v-else-if="profiles && profiles.length > 0" class="flex flex-col gap-2">
          <div v-for="p in profiles" :key="p.id" class="flex items-center justify-between rounded-md border p-3 text-sm">
            <div>
              <span class="font-medium">{{ p.display_name || p.id }}</span>
              <span class="ml-2 text-muted-foreground">{{ p.preferred_name || '-' }}</span>
            </div>
            <div class="flex items-center gap-2">
              <StatusBadge :variant="p.enabled !== false ? 'success' : 'default'">{{ p.enabled !== false ? 'Active' : 'Disabled' }}</StatusBadge>
              <Button variant="ghost" size="icon" class="size-8" @click="editProfile(p)"><Pencil class="size-4" /></Button>
              <Button variant="ghost" size="icon" class="size-8" @click="deleteProfile(p.id)"><Trash class="size-4 text-destructive" /></Button>
            </div>
          </div>
        </div>
        <EmptyState v-else title="No profiles" />
      </CardContent>
    </Card>

    <Dialog :open="showEdit" @update:open="showEdit = $event">
      <DialogContent class="sm:max-w-md">
        <DialogHeader><DialogTitle>Edit Profile</DialogTitle></DialogHeader>
        <form class="flex flex-col gap-4" @submit.prevent="doSave">
          <div class="flex flex-col gap-2"><Label>Display Name</Label><Input v-model="editForm.display_name" /></div>
          <div class="flex flex-col gap-2"><Label>Preferred Name</Label><Input v-model="editForm.preferred_name" /></div>
          <div class="flex items-center gap-2"><Switch :checked="editForm.enabled" @update:checked="editForm.enabled = $event" /><Label>Enabled</Label></div>
          <DialogFooter>
            <Button variant="outline" type="button" @click="showEdit = false">Cancel</Button>
            <Button type="submit">Save</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue"
import { RotateCw, Pencil, Trash } from "@lucide/vue"
import { useRequest } from "@/composables/useRequest"
import client from "@/api/client"
import { useNoticeStore } from "@/stores/notice"
import { getApiErrorMessage } from "@/api/client"
import { aiSessionsService } from "@/api/services/ai-sessions"
import Button from "@/components/ui/button/Button.vue"
import Input from "@/components/ui/input/Input.vue"
import Label from "@/components/ui/label/Label.vue"
import Switch from "@/components/ui/switch/Switch.vue"
import Skeleton from "@/components/ui/skeleton/Skeleton.vue"
import Dialog from "@/components/ui/dialog/Dialog.vue"
import { DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import Card from "@/components/ui/card/Card.vue"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import StatusBadge from "@/components/StatusBadge.vue"
import EmptyState from "@/components/EmptyState.vue"

const notice = useNoticeStore()
const { data: profiles, loading, refresh } = useRequest("ai-profiles", () => aiSessionsService.getProfiles())

const showEdit = ref(false)
const editTargetId = ref("")
const editForm = reactive({ display_name: "", preferred_name: "", enabled: true })

function editProfile(p: Record<string, unknown>) {
  editTargetId.value = p.id as string
  editForm.display_name = (p.display_name as string) ?? ""
  editForm.preferred_name = (p.preferred_name as string) ?? ""
  editForm.enabled = p.enabled !== false
  showEdit.value = true
}

async function doSave() {
  try {
    await client.patch("/ai/profiles", { ...editForm, id: editTargetId.value })
    showEdit.value = false
    refresh()
    notice.show("Profile saved", "success")
  } catch (err) { notice.show(getApiErrorMessage(err, "Failed"), "error") }
}

async function deleteProfile(id: string) {
  try { await client.delete("/ai/profiles", { params: { profile_id: id } }); refresh(); notice.show("Deleted", "success") }
  catch (err) { notice.show(getApiErrorMessage(err, "Failed"), "error") }
}
</script>
