<template>
  <div class="flex flex-col gap-6">
    <div class="flex items-center justify-between">
      <div />
      <Button @click="showCreate = true"><Plus class="size-4" /> Add Rule</Button>
    </div>

    <Skeleton v-if="loading" class="h-64 w-full" />

    <div v-if="rules && !loading" class="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader><CardTitle>Access Rules</CardTitle></CardHeader>
        <CardContent>
          <DataTable
            v-if="rules.length > 0"
            :columns="ruleCols"
            :rows="rules as unknown as Record<string, unknown>[]"
          >
            <template #cell-effect="{ row }">
              <StatusBadge :variant="(row as unknown as AccessRule).effect === 'allow' ? 'success' : 'error'">
                {{ (row as unknown as AccessRule).effect }}
              </StatusBadge>
            </template>
            <template #cell-actions="{ row }">
              <Button variant="ghost" size="icon" class="size-8" @click="confirmRemove(row as unknown as AccessRule)">
                <Trash class="size-4 text-destructive" />
              </Button>
            </template>
          </DataTable>
          <EmptyState v-else title="No rules" description="Create a rule to control access." />
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Plugin Access Modes</CardTitle></CardHeader>
        <CardContent>
          <EmptyState title="Plugin list unavailable" description="Access modes are set per plugin." />
        </CardContent>
      </Card>
    </div>

    <!-- Create Rule Dialog -->
    <Dialog :open="showCreate" @update:open="showCreate = $event">
      <DialogContent class="sm:max-w-md">
        <DialogHeader><DialogTitle>Add Access Rule</DialogTitle></DialogHeader>
        <form class="flex flex-col gap-4" @submit.prevent="doCreate">
          <div class="flex flex-col gap-2">
            <Label>Subject Type</Label>
            <Select v-model="form.subject_type">
              <SelectTrigger><SelectValue placeholder="Select..." /></SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="user">User</SelectItem>
                  <SelectItem value="group">Group</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
          </div>
          <div class="flex flex-col gap-2">
            <Label>Subject ID</Label>
            <Input v-model="form.subject_id" placeholder="User or group ID" />
          </div>
          <div class="flex flex-col gap-2">
            <Label>Plugin Module</Label>
            <Input v-model="form.plugin_module" placeholder="e.g. nonebot_plugin_xxx" />
          </div>
          <div class="flex flex-col gap-2">
            <Label>Effect</Label>
            <ToggleGroup v-model="form.effect" type="single">
              <ToggleGroupItem value="allow">Allow</ToggleGroupItem>
              <ToggleGroupItem value="deny">Deny</ToggleGroupItem>
            </ToggleGroup>
          </div>
          <DialogFooter>
            <Button variant="outline" type="button" @click="showCreate = false">Cancel</Button>
            <Button type="submit" :disabled="!valid">Create</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>

    <!-- Delete Confirm -->
    <ConfirmDialog
      :open="showRemoveConfirm"
      title="Remove Rule"
      :description="`Remove rule for ${removeTarget?.subject_type}:${removeTarget?.subject_id} on ${removeTarget?.plugin_module}?`"
      confirm-label="Remove"
      @update:open="showRemoveConfirm = $event"
      @confirm="doRemove"
      @cancel="showRemoveConfirm = false"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from "vue"
import { Plus, Trash } from "@lucide/vue"
import { useRequest } from "@/composables/useRequest"
import { permissionsService, type AccessRule } from "@/api/services/permissions"
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
import CardContent from "@/components/ui/card/CardContent.vue"
import CardHeader from "@/components/ui/card/CardHeader.vue"
import CardTitle from "@/components/ui/card/CardTitle.vue"
import Select from "@/components/ui/select/Select.vue"
import SelectContent from "@/components/ui/select/SelectContent.vue"
import SelectGroup from "@/components/ui/select/SelectGroup.vue"
import SelectItem from "@/components/ui/select/SelectItem.vue"
import SelectTrigger from "@/components/ui/select/SelectTrigger.vue"
import SelectValue from "@/components/ui/select/SelectValue.vue"
import ToggleGroup from "@/components/ui/toggle-group/ToggleGroup.vue"
import ToggleGroupItem from "@/components/ui/toggle-group/ToggleGroupItem.vue"
import DataTable from "@/components/DataTable.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import EmptyState from "@/components/EmptyState.vue"
import ConfirmDialog from "@/components/ConfirmDialog.vue"

const notice = useNoticeStore()
const ruleCols = [
  { key: "subject_type", label: "Type" },
  { key: "subject_id", label: "ID" },
  { key: "plugin_module", label: "Plugin" },
  { key: "effect", label: "Effect" },
  { key: "actions", label: "", class: "w-[60px]" },
]

const { data: rules, loading, refresh } = useRequest("permissions", () => permissionsService.listRules())

const showCreate = ref(false)
const form = reactive({
  subject_type: "user",
  subject_id: "",
  plugin_module: "",
  effect: "allow",
})
const valid = computed(() => form.subject_id && form.plugin_module)

async function doCreate() {
  try {
    await permissionsService.createRule({ ...form } as AccessRule)
    showCreate.value = false
    form.subject_id = ""
    form.plugin_module = ""
    refresh()
    notice.show("Rule created", "success")
  } catch (err) {
    notice.show(getApiErrorMessage(err, "Failed"), "error")
  }
}

const showRemoveConfirm = ref(false)
const removeTarget = ref<AccessRule | null>(null)

function confirmRemove(rule: AccessRule) {
  removeTarget.value = rule
  showRemoveConfirm.value = true
}

async function doRemove() {
  if (!removeTarget.value) return
  try {
    await permissionsService.deleteRule(removeTarget.value)
    showRemoveConfirm.value = false
    refresh()
    notice.show("Rule removed", "success")
  } catch (err) {
    notice.show(getApiErrorMessage(err, "Failed"), "error")
  }
}
</script>
