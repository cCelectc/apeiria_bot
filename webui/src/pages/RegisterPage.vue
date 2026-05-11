<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import {
  AlertCircle,
  ArrowLeft,
  KeyRound,
  Loader2,
  ShieldCheck,
  TicketCheck,
  UserPlus,
} from 'lucide-vue-next'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { register } from '@/api/auth'
import { getErrorMessage } from '@/api/client'
import { useNoticeStore } from '@/stores/notice'

const { t } = useI18n()
const router = useRouter()
const noticeStore = useNoticeStore()
const registrationCode = ref('')
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const loading = ref(false)
const errorMessage = ref('')
const attemptedSubmit = ref(false)

const registrationCodeError = computed(() =>
  attemptedSubmit.value && !registrationCode.value.trim()
    ? t('register.registrationCodeRequired')
    : '',
)
const usernameError = computed(() =>
  attemptedSubmit.value && !username.value.trim() ? t('register.usernameRequired') : '',
)
const passwordError = computed(() =>
  attemptedSubmit.value && !password.value ? t('register.passwordRequired') : '',
)
const confirmPasswordError = computed(() => {
  if (!attemptedSubmit.value && !confirmPassword.value) {
    return ''
  }
  if (!confirmPassword.value) {
    return t('register.confirmPasswordRequired')
  }
  if (password.value !== confirmPassword.value) {
    return t('register.passwordMismatch')
  }
  return ''
})
const hasValidationError = computed(() =>
  Boolean(
    registrationCodeError.value
    || usernameError.value
    || passwordError.value
    || confirmPasswordError.value,
  ),
)

async function submitRegister() {
  if (loading.value) {
    return
  }
  attemptedSubmit.value = true
  errorMessage.value = ''
  if (hasValidationError.value) {
    errorMessage.value = t('register.missingFields')
    return
  }
  loading.value = true
  try {
    const response = await register({
      registration_code: registrationCode.value.trim(),
      username: username.value.trim(),
      password: password.value,
    })
    noticeStore.show(response.data.detail || t('register.success'), 'success')
    await router.push('/login')
  } catch (error) {
    errorMessage.value = getErrorMessage(error, t('register.failed'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="auth-screen">
    <section class="auth-shell auth-shell--register" :aria-label="t('register.submit')">
      <aside class="auth-panel">
        <div class="auth-brand">
          <span class="auth-brand__mark">
            <TicketCheck :size="22" />
          </span>
          <span>
            <strong>{{ t('layout.brand') }}</strong>
            <small>{{ t('layout.subtitle') }}</small>
          </span>
        </div>
        <div class="auth-panel__copy">
          <p>{{ t('auth.registrationEntry') }}</p>
          <h1>{{ t('register.description') }}</h1>
        </div>
        <div class="auth-panel__rules">
          <div class="auth-panel__rule">
            <KeyRound :size="16" />
            <span>{{ t('auth.registrationCodeGate') }}</span>
          </div>
          <div class="auth-panel__rule">
            <ShieldCheck :size="16" />
            <span>{{ t('auth.controlPanelGate') }}</span>
          </div>
        </div>
      </aside>

      <section class="auth-form-panel">
        <div class="auth-card auth-card--wide">
          <div class="auth-card__header">
            <span class="auth-card__icon">
              <UserPlus :size="18" />
            </span>
            <div>
              <p class="auth-card__kicker">
                {{ t('layout.brand') }}
              </p>
              <h2 id="register-title">
                {{ t('register.submit') }}
              </h2>
              <p>{{ t('auth.registerPanel') }}</p>
            </div>
          </div>

          <form class="auth-form" aria-labelledby="register-title" @submit.prevent="submitRegister">
            <Alert v-if="errorMessage" variant="destructive">
              <AlertCircle :size="16" />
              <AlertTitle>{{ t('register.failed') }}</AlertTitle>
              <AlertDescription>{{ errorMessage }}</AlertDescription>
            </Alert>

            <div class="auth-field">
              <Label for="registration-code">{{ t('register.registrationCode') }}</Label>
              <Input
                id="registration-code"
                v-model="registrationCode"
                :aria-describedby="registrationCodeError ? 'registration-code-error' : 'registration-code-helper'"
                :aria-invalid="registrationCodeError ? 'true' : undefined"
                autocomplete="one-time-code"
                autofocus
              />
              <p v-if="registrationCodeError" id="registration-code-error" class="auth-field__error">
                {{ registrationCodeError }}
              </p>
              <p v-else id="registration-code-helper" class="auth-field__helper">
                {{ t('register.registrationCodeHelper') }}
              </p>
            </div>

            <div class="auth-form__grid">
              <div class="auth-field">
                <Label for="register-username">{{ t('register.username') }}</Label>
                <Input
                  id="register-username"
                  v-model="username"
                  :aria-describedby="usernameError ? 'register-username-error' : 'register-username-helper'"
                  :aria-invalid="usernameError ? 'true' : undefined"
                  autocomplete="username"
                />
                <p v-if="usernameError" id="register-username-error" class="auth-field__error">
                  {{ usernameError }}
                </p>
                <p v-else id="register-username-helper" class="auth-field__helper">
                  {{ t('register.usernameHelper') }}
                </p>
              </div>

              <div class="auth-field">
                <Label for="register-password">{{ t('register.password') }}</Label>
                <Input
                  id="register-password"
                  v-model="password"
                  :aria-describedby="passwordError ? 'register-password-error' : 'register-password-helper'"
                  :aria-invalid="passwordError ? 'true' : undefined"
                  autocomplete="new-password"
                  type="password"
                />
                <p v-if="passwordError" id="register-password-error" class="auth-field__error">
                  {{ passwordError }}
                </p>
                <p v-else id="register-password-helper" class="auth-field__helper">
                  {{ t('register.passwordHelper') }}
                </p>
              </div>
            </div>

            <div class="auth-field">
              <Label for="confirm-password">{{ t('register.confirmPassword') }}</Label>
              <Input
                id="confirm-password"
                v-model="confirmPassword"
                :aria-describedby="confirmPasswordError ? 'confirm-password-error' : 'confirm-password-helper'"
                :aria-invalid="confirmPasswordError ? 'true' : undefined"
                autocomplete="new-password"
                type="password"
              />
              <p v-if="confirmPasswordError" id="confirm-password-error" class="auth-field__error">
                {{ confirmPasswordError }}
              </p>
              <p v-else id="confirm-password-helper" class="auth-field__helper">
                {{ t('register.confirmPasswordHelper') }}
              </p>
            </div>

            <Button class="auth-submit" :disabled="loading" size="lg" type="submit">
              <Loader2 v-if="loading" class="auth-spin" :size="16" />
              <UserPlus v-else :size="16" />
              {{ loading ? t('common.loading') : t('register.submit') }}
            </Button>

            <Button as-child class="auth-secondary-link" type="button" variant="link">
              <RouterLink to="/login">
                <ArrowLeft :size="14" />
                {{ t('register.toLogin') }}
              </RouterLink>
            </Button>
          </form>
        </div>
      </section>
    </section>
  </main>
</template>
