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
  <div
    v-if="!ready"
    class="flex items-center justify-center h-full min-h-[400px] w-full border rounded-md"
  >
    <Loader2 class="size-8 animate-spin text-muted-foreground" />
  </div>
  <div ref="containerRef" v-else class="h-full min-h-[400px] w-full border rounded-md" />
</template>
