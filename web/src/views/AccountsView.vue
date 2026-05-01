<template>
  <PageScaffold :error-message="errorMessage" :title="t('accounts.title')">
    <template #actions>
      <v-btn :loading="loading" variant="tonal" @click="loadData">
        {{ t('common.refresh') }}
      </v-btn>
    </template>

    <MetricStrip :items="accountMetrics" />

    <v-row>
      <v-col cols="12" lg="5">
        <v-card class="page-panel">
          <v-card-title class="page-panel__title">{{ t('accounts.profileTitle') }}</v-card-title>

          <v-card-text class="d-flex flex-column ga-4">
            <div class="security-stat">
              <div class="security-stat__label">{{ t('accounts.username') }}</div>
              <div class="security-stat__value">{{ currentAccount?.username || t('common.none') }}</div>
            </div>

            <div class="security-stat">
              <div class="security-stat__label">{{ t('accounts.currentRole') }}</div>
              <div class="security-stat__value">{{ roleLabel(authStore.role) }}</div>
            </div>

            <div class="security-stat">
              <div class="security-stat__label">{{ t('accounts.lastLogin') }}</div>
              <div class="security-stat__value">{{ formatTimestamp(currentAccount?.last_login_at) }}</div>
            </div>

            <div class="security-stat">
              <div class="security-stat__label">{{ t('accounts.passwordChangedAt') }}</div>
              <div class="security-stat__value">{{ formatTimestamp(currentAccount?.password_changed_at) }}</div>
            </div>
          </v-card-text>
        </v-card>

        <v-card class="page-panel mt-4">
          <v-card-title class="page-panel__title">{{ t('accounts.securityTitle') }}</v-card-title>

          <v-card-text class="d-flex flex-column ga-3">
            <div class="d-flex justify-end">
              <v-btn color="warning" :loading="revokingSessions" variant="tonal" @click="handleRevokeOtherSessions">
                {{ t('accounts.revokeOtherSessions') }}
              </v-btn>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" lg="7">
        <v-card class="page-panel">
          <v-card-title class="page-panel__title">{{ t('accounts.passwordTitle') }}</v-card-title>

          <v-card-text class="d-flex flex-column ga-3">
            <v-text-field
              v-model="passwordForm.current_password"
              :label="t('accounts.currentPassword')"
              type="password"
            />

            <v-text-field
              v-model="passwordForm.new_password"
              :label="t('accounts.newPassword')"
              type="password"
            />

            <v-text-field
              v-model="confirmPassword"
              :error-messages="passwordError"
              :label="t('accounts.confirmPassword')"
              type="password"
            />

            <div class="d-flex justify-end">
              <v-btn color="primary" :loading="passwordSaving" @click="submitPassword">
                {{ t('accounts.changePassword') }}
              </v-btn>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-card class="page-panel mt-4">
      <v-card-title class="page-panel__title">{{ t('accounts.auditTitle') }}</v-card-title>

      <v-card-text>
        <v-data-table
          class="page-table accounts-audit-table"
          density="compact"
          :headers="auditHeaders"
          :items="auditEvents"
          :loading="loading"
        >
          <template #item.event_type="{ value }">
            <span>{{ auditEventLabel(value) }}</span>
          </template>

          <template #item.occurred_at="{ value }">
            <span>{{ formatTimestamp(value) }}</span>
          </template>

          <template #item.actor_username="{ value }">
            <span>{{ value || t('common.none') }}</span>
          </template>

          <template #item.target_username="{ value }">
            <span>{{ value || t('common.none') }}</span>
          </template>

          <template #item.detail="{ value }">
            <span>{{ value || t('common.none') }}</span>
          </template>
        </v-data-table>

        <div class="accounts-audit-cards">
          <article
            v-for="event in auditEvents"
            :key="`${event.event_type}:${event.occurred_at}:${event.actor_username}:${event.target_username}`"
            class="accounts-audit-card"
          >
            <div class="accounts-audit-card__header">
              <div>
                <div class="accounts-audit-card__title">{{ auditEventLabel(event.event_type) }}</div>
                <div class="accounts-audit-card__time">{{ formatTimestamp(event.occurred_at) }}</div>
              </div>
            </div>

            <div class="accounts-audit-card__grid">
              <div>
                <span>{{ t('accounts.auditActor') }}</span>
                <strong>{{ event.actor_username || t('common.none') }}</strong>
              </div>

              <div>
                <span>{{ t('accounts.auditTarget') }}</span>
                <strong>{{ event.target_username || t('common.none') }}</strong>
              </div>

              <div>
                <span>{{ t('accounts.auditDetail') }}</span>
                <strong>{{ event.detail || t('common.none') }}</strong>
              </div>
            </div>
          </article>

          <div v-if="auditEvents.length === 0" class="accounts-audit-empty">
            {{ t('common.noData') }}
          </div>
        </div>
      </v-card-text>
    </v-card>
  </PageScaffold>
