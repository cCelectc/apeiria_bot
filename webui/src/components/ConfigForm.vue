<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { toast } from 'vue-sonner'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { useConfigMutation } from '@/composables/useConfig'
import { usePluginConfigQuery } from '@/composables/usePlugins'

const props = defineProps<{ pluginName: string; open: boolean }>()
const emit = defineEmits<{ 'update:open': [boolean] }>()

const name = computed(() => props.pluginName)
const { data, isLoading } = usePluginConfigQuery(name)
const save = useConfigMutation()

const values = ref<Record<string, unknown>>({})

watch(
  data,
  (cfg) => {
    if (!cfg) return
    const next: Record<string, unknown> = {}
    for (const f of cfg.fields) next[f.key] = f.default
    values.value = next
  },
  { immediate: true },
)

function onSave() {
  save.mutate(
    { section: 'plugins', data: { [props.pluginName]: values.value } },
    {
      onSuccess: () => {
        toast.success('配置已保存')
        emit('update:open', false)
      },
      onError: (e: Error) => toast.error(e.message),
    },
  )
}
</script>

<template>
  <Dialog :open="open" @update:open="(v: boolean) => emit('update:open', v)">
    <DialogContent class="max-h-[80vh] overflow-auto">
      <DialogHeader>
        <DialogTitle>{{ pluginName }} · 配置</DialogTitle>
        <DialogDescription>编辑插件配置项，保存后即时生效</DialogDescription>
      </DialogHeader>

      <div v-if="isLoading" class="py-6 text-center text-sm text-muted-foreground">
        加载中...
      </div>
      <div
        v-else-if="!data || !data.fields.length"
        class="py-6 text-center text-sm text-muted-foreground"
      >
        该插件无可配置项
      </div>
      <div v-else class="space-y-4 py-2">
        <div v-for="f in data.fields" :key="f.key" class="space-y-2">
          <Label :for="f.key">{{ f.label }}</Label>

          <div v-if="f.type === 'bool'" class="flex items-center">
            <Switch
              :id="f.key"
              :model-value="Boolean(values[f.key])"
              @update:model-value="(v: boolean) => (values[f.key] = v)"
            />
          </div>

          <Select
            v-else-if="f.choices && f.choices.length"
            :model-value="String(values[f.key] ?? '')"
            @update:model-value="(v) => (values[f.key] = v)"
          >
            <SelectTrigger :id="f.key">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem
                v-for="c in f.choices"
                :key="String(c)"
                :value="String(c)"
              >
                {{ c }}
              </SelectItem>
            </SelectContent>
          </Select>

          <Input
            v-else-if="f.type === 'int' || f.type === 'float'"
            :id="f.key"
            type="number"
            :model-value="values[f.key] as number"
            @update:model-value="(v) => (values[f.key] = Number(v))"
          />

          <Input
            v-else
            :id="f.key"
            :type="f.secret ? 'password' : 'text'"
            :model-value="values[f.key] as string"
            @update:model-value="(v) => (values[f.key] = v)"
          />

          <p v-if="f.help" class="text-xs text-muted-foreground">{{ f.help }}</p>
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" @click="emit('update:open', false)">取消</Button>
        <Button :disabled="save.isPending.value" @click="onSave">保存</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
