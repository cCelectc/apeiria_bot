<script setup lang="ts">
import type { SecurityAuditEventItem, WebUIAccountItem } from '@/api/auth'
import type { WorkbenchMetricItem, WorkbenchTableColumn } from '@/components/management'
import {
  Clock3,
  History,
  KeyRound,
  LockKeyhole,
  RefreshCw,
  RotateCcwKey,
  ShieldCheck,
  UserRound,
} from 'lucide-vue-next'
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  changePassword,
  getCurrentAccount,
  getSecurityAuditEvents,
  revokeOtherSessions,
} from '@/api/auth'
import { getErrorMessage } from '@/api/client'
import {
  DataTablePanel,
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
  TableCell,
  TableRow,
} from '@/components/ui/table'
import { useAuthStore } from '@/stores/auth'
import { useNoticeStore } from '@/stores/notice'

const { t } = useI18n()
const authStore = useAuthStore()
const noticeStore = useNoticeStore()
const currentAccount = ref<WebUIAccountItem | null>(null)
const auditEvents = ref<SecurityAuditEventItem[]>([])
const loading = ref(false)
const passwordSaving = ref(false)
const revokingSessions = ref(false)
const errorMessage = ref('')
const passwordError = ref('')
const confirmPassword = ref('')
const passwordForm = reactive({
  current_password: '',
  new_password: '',
})

