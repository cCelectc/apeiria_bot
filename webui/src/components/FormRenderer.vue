<script setup lang="ts">
import { computed } from 'vue'
import { Plus, X } from '@lucide/vue'
import type { FieldNode, PrimitiveField, ObjectField, ArrayField, MapField } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'

const props = defineProps<{
  fields: FieldNode[]
  modelValue: Record<string, unknown>
}>()

const emit = defineEmits<{
  'update:modelValue': [value: Record<string, unknown>]
}>()

const sortedFields = computed(() =>
  [...props.fields].sort((a, b) => a.order - b.order)
)

function updateField(key: string, value: unknown) {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}

function addArrayItem(field: ArrayField) {
  const arr = [...(props.modelValue[field.key] as unknown[] || [])]
  const defaultItem = field.item_schema?.kind === 'object'
    ? {}
    : field.item_schema?.kind === 'primitive'
      ? (field.item_schema as PrimitiveField).default ?? ''
      : ''
  arr.push(defaultItem)
  updateField(field.key, arr)
}

function removeArrayItem(field: ArrayField, index: number) {
  const arr = [...(props.modelValue[field.key] as unknown[] || [])]
  arr.splice(index, 1)
  updateField(field.key, arr)
}

function updateArrayItem(field: ArrayField, index: number, value: unknown) {
  const arr = [...(props.modelValue[field.key] as unknown[] || [])]
  arr[index] = value
  updateField(field.key, arr)
}

function addMapEntry(field: MapField) {
  const obj = { ...(props.modelValue[field.key] as Record<string, unknown> || {}) }
  obj[''] = field.value_schema?.kind === 'primitive'
    ? (field.value_schema as PrimitiveField).default ?? ''
    : {}
  updateField(field.key, obj)
}

function removeMapEntry(field: MapField, key: string) {
  const obj = { ...(props.modelValue[field.key] as Record<string, unknown> || {}) }
  delete obj[key]
  updateField(field.key, obj)
}

function updateMapKey(field: MapField, oldKey: string, newKey: string) {
  const obj = { ...(props.modelValue[field.key] as Record<string, unknown> || {}) }
  if (oldKey === newKey || oldKey === '') return
  obj[newKey] = obj[oldKey]
  delete obj[oldKey]
  updateField(field.key, obj)
}

function updateMapValue(field: MapField, key: string, value: unknown) {
  const obj = { ...(props.modelValue[field.key] as Record<string, unknown> || {}) }
  obj[key] = value
  updateField(field.key, obj)
}
</script>

