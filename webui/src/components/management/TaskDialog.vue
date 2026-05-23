<script setup lang="ts">
import {
  CheckCircle2,
  Circle,
  CircleAlert,
  CircleDashed,
  Clock3,
  RefreshCw,
} from '@lucide/vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { StatusBadge } from '.'

type TaskStep = {
  phase?: string | null
  label?: string | null
  status?: string | null
  detail?: string | null
  command?: string | null
  output_excerpt?: string | null
  started_at?: string | null
  finished_at?: string | null
}

type TaskDiagnostic = {
  phase?: string
  message?: string
  [key: string]: unknown
}

const props = withDefaults(defineProps<{
  bindingValue?: string | null
  closeDisabled?: boolean
  closeLabel: string
  currentPhase?: string | null
  currentPhaseLabel?: string | null
  diagnostics?: TaskDiagnostic[]
  loading?: boolean
  logs?: string
  modelValue: boolean
  operation?: string | null
  queuePosition?: number | null
  rawStatus?: string
  requirement?: string | null
  resourceKind?: string | null
  restartRequired?: boolean
  retryLabel?: string
  status?: string
  statusTone?: 'default' | 'success' | 'warning' | 'error' | 'info'
  steps?: TaskStep[]
  title: string
  waitingText: string
}>(), {
  bindingValue: null,
  closeDisabled: false,
  currentPhase: null,
  currentPhaseLabel: null,
  diagnostics: () => [],
  loading: false,
  logs: '',
  operation: null,
  queuePosition: null,
  rawStatus: '',
  requirement: null,
  resourceKind: null,
  restartRequired: false,
  retryLabel: '',
  status: '',
  statusTone: 'default',
  steps: () => [],
})

const emit = defineEmits<{
  retry: []
  'update:modelValue': [value: boolean]
}>()

const { t } = useI18n()

const visible = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value),
})

const hasStructuredProgress = computed(() =>
  props.steps.length > 0
  || Boolean(props.currentPhaseLabel)
  || props.queuePosition !== null
  || props.diagnostics.length > 0,
)

const metadata = computed(() => [
  { key: 'operation', label: t('taskDialog.operation'), value: props.operation },
  { key: 'resource', label: t('taskDialog.resource'), value: props.resourceKind },
  { key: 'requirement', label: t('taskDialog.package'), value: props.requirement },
  { key: 'binding', label: t('taskDialog.binding'), value: props.bindingValue },
].filter(item => item.value && String(item.value).trim()))

const normalizedStatus = computed(() => props.rawStatus || props.status)
const isTerminal = computed(() =>
  normalizedStatus.value === 'succeeded' || normalizedStatus.value === 'failed',
)
const hasFailed = computed(() => normalizedStatus.value === 'failed')

const bannerText = computed(() => {
  if (normalizedStatus.value === 'succeeded' && props.restartRequired) {
    return t('taskDialog.succeededRestartRequired')
  }
  if (normalizedStatus.value === 'succeeded') {
    return t('taskDialog.succeeded')
  }
  if (normalizedStatus.value === 'failed') {
    return t('taskDialog.failed')
  }
  if (props.queuePosition !== null && props.queuePosition !== undefined) {
    return t('taskDialog.queuePosition', {
      label: localizedPhase(
        props.currentPhase || props.currentPhaseLabel || props.status || props.waitingText,
      ),
      position: props.queuePosition,
    })
  }
  return localizedPhase(
    props.currentPhase || props.currentPhaseLabel || props.status || props.waitingText,
  )
})

function stepTone(step: TaskStep) {
  if (step.status === 'failed') {
    return 'error'
  }
  if (step.status === 'succeeded') {
    return 'success'
  }
  if (step.status === 'running') {
    return 'info'
  }
  return 'default'
}

function stepIcon(step: TaskStep) {
  if (step.status === 'failed') {
    return CircleAlert
  }
  if (step.status === 'succeeded') {
    return CheckCircle2
  }
  if (step.status === 'running') {
    return Clock3
  }
  if (step.status === 'queued') {
    return CircleDashed
  }
  return Circle
}

function diagnosticMessage(item: TaskDiagnostic) {
  const message = item.message
  if (typeof message === 'string' && message.trim()) {
    return message.trim()
  }
  return JSON.stringify(item)
}

function localizedPhase(value: string | null | undefined) {
  if (!value) {
    return ''
  }
  const normalized = value.replaceAll('-', '_')
  const key = `taskDialog.phase.${normalized}`
  const translated = t(key)
  return translated === key ? value : translated
}

function localizedStepLabel(step: TaskStep) {
  return localizedPhase(step.phase || step.label) || step.label || step.status || ''
}

function localizedStepStatus(step: TaskStep) {
  if (!step.status) {
    return ''
  }
  const key = `taskDialog.status.${step.status}`
  const translated = t(key)
  return translated === key ? step.status : translated
}
</script>

<template>
  <Dialog v-model:open="visible">
    <DialogContent class="workbench-task-dialog">
      <DialogHeader>
        <div class="workbench-task-dialog__title-row">
          <DialogTitle>{{ title }}</DialogTitle>
          <StatusBadge v-if="status" :label="status" :tone="loading ? 'info' : statusTone" />
        </div>
        <DialogDescription v-if="$slots.details">
          <slot name="details" />
        </DialogDescription>
      </DialogHeader>

      <div v-if="loading" class="workbench-progress" />

      <section
        v-if="hasStructuredProgress"
        :aria-busy="loading ? 'true' : undefined"
        aria-live="polite"
        class="workbench-task-progress"
      >
        <div
          class="workbench-task-progress__banner"
          :class="`workbench-task-progress__banner--${statusTone}`"
          :data-terminal="isTerminal ? true : undefined"
        >
          <strong>{{ bannerText }}</strong>
          <span v-if="restartRequired">
            {{ t('taskDialog.restartRequired') }}
          </span>
        </div>

        <dl v-if="metadata.length" class="workbench-task-progress__meta">
          <div v-for="item in metadata" :key="item.key">
            <dt>{{ item.label }}</dt>
            <dd>{{ item.value }}</dd>
          </div>
        </dl>

        <ol v-if="steps.length" class="workbench-task-progress__timeline">
          <li
            v-for="(step, index) in steps"
            :key="`${step.phase || 'step'}-${index}`"
            :class="`workbench-task-progress__step--${stepTone(step)}`"
          >
            <component :is="stepIcon(step)" :size="17" />
            <div>
              <div class="workbench-task-progress__step-heading">
                <strong>{{ localizedStepLabel(step) }}</strong>
                <span>{{ localizedStepStatus(step) }}</span>
              </div>
              <p v-if="step.detail">{{ step.detail }}</p>
              <code v-if="step.command">{{ step.command }}</code>
              <pre v-if="step.output_excerpt">{{ step.output_excerpt }}</pre>
            </div>
          </li>
        </ol>

        <div v-if="diagnostics.length" class="workbench-task-progress__diagnostics">
          <strong>{{ t('taskDialog.diagnostics') }}</strong>
          <pre>{{ diagnostics.map(diagnosticMessage).join('\n\n') }}</pre>
        </div>
      </section>

      <div class="workbench-task-dialog__log">
        <pre>{{ logs || waitingText }}</pre>
      </div>

      <DialogFooter>
        <Button
          v-if="hasFailed && retryLabel"
          variant="secondary"
          @click="emit('retry')"
        >
          <RefreshCw data-icon="inline-start" />
          {{ retryLabel }}
        </Button>
        <Button :disabled="closeDisabled" variant="secondary" @click="visible = false">
          {{ closeLabel }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
