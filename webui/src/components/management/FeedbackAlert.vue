<script setup lang="ts">
import { AlertCircle, RefreshCw } from '@lucide/vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'

const props = withDefaults(defineProps<{
  message: string
  retryLabel?: string
  stale?: boolean
  title?: string
}>(), {
  retryLabel: '',
  stale: false,
  title: '',
})

defineEmits<{
  retry: []
}>()

const { t } = useI18n()

const resolvedTitle = computed(() =>
  props.title || (props.stale ? t('feedback.refreshFailed') : t('feedback.loadFailed')),
)
</script>

<template>
  <Alert
    class="workbench-feedback-alert"
    role="alert"
    :data-stale="stale ? true : undefined"
    variant="destructive"
  >
    <AlertCircle data-icon="inline-start" />
    <div class="workbench-feedback-alert__content">
      <AlertTitle>{{ resolvedTitle }}</AlertTitle>
      <AlertDescription>
        {{ message }}
      </AlertDescription>
    </div>
    <Button
      v-if="retryLabel"
      size="sm"
      variant="secondary"
      @click="$emit('retry')"
    >
      <RefreshCw data-icon="inline-start" />
      {{ retryLabel }}
    </Button>
  </Alert>
</template>
