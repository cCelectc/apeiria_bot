<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import loader from '@monaco-editor/loader'
import { Loader2 } from '@lucide/vue'
import type * as Monaco from 'monaco-editor'

const props = defineProps<{
  modelValue: string
  jsonSchema?: Record<string, unknown>
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const containerRef = ref<HTMLElement | null>(null)
const ready = ref(false)
let editor: Monaco.editor.IStandaloneCodeEditor | null = null
let debounceTimer: ReturnType<typeof setTimeout> | null = null

onMounted(async () => {
  const monaco = await loader.init()

  if (!containerRef.value) return

  editor = monaco.editor.create(containerRef.value, {
    value: props.modelValue,
    language: 'yaml',
    theme: document.documentElement.classList.contains('dark') ? 'vs-dark' : 'vs',
    minimap: { enabled: false },
    fontSize: 13,
    tabSize: 2,
    automaticLayout: true,
    scrollBeyondLastLine: false,
    lineNumbers: 'on',
    renderWhitespace: 'selection',
  })

  editor!.onDidChangeModelContent(() => {
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => {
      emit('update:modelValue', editor!.getValue())
    }, 500)
  })

  const observer = new MutationObserver(() => {
    if (editor) {
      monaco.editor.setTheme(
        document.documentElement.classList.contains('dark') ? 'vs-dark' : 'vs'
      )
    }
  })
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })

  ready.value = true
})

onBeforeUnmount(() => {
  if (debounceTimer) clearTimeout(debounceTimer)
  editor?.dispose()
})

watch(
  () => props.modelValue,
  (newVal) => {
    if (editor && newVal !== editor.getValue()) {
      editor.setValue(newVal)
    }
  }
)
</script>

<template>
  <div ref="containerRef" class="relative h-full min-h-[200px] w-full border rounded-md">
    <div
      v-if="!ready"
      class="absolute inset-0 flex items-center justify-center bg-background"
    >
      <Loader2 class="size-8 animate-spin text-muted-foreground" />
    </div>
  </div>
</template>
