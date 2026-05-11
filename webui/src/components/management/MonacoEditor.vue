<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

interface MonacoModule {
  editor: {
    create: (
      element: HTMLElement,
      options: Record<string, unknown>,
    ) => MonacoEditorInstance
    setModelMarkers: (
      model: MonacoTextModel,
      owner: string,
      markers: MonacoMarkerData[],
    ) => void
    setTheme: (theme: string) => void
  }
  MarkerSeverity: {
    Error: number
  }
  languages: {
    register: (language: { id: string }) => void
    setLanguageConfiguration: (
      languageId: string,
      configuration: Record<string, unknown>,
    ) => void
    setMonarchTokensProvider: (
      languageId: string,
      provider: Record<string, unknown>,
    ) => void
  }
}

interface MonacoTextModel {
  getLineCount: () => number
  getLineMaxColumn: (lineNumber: number) => number
}

interface MonacoMarkerData {
  endColumn: number
  endLineNumber: number
  message: string
  severity: number
  startColumn: number
  startLineNumber: number
}

interface MonacoEditorInstance {
  dispose: () => void
  getModel: () => MonacoTextModel | null
  getValue: () => string
  layout: () => void
  onDidChangeModelContent: (listener: () => void) => { dispose: () => void }
  setValue: (value: string) => void
  updateOptions: (options: Record<string, unknown>) => void
}

const props = withDefaults(defineProps<{
  height?: number | string
  language?: string
  modelValue: string
  readOnly?: boolean
  validationColumn?: number | null
  validationLine?: number | null
  validationMessage?: string
}>(), {
  height: 360,
  language: 'toml',
  readOnly: false,
  validationColumn: null,
  validationLine: null,
  validationMessage: '',
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const container = ref<HTMLElement | null>(null)
const normalizedHeight = computed(() =>
  typeof props.height === 'number' ? `${props.height}px` : props.height,
)

let editor: MonacoEditorInstance | null = null
let changeSubscription: { dispose: () => void } | null = null
let monacoModuleRef: MonacoModule | null = null
let tomlRegistered = false
let disposed = false

function currentTheme() {
  return localStorage.getItem('apeiria-theme') === 'light' ? 'vs' : 'vs-dark'
}

function ensureTomlLanguage(monacoModule: MonacoModule) {
  if (tomlRegistered) {
    return
  }
  tomlRegistered = true
  monacoModule.languages.register({ id: 'toml' })
  monacoModule.languages.setLanguageConfiguration('toml', {
    autoClosingPairs: [
      { open: '{', close: '}' },
      { open: '[', close: ']' },
      { open: '"', close: '"' },
    ],
    brackets: [
      ['{', '}'],
      ['[', ']'],
    ],
    comments: {
      lineComment: '#',
    },
    surroundingPairs: [
      { open: '{', close: '}' },
      { open: '[', close: ']' },
      { open: '"', close: '"' },
    ],
  })
  monacoModule.languages.setMonarchTokensProvider('toml', {
    brackets: [
      { open: '{', close: '}', token: 'delimiter.curly' },
      { open: '[', close: ']', token: 'delimiter.square' },
    ],
    defaultToken: '',
    escapes: /\\(?:[btnfr"\\]|u[0-9A-Fa-f]{4})/,
    ignoreCase: false,
    keywords: ['true', 'false'],
    tokenizer: {
      root: [
        [/^\s*\[[^[\]]+\]\s*$/, 'type.identifier'],
        [/[A-Za-z0-9_-]+(?=\s*=)/, 'key'],
        [/#.*$/, 'comment'],
        [/"([^"\\]|\\.)*$/, 'string.invalid'],
        [/"/, { token: 'string.quote', next: '@string' }],
        [/-?\d+\.\d+([eE][+-]?\d+)?/, 'number.float'],
        [/-?\d+/, 'number'],
        [/\b(?:true|false)\b/, 'keyword'],
        [/[{}[\]]/, '@brackets'],
        [/[=,]/, 'delimiter'],
      ],
      string: [
        [/[^\\"]+/, 'string'],
        [/@escapes/, 'string.escape'],
        [/\\./, 'string.escape.invalid'],
        [/"/, { token: 'string.quote', next: '@pop' }],
      ],
    },
  })
}

function applyValidationMarker() {
  if (!editor || !monacoModuleRef) {
    return
  }
  const model = editor.getModel()
  if (!model) {
    return
  }
  if (!props.validationMessage) {
    monacoModuleRef.editor.setModelMarkers(model, 'apeiria-raw-validation', [])
    return
  }

  const lineCount = Math.max(1, model.getLineCount())
  const line = Math.min(Math.max(props.validationLine || 1, 1), lineCount)
  const maxColumn = Math.max(1, model.getLineMaxColumn(line))
  const column = Math.min(Math.max(props.validationColumn || 1, 1), maxColumn)

  monacoModuleRef.editor.setModelMarkers(model, 'apeiria-raw-validation', [
    {
      endColumn: Math.min(column + 1, maxColumn),
      endLineNumber: line,
      message: props.validationMessage,
      severity: monacoModuleRef.MarkerSeverity.Error,
      startColumn: column,
      startLineNumber: line,
    },
  ])
}

onMounted(async () => {
  if (!container.value) {
    return
  }
  const [monacoApiModule] = await Promise.all([
    import('monaco-editor/esm/vs/editor/editor.api.js'),
    import('monaco-editor/esm/vs/editor/contrib/contextmenu/browser/contextmenu.js'),
    import('monaco-editor/esm/vs/editor/contrib/clipboard/browser/clipboard.js'),
  ])
  if (disposed || !container.value) {
    return
  }
  const monacoModule = monacoApiModule as unknown as MonacoModule
  monacoModuleRef = monacoModule
  if (props.language === 'toml') {
    ensureTomlLanguage(monacoModule)
  }
  monacoModule.editor.setTheme(currentTheme())
  const instance = monacoModule.editor.create(container.value, {
    automaticLayout: true,
    contextmenu: true,
    language: props.language,
    minimap: { enabled: false },
    readOnly: props.readOnly,
    scrollBeyondLastLine: false,
    scrollbar: {
      alwaysConsumeMouseWheel: false,
      horizontal: 'auto',
      vertical: 'auto',
    },
    value: props.modelValue,
    wordWrap: 'on',
  })
  editor = instance
  changeSubscription = instance.onDidChangeModelContent(() => {
    emit('update:modelValue', instance.getValue())
  })
  applyValidationMarker()
})

watch(
  () => props.modelValue,
  nextValue => {
    if (!editor || editor.getValue() === nextValue) {
      return
    }
    editor.setValue(nextValue)
  },
)

watch(
  () => props.readOnly,
  nextValue => {
    editor?.updateOptions({ readOnly: nextValue })
  },
)

watch(
  () => [props.validationMessage, props.validationLine, props.validationColumn],
  () => {
    applyValidationMarker()
  },
)

watch(normalizedHeight, () => {
  editor?.layout()
})

onBeforeUnmount(() => {
  disposed = true
  changeSubscription?.dispose()
  editor?.dispose()
})
</script>

<template>
  <div ref="container" class="monaco-editor-host" :style="{ height: normalizedHeight }" />
</template>
