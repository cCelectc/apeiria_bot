<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import {
  AlertCircle,
  ArrowRight,
  Loader2,
  LogIn,
  ShieldCheck,
} from 'lucide-vue-next'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { login } from '@/api/auth'
import { getErrorMessage } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { normalizeAuthRedirect } from '@/utils/routeRedirect'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const username = ref('')
const password = ref('')
const loading = ref(false)
const errorMessage = ref('')
const attemptedSubmit = ref(false)

const usernameError = computed(() =>
  attemptedSubmit.value && !username.value.trim() ? t('login.usernameRequired') : '',
)
const passwordError = computed(() =>
  attemptedSubmit.value && !password.value ? t('login.passwordRequired') : '',
)
const hasValidationError = computed(() =>
  Boolean(usernameError.value || passwordError.value),
)
const authStateMessage = computed(() => {
  if (authStore.status === 'expired') {
    return t('login.sessionExpired')
  }
  if (authStore.status === 'forbidden') {
    return t('login.forbidden')
  }
  return ''
})
const visibleError = computed(() => errorMessage.value || authStateMessage.value)

async function submitLogin() {
  if (loading.value) {
    return
  }
  attemptedSubmit.value = true
  errorMessage.value = ''
  if (hasValidationError.value) {
    errorMessage.value = t('login.missingFields')
    return
  }
  loading.value = true
  try {
    const response = await login({
      username: username.value.trim(),
      password: password.value,
    })
    authStore.acceptSession(response.data.token, response.data.principal)
    if (authStore.isAuthenticated) {
      await router.push(normalizeAuthRedirect(route.query.redirect))
      return
    }
    authStore.handleForbidden()
    errorMessage.value = t('login.forbidden')
  } catch (error) {
    errorMessage.value = getErrorMessage(error, t('login.wrongPassword'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="auth-screen">
    <section class="auth-shell" :aria-label="t('login.submit')">
      <section class="auth-form-panel">
        <div class="auth-card">
          <div class="auth-card__header">
            <span class="auth-brand__mark">
              <ShieldCheck :size="20" />
            </span>
            <div>
              <p class="auth-card__kicker">
                {{ t('layout.brand') }}
              </p>
              <h2 id="login-title">
                {{ t('login.submit') }}
              </h2>
            </div>
          </div>

          <form class="auth-form" aria-labelledby="login-title" @submit.prevent="submitLogin">
            <Alert v-if="visibleError" variant="destructive">
              <AlertCircle :size="16" />
              <AlertTitle>{{ t('login.errorTitle') }}</AlertTitle>
              <AlertDescription>{{ visibleError }}</AlertDescription>
            </Alert>

            <div class="auth-field">
              <Label for="login-username">{{ t('login.username') }}</Label>
              <Input
                id="login-username"
                v-model="username"
                :aria-describedby="usernameError ? 'login-username-error' : undefined"
                :aria-invalid="usernameError ? 'true' : undefined"
                autocomplete="username"
                autofocus
              />
              <p v-if="usernameError" id="login-username-error" class="auth-field__error">
                {{ usernameError }}
              </p>
            </div>

            <div class="auth-field">
              <Label for="login-password">{{ t('login.password') }}</Label>
              <Input
                id="login-password"
                v-model="password"
                :aria-describedby="passwordError ? 'login-password-error' : undefined"
                :aria-invalid="passwordError ? 'true' : undefined"
                autocomplete="current-password"
                type="password"
              />
              <p v-if="passwordError" id="login-password-error" class="auth-field__error">
                {{ passwordError }}
              </p>
            </div>

            <Button class="auth-submit" :disabled="loading" size="lg" type="submit">
              <Loader2 v-if="loading" class="auth-spin" :size="16" />
              <LogIn v-else :size="16" />
              {{ loading ? t('common.loading') : t('login.submit') }}
            </Button>

            <Button as-child class="auth-secondary-link" type="button" variant="link">
              <RouterLink to="/register">
                {{ t('login.toRegister') }}
                <ArrowRight :size="14" />
              </RouterLink>
            </Button>
          </form>
        </div>
      </section>
    </section>
  </main>
</template>
