<template>
  <div class="flex flex-col gap-6">
    <Tabs v-model="mode" class="w-full">
      <TabsList>
        <TabsTrigger value="live">Live</TabsTrigger>
        <TabsTrigger value="history">History</TabsTrigger>
      </TabsList>

      <TabsContent value="live" class="mt-4">
        <Card>
          <CardHeader class="flex-row items-center justify-between">
            <CardTitle>Live Logs</CardTitle>
            <div class="flex items-center gap-2">
              <ToggleGroup v-model="liveLevel" type="single">
                <ToggleGroupItem value="">All</ToggleGroupItem>
                <ToggleGroupItem value="ERROR">Error</ToggleGroupItem>
                <ToggleGroupItem value="WARNING">Warn</ToggleGroupItem>
                <ToggleGroupItem value="INFO">Info</ToggleGroupItem>
              </ToggleGroup>
              <Button variant="outline" size="sm" :disabled="!connected" @click="clearLive">Clear</Button>
              <StatusBadge :variant="connected ? 'success' : 'error'">
                {{ connected ? 'Connected' : 'Disconnected' }}
              </StatusBadge>
            </div>
          </CardHeader>
          <CardContent>
            <div ref="liveRef" class="max-h-[500px] overflow-auto rounded-md bg-muted p-3 font-mono text-xs">
              <div v-if="liveLines.length === 0" class="text-muted-foreground">Waiting for log events...</div>
              <div v-for="(entry, i) in liveLines" :key="i" class="leading-relaxed">
                <span class="text-muted-foreground">{{ entry.time }}</span>
                <span :class="levelColor(entry.level)" class="ml-2">{{ entry.level }}</span>
                <span class="ml-2 text-muted-foreground">{{ entry.source }}</span>
                <span class="ml-2">{{ entry.message }}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </TabsContent>

      <TabsContent value="history" class="mt-4">
        <Card>
          <CardHeader><CardTitle>Log History</CardTitle></CardHeader>
          <CardContent>
            <div class="flex items-center gap-2 mb-4 flex-wrap">
              <Input v-model="search" placeholder="Search..." class="max-w-xs" />
              <Select v-model="historyLevel">
                <SelectTrigger class="w-28"><SelectValue placeholder="Level" /></SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value="">All</SelectItem>
                    <SelectItem value="ERROR">Error</SelectItem>
                    <SelectItem value="WARNING">Warning</SelectItem>
                    <SelectItem value="INFO">Info</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
              <Button variant="outline" size="sm" @click="fetchHistory">Search</Button>
            </div>
            <Skeleton v-if="historyLoading" class="h-64 w-full" />
            <DataTable
              v-else-if="historyItems.length > 0"
              :columns="logCols"
              :rows="historyItems as unknown as Record<string, unknown>[]"
            />
            <EmptyState v-else title="No logs" description="Try adjusting filters." />
          </CardContent>
        </Card>
      </TabsContent>
    </Tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from "vue"
import { logsService, type LogItem } from "@/api/services/logs"
import Tabs from "@/components/ui/tabs/Tabs.vue"
import TabsContent from "@/components/ui/tabs/TabsContent.vue"
import TabsList from "@/components/ui/tabs/TabsList.vue"
import TabsTrigger from "@/components/ui/tabs/TabsTrigger.vue"
import Card from "@/components/ui/card/Card.vue"
import CardContent from "@/components/ui/card/CardContent.vue"
import CardHeader from "@/components/ui/card/CardHeader.vue"
import CardTitle from "@/components/ui/card/CardTitle.vue"
import Button from "@/components/ui/button/Button.vue"
import Input from "@/components/ui/input/Input.vue"
import Skeleton from "@/components/ui/skeleton/Skeleton.vue"
import Select from "@/components/ui/select/Select.vue"
import SelectContent from "@/components/ui/select/SelectContent.vue"
import SelectGroup from "@/components/ui/select/SelectGroup.vue"
import SelectItem from "@/components/ui/select/SelectItem.vue"
import SelectTrigger from "@/components/ui/select/SelectTrigger.vue"
import SelectValue from "@/components/ui/select/SelectValue.vue"
import ToggleGroup from "@/components/ui/toggle-group/ToggleGroup.vue"
import ToggleGroupItem from "@/components/ui/toggle-group/ToggleGroupItem.vue"
import DataTable from "@/components/DataTable.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import EmptyState from "@/components/EmptyState.vue"

const mode = ref("live")
const logCols = [
  { key: "timestamp", label: "Time" },
  { key: "level", label: "Level" },
  { key: "source", label: "Source" },
  { key: "message", label: "Message" },
]

// Live
interface LiveEntry { time: string; level: string; source: string; message: string }
const liveLines = ref<LiveEntry[]>([])
const liveLevel = ref("")
const liveRef = ref<HTMLElement>()
const connected = ref(false)
let ws: WebSocket | null = null

function levelColor(l: string) {
  if (l === "ERROR") return "text-destructive font-semibold"
  if (l === "WARNING") return "text-yellow-500"
  return "text-emerald-500"
}

function connectLive() {
  const protocol = location.protocol === "https:" ? "wss" : "ws"
  ws = new WebSocket(`${protocol}://${location.host}/api/logs/ws`)
  ws.onopen = () => { connected.value = true }
  ws.onclose = () => { connected.value = false; setTimeout(connectLive, 3000) }
  ws.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data) as LogItem
      if (liveLevel.value && data.level !== liveLevel.value) return
      liveLines.value.push({
        time: new Date(data.timestamp).toLocaleTimeString(),
        level: data.level,
        source: data.source,
        message: data.message,
      })
      if (liveLines.value.length > 500) liveLines.value.splice(0, 100)
      nextTick(() => {
        if (liveRef.value) liveRef.value.scrollTop = liveRef.value.scrollHeight
      })
    } catch { /* ignore malformed frames */ }
  }
}

function clearLive() { liveLines.value = [] }

onMounted(connectLive)
onBeforeUnmount(() => ws?.close())

// History
const search = ref("")
const historyLevel = ref("")
const historyLoading = ref(false)
const historyItems = ref<LogItem[]>([])

async function fetchHistory() {
  historyLoading.value = true
  try {
    const data = await logsService.history({
      search: search.value || undefined,
      level: historyLevel.value || undefined,
      page_size: 200,
    })
    historyItems.value = data.items
  } finally {
    historyLoading.value = false
  }
}
</script>
