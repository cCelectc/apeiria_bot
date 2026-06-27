<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { dump, load } from 'js-yaml'
import { toast } from 'vue-sonner'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { deepEqual } from '@/lib/configDiff'
import type { ConfigContract } from '@/types'
import FormRenderer from './FormRenderer.vue'
import MonacoEditor from './MonacoEditor.vue'
import UnsavedChangesDialog from './UnsavedChangesDialog.vue'

const props = defineProps<{
  schema: ConfigContract
  modelValue: Record<string, unknown>
  section: string
  ownerId?: string
  saveMutation: (data: Record<string, unknown>) => Promise<void>
}>()

const emit = defineEmits<{
  'update:modelValue': [value: Record<string, unknown>]
}>()

function clone(v: Record<string, unknown>): Record<string, unknown> {
  return JSON.parse(JSON.stringify(v)) as Record<string, unknown>
}

const mode = ref<'form' | 'code'>('form')
const data = ref<Record<string, unknown>>(clone(props.modelValue))
const baseline = ref<Record<string, unknown>>(clone(props.modelValue))
const yamlRaw = ref('')

const isDirty = computed(() => !deepEqual(data.value, baseline.value))

watch(
  () => props.modelValue,
  (val) => {
    data.value = clone(val)
    baseline.value = clone(val)
    if (mode.value === 'code') {
      yamlRaw.value = dump(val, { indent: 2 })
    }
  },
  { deep: true },
)

function onFormUpdate(value: Record<string, unknown>) {
  data.value = value
  if (mode.value === 'code') {
    yamlRaw.value = dump(value, { indent: 2 })
  }
}

function onCodeUpdate(value: string) {
  yamlRaw.value = value
  try {
    const parsed = load(value)
    if (typeof parsed === 'object' && parsed !== null) {
      data.value = parsed as Record<string, unknown>
    }
  } catch {
    // invalid YAML — don't update data
  }
}

function syncFromCode() {
  if (mode.value !== 'code') return
  try {
    const parsed = load(yamlRaw.value)
    if (typeof parsed === 'object' && parsed !== null) {
      data.value = parsed as Record<string, unknown>
    }
  } catch {
    // keep last valid data
  }
}

function switchMode(newMode: 'form' | 'code') {
  if (newMode === mode.value) return
  if (newMode === 'code') {
    yamlRaw.value = dump(data.value, { indent: 2 })
    mode.value = 'code'
  } else {
    try {
      const parsed = load(yamlRaw.value)
      if (typeof parsed === 'object' && parsed !== null) {
        data.value = parsed as Record<string, unknown>
        mode.value = 'form'
      } else {
        toast.error('YAML 内容必须是映射对象')
      }
    } catch (e) {
      toast.error(`YAML 语法错误: ${(e as Error).message}`)
    }
  }
}

const saving = ref(false)

async function doSave(): Promise<boolean> {
  let submitData: Record<string, unknown>
  if (mode.value === 'code') {
    try {
      const parsed = load(yamlRaw.value)
      if (typeof parsed !== 'object' || parsed === null) {
        toast.error('YAML 内容必须是映射对象')
        return false
      }
      submitData = parsed as Record<string, unknown>
    } catch (e) {
      toast.error(`YAML 解析失败: ${(e as Error).message}`)
      return false
    }
  } else {
    submitData = data.value
  }

  saving.value = true
  try {
    await props.saveMutation(submitData)
    toast.success('配置已保存')
    data.value = clone(submitData)
    baseline.value = clone(submitData)
    emit('update:modelValue', submitData)
    return true
  } catch (e) {
    toast.error(`保存失败: ${(e as Error).message}`)
    return false
  } finally {
    saving.value = false
  }
}

function handleSave() {
  void doSave()
}

const confirmOpen = ref(false)
let closeResolver: ((ok: boolean) => void) | null = null

function resolveClose(ok: boolean) {
  confirmOpen.value = false
  const r = closeResolver
  closeResolver = null
  r?.(ok)
}

function attemptClose(): Promise<boolean> {
  syncFromCode()
  if (!isDirty.value) return Promise.resolve(true)
  return new Promise<boolean>((resolve) => {
    closeResolver = resolve
    confirmOpen.value = true
  })
}

function onConfirmCancel() {
  resolveClose(false)
}

function onConfirmDiscard() {
  data.value = clone(baseline.value)
  if (mode.value === 'code') {
    yamlRaw.value = dump(data.value, { indent: 2 })
  }
  resolveClose(true)
}

async function onConfirmSave() {
  if (await doSave()) {
    resolveClose(true)
  }
}

defineExpose({ isDirty, attemptClose })
</script>

<template>
  <div class="flex flex-1 min-h-0 flex-col space-y-4">
    <div
      v-if="schema.source !== 'none'"
      class="-mx-1 flex items-center justify-between border-b px-1 pb-3"
    >
      <Tabs :model-value="mode" @update:model-value="(v) => v && switchMode(v as 'form' | 'code')">
        <TabsList>
          <TabsTrigger value="form">{{ $t('config.formTab') }}</TabsTrigger>
          <TabsTrigger value="code">{{ $t('config.codeTab') }}</TabsTrigger>
        </TabsList>
      </Tabs>
      <Button :disabled="saving" @click="handleSave">
        {{ saving ? $t('config.saving') : $t('config.save') }}
      </Button>
    </div>

    <div
      v-if="schema.source === 'none'"
      class="rounded-lg border border-dashed py-10 text-center text-sm text-muted-foreground"
    >
      {{ $t('config.noConfigDetail', { type: schema.owner_kind === 'adapter' ? $t('nav.adapters') : $t('nav.plugins') }) }}
    </div>

    <div v-else-if="mode === 'form'" class="flex-1 min-h-0 overflow-auto">
      <FormRenderer :fields="schema.fields" :model-value="data" @update:model-value="onFormUpdate" />
    </div>

    <div v-else class="flex-1 min-h-0 overflow-auto">
      <MonacoEditor
        :model-value="yamlRaw"
        :json-schema="(schema.json_schema as Record<string, unknown>) || undefined"
        @update:model-value="onCodeUpdate"
      />
    </div>

    <UnsavedChangesDialog
      v-model:open="confirmOpen"
      :original="baseline"
      :current="data"
      :fields="schema.fields"
      :saving="saving"
      @save="onConfirmSave"
      @discard="onConfirmDiscard"
      @cancel="onConfirmCancel"
    />
  </div>
</template>
