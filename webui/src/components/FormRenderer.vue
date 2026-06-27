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

const GROUP_TYPE_LABEL: Record<string, string> = {
  object: '对象',
  array: '数组',
  map: '映射',
  any: 'any',
}

function primTypeLabel(field: PrimitiveField): string {
  if (field.choices?.length) return 'enum'
  return field.type
}

function hasDefault(value: unknown): boolean {
  return value !== undefined && value !== null && value !== ''
}

function fmtDefault(value: unknown): string {
  if (typeof value === 'object') return JSON.stringify(value)
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  return String(value)
}

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
  const tempKey = `__temp_${Date.now()}`
  obj[tempKey] = field.value_schema?.kind === 'primitive'
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
  <div class="divide-y divide-border">
    <template v-for="field in sortedFields" :key="field.key">
      <!-- PrimitiveField -->
      <div v-if="field.kind === 'primitive'" class="py-4 first:pt-0 last:pb-0">
        <div class="flex flex-wrap items-center gap-2">
          <Label :for="field.key" class="font-medium" :class="{ 'cursor-pointer': (field as PrimitiveField).type === 'bool' }">
            {{ (field as PrimitiveField).label }}
          </Label>
          <span v-if="(field as PrimitiveField).required" class="text-destructive text-xs">*</span>
          <span class="rounded-sm bg-accent px-1.5 py-0.5 text-xs font-medium text-accent-foreground">
            {{ primTypeLabel(field as PrimitiveField) }}
          </span>
          <span
            v-if="hasDefault((field as PrimitiveField).default)"
            class="rounded-sm bg-muted px-1.5 py-0.5 text-xs text-muted-foreground"
          >
            默认: {{ fmtDefault((field as PrimitiveField).default) }}
          </span>
        </div>
        <p v-if="field.description" class="mt-1 text-[0.8rem] text-muted-foreground">{{ field.description }}</p>
        <div class="mt-2">
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
      </div>

      <!-- ObjectField -->
      <div v-if="field.kind === 'object'" class="py-4 first:pt-0 last:pb-0">
        <div class="flex items-center gap-2">
          <span class="text-sm font-semibold">{{ field.label }}</span>
          <span class="rounded-sm bg-accent px-1.5 py-0.5 text-xs font-medium text-accent-foreground">
            {{ GROUP_TYPE_LABEL.object }}
          </span>
        </div>
        <p v-if="field.description" class="mt-1 text-[0.8rem] text-muted-foreground">{{ field.description }}</p>
        <div class="mt-3 border-l border-border pl-4">
          <FormRenderer
            :fields="(field as ObjectField).children"
            :model-value="(modelValue[field.key] as Record<string, unknown>) || {}"
            @update:model-value="(v: Record<string, unknown>) => updateField(field.key, v)"
          />
        </div>
      </div>

      <!-- ArrayField -->
      <div v-if="field.kind === 'array'" class="py-4 first:pt-0 last:pb-0">
        <div class="flex items-center gap-2">
          <span class="text-sm font-semibold">{{ field.label }}</span>
          <span class="rounded-sm bg-accent px-1.5 py-0.5 text-xs font-medium text-accent-foreground">
            {{ GROUP_TYPE_LABEL.array }}
          </span>
        </div>
        <p v-if="field.description" class="mt-1 text-[0.8rem] text-muted-foreground">{{ field.description }}</p>
        <div class="mt-3 divide-y divide-border border-l border-border pl-4">
          <div
            v-for="(item, idx) in (modelValue[field.key] as unknown[] || [])"
            :key="idx"
            class="space-y-2 py-3 first:pt-0 last:pb-0"
          >
            <div class="flex justify-between items-center">
              <span class="text-xs text-muted-foreground font-mono">#{{ idx + 1 }}</span>
              <Button variant="ghost" size="icon" aria-label="删除此项" @click="removeArrayItem(field as ArrayField, idx)">
                <X class="size-4" aria-hidden="true" />
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
        <Button variant="outline" size="sm" class="mt-2" @click="addArrayItem(field as ArrayField)">
          <Plus class="size-4" /> 添加
        </Button>
      </div>

      <!-- MapField -->
      <div v-if="field.kind === 'map'" class="py-4 first:pt-0 last:pb-0">
        <div class="flex items-center gap-2">
          <span class="text-sm font-semibold">{{ field.label }}</span>
          <span class="rounded-sm bg-accent px-1.5 py-0.5 text-xs font-medium text-accent-foreground">
            {{ GROUP_TYPE_LABEL.map }}
          </span>
        </div>
        <p v-if="field.description" class="mt-1 text-[0.8rem] text-muted-foreground">{{ field.description }}</p>
        <div class="mt-3 divide-y divide-border border-l border-border pl-4">
          <div
            v-for="(v, k) in (modelValue[field.key] as Record<string, unknown> || {})"
            :key="k"
            class="flex items-center gap-2 py-3 first:pt-0 last:pb-0"
          >
            <Input
              class="w-1/3"
              placeholder="键"
              aria-label="键"
              :model-value="String(k)"
              @update:model-value="(nk: string | number) => updateMapKey(field as MapField, String(k), String(nk))"
            />
            <span class="text-muted-foreground text-xs font-mono">→</span>
            <Input
              v-if="(field as MapField).value_schema?.kind === 'primitive'"
              class="flex-1"
              placeholder="值"
              aria-label="值"
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
            <Button variant="ghost" size="icon" aria-label="删除此项" @click="removeMapEntry(field as MapField, String(k))">
              <X class="size-4" aria-hidden="true" />
            </Button>
          </div>
        </div>
        <Button variant="outline" size="sm" class="mt-2" @click="addMapEntry(field as MapField)">
          <Plus class="size-4" /> 添加
        </Button>
      </div>

      <!-- AnyField -->
      <div v-if="field.kind === 'any'" class="py-4 first:pt-0 last:pb-0">
        <div class="flex items-center gap-2">
          <Label class="font-medium">{{ field.label }}</Label>
          <span class="rounded-sm bg-accent px-1.5 py-0.5 text-xs font-medium text-accent-foreground">
            {{ GROUP_TYPE_LABEL.any }}
          </span>
        </div>
        <p v-if="field.description" class="mt-1 text-[0.8rem] text-muted-foreground">{{ field.description }}</p>
        <div class="mt-2">
          <Input
            :model-value="String(modelValue[field.key] ?? '')"
            @update:model-value="(v: string | number) => updateField(field.key, String(v))"
          />
        </div>
      </div>
    </template>
  </div>
</template>
