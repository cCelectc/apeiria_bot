<script setup lang="ts">
import { ref, watch } from 'vue'
import { dump, load } from 'js-yaml'
import { toast } from 'vue-sonner'
import type { ConfigContract } from '@/types'
import FormRenderer from './FormRenderer.vue'
import MonacoEditor from './MonacoEditor.vue'

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

const mode = ref<'form' | 'code'>('form')
const data = ref<Record<string, unknown>>({ ...props.modelValue })
const yamlRaw = ref('')

watch(
  () => props.modelValue,
  (val) => {
    data.value = { ...val }
    if (mode.value === 'code') {
      yamlRaw.value = dump(val, { indent: 2 })
    }
  },
  { deep: true }
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

function switchMode(newMode: 'form' | 'code') {
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

async function handleSave() {
  let submitData: Record<string, unknown>
  if (mode.value === 'code') {
    try {
      const parsed = load(yamlRaw.value)
      if (typeof parsed !== 'object' || parsed === null) {
        toast.error('YAML 内容必须是映射对象')
        return
      }
      submitData = parsed as Record<string, unknown>
    } catch (e) {
      toast.error(`YAML 解析失败: ${(e as Error).message}`)
      return
    }
  } else {
    submitData = data.value
  }

  saving.value = true
  try {
    await props.saveMutation(submitData)
    toast.success('配置已保存')
    emit('update:modelValue', submitData)
  } catch (e) {
    toast.error(`保存失败: ${(e as Error).message}`)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-1 border rounded-md p-0.5 bg-muted/50">
        <button
          class="px-3 py-1 text-sm rounded-sm transition-colors"
          :class="mode === 'form' ? 'bg-background shadow-sm' : 'text-muted-foreground hover:text-foreground'"
          @click="switchMode('form')"
        >
          表单
        </button>
        <button
          class="px-3 py-1 text-sm rounded-sm transition-colors"
          :class="mode === 'code' ? 'bg-background shadow-sm' : 'text-muted-foreground hover:text-foreground'"
          @click="switchMode('code')"
        >
          源码
        </button>
      </div>
      <Button :disabled="saving" @click="handleSave">
        {{ saving ? '保存中...' : '保存配置' }}
      </Button>
    </div>

    <div v-if="schema.source === 'none'" class="text-muted-foreground text-sm py-8 text-center">
      此{{ schema.owner_kind === 'adapter' ? '适配器' : '插件' }}无配置项
    </div>

    <div v-else-if="mode === 'form'" class="max-h-[60vh] overflow-y-auto pr-1">
      <FormRenderer :fields="schema.fields" :model-value="data" @update:model-value="onFormUpdate" />
    </div>

    <div v-else class="h-[60vh]">
      <MonacoEditor
        :model-value="yamlRaw"
        :json-schema="(schema.json_schema as Record<string, unknown>) || undefined"
        @update:model-value="onCodeUpdate"
      />
    </div>
  </div>
</template>