<template>
  <div class="space-y-5">
    <template v-for="field in sortedFields" :key="field.key">
      <!-- PrimitiveField -->
      <div v-if="field.kind === 'primitive'" class="space-y-2">
        <div class="flex items-center gap-2">
          <Label v-if="(field as PrimitiveField).type !== 'bool'" :for="field.key">
            {{ (field as PrimitiveField).label }}
          </Label>
          <span v-if="(field as PrimitiveField).required && (field as PrimitiveField).type !== 'bool'" class="text-destructive text-xs">*</span>
          <Label v-if="(field as PrimitiveField).type === 'bool'" :for="field.key" class="cursor-pointer">
            {{ (field as PrimitiveField).label }}
          </Label>
        </div>
        <p v-if="field.description" class="text-[0.8rem] text-muted-foreground">{{ field.description }}</p>
        <Switch
          v-if="(field as PrimitiveField).type === 'bool'"
          :id="field.key"
          :model-value="!!modelValue[field.key]"
          @update:model-value="(v: boolean) => updateField(field.key, v)"
        />
        <Select
          v-else-if="(field as PrimitiveField).choices?.length"
          :model-value="String(modelValue[field.key] ?? '')"
          @update:model-value="(v: any) => updateField(field.key, String(v ?? ''))"
        >
          <SelectTrigger :id="field.key">
            <SelectValue :placeholder="field.label" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem
              v-for="choice in (field as PrimitiveField).choices"
              :key="choice.value"
              :value="choice.value"
            >
              {{ choice.label }}
            </SelectItem>
          </SelectContent>
        </Select>
        <Input
          v-else-if="(field as PrimitiveField).secret"
          :id="field.key"
          type="password"
          :model-value="String(modelValue[field.key] ?? '')"
          @update:model-value="(v: string | number) => updateField(field.key, String(v))"
        />
        <Input
          v-else-if="(field as PrimitiveField).type === 'int' || (field as PrimitiveField).type === 'float'"
          :id="field.key"
          type="number"
          :model-value="modelValue[field.key] !== undefined ? Number(modelValue[field.key]) : undefined"
          @update:model-value="(v: string | number) => updateField(field.key, (field as PrimitiveField).type === 'int' ? parseInt(String(v)) || 0 : parseFloat(String(v)) || 0)"
        />
        <Textarea
          v-else-if="(field as PrimitiveField).type === 'str'"
          :id="field.key"
          :model-value="String(modelValue[field.key] ?? '')"
          @update:model-value="(v: string | number) => updateField(field.key, String(v))"
        />
        <Input
          v-else
          :id="field.key"
          :model-value="String(modelValue[field.key] ?? '')"
          @update:model-value="(v: string | number) => updateField(field.key, String(v))"
        />
      </div>

      <!-- ObjectField -->
      <div v-if="field.kind === 'object'" class="border rounded-lg p-4 space-y-3 bg-muted/30">
        <div class="text-sm font-semibold">{{ field.label }}</div>
        <p v-if="field.description" class="text-[0.8rem] text-muted-foreground">{{ field.description }}</p>
        <FormRenderer
          :fields="(field as ObjectField).children"
          :model-value="(modelValue[field.key] as Record<string, unknown>) || {}"
          @update:model-value="(v: Record<string, unknown>) => updateField(field.key, v)"
        />
      </div>

      <!-- ArrayField -->
      <div v-if="field.kind === 'array'" class="space-y-3">
        <div class="flex items-center gap-2">
          <span class="text-sm font-medium">{{ field.label }}</span>
        </div>
        <p v-if="field.description" class="text-[0.8rem] text-muted-foreground">{{ field.description }}</p>
        <div class="space-y-2">
          <div
            v-for="(item, idx) in (modelValue[field.key] as unknown[] || [])"
            :key="idx"
            class="border rounded-md p-3 space-y-2 bg-background"
          >
            <div class="flex justify-between items-center">
              <span class="text-xs text-muted-foreground font-mono">#{{ idx + 1 }}</span>
              <Button variant="ghost" size="icon" @click="removeArrayItem(field as ArrayField, idx)">
                <X class="size-4" />
              </Button>
            </div>
            <FormRenderer
              v-if="(field as ArrayField).item_schema?.kind === 'object'"
              :fields="[(field as ArrayField).item_schema!]"
              :model-value="item as Record<string, unknown>"
              @update:model-value="(v: Record<string, unknown>) => updateArrayItem(field as ArrayField, idx, v)"
            />
            <Input
              v-else
              :model-value="String(item ?? '')"
              @update:model-value="(v: string | number) => updateArrayItem(field as ArrayField, idx, String(v))"
            />
          </div>
        </div>
        <Button variant="outline" size="sm" @click="addArrayItem(field as ArrayField)">
          <Plus class="size-4" /> 添加
        </Button>
      </div>

      <!-- MapField -->
      <div v-if="field.kind === 'map'" class="space-y-3">
        <div class="flex items-center gap-2">
          <span class="text-sm font-medium">{{ field.label }}</span>
        </div>
        <p v-if="field.description" class="text-[0.8rem] text-muted-foreground">{{ field.description }}</p>
        <div class="space-y-2">
          <div
            v-for="(v, k) in (modelValue[field.key] as Record<string, unknown> || {})"
            :key="k"
            class="flex items-center gap-2"
          >
            <Input
              class="w-1/3"
              placeholder="键"
              :model-value="String(k)"
              @update:model-value="(nk: string | number) => updateMapKey(field as MapField, String(k), String(nk))"
            />
            <span class="text-muted-foreground text-xs font-mono">→</span>
            <Input
              v-if="(field as MapField).value_schema?.kind === 'primitive'"
              class="flex-1"
              placeholder="值"
              :model-value="String(v ?? '')"
              @update:model-value="(val: string | number) => updateMapValue(field as MapField, String(k), String(val))"
            />
            <FormRenderer
              v-else-if="(field as MapField).value_schema?.kind === 'object'"
              class="flex-1"
              :fields="[(field as MapField).value_schema!]"
              :model-value="v as Record<string, unknown>"
              @update:model-value="(val: Record<string, unknown>) => updateMapValue(field as MapField, String(k), val)"
            />
            <Button variant="ghost" size="icon" @click="removeMapEntry(field as MapField, String(k))">
              <X class="size-4" />
            </Button>
          </div>
        </div>
        <Button variant="outline" size="sm" @click="addMapEntry(field as MapField)">
          <Plus class="size-4" /> 添加
        </Button>
      </div>

      <!-- AnyField -->
      <div v-if="field.kind === 'any'" class="space-y-2">
        <Label>{{ field.label }}</Label>
        <p v-if="field.description" class="text-[0.8rem] text-muted-foreground">{{ field.description }}</p>
        <Input
          :model-value="String(modelValue[field.key] ?? '')"
          @update:model-value="(v: string | number) => updateField(field.key, String(v))"
        />
      </div>
    </template>
  </div>
</template>
