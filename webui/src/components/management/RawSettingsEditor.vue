<script setup lang="ts">
import { computed } from 'vue'
import { Button } from '@/components/ui/button'
import MonacoEditor from './MonacoEditor.vue'

const model = defineModel<string>({ required: true })

defineEmits<{
  reload: []
  save: []
}>()

const props = withDefaults(defineProps<{
  description: string
  dirty: boolean
  errorMessage: string
  loading: boolean
  reloadLabel: string
  saveLabel: string
  saving: boolean
  validationErrorColumn?: number | null
  validationErrorLine?: number | null
  validationErrorMessage?: string
  validationPending?: boolean
}>(), {
  validationErrorColumn: null,
  validationErrorLine: null,
  validationErrorMessage: '',
  validationPending: false,
})

const activeErrorMessage = computed(() =>
  props.validationErrorMessage || props.errorMessage,
)
</script>

<template>
  <div class="raw-settings-editor">
    <div class="raw-settings-editor__toolbar">
      <div class="raw-settings-editor__description">
        {{ description }}
      </div>
      <div class="raw-settings-editor__actions">
        <Button
          :disabled="loading || saving"
          size="sm"
          variant="ghost"
          @click="$emit('reload')"
        >
          {{ reloadLabel }}
        </Button>
        <Button
          :disabled="!dirty || validationPending || Boolean(validationErrorMessage)"
          size="sm"
          @click="$emit('save')"
        >
          {{ saveLabel }}
        </Button>
      </div>
    </div>

    <div v-if="activeErrorMessage" class="raw-settings-editor__error">
      {{ activeErrorMessage }}
    </div>

    <div class="raw-settings-editor__editor">
      <MonacoEditor
        v-model="model"
        height="100%"
        language="toml"
        :read-only="loading || saving"
        :validation-column="validationErrorColumn"
        :validation-line="validationErrorLine"
        :validation-message="validationErrorMessage"
      />
    </div>
  </div>
</template>
