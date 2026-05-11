import type { RawSettingsValidationResponse } from '@/api/settings'
import { computed, onBeforeUnmount, ref, type Ref, watch } from 'vue'
import { getErrorMessage } from '@/api/client'

interface UseRawTomlValidationOptions {
  fallbackMessage: string
  initialText: Ref<string>
  text: Ref<string>
  validate: (text: string) => Promise<RawSettingsValidationResponse>
}

export function useRawTomlValidation(options: UseRawTomlValidationOptions) {
  const validationMessage = ref('')
  const validationLine = ref<number | null>(null)
  const validationColumn = ref<number | null>(null)
  const validationPending = ref(false)

  let debounceTimer: number | null = null
  let requestId = 0

  function clearValidation() {
    validationMessage.value = ''
    validationLine.value = null
    validationColumn.value = null
  }

  function cancelScheduledValidation() {
    if (debounceTimer !== null) {
      window.clearTimeout(debounceTimer)
      debounceTimer = null
    }
  }

  async function runValidation(text: string) {
    const currentRequestId = ++requestId
    validationPending.value = true
    try {
      const result = await options.validate(text)
      if (currentRequestId !== requestId) {
        return false
      }
      if (result.valid) {
        clearValidation()
        return true
      }
      validationMessage.value = result.message || options.fallbackMessage
      validationLine.value = result.line ?? null
      validationColumn.value = result.column ?? null
      return false
    } catch (error) {
      if (currentRequestId !== requestId) {
        return false
      }
      validationMessage.value = getErrorMessage(error, options.fallbackMessage)
      validationLine.value = null
      validationColumn.value = null
      return false
    } finally {
      if (currentRequestId === requestId) {
        validationPending.value = false
      }
    }
  }

  function scheduleValidation() {
    cancelScheduledValidation()
    requestId += 1

    if (options.text.value === options.initialText.value) {
      validationPending.value = false
      clearValidation()
      return
    }

    clearValidation()
    validationPending.value = true
    debounceTimer = window.setTimeout(() => {
      debounceTimer = null
      void runValidation(options.text.value)
    }, 260)
  }

  async function validateNow() {
    cancelScheduledValidation()
    if (options.text.value === options.initialText.value) {
      validationPending.value = false
      clearValidation()
      return true
    }
    return runValidation(options.text.value)
  }

  watch([options.text, options.initialText], scheduleValidation)
  onBeforeUnmount(cancelScheduledValidation)

  const hasValidationError = computed(() => Boolean(validationMessage.value))

  return {
    hasValidationError,
    validateNow,
    validationColumn,
    validationLine,
    validationMessage,
    validationPending,
  }
}
