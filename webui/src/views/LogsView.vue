<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { ChevronLeft, ChevronRight, Pause, Play, Trash2 } from '@lucide/vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useLogHistoryQuery } from '@/composables/useLogs'
import { createSseClient } from '@/lib/sse'
import { useAuthStore } from '@/stores/auth'
import type { LogRecord } from '@/types'

const LEVELS = ['DEBUG', 'INFO', 'SUCCESS', 'WARNING', 'ERROR', 'CRITICAL']
const PAGE_SIZE = 100
const MAX_LIVE = 1000

const auth = useAuthStore()
const tab = ref('live')

function levelClass(level: string): string {
  const map: Record<string, string> = {
    DEBUG: 'text-log-debug',
    INFO: 'text-log-info',
    SUCCESS: 'text-log-success',
    WARNING: 'text-log-warning',
    ERROR: 'text-log-error',
    CRITICAL: 'text-log-critical',
  }
  return map[level] ?? 'text-muted-foreground'
}

// ---- live ----
const live = ref<LogRecord[]>([])
const paused = ref(false)
const scrollEl = ref<HTMLElement | null>(null)
let sseClient: ReturnType<typeof createSseClient> | null = null

function scrollToBottom() {
  const el = scrollEl.value
  if (el) el.scrollTop = el.scrollHeight
}

function connect() {
  disconnect()
  if (!auth.token) return
  sseClient = createSseClient(
    '/api/logs/stream',
    auth.token,
    (data) => {
      try {
        const rec = JSON.parse(data) as LogRecord
        live.value.push(rec)
        if (live.value.length > MAX_LIVE) {
          live.value.splice(0, live.value.length - MAX_LIVE)
        }
        if (!paused.value) void nextTick(scrollToBottom)
      } catch {
        // ignore malformed lines
      }
    },
  )
}

function disconnect() {
  sseClient?.close()
  sseClient = null
}

function clearLive() {
  live.value = []
}

watch(
  tab,
  (t) => {
    if (t === 'live') connect()
    else disconnect()
  },
  { immediate: true },
)

onUnmounted(disconnect)

// ---- history ----
const level = ref('all')
const keyword = ref('')
const page = ref(1)

const params = computed(() => ({
  level: level.value === 'all' ? '' : level.value,
  q: keyword.value,
  page: page.value,
  size: PAGE_SIZE,
}))

const { data: history, isFetching } = useLogHistoryQuery(params)

const totalPages = computed(() =>
  history.value ? Math.max(1, Math.ceil(history.value.total / PAGE_SIZE)) : 1,
)

watch([level, keyword], () => {
  page.value = 1
})
</script>

<template>
  <div class="flex h-full flex-col p-6 lg:p-8">
    <h1 class="text-2xl font-semibold tracking-tight">日志</h1>
    <p class="mb-6 mt-1 text-sm text-muted-foreground">实时与历史日志</p>

    <Tabs v-model="tab" class="flex min-h-0 flex-1 flex-col">
      <TabsList class="w-fit">
        <TabsTrigger value="live">实时</TabsTrigger>
        <TabsTrigger value="history">历史</TabsTrigger>
      </TabsList>

      <TabsContent value="live" class="flex min-h-0 flex-1 flex-col">
        <div class="mb-2 flex items-center gap-2">
          <Button variant="outline" size="sm" @click="paused = !paused">
            <component :is="paused ? Play : Pause" class="size-4" />
            {{ paused ? '继续滚动' : '暂停滚动' }}
          </Button>
          <Button variant="outline" size="sm" @click="clearLive">
            <Trash2 class="size-4" />
            清空
          </Button>
        </div>
        <div
          ref="scrollEl"
          class="flex-1 min-h-0 overflow-auto rounded-xl border bg-card p-3 font-mono text-xs"
        >
          <p v-if="!live.length" class="py-6 text-center text-muted-foreground">
            等待日志…
          </p>
          <div v-for="(r, i) in live" :key="i" class="flex gap-2 py-0.5">
            <span class="shrink-0 text-muted-foreground">{{ r.time }}</span>
            <span :class="['w-16 shrink-0 font-medium', levelClass(r.level)]">
              {{ r.level }}
            </span>
            <span class="break-all">{{ r.message }}</span>
          </div>
        </div>
      </TabsContent>

      <TabsContent value="history" class="flex min-h-0 flex-1 flex-col">
        <div class="mb-2 flex flex-wrap items-center gap-2">
          <Select v-model="level">
            <SelectTrigger class="w-36">
              <SelectValue placeholder="级别" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部级别</SelectItem>
              <SelectItem v-for="l in LEVELS" :key="l" :value="l">{{ l }}</SelectItem>
            </SelectContent>
          </Select>
          <Input v-model="keyword" placeholder="关键词…" aria-label="日志关键词" class="max-w-xs" />
        </div>

        <div
          class="flex-1 min-h-0 overflow-auto rounded-xl border bg-card p-3 font-mono text-xs"
        >
          <p v-if="isFetching" class="py-6 text-center text-muted-foreground">加载中…</p>
          <p
            v-else-if="!history || !history.items.length"
            class="py-6 text-center text-muted-foreground"
          >
            暂无日志
          </p>
          <div v-for="(r, i) in history?.items ?? []" :key="i" class="flex gap-2 py-0.5">
            <span class="shrink-0 text-muted-foreground">{{ r.time }}</span>
            <span :class="['w-16 shrink-0 font-medium', levelClass(r.level)]">
              {{ r.level }}
            </span>
            <span class="break-all">{{ r.message }}</span>
          </div>
        </div>

        <div class="mt-2 flex items-center justify-end gap-2 text-sm">
          <span class="text-muted-foreground">
            第 {{ page }} / {{ totalPages }} 页（共 {{ history?.total ?? 0 }} 条）
          </span>
          <Button
            variant="outline"
            size="icon"
            aria-label="上一页"
            :disabled="page <= 1"
            @click="page--"
          >
            <ChevronLeft class="size-4" aria-hidden="true" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            aria-label="下一页"
            :disabled="page >= totalPages"
            @click="page++"
          >
            <ChevronRight class="size-4" aria-hidden="true" />
          </Button>
        </div>
      </TabsContent>
    </Tabs>
  </div>
</template>