</template>

<script setup lang="ts">
  import type { SecurityAuditEventItem, WebUIAccountItem } from '@/api/auth'
  import type { WorkbenchMetricItem } from '@/components/workbench'
  import { computed, onMounted, reactive, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import {
    changePassword,
    getCurrentAccount,
    getSecurityAuditEvents,
    revokeOtherSessions,
  } from '@/api/auth'
  import { getErrorMessage } from '@/api/client'
  import { MetricStrip, PageScaffold } from '@/components/workbench'
  import { useAuthStore } from '@/stores/auth'
  import { useNoticeStore } from '@/stores/notice'

  const { t } = useI18n()
  const authStore = useAuthStore()
  const noticeStore = useNoticeStore()

  const loading = ref(false)
  const passwordSaving = ref(false)
  const revokingSessions = ref(false)
  const errorMessage = ref('')
  const passwordError = ref('')
  const confirmPassword = ref('')
  const currentAccount = ref<WebUIAccountItem | null>(null)
  const auditEvents = ref<SecurityAuditEventItem[]>([])
  const passwordForm = reactive({
    current_password: '',
    new_password: '',
  })

  const auditHeaders = computed(() => [
    { title: t('accounts.auditTime'), key: 'occurred_at', sortable: false },
    { title: t('accounts.auditType'), key: 'event_type', sortable: false },
    { title: t('accounts.auditActor'), key: 'actor_username', sortable: false },
    { title: t('accounts.auditTarget'), key: 'target_username', sortable: false },
    { title: t('accounts.auditDetail'), key: 'detail', sortable: false },
  ])
  const accountMetrics = computed<WorkbenchMetricItem[]>(() => [
    {
      key: 'role',
      label: t('accounts.currentRole'),
      value: roleLabel(authStore.role),
      icon: 'mdi-shield-account-outline',
    },
    {
      key: 'username',
      label: t('accounts.username'),
      value: currentAccount.value?.username || t('common.none'),
      icon: 'mdi-account-outline',
    },
    {
      key: 'last-login',
      label: t('accounts.lastLogin'),
      value: formatTimestamp(currentAccount.value?.last_login_at),
      icon: 'mdi-login',
    },
    {
      key: 'password-changed',
      label: t('accounts.passwordChangedAt'),
      value: formatTimestamp(currentAccount.value?.password_changed_at),
      icon: 'mdi-lock-reset',
    },
  ])
  function roleLabel (role: string) {
    if (role === 'owner') {
      return t('accounts.roles.owner')
    }
    return role || t('common.none')
  }

  function formatTimestamp (value: string | null | undefined) {
    if (!value) {
      return t('common.none')
    }
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) {
      return value
    }
    return date.toLocaleString()
  }

  function auditEventLabel (eventType: string) {
    return t(`accounts.auditEvents.${eventType}`)
  }

  async function loadData () {
    loading.value = true
    errorMessage.value = ''
    try {
      const [currentAccountResponse, auditEventsResponse] = await Promise.all([
        getCurrentAccount(),
        getSecurityAuditEvents(),
      ])
      currentAccount.value = currentAccountResponse.data
      auditEvents.value = auditEventsResponse.data
    } catch (error) {
      errorMessage.value = getErrorMessage(error, t('accounts.loadFailed'))
    } finally {
      loading.value = false
    }
  }

  async function submitPassword () {
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

  async function handleRevokeOtherSessions () {
    revokingSessions.value = true
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

<style scoped>
.security-stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.security-stat__label {
  color: rgba(var(--v-theme-on-surface), 0.64);
  font-size: 0.82rem;
}

.security-stat__value {
  font-weight: 600;
}

.accounts-audit-cards {
  display: none;
}

@media (max-width: 760px) {
  .accounts-audit-table {
    display: none;
  }

  .accounts-audit-cards {
    display: grid;
    gap: 10px;
  }

  .accounts-audit-card {
    display: flex;
    min-width: 0;
    flex-direction: column;
    gap: 12px;
    padding: 12px;
    border: 1px solid rgba(var(--v-theme-outline-variant), var(--surface-border-opacity));
    border-radius: var(--shape-panel);
    background: rgb(var(--v-theme-surface-container-low));
  }

  .accounts-audit-card__title {
    font-weight: 700;
  }

  .accounts-audit-card__time,
  .accounts-audit-card__grid span,
  .accounts-audit-empty {
    color: rgba(var(--v-theme-on-surface), 0.64);
    font-size: 0.82rem;
  }

  .accounts-audit-card__grid {
    display: grid;
    gap: 9px;
  }

  .accounts-audit-card__grid > div {
    display: grid;
    min-width: 0;
    gap: 3px;
  }

  .accounts-audit-card__grid strong {
    min-width: 0;
    overflow-wrap: anywhere;
  }
}
</style>
