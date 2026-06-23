<template>
  <div class="flex flex-col gap-6">
    <div class="flex items-center justify-between">
      <FeedbackAlert v-if="error" :message="error" variant="destructive" />
      <Button @click="showCreate = true">
        <Plus class="size-4" />
        Add Account
      </Button>
    </div>

    <Skeleton v-if="loading" class="h-64 w-full" />
    <DataTable
      v-else-if="accounts"
      :columns="columns"
      :rows="accounts as unknown as Record<string, unknown>[]"
    >
      <template #cell-status="{ row }">
        <StatusBadge :variant="(row as unknown as AccountItem).is_disabled ? 'default' : 'success'">
          {{ (row as unknown as AccountItem).is_disabled ? 'Disabled' : 'Active' }}
        </StatusBadge>
      </template>
      <template #cell-actions="{ row }">
        <div class="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            class="size-8"
            @click="confirmDisable(row as unknown as AccountItem)"
          >
            <Ban class="size-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            class="size-8"
            @click="confirmResetPassword(row as unknown as AccountItem)"
          >
            <Key class="size-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            class="size-8"
            @click="confirmDelete(row as unknown as AccountItem)"
          >
            <Trash class="size-4 text-destructive" />
          </Button>
        </div>
      </template>
    </DataTable>

    <!-- Create Dialog -->
    <Dialog :open="showCreate" @update:open="showCreate = $event">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create Account</DialogTitle>
        </DialogHeader>
        <form class="flex flex-col gap-4" @submit.prevent="doCreate">
          <div class="flex flex-col gap-2">
            <Label for="new-username">Username</Label>
            <Input id="new-username" v-model="newUsername" placeholder="Username" />
          </div>
          <div class="flex flex-col gap-2">
            <Label for="new-password">Password</Label>
            <Input id="new-password" v-model="newPassword" type="password" placeholder="Min 8 chars" />
          </div>
          <DialogFooter>
            <Button variant="outline" type="button" @click="showCreate = false">Cancel</Button>
            <Button type="submit" :disabled="!newUsername || newPassword.length < 8">
              Create
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>

    <!-- Delete Confirm -->
    <ConfirmDialog
      :open="showDeleteConfirm"
      title="Delete Account"
      :description="`Delete ${deleteTarget?.username}?`"
      confirm-label="Delete"
      @update:open="showDeleteConfirm = $event"
      @confirm="doDelete"
      @cancel="showDeleteConfirm = false"
    />

    <!-- Disable Confirm -->
    <ConfirmDialog
      :open="showDisableConfirm"
      :title="disableTarget?.is_disabled ? 'Enable Account' : 'Disable Account'"
      :description="`${disableTarget?.is_disabled ? 'Enable' : 'Disable'} ${disableTarget?.username}?`"
      :confirm-label="disableTarget?.is_disabled ? 'Enable' : 'Disable'"
      @update:open="showDisableConfirm = $event"
      @confirm="doDisable"
      @cancel="showDisableConfirm = false"
    />

    <!-- Reset Password Dialog -->
    <Dialog :open="showResetPassword" @update:open="showResetPassword = $event">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Reset Password for {{ resetTarget?.username }}</DialogTitle>
        </DialogHeader>
        <form class="flex flex-col gap-4" @submit.prevent="doResetPassword">
          <div class="flex flex-col gap-2">
            <Label for="reset-pw">New Password</Label>
            <Input id="reset-pw" v-model="resetPasswordValue" type="password" placeholder="Min 8 chars" />
          </div>
          <DialogFooter>
            <Button variant="outline" type="button" @click="showResetPassword = false">Cancel</Button>
            <Button type="submit" :disabled="resetPasswordValue.length < 8">Reset</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { Plus, Ban, Key, Trash } from "@lucide/vue"
import { useRequest } from "@/composables/useRequest"
import { accountsService, type AccountItem } from "@/api/services/accounts"
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
import DataTable from "@/components/DataTable.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import FeedbackAlert from "@/components/FeedbackAlert.vue"
import ConfirmDialog from "@/components/ConfirmDialog.vue"

const notice = useNoticeStore()
const columns = [
  { key: "username", label: "Username" },
  { key: "status", label: "Status" },
  { key: "last_login_at", label: "Last Login" },
  { key: "actions", label: "", class: "w-[120px]" },
]

const { data: accounts, loading, error, refresh } = useRequest(
  "accounts",
  () => accountsService.list(),
)

// Create
const showCreate = ref(false)
const newUsername = ref("")
const newPassword = ref("")

async function doCreate() {
  try {
    await accountsService.create({
      username: newUsername.value,
      password: newPassword.value,
    })
    showCreate.value = false
    newUsername.value = ""
    newPassword.value = ""
    refresh()
    notice.show("Account created", "success")
  } catch (err) {
    notice.show(getApiErrorMessage(err, "Failed to create"), "error")
  }
}

// Delete
const showDeleteConfirm = ref(false)
const deleteTarget = ref<AccountItem | null>(null)

function confirmDelete(account: AccountItem) {
  deleteTarget.value = account
  showDeleteConfirm.value = true
}

async function doDelete() {
  if (!deleteTarget.value) return
  try {
    await accountsService.delete(deleteTarget.value.user_id)
    showDeleteConfirm.value = false
    refresh()
    notice.show("Account deleted", "success")
  } catch (err) {
    notice.show(getApiErrorMessage(err, "Failed to delete"), "error")
  }
}

// Disable/Enable
const showDisableConfirm = ref(false)
const disableTarget = ref<AccountItem | null>(null)

function confirmDisable(account: AccountItem) {
  disableTarget.value = account
  showDisableConfirm.value = true
}

async function doDisable() {
  if (!disableTarget.value) return
  try {
    await accountsService.disable(disableTarget.value.user_id)
    showDisableConfirm.value = false
    refresh()
    notice.show("Account updated", "success")
  } catch (err) {
    notice.show(getApiErrorMessage(err, "Failed to update"), "error")
  }
}

// Reset Password
const showResetPassword = ref(false)
const resetTarget = ref<AccountItem | null>(null)
const resetPasswordValue = ref("")

function confirmResetPassword(account: AccountItem) {
  resetTarget.value = account
  resetPasswordValue.value = ""
  showResetPassword.value = true
}

async function doResetPassword() {
  if (!resetTarget.value) return
  try {
    await accountsService.resetPassword(resetTarget.value.user_id, resetPasswordValue.value)
    showResetPassword.value = false
    notice.show("Password reset", "success")
  } catch (err) {
    notice.show(getApiErrorMessage(err, "Failed to reset"), "error")
  }
}
</script>
