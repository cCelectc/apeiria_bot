<script setup lang="ts">
import { computed } from 'vue'
import { Activity, Plug, Puzzle } from '@lucide/vue'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useStatusQuery } from '@/composables/useStatus'

const { data, isLoading } = useStatusQuery()

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const parts: string[] = []
  if (d) parts.push(`${d}天`)
  if (h) parts.push(`${h}小时`)
  parts.push(`${m}分`)
  return parts.join(' ')
}

const cards = computed(() => {
  const d = data.value
  return [
    {
      label: '运行时长',
      value: d ? formatUptime(d.uptime) : '—',
      icon: Activity,
      color: 'bg-primary/10 text-primary',
    },
    {
      label: '已加载插件',
      value: d ? String(d.plugin_count) : '—',
      icon: Puzzle,
      color: 'bg-chart-2/10 text-chart-2',
    },
    {
      label: '已加载适配器',
      value: d ? String(d.adapters.length) : '—',
      icon: Plug,
      color: 'bg-chart-3/10 text-chart-3',
    },
  ]
})
</script>

<template>
  <div class="p-6 lg:p-8">
    <h1 class="text-2xl font-semibold tracking-tight">看板</h1>
    <p class="mb-6 mt-1 text-sm text-muted-foreground">运行状态总览</p>

    <div v-if="isLoading" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <Skeleton v-for="i in 3" :key="i" class="h-28 rounded-xl" />
    </div>
    <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <Card v-for="c in cards" :key="c.label">
        <CardContent class="flex items-center gap-4 p-6">
          <div :class="['flex size-12 items-center justify-center rounded-xl', c.color]">
            <component :is="c.icon" class="size-6" />
          </div>
          <div>
            <p class="text-sm text-muted-foreground">{{ c.label }}</p>
            <p class="text-2xl font-bold">{{ c.value }}</p>
          </div>
        </CardContent>
      </Card>
    </div>

    <Card v-if="data && data.adapters.length" class="mt-4">
      <CardContent class="p-6">
        <p class="mb-3 text-sm font-medium">已加载适配器</p>
        <div class="flex flex-wrap gap-2">
          <span
            v-for="a in data.adapters"
            :key="a"
            class="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground"
          >
            {{ a }}
          </span>
        </div>
      </CardContent>
    </Card>
  </div>
</template>
