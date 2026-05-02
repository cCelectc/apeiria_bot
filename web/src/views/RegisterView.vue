<template>
  <v-container class="fill-height auth-view" fluid>
    <v-row align="center" justify="center">
      <v-col cols="12" lg="4" md="5" sm="8">
        <v-card class="auth-card">
          <v-card-title class="auth-card__title">
            <v-icon color="primary" size="40">mdi-account-plus</v-icon>
            <div class="auth-card__brand">
              <div class="auth-card__name">{{ t('layout.brand') }}</div>
              <div class="auth-card__subtitle">{{ t('register.description') }}</div>
            </div>
          </v-card-title>

          <v-card-text>
            <v-form class="auth-form" @submit.prevent="handleRegister">
              <label class="workbench-field">
                <span class="workbench-field__title">{{ t('register.registrationCode') }}</span>
                <v-text-field
                  v-model.trim="registrationCode"
                  :aria-label="t('register.registrationCode')"
                  autocomplete="one-time-code"
                  autofocus
                  class="workbench-field__control"
                  prepend-inner-icon="mdi-ticket-confirmation-outline"
                />
              </label>
              <label class="workbench-field">
                <span class="workbench-field__title">{{ t('register.username') }}</span>
                <v-text-field
                  v-model.trim="username"
                  :aria-label="t('register.username')"
                  autocomplete="username"
                  class="workbench-field__control"
                  prepend-inner-icon="mdi-account"
                />
              </label>
              <label class="workbench-field">
                <span class="workbench-field__title">{{ t('register.password') }}</span>
                <v-text-field
                  v-model="password"
                  :aria-label="t('register.password')"
                  autocomplete="new-password"
                  class="workbench-field__control"
                  prepend-inner-icon="mdi-lock"
                  type="password"
                />
              </label>
              <label class="workbench-field">
                <span class="workbench-field__title">{{ t('register.confirmPassword') }}</span>
                <v-text-field
                  v-model="confirmPassword"
                  :aria-label="t('register.confirmPassword')"
                  autocomplete="new-password"
                  class="workbench-field__control"
                  :error-messages="error"
                  prepend-inner-icon="mdi-lock-check"
                  type="password"
                />
              </label>
              <v-btn
                block
                class="mt-4"
                color="primary"
                :loading="loading"
                size="large"
                type="submit"
              >
                {{ t('register.submit') }}
              </v-btn>
              <v-btn
                block
                class="mt-2"
                variant="text"
                @click="router.push('/login')"
              >
                {{ t('register.toLogin') }}
              </v-btn>
            </v-form>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
  import { ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRouter } from 'vue-router'
  import { register } from '@/api/auth'
  import { getErrorMessage } from '@/api/client'
  import { useNoticeStore } from '@/stores/notice'

  const registrationCode = ref('')
  const username = ref('')
  const password = ref('')
  const confirmPassword = ref('')
  const error = ref('')
  const loading = ref(false)
  const { t } = useI18n()
  const router = useRouter()
  const noticeStore = useNoticeStore()

  async function handleRegister () {
    if (!registrationCode.value.trim() || !username.value.trim() || !password.value || !confirmPassword.value) {
      error.value = t('register.missingFields')
      return
    }
    if (password.value !== confirmPassword.value) {
      error.value = t('register.passwordMismatch')
      return
    }

    loading.value = true
    error.value = ''
    try {
      const response = await register({
        registration_code: registrationCode.value.trim(),
        username: username.value.trim(),
        password: password.value,
      })
      noticeStore.show(response.data.detail || t('register.success'), 'success')
      router.push('/login')
    } catch (error_) {
      error.value = getErrorMessage(error_, t('register.failed'))
    } finally {
      loading.value = false
    }
  }
</script>

<style scoped>
.auth-form {
  display: grid;
  gap: 14px;
}
</style>
