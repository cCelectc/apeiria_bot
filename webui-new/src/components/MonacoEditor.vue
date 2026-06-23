<template>
  <div ref="containerRef" class="rounded-md border overflow-hidden" :style="style" />
</template>

<script setup lang="ts">
import { ref, onMounted, watch, onBeforeUnmount } from "vue"
import type { editor } from "monaco-editor"

const props = withDefaults(defineProps<{
  modelValue: string
  language?: string
  disabled?: boolean
  style?: Record<string, string>
}>(), {
  language: "json",
  disabled: false,
  style: () => ({ height: "200px" }),
})

const emit = defineEmits<{
  "update:modelValue": [value: string]
}>()

const containerRef = ref<HTMLElement>()
let monacoEditor: editor.IStandaloneCodeEditor | null = null

onMounted(async () => {
  if (!containerRef.value) return
  const monaco = await import("monaco-editor")
  monacoEditor = monaco.editor.create(containerRef.value, {
    value: props.modelValue,
    language: props.language,
    theme: "vs-dark",
    minimap: { enabled: false },
    lineNumbers: "on",
    scrollBeyondLastLine: false,
    readOnly: props.disabled,
    automaticLayout: true,
    fontSize: 13,
    lineHeight: 20,
  })
  monacoEditor.onDidChangeModelContent(() => {
    const val = monacoEditor?.getValue() ?? ""
    emit("update:modelValue", val)
  })
})

watch(() => props.disabled, (v) => {
  monacoEditor?.updateOptions({ readOnly: v })
})

onBeforeUnmount(() => {
  monacoEditor?.dispose()
})
</script>
