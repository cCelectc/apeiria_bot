<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import {
  AlertCircle,
  Loader2,
  ShieldCheck,
  UserPlus,
} from '@lucide/vue'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { getErrorMessage } from '@/api/client'
import { setupAccount } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const loading = ref(false)
const errorMessage = ref('')
const attemptedSubmit = ref(false)

const usernameError = computed(() =>
  attemptedSubmit.value && !username.value.trim() ? t('login.usernameRequired') : '',
)
const passwordError = computed(() =>
  attemptedSubmit.value && !password.value ? t('login.passwordRequired') : '',
)
const confirmError = computed(() =>
  attemptedSubmit.value && password.value !== confirmPassword.value
    ? t('setup.passwordsMismatch')
    : '',
)
const hasValidationError = computed(() =>
  Boolean(usernameError.value || passwordError.value || confirmError.value),
)

async function submitSetup() {
  if (loading.value) {
    return
  }
  attemptedSubmit.value = true
  errorMessage.value = ''
  if (hasValidationError.value) {
    errorMessage.value = t('setup.fixErrors')
    return
  }
  loading.value = true
  try {
    const response = await setupAccount({
      username: username.value.trim(),
      password: password.value,
    })
    authStore.acceptSession(response.data)
    await router.push('/dashboard')
  } catch (error) {
    errorMessage.value = getErrorMessage(error, t('setup.failed'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="auth-screen">
    <section class="auth-shell" :aria-label="t('setup.title')">
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
              <h2 id="setup-title">
                {{ t('setup.title') }}
              </h2>
            </div>
          </div>

          <p class="auth-card__description">
            {{ t('setup.description') }}
          </p>

          <form
            class="auth-form"
            aria-labelledby="setup-title"
            @submit.prevent="submitSetup"
          >
            <Alert v-if="errorMessage" variant="destructive">
              <AlertCircle :size="16" />
              <AlertTitle>{{ t('login.errorTitle') }}</AlertTitle>
              <AlertDescription>{{ errorMessage }}</AlertDescription>
            </Alert>

            <div class="auth-field">
              <Label for="setup-username">{{ t('login.username') }}</Label>
              <Input
                id="setup-username"
                v-model="username"
                :aria-describedby="usernameError ? 'setup-username-error' : undefined"
                :aria-invalid="usernameError ? 'true' : undefined"
                autocomplete="username"
                autofocus
              />
              <p
                v-if="usernameError"
                id="setup-username-error"
                class="auth-field__error"
              >
                {{ usernameError }}
              </p>
            </div>

            <div class="auth-field">
              <Label for="setup-password">{{ t('login.password') }}</Label>
              <Input
                id="setup-password"
                v-model="password"
                :aria-describedby="passwordError ? 'setup-password-error' : undefined"
                :aria-invalid="passwordError ? 'true' : undefined"
                autocomplete="new-password"
                type="password"
              />
              <p
                v-if="passwordError"
                id="setup-password-error"
                class="auth-field__error"
              >
                {{ passwordError }}
              </p>
            </div>

            <div class="auth-field">
              <Label for="setup-confirm-password">{{ t('setup.confirmPassword') }}</Label>
              <Input
                id="setup-confirm-password"
                v-model="confirmPassword"
                :aria-describedby="confirmError ? 'setup-confirm-error' : undefined"
                :aria-invalid="confirmError ? 'true' : undefined"
                autocomplete="new-password"
                type="password"
              />
              <p
                v-if="confirmError"
                id="setup-confirm-error"
                class="auth-field__error"
              >
                {{ confirmError }}
              </p>
            </div>

            <Button class="auth-submit" :disabled="loading" size="lg" type="submit">
              <Loader2 v-if="loading" class="auth-spin" :size="16" />
              <UserPlus v-else :size="16" />
              {{ loading ? t('common.loading') : t('setup.submit') }}
            </Button>
          </form>
        </div>
      </section>
    </section>
  </main>
</template>
