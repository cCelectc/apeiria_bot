<template>
  <div class="flex flex-col gap-1.5">
    <div class="flex items-center gap-2">
      <Label v-if="field.label" :for="fieldId">{{ field.label }}</Label>
      <span v-if="field.immutable" class="text-[10px] uppercase text-muted-foreground">Read-only</span>
    </div>
    <p v-if="field.description" class="text-xs text-muted-foreground">{{ field.description }}</p>

    <!-- string -->
    <Input
      v-if="field.type === 'string'"
      :id="fieldId"
      :model-value="stringValue"
      :placeholder="field.placeholder"
      :disabled="disabled"
      @update:model-value="emit('update:modelValue', $event)"
    />

    <!-- integer / float -->
    <Input
      v-else-if="field.type === 'integer' || field.type === 'float'"
      :id="fieldId"
      type="number"
      :model-value="(modelValue as string | number | undefined)"
      :min="field.meta?.min"
      :max="field.meta?.max"
      :step="field.type === 'float' ? (field.meta?.step ?? 0.1) : 1"
      :placeholder="field.placeholder"
      :disabled="disabled"
      @update:model-value="emit('update:modelValue', $event)"
    />

    <!-- boolean -->
    <div v-else-if="field.type === 'boolean'" class="flex items-center gap-2">
      <Switch
        :id="fieldId"
        :checked="!!modelValue"
        :disabled="disabled"
        @update:checked="emit('update:modelValue', $event)"
      />
      <Label v-if="field.label" :for="fieldId" class="text-sm text-muted-foreground">
        {{ !!modelValue ? 'Enabled' : 'Disabled' }}
      </Label>
    </div>

    <!-- enum / select -->
    <Select
      v-else-if="field.type === 'enum' || field.type === 'select'"
      :model-value="stringValue"
      :disabled="disabled"
      @update:model-value="emit('update:modelValue', $event)"
    >
      <SelectTrigger :id="fieldId" class="w-full">
        <SelectValue :placeholder="field.placeholder ?? 'Select...'" />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          <SelectItem v-for="opt in (field.meta?.options ?? [])" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </SelectItem>
        </SelectGroup>
      </SelectContent>
    </Select>

    <!-- json / toml -->
    <MonacoEditor
      v-else-if="field.type === 'json' || field.type === 'toml'"
      :model-value="stringValue"
      :language="field.type"
      :disabled="disabled"
      :style="{ height: '120px' }"
      @update:model-value="emit('update:modelValue', $event)"
    />

    <!-- chips -->
    <div v-else-if="field.type === 'chips'" class="flex flex-wrap gap-1.5">
      <Badge v-for="(chip, i) in chipItems" :key="i" variant="secondary" class="gap-1">
        {{ chip }}
        <button
          v-if="!disabled"
          class="ml-0.5 rounded-full hover:bg-muted-foreground/20"
          @click="removeChip(i)"
        >
          <X class="size-3" />
        </button>
      </Badge>
      <Input
        v-if="!disabled"
        class="h-7 w-24"
        placeholder="Add..."
        @keydown.enter="addChip"
      />
    </div>

    <!-- object (recursive) -->
    <SettingsEditor
      v-else-if="field.type === 'object' && field.children"
      :fields="field.children"
      :model-value="(modelValue as Record<string, unknown>) ?? {}"
      :disabled="disabled"
      :depth="depth + 1"
      class="mt-1"
      @update:model-value="emit('update:modelValue', $event)"
    />

    <!-- array -->
    <div v-else-if="field.type === 'array'" class="flex flex-col gap-2">
      <div v-for="(item, i) in arrayItems" :key="i" class="flex items-start gap-2">
        <Input
          :model-value="item"
          class="flex-1"
          :disabled="disabled"
          @update:model-value="updateArrayItem(i, $event)"
        />
        <Button
          v-if="!disabled"
          variant="ghost"
          size="icon"
          class="size-8"
          @click="removeArrayItem(i)"
        >
          <X class="size-4" />
        </Button>
      </div>
      <Button v-if="!disabled" variant="outline" size="sm" class="w-fit" @click="addArrayItem">
        <Plus class="size-4" />
        Add
      </Button>
    </div>

    <!-- mapping -->
    <div v-else-if="field.type === 'mapping'" class="flex flex-col gap-2">
      <div v-for="(val, key) in (modelValue as Record<string, string>) ?? {}" :key="key" class="flex items-center gap-2">
        <Input :model-value="key" class="flex-1" disabled />
        <Input
          :model-value="val"
          class="flex-1"
          :disabled="disabled"
          @update:model-value="updateMappingValue(key, $event)"
        />
        <Button
          v-if="!disabled"
          variant="ghost"
          size="icon"
          class="size-8"
          @click="removeMappingKey(key)"
        >
          <X class="size-4" />
        </Button>
      </div>
      <div v-if="!disabled" class="flex items-center gap-2">
        <Input v-model="newMappingKey" class="flex-1" placeholder="Key" />
        <Input v-model="newMappingValue" class="flex-1" placeholder="Value" />
        <Button variant="outline" size="sm" @click="addMappingItem">
          <Plus class="size-4" />
          Add
        </Button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { Plus, X } from "@lucide/vue"
