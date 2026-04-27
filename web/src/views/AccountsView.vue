<template>
  <div class="page-view">
    <div class="page-header">
      <h1 class="page-title">{{ t('accounts.title') }}</h1>
      <div class="page-actions">
        <v-btn :loading="loading" variant="tonal" @click="loadData">
          {{ t('common.refresh') }}
        </v-btn>
      </div>
    </div>

    <v-alert v-if="errorMessage" density="comfortable" type="error" variant="tonal">
      {{ errorMessage }}
    </v-alert>

    <div class="page-summary-grid mb-4">
      <v-sheet class="summary-card" rounded="lg">
        <div class="summary-card__label">{{ t('accounts.currentRole') }}</div>
        <div class="summary-card__value summary-card__value--text">{{ roleLabel(authStore.role) }}</div>
      </v-sheet>
      <v-sheet class="summary-card" rounded="lg">
        <div class="summary-card__label">{{ t('accounts.username') }}</div>
        <div class="summary-card__value summary-card__value--text">{{ currentAccount?.username || t('common.none') }}</div>
      </v-sheet>
      <v-sheet class="summary-card" rounded="lg">
        <div class="summary-card__label">{{ t('accounts.lastLogin') }}</div>
        <div class="summary-card__value summary-card__value--text">{{ formatTimestamp(currentAccount?.last_login_at) }}</div>
      </v-sheet>
      <v-sheet class="summary-card" rounded="lg">
        <div class="summary-card__label">{{ t('accounts.passwordChangedAt') }}</div>
        <div class="summary-card__value summary-card__value--text">{{ formatTimestamp(currentAccount?.password_changed_at) }}</div>
      </v-sheet>
    </div>

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
          class="page-table"
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
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup lang="ts">
  import type { SecurityAuditEventItem, WebUIAccountItem } from '@/api/auth'
  import { computed, onMounted, reactive, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import {
    changePassword,
    getCurrentAccount,
    getSecurityAuditEvents,
    revokeOtherSessions,
  } from '@/api/auth'
  import { getErrorMessage } from '@/api/client'
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
</style>
