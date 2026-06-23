<template>
  <div class="flex items-center gap-2">
    <Search class="size-4 text-muted-foreground" />
    <Input
      :model-value="modelValue"
      :placeholder="placeholder"
      class="h-9 flex-1 border-0 bg-transparent focus-visible:ring-0"
      @update:model-value="onSearchInput"
    />
    <div v-if="filters && filters.length > 0" class="flex items-center gap-2">
      <Select v-for="f in filters" :key="f.key" :model-value="f.value"         @update:model-value="(v) => onFilterChange(f.key, String(v))">
        <SelectTrigger class="h-9 w-auto gap-1 border-0 bg-muted px-3">
          <SelectValue :placeholder="f.label" />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectItem v-for="opt in f.options" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </SelectItem>
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Search } from "@lucide/vue"
import Input from "@/components/ui/input/Input.vue"
import Select from "@/components/ui/select/Select.vue"
import SelectContent from "@/components/ui/select/SelectContent.vue"
import SelectGroup from "@/components/ui/select/SelectGroup.vue"
import SelectItem from "@/components/ui/select/SelectItem.vue"
import SelectTrigger from "@/components/ui/select/SelectTrigger.vue"
import SelectValue from "@/components/ui/select/SelectValue.vue"

interface FilterDef {
  key: string
  label: string
  value: string
  options: { label: string; value: string }[]
}

defineProps<{
  modelValue: string
  placeholder?: string
  filters?: FilterDef[]
}>()

const emit = defineEmits<{
  "update:modelValue": [value: string]
  "filterChange": [key: string, value: string]
}>()

function onFilterChange(key: string, value: string) {
  emit("filterChange", key, value)
}

function onSearchInput(value: string | number) {
  emit("update:modelValue", String(value))
}
</script>