import type { SettingsFieldItem } from "@/types/settings"
import Input from "@/components/ui/input/Input.vue"
import Label from "@/components/ui/label/Label.vue"
import Switch from "@/components/ui/switch/Switch.vue"
import Badge from "@/components/ui/badge/Badge.vue"
import Button from "@/components/ui/button/Button.vue"
import Select from "@/components/ui/select/Select.vue"
import SelectContent from "@/components/ui/select/SelectContent.vue"
import SelectGroup from "@/components/ui/select/SelectGroup.vue"
import SelectItem from "@/components/ui/select/SelectItem.vue"
import SelectTrigger from "@/components/ui/select/SelectTrigger.vue"
import SelectValue from "@/components/ui/select/SelectValue.vue"
import MonacoEditor from "@/components/MonacoEditor.vue"
import SettingsEditor from "@/components/SettingsEditor.vue"

const props = defineProps<{
  field: SettingsFieldItem
  modelValue: unknown
  disabled?: boolean
  depth?: number
}>()

const emit = defineEmits<{
  "update:modelValue": [value: unknown]
}>()

const depth = computed(() => props.depth ?? 0)
const fieldId = computed(() => `field-${props.field.key}`)

// String value (for integer/float display)
const stringValue = computed(() => {
  if (props.modelValue === null || props.modelValue === undefined) return ""
  return String(props.modelValue)
})

// Chips
const chipItems = computed(() => {
  if (Array.isArray(props.modelValue)) return props.modelValue as string[]
  return []
})

function addChip(e: Event) {
  const target = e.target as HTMLInputElement
  const val = target.value.trim()
  if (!val) return
  emit("update:modelValue", [...chipItems.value, val])
  target.value = ""
}

function removeChip(i: number) {
  const next = [...chipItems.value]
  next.splice(i, 1)
  emit("update:modelValue", next)
}

// Array
const arrayItems = computed(() => {
  if (Array.isArray(props.modelValue)) return props.modelValue as string[]
  return []
})

function addArrayItem() {
  emit("update:modelValue", [...arrayItems.value, ""])
}

function removeArrayItem(i: number) {
  const next = [...arrayItems.value]
  next.splice(i, 1)
  emit("update:modelValue", next)
}

function updateArrayItem(i: number, val: string | number) {
  const next = [...arrayItems.value]
  next[i] = String(val)
  emit("update:modelValue", next)
}

// Mapping
const newMappingKey = ref("")
const newMappingValue = ref("")

const mappingObj = computed(() => {
  if (props.modelValue && typeof props.modelValue === "object") return props.modelValue as Record<string, string>
  return {}
})

function addMappingItem() {
  if (!newMappingKey.value.trim()) return
  const next = { ...mappingObj.value, [newMappingKey.value]: newMappingValue.value }
  newMappingKey.value = ""
  newMappingValue.value = ""
  emit("update:modelValue", next)
}

function removeMappingKey(key: string) {
  const next = { ...mappingObj.value }
  delete next[key]
  emit("update:modelValue", next)
}

function updateMappingValue(key: string, val: string | number) {
  emit("update:modelValue", { ...mappingObj.value, [key]: String(val) })
}
</script>
