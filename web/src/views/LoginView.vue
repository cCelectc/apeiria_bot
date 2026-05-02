<template>
  <v-container class="fill-height auth-view" fluid>
    <v-row align="center" justify="center">
      <v-col cols="12" lg="3" md="4" sm="8">
        <v-card class="auth-card">
          <v-card-title class="auth-card__title">
            <v-icon color="primary" size="40">mdi-robot-happy</v-icon>
            <div class="auth-card__brand">
              <div class="auth-card__name">{{ t('layout.brand') }}</div>
              <div class="auth-card__subtitle">{{ t('login.description') }}</div>
            </div>
          </v-card-title>

          <v-card-text>
            <v-form class="auth-form" @submit.prevent="handleLogin">
              <label class="workbench-field">
                <span class="workbench-field__title">{{ t('login.username') }}</span>
                <v-text-field
                  v-model.trim="username"
                  :aria-label="t('login.username')"
                  autocomplete="username"
                  autofocus
                  class="workbench-field__control"
                  prepend-inner-icon="mdi-account"
                />
              </label>
              <label class="workbench-field">
                <span class="workbench-field__title">{{ t('login.password') }}</span>
                <v-text-field
                  v-model="password"
                  :aria-label="t('login.password')"
                  autocomplete="current-password"
                  class="workbench-field__control"
                  :error-messages="error"
                  prepend-inner-icon="mdi-lock"
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
                {{ t('login.submit') }}
              </v-btn>
              <v-btn
                block
                class="mt-2"
                variant="text"
                @click="router.push('/register')"
              >
                {{ t('login.toRegister') }}
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
  import { login } from '@/api/auth'
  import { getErrorMessage } from '@/api/client'
  import { useAuthStore } from '@/stores/auth'

  const username = ref('')
  const password = ref('')
  const error = ref('')
  const loading = ref(false)
  const { t } = useI18n()
  const router = useRouter()
  const authStore = useAuthStore()

  async function handleLogin () {
    if (!username.value.trim() || !password.value) {
      error.value = t('login.missingFields')
      return
    }
    loading.value = true
    error.value = ''
    try {
      const res = await login({
        username: username.value.trim(),
        password: password.value,
      })
      authStore.acceptSession(res.data.token, res.data.principal)
      if (authStore.isAuthenticated) {
        router.push('/dashboard')
      } else {
        authStore.handleForbidden()
        error.value = t('login.forbidden')
      }
    } catch (error_) {
      error.value = getErrorMessage(error_, t('login.wrongPassword'))
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