const auditColumns = computed<WorkbenchTableColumn[]>(() => [
  { key: 'occurred_at', label: t('accounts.auditTime') },
  { key: 'event_type', label: t('accounts.auditType') },
  { key: 'actor_username', label: t('accounts.auditActor') },
  { key: 'target_username', label: t('accounts.auditTarget') },
  { key: 'detail', label: t('accounts.auditDetail') },
])
const metrics = computed<WorkbenchMetricItem[]>(() => [
  {
    icon: ShieldCheck,
    key: 'role',
    label: t('accounts.currentRole'),
    tone: 'info',
    value: roleLabel(authStore.role),
  },
  {
    icon: UserRound,
    key: 'username',
    label: t('accounts.username'),
    value: currentAccount.value?.username || t('common.none'),
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
const passwordSubmitDisabled = computed(() =>
  passwordSaving.value
  || !passwordForm.current_password
  || !passwordForm.new_password
  || !confirmPassword.value,
)

function roleLabel(role: string) {
  if (role === 'owner') {
    return t('accounts.roles.owner')
  }
  return role || t('common.none')
}

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

function auditEventLabel(eventType: string) {
  const label = t(`accounts.auditEvents.${eventType}`)
  return label === `accounts.auditEvents.${eventType}` ? eventType : label
}

function auditKey(event: SecurityAuditEventItem) {
  return [
    event.event_type,
    event.occurred_at,
    event.actor_username || '',
    event.target_username || '',
    event.detail || '',
  ].join(':')
}

async function loadData() {
  loading.value = true
  errorMessage.value = ''
  try {
    const [accountResponse, auditResponse] = await Promise.all([
      getCurrentAccount(),
      getSecurityAuditEvents(),
    ])
    currentAccount.value = accountResponse.data
    auditEvents.value = auditResponse.data
  } catch (error) {
    errorMessage.value = getErrorMessage(error, t('accounts.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function submitPassword() {
  if (!passwordForm.current_password || !passwordForm.new_password || !confirmPassword.value) {
    passwordError.value = t('accounts.passwordIncomplete')
    return
  }
  if (passwordForm.new_password !== confirmPassword.value) {
    passwordError.value = t('register.passwordMismatch')
    return
  }

  passwordSaving.value = true
  passwordError.value = ''
  try {
    const response = await changePassword(passwordForm)
    authStore.acceptSession(response.data.token, response.data.principal)
    noticeStore.show(response.data.detail || t('accounts.passwordChanged'), 'success')
    passwordForm.current_password = ''
    passwordForm.new_password = ''
    confirmPassword.value = ''
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
    authStore.acceptSession(response.data.token, response.data.principal)
    noticeStore.show(response.data.detail || t('accounts.otherSessionsRevoked'), 'success')
    await loadData()
  } catch (error) {
    errorMessage.value = getErrorMessage(error, t('accounts.revokeOtherSessionsFailed'))
  } finally {
    revokingSessions.value = false
  }
}

onMounted(loadData)
</script>

<template>
  <PageScaffold
    :error-message="errorMessage"
    :subtitle="t('accounts.description')"
    :title="t('accounts.title')"
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
              <span>{{ t('accounts.currentRole') }}</span>
              <strong>{{ roleLabel(authStore.role) }}</strong>
            </div>
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
        <input
          autocomplete="username"
          hidden
          name="username"
          readonly
          type="text"
          :value="currentAccount?.username || authStore.principal?.username || ''"
        >

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
            v-model="confirmPassword"
            autocomplete="new-password"
            type="password"
          />
        </FormField>

        <div class="accounts-form-actions">
          <Button
            :disabled="passwordSubmitDisabled"
            type="submit"
          >
            <KeyRound :class="{ 'animate-spin': passwordSaving }" :size="16" />
            {{ t('accounts.changePassword') }}
          </Button>
        </div>
      </form>
    </Panel>

    <DataTablePanel
      :columns="auditColumns"
      :empty-title="auditEvents.length === 0 && !loading ? t('accounts.noAuditEvents') : ''"
      :loading="loading"
      :subtitle="t('accounts.auditHint')"
      :title="t('accounts.auditTitle')"
    >
      <template v-if="auditEvents.length === 0 && !loading" #actions>
        <Button variant="secondary" @click="loadData">
          <RefreshCw :size="16" />
          {{ t('common.refresh') }}
        </Button>
      </template>

      <TableRow
        v-for="event in auditEvents"
        :key="auditKey(event)"
        class="accounts-audit-table-row"
      >
        <TableCell class="accounts-audit-time">
          {{ formatTimestamp(event.occurred_at) }}
        </TableCell>
        <TableCell>
          <span class="accounts-audit-event">{{ auditEventLabel(event.event_type) }}</span>
        </TableCell>
        <TableCell>{{ event.actor_username || t('common.none') }}</TableCell>
        <TableCell>{{ event.target_username || t('common.none') }}</TableCell>
        <TableCell class="accounts-audit-detail">
          {{ event.detail || t('common.none') }}
        </TableCell>
      </TableRow>
    </DataTablePanel>

    <div class="accounts-audit-cards">
      <EmptyState
        v-if="auditEvents.length === 0 && !loading"
        :icon="History"
        :title="t('accounts.noAuditEvents')"
      />
      <article
        v-for="event in auditEvents"
        :key="`card:${auditKey(event)}`"
        class="accounts-audit-card"
      >
        <div class="accounts-audit-card__header">
          <div>
            <strong>{{ auditEventLabel(event.event_type) }}</strong>
            <span>{{ formatTimestamp(event.occurred_at) }}</span>
          </div>
        </div>
        <dl class="accounts-audit-card__grid">
          <div>
            <dt>{{ t('accounts.auditActor') }}</dt>
            <dd>{{ event.actor_username || t('common.none') }}</dd>
          </div>
          <div>
            <dt>{{ t('accounts.auditTarget') }}</dt>
            <dd>{{ event.target_username || t('common.none') }}</dd>
          </div>
          <div>
            <dt>{{ t('accounts.auditDetail') }}</dt>
            <dd>{{ event.detail || t('common.none') }}</dd>
          </div>
        </dl>
      </article>
    </div>

    <Alert v-if="authStore.status === 'forbidden'" variant="destructive">
      <AlertDescription>{{ t('login.forbidden') }}</AlertDescription>
    </Alert>
  </PageScaffold>
</template>
