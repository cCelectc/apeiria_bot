<script setup lang="ts">
import { computed } from 'vue'
import { dump } from 'js-yaml'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { type DiffKind, flattenDiff, lineDiff } from '@/lib/configDiff'
import type { FieldNode } from '@/types'

const props = defineProps<{
  open: boolean
  original: Record<string, unknown>
  current: Record<string, unknown>
  fields: FieldNode[]
  saving?: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  save: []
  discard: []
  cancel: []
}>()

const structured = computed(() =>
  flattenDiff(props.original, props.current, props.fields),
)
const lines = computed(() =>
  lineDiff(dump(props.original, { indent: 2 }), dump(props.current, { indent: 2 })),
)

function fmt(v: unknown): string {
  if (v === undefined) return '—'
  if (v === null) return 'null'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

const kindLabel: Record<DiffKind, string> = {
  added: '新增',
  removed: '删除',
  changed: '变更',
}

function rowClass(kind: DiffKind): string {
  if (kind === 'added') return 'bg-emerald-500/10'
  if (kind === 'removed') return 'bg-red-500/10'
  return 'bg-amber-500/10'
}

function onOpenChange(v: boolean) {
  emit('update:open', v)
  if (!v) emit('cancel')
}
</script>

<template>
  <Dialog :open="open" @update:open="onOpenChange">
    <DialogContent class="max-w-lg">
      <DialogHeader>
        <DialogTitle>未保存的更改</DialogTitle>
        <DialogDescription>你有未保存的配置改动，请选择如何处理。</DialogDescription>
      </DialogHeader>

      <Tabs default-value="structured">
        <TabsList>
          <TabsTrigger value="structured">结构化</TabsTrigger>
          <TabsTrigger value="advanced">高级</TabsTrigger>
        </TabsList>

        <TabsContent value="structured">
          <div class="max-h-[45vh] space-y-2 overflow-y-auto pt-2">
            <p v-if="!structured.length" class="py-6 text-center text-sm text-muted-foreground">
              无差异
            </p>
            <div
              v-for="d in structured"
              :key="d.path"
              :class="rowClass(d.kind)"
              class="rounded-md px-3 py-2 text-sm"
            >
              <div class="flex items-center gap-2">
                <span class="font-medium">{{ d.label }}</span>
                <span class="font-mono text-xs text-muted-foreground">{{ d.path }}</span>
                <span class="ml-auto text-xs text-muted-foreground">{{ kindLabel[d.kind] }}</span>
              </div>
              <div class="mt-1 font-mono text-xs">
                <span v-if="d.kind !== 'added'" class="text-red-600 line-through dark:text-red-400">
                  {{ fmt(d.before) }}
                </span>
                <span v-if="d.kind === 'changed'" class="mx-1 text-muted-foreground">→</span>
                <span v-if="d.kind !== 'removed'" class="text-emerald-600 dark:text-emerald-400">
                  {{ fmt(d.after) }}
                </span>
              </div>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="advanced">
          <pre class="max-h-[45vh] overflow-auto rounded-md bg-muted p-3 font-mono text-xs leading-relaxed"><template v-for="(l, i) in lines" :key="i"><span
              :class="{
                'block bg-emerald-500/15 text-emerald-700 dark:text-emerald-300': l.kind === 'add',
                'block bg-red-500/15 text-red-700 dark:text-red-300': l.kind === 'del',
                'block text-muted-foreground': l.kind === 'same',
              }"
            >{{ l.kind === 'add' ? '+ ' : l.kind === 'del' ? '- ' : '  ' }}{{ l.text }}</span></template></pre>
        </TabsContent>
      </Tabs>

      <DialogFooter>
        <Button variant="ghost" @click="emit('cancel')">继续编辑</Button>
        <Button variant="outline" @click="emit('discard')">放弃更改并关闭</Button>
        <Button :disabled="saving" @click="emit('save')">
          {{ saving ? '保存中…' : '保存并关闭' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
