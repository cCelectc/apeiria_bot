<script setup lang="ts">
import { ref, watch } from 'vue'
import { toast } from 'vue-sonner'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { useConfigMutation, useConfigQuery } from '@/composables/useConfig'

const sections = ['nonebot', 'plugins', 'adapters', 'apeiria'] as const

const { data, isLoading } = useConfigQuery()
const save = useConfigMutation()

const drafts = ref<Record<string, string>>({})

watch(
  data,
  (cfg) => {
    if (!cfg) return
    const next: Record<string, string> = {}
    for (const s of sections) next[s] = JSON.stringify(cfg[s] ?? {}, null, 2)
    drafts.value = next
  },
  { immediate: true },
)

function saveSection(section: string) {
  let parsed: Record<string, unknown>
  try {
    parsed = JSON.parse(drafts.value[section] ?? '{}')
  } catch {
    toast.error('JSON 格式错误')
    return
  }
  save.mutate(
    { section, data: parsed },
    {
      onSuccess: () => toast.success('已保存'),
      onError: (e: Error) => toast.error(e.message),
    },
  )
}
</script>

<template>
  <div class="p-6 lg:p-8">
    <h1 class="text-2xl font-semibold tracking-tight">配置</h1>
    <p class="mb-6 mt-1 text-sm text-muted-foreground">
      四块配置读写（nonebot 的 host/port 等核心字段修改后需重启生效）
    </p>

    <div v-if="isLoading" class="text-sm text-muted-foreground">加载中...</div>
    <Tabs v-else default-value="nonebot">
      <TabsList>
        <TabsTrigger v-for="s in sections" :key="s" :value="s">{{ s }}</TabsTrigger>
      </TabsList>
      <TabsContent v-for="s in sections" :key="s" :value="s" class="space-y-3">
        <Textarea
          v-model="drafts[s]"
          spellcheck="false"
          class="min-h-80 font-mono text-xs"
        />
        <Button :disabled="save.isPending.value" @click="saveSection(s)">保存</Button>
      </TabsContent>
    </Tabs>
  </div>
</template>
