<script setup lang="ts">
import type { WebUIAccountItem } from '@/api/auth'
import type { WorkbenchMetricItem } from '@/components/management'
import {
  Clock3,
  KeyRound,
  LockKeyhole,
  Plus,
  RefreshCw,
  RotateCcwKey,
  ShieldCheck,
  Trash2,
  UserRound,
  UserRoundPlus,
} from '@lucide/vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  changePassword,
  createAccount,
  deleteAccount,
  getAccounts,
  resetAccountPassword,
  revokeOtherSessions,
  updateAccountDisabled,
} from '@/api/auth'
import { getErrorMessage } from '@/api/client'
import {
  EmptyState,
  FormField,
  MetricStrip,
  PageScaffold,
  Panel,
  StatusBadge,
} from '@/components/management'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useAuthStore } from '@/stores/auth'
import { useNoticeStore } from '@/stores/notice'
import { resolveCollectionFeedback } from '@/utils/feedbackState'

const { t } = useI18n()
const authStore = useAuthStore()
const noticeStore = useNoticeStore()

const accounts = ref<WebUIAccountItem[]>([])
const loading = ref(false)
const errorMessage = ref('')
const passwordError = ref('')
const createError = ref('')
const resetError = ref('')
const passwordSaving = ref(false)
const createSaving = ref(false)
const resetSavingFor = ref('')
const revokingSessions = ref(false)

const createForm = reactive({
  username: '',
  password: '',
  confirm_password: '',
  actor_password: '',
})
const passwordForm = reactive({
  current_password: '',
  new_password: '',
  confirm_password: '',
})
const resetForms = reactive<Record<string, {
  new_password: string
  confirm_password: string
  actor_password: string
}>>({})
const disableActorPasswords = reactive<Record<string, string>>({})
const deleteActorPasswords = reactive<Record<string, string>>({})

const currentAccount = computed(() =>
  accounts.value.find(item => item.user_id === authStore.principal?.user_id) || null,
)
const enabledCount = computed(() =>
  accounts.value.filter(item => !item.is_disabled).length,
)
const metrics = computed<WorkbenchMetricItem[]>(() => [
  {
    icon: ShieldCheck,
    key: 'accounts',
    label: t('accounts.title'),
    tone: 'info',
    value: accounts.value.length,
  },
  {
    icon: UserRound,
    key: 'enabled',
    label: t('accounts.enabled'),
    value: enabledCount.value,
  },
  {
    icon: Clock3,
    key: 'last-login',
    label: t('accounts.lastLogin'),
    value: formatTimestamp(currentAccount.value?.last_login_at),
  },
  {
    icon: LockKeyhole,
    key: 'password-changed',
    label: t('accounts.passwordChangedAt'),
    value: formatTimestamp(currentAccount.value?.password_changed_at),
  },
])
const accountFeedback = computed(() =>
  resolveCollectionFeedback({
    errorMessage: errorMessage.value,
    hasFilters: false,
    loading: loading.value,
    totalCount: accounts.value.length,
    visibleCount: accounts.value.length,
  }),
)

function formatTimestamp(value: string | null | undefined) {
  if (!value) {
    return t('common.none')
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString()
}

function isCurrentAccount(item: WebUIAccountItem) {
  return item.user_id === authStore.principal?.user_id
}

function getResetForm(userId: string) {
  if (!resetForms[userId]) {
    resetForms[userId] = {
      new_password: '',
      confirm_password: '',
      actor_password: '',
    }
  }
  return resetForms[userId]
}

function canToggle(item: WebUIAccountItem) {
  return !isCurrentAccount(item)
}

function canDelete(item: WebUIAccountItem) {
  return !isCurrentAccount(item)
}

async function loadData() {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await getAccounts()
    accounts.value = response.data
  } catch (error) {
    errorMessage.value = getErrorMessage(error, t('accounts.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function submitCreate() {
  createError.value = ''
  if (!createForm.username.trim()) {
    createError.value = t('register.usernameRequired')
    return
  }
  if (!createForm.password || !createForm.confirm_password || !createForm.actor_password) {
    createError.value = t('accounts.passwordIncomplete')
    return
  }
  if (createForm.password !== createForm.confirm_password) {
    createError.value = t('register.passwordMismatch')
    return
  }
  createSaving.value = true
  try {
    const response = await createAccount({
      username: createForm.username.trim(),
      password: createForm.password,
      actor_password: createForm.actor_password,
    })
    noticeStore.show(
      t('accounts.accountCreated', { username: response.data.username }),
      'success',
    )
    createForm.username = ''
    createForm.password = ''
    createForm.confirm_password = ''
    createForm.actor_password = ''
    await loadData()
  } catch (error) {
    createError.value = getErrorMessage(error, t('accounts.createFailed'))
  } finally {
    createSaving.value = false
  }
}

async function submitPassword() {
  passwordError.value = ''
  if (
    !passwordForm.current_password
    || !passwordForm.new_password
    || !passwordForm.confirm_password
  ) {
    passwordError.value = t('accounts.passwordIncomplete')
    return
  }
  if (passwordForm.new_password !== passwordForm.confirm_password) {
    passwordError.value = t('register.passwordMismatch')
    return
  }

  passwordSaving.value = true
  try {
    const response = await changePassword({
      current_password: passwordForm.current_password,
      new_password: passwordForm.new_password,
    })
    authStore.acceptSession(response.data.principal)
    noticeStore.show(response.data.detail || t('accounts.passwordChanged'), 'success')
    passwordForm.current_password = ''
    passwordForm.new_password = ''
    passwordForm.confirm_password = ''
    await loadData()
  } catch (error) {
    passwordError.value = getErrorMessage(error, t('accounts.passwordChangeFailed'))
  } finally {
    passwordSaving.value = false
  }
}

async function handleRevokeOtherSessions() {
  revokingSessions.value = true
  errorMessage.value = ''
  try {
    const response = await revokeOtherSessions()
    authStore.acceptSession(response.data.principal)
    noticeStore.show(response.data.detail || t('accounts.otherSessionsRevoked'), 'success')
    await loadData()
  } catch (error) {
    errorMessage.value = getErrorMessage(error, t('accounts.revokeOtherSessionsFailed'))
  } finally {
    revokingSessions.value = false
  }
}

async function toggleAccount(item: WebUIAccountItem) {
  const actorPassword = disableActorPasswords[item.user_id] || ''
  if (!actorPassword) {
    errorMessage.value = t('accounts.actorPasswordRequired')
    return
  }
  errorMessage.value = ''
  try {
    const response = await updateAccountDisabled(item.user_id, {
      is_disabled: !item.is_disabled,
      actor_password: actorPassword,
    })
    disableActorPasswords[item.user_id] = ''
    noticeStore.show(
      response.data.is_disabled
        ? t('accounts.accountDisabled', { username: response.data.username })
        : t('accounts.accountEnabled', { username: response.data.username }),
      'success',
    )
    await loadData()
  } catch (error) {
    errorMessage.value = getErrorMessage(error, t('accounts.updateFailed'))
  }
}

async function handleDelete(item: WebUIAccountItem) {
  const actorPassword = deleteActorPasswords[item.user_id] || ''
  if (!actorPassword) {
    errorMessage.value = t('accounts.actorPasswordRequired')
    return
  }
  errorMessage.value = ''
  try {
    await deleteAccount(item.user_id, { actor_password: actorPassword })
    deleteActorPasswords[item.user_id] = ''
    noticeStore.show(
      t('accounts.accountDeleted', { username: item.username }),
      'success',
    )
    await loadData()
  } catch (error) {
    errorMessage.value = getErrorMessage(error, t('accounts.deleteFailed'))
  }
}

async function handleReset(item: WebUIAccountItem) {
  const form = getResetForm(item.user_id)
  resetError.value = ''
  if (!form.new_password || !form.confirm_password || !form.actor_password) {
    resetError.value = t('accounts.passwordIncomplete')
    return
  }
  if (form.new_password !== form.confirm_password) {
    resetError.value = t('register.passwordMismatch')
    return
  }
  resetSavingFor.value = item.user_id
  try {
    const response = await resetAccountPassword(item.user_id, {
      new_password: form.new_password,
      actor_password: form.actor_password,
    })
    resetForms[item.user_id] = {
      new_password: '',
      confirm_password: '',
      actor_password: '',
    }
    noticeStore.show(
      t('accounts.passwordReset', { username: response.data.username }),
      'success',
    )
    await loadData()
  } catch (error) {
    resetError.value = getErrorMessage(error, t('accounts.resetFailed'))
  } finally {
    resetSavingFor.value = ''
  }
}

onMounted(loadData)
</script>

<template>
  <PageScaffold
    :aria-busy="accountFeedback.ariaBusy"
    :error-message="errorMessage"
    :retry-label="t('feedback.retry')"
    :subtitle="t('accounts.description')"
    :title="t('accounts.title')"
    @retry="loadData"
  >
    <template #actions>
      <Button
        :disabled="loading"
        variant="secondary"
        @click="loadData"
      >
        <RefreshCw :class="{ 'animate-spin': loading }" :size="16" />
        {{ t('common.refresh') }}
      </Button>
    </template>

    <MetricStrip :items="metrics" />

    <div class="accounts-grid">
      <Panel :subtitle="t('accounts.profileHint')" :title="t('accounts.profileTitle')">
        <div class="accounts-profile">
          <div class="accounts-identity">
            <div class="accounts-identity__mark">
              <UserRound :size="26" />
            </div>
            <div>
              <strong>{{ currentAccount?.username || t('common.none') }}</strong>
              <span>{{ currentAccount?.user_id || authStore.principal?.user_id || t('common.none') }}</span>
            </div>
          </div>

          <div class="accounts-stat-list">
            <div class="accounts-stat">
              <span>{{ t('accounts.lastLogin') }}</span>
              <strong>{{ formatTimestamp(currentAccount?.last_login_at) }}</strong>
            </div>
            <div class="accounts-stat">
              <span>{{ t('accounts.passwordChangedAt') }}</span>
              <strong>{{ formatTimestamp(currentAccount?.password_changed_at) }}</strong>
            </div>
            <div class="accounts-stat">
              <span>{{ t('accounts.status') }}</span>
              <StatusBadge
                :label="currentAccount?.is_disabled ? t('accounts.disabled') : t('accounts.enabled')"
                :tone="currentAccount?.is_disabled ? 'warning' : 'success'"
              />
            </div>
          </div>
        </div>
      </Panel>

      <Panel :subtitle="t('accounts.securityHint')" :title="t('accounts.securityTitle')">
        <div class="accounts-security">
          <div>
            <div class="accounts-section-title">
              {{ t('accounts.sessionRefreshTitle') }}
            </div>
            <p>{{ t('accounts.sessionRefreshHint') }}</p>
          </div>
          <Button
            :disabled="revokingSessions"
            variant="secondary"
            @click="handleRevokeOtherSessions"
          >
            <RotateCcwKey :class="{ 'animate-spin': revokingSessions }" :size="16" />
            {{ t('accounts.revokeOtherSessions') }}
          </Button>
        </div>
      </Panel>
    </div>

    <Panel :subtitle="t('accounts.passwordHint')" :title="t('accounts.passwordTitle')">
      <form class="accounts-password-form" @submit.prevent="submitPassword">
        <FormField
          for-id="account-current-password"
          :label="t('accounts.currentPassword')"
          required
        >
          <Input
            id="account-current-password"
            v-model="passwordForm.current_password"
            autocomplete="current-password"
            type="password"
          />
        </FormField>

        <FormField
          for-id="account-new-password"
          :helper="t('accounts.newPasswordHelper')"
          :label="t('accounts.newPassword')"
          required
        >
          <Input
            id="account-new-password"
            v-model="passwordForm.new_password"
            autocomplete="new-password"
            type="password"
          />
        </FormField>

        <FormField
          :error="passwordError"
          for-id="account-confirm-password"
          :label="t('accounts.confirmPassword')"
          required
        >
          <Input
            id="account-confirm-password"
            v-model="passwordForm.confirm_password"
            autocomplete="new-password"
            type="password"
          />
        </FormField>

        <div class="accounts-form-actions">
          <Button
            :disabled="passwordSaving"
            type="submit"
          >
            <KeyRound :class="{ 'animate-spin': passwordSaving }" :size="16" />
            {{ t('accounts.changePassword') }}
          </Button>
        </div>
      </form>
    </Panel>

    <Panel :subtitle="t('accounts.createHint')" :title="t('accounts.createTitle')">
      <form class="accounts-password-form" @submit.prevent="submitCreate">
        <FormField
          for-id="account-create-username"
          :label="t('accounts.username')"
          required
        >
          <Input
            id="account-create-username"
            v-model="createForm.username"
            autocomplete="off"
          />
        </FormField>

        <FormField
          for-id="account-create-password"
          :label="t('accounts.newPassword')"
          required
        >
          <Input
            id="account-create-password"
            v-model="createForm.password"
            autocomplete="new-password"
            type="password"
          />
        </FormField>

        <FormField
          for-id="account-create-confirm-password"
          :label="t('accounts.confirmPassword')"
          required
        >
          <Input
            id="account-create-confirm-password"
            v-model="createForm.confirm_password"
            autocomplete="new-password"
            type="password"
          />
        </FormField>

        <FormField
          :error="createError"
          for-id="account-create-actor-password"
          :helper="t('accounts.actorPasswordHelper')"
          :label="t('accounts.actorPassword')"
          required
        >
          <Input
            id="account-create-actor-password"
            v-model="createForm.actor_password"
            autocomplete="current-password"
            type="password"
          />
        </FormField>

        <div class="accounts-form-actions">
          <Button
            :disabled="createSaving"
            type="submit"
          >
            <UserRoundPlus :class="{ 'animate-spin': createSaving }" :size="16" />
            {{ t('accounts.createAccount') }}
          </Button>
        </div>
      </form>
    </Panel>

    <Panel :subtitle="t('accounts.manageHint')" :title="t('accounts.manageTitle')">
      <EmptyState
        v-if="accounts.length === 0 && !loading"
        :icon="UserRound"
        :title="t('accounts.noAccounts')"
      />

      <Table v-else>
        <TableHeader>
          <TableRow>
            <TableHead>{{ t('accounts.username') }}</TableHead>
            <TableHead>{{ t('accounts.status') }}</TableHead>
            <TableHead>{{ t('accounts.lastLogin') }}</TableHead>
            <TableHead>{{ t('accounts.passwordChangedAt') }}</TableHead>
            <TableHead>{{ t('common.actions') }}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="item in accounts" :key="item.user_id">
            <TableCell>
              <div class="accounts-table-user">
                <strong>{{ item.username }}</strong>
                <span v-if="isCurrentAccount(item)">{{ t('accounts.currentAccount') }}</span>
              </div>
            </TableCell>
            <TableCell>
              <StatusBadge
                :label="item.is_disabled ? t('accounts.disabled') : t('accounts.enabled')"
                :tone="item.is_disabled ? 'warning' : 'success'"
              />
            </TableCell>
            <TableCell>{{ formatTimestamp(item.last_login_at) }}</TableCell>
            <TableCell>{{ formatTimestamp(item.password_changed_at) }}</TableCell>
            <TableCell>
              <div class="accounts-table-actions">
                <FormField
                  :label="t('accounts.actorPassword')"
                  :label-class="'sr-only'"
                >
                  <Input
                    v-model="disableActorPasswords[item.user_id]"
                    autocomplete="current-password"
                    :placeholder="t('accounts.actorPassword')"
                    type="password"
                  />
                </FormField>
                <Button
                  :disabled="!canToggle(item)"
                  size="sm"
                  variant="secondary"
                  @click="toggleAccount(item)"
                >
                  {{ item.is_disabled ? t('accounts.enableAccount') : t('accounts.disableAccount') }}
                </Button>
                <FormField
                  :label="t('accounts.actorPassword')"
                  :label-class="'sr-only'"
                >
                  <Input
                    v-model="deleteActorPasswords[item.user_id]"
                    autocomplete="current-password"
                    :placeholder="t('accounts.actorPassword')"
                    type="password"
                  />
                </FormField>
                <Button
                  :disabled="!canDelete(item)"
                  size="sm"
                  variant="destructive"
                  @click="handleDelete(item)"
                >
                  <Trash2 :size="15" />
                  {{ t('common.delete') }}
                </Button>
              </div>

              <div v-if="!isCurrentAccount(item)" class="accounts-reset-form">
                <FormField
                  :label="t('accounts.newPassword')"
                  :label-class="'sr-only'"
                >
                  <Input
                    v-model="getResetForm(item.user_id).new_password"
                    autocomplete="new-password"
                    :placeholder="t('accounts.newPassword')"
                    type="password"
                  />
                </FormField>
                <FormField
                  :label="t('accounts.confirmPassword')"
                  :label-class="'sr-only'"
                >
                  <Input
                    v-model="getResetForm(item.user_id).confirm_password"
                    autocomplete="new-password"
                    :placeholder="t('accounts.confirmPassword')"
                    type="password"
                  />
                </FormField>
                <FormField
                  :error="resetSavingFor === item.user_id ? resetError : ''"
                  :label="t('accounts.actorPassword')"
                  :label-class="'sr-only'"
                >
                  <Input
                    v-model="getResetForm(item.user_id).actor_password"
                    autocomplete="current-password"
                    :placeholder="t('accounts.actorPassword')"
                    type="password"
                  />
                </FormField>
                <Button
                  :disabled="resetSavingFor === item.user_id"
                  size="sm"
                  @click="handleReset(item)"
                >
                  <Plus :class="{ 'animate-spin': resetSavingFor === item.user_id }" :size="15" />
                  {{ t('accounts.resetPassword') }}
                </Button>
              </div>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </Panel>

    <Alert v-if="resetError && !resetSavingFor" variant="destructive">
      <AlertDescription>{{ resetError }}</AlertDescription>
    </Alert>
  </PageScaffold>
</template>
