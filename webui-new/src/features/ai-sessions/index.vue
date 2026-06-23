<template>
  <div class="grid gap-6 lg:grid-cols-[320px_1fr]">
    <Card class="h-fit">
      <CardHeader class="pb-2">
        <CardTitle class="text-base">Sessions</CardTitle>
        <div class="flex items-center gap-1">
          <Input v-model="sessionFilter" placeholder="Filter..." class="h-8 text-xs" />
          <Button variant="ghost" size="icon" class="size-8" @click="refresh()">
            <RotateCw class="size-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent class="flex flex-col gap-1 max-h-[600px] overflow-auto">
        <Skeleton v-if="sessionsLoading" class="h-48 w-full" />
        <button
          v-for="s in filteredSessions"
          :key="s.id"
          class="flex flex-col rounded-md p-2 text-left text-sm transition-colors hover:bg-muted"
          :class="{ 'bg-muted': selectedId === s.id }"
          @click="selectSession(s.id)"
        >
          <span class="font-mono text-xs truncate">{{ s.id?.slice(0, 16) }}</span>
          <span class="text-xs text-muted-foreground">
            <StatusBadge :variant="s.ai_enabled ? 'success' : 'default'" class="text-[10px]">
              {{ s.ai_enabled ? 'AI on' : 'AI off' }}
            </StatusBadge>
          </span>
        </button>
        <EmptyState v-if="!sessionsLoading && (!sessions || sessions.length === 0)" title="No sessions" />
      </CardContent>
    </Card>

    <Card v-if="selectedId">
      <CardHeader class="flex-row items-center justify-between pb-2">
        <div>
          <CardTitle class="text-sm font-mono">{{ selectedId?.slice(0, 24) }}</CardTitle>
          <CardDescription v-if="detail">
            AI: {{ detail.ai_enabled ? 'Enabled' : 'Disabled' }}
            {{ detail.persona_id ? '| Persona: ' + detail.persona_id : '' }}
          </CardDescription>
        </div>
        <div class="flex items-center gap-2">
          <Button variant="outline" size="sm" @click="toggleAi">
            {{ detail?.ai_enabled ? 'Disable AI' : 'Enable AI' }}
          </Button>
          <Button variant="outline" size="sm" @click="resetCtx">Reset Context</Button>
        </div>
      </CardHeader>
      <CardContent>
        <Skeleton v-if="detailLoading" class="h-64 w-full" />
        <div v-else-if="detail" class="flex flex-col gap-2">
          <div v-for="(msg, i) in (detail.messages as unknown[] ?? [])" :key="i"
            class="flex flex-col rounded-md border p-2 text-sm">
            <div class="flex items-center gap-2 text-xs text-muted-foreground">
              <span>{{ (msg as Record<string,unknown>).role }}</span>
              <span>{{ new Date((msg as Record<string,unknown>).timestamp as string).toLocaleString() }}</span>
            </div>
            <p class="mt-1">{{ String((msg as Record<string,unknown>).content ?? '').slice(0, 300) }}</p>
          </div>
        </div>
        <EmptyState v-else title="No detail" />
      </CardContent>
    </Card>

    <Card v-else>
      <CardContent class="py-12">
        <EmptyState title="Select a session" description="Choose a session from the list to view details." />
      </CardContent>
    </Card>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { RotateCw } from "@lucide/vue"
import { useRequest } from "@/composables/useRequest"
import { aiSessionsService } from "@/api/services/ai-sessions"
import { getApiErrorMessage } from "@/api/client"
import { useNoticeStore } from "@/stores/notice"
import Button from "@/components/ui/button/Button.vue"
import Input from "@/components/ui/input/Input.vue"
import Skeleton from "@/components/ui/skeleton/Skeleton.vue"
import Card from "@/components/ui/card/Card.vue"
import CardContent from "@/components/ui/card/CardContent.vue"
import CardDescription from "@/components/ui/card/CardDescription.vue"
import CardHeader from "@/components/ui/card/CardHeader.vue"
import CardTitle from "@/components/ui/card/CardTitle.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import EmptyState from "@/components/EmptyState.vue"

const notice = useNoticeStore()
const { data: sessions, loading: sessionsLoading, refresh } = useRequest("ai-sessions", () => aiSessionsService.list())
const selectedId = ref<string | null>(null)
const sessionFilter = ref("")

const filteredSessions = computed(() => {
  if (!sessions.value) return []
  const f = sessionFilter.value.toLowerCase()
  if (!f) return sessions.value
  return sessions.value.filter((s: Record<string, unknown>) => String(s.id).toLowerCase().includes(f))
})

// Detail
const detail = ref<Record<string, unknown> | null>(null)
const detailLoading = ref(false)

async function selectSession(id: string) {
  selectedId.value = id
  detailLoading.value = true
  try {
    detail.value = await aiSessionsService.get(id)
  } catch {
    detail.value = null
  } finally {
    detailLoading.value = false
  }
}

async function toggleAi() {
  if (!selectedId.value || !detail.value) return
  try {
    const enabled = !detail.value.ai_enabled
    await aiSessionsService.toggleAi(selectedId.value, enabled)
    detail.value.ai_enabled = enabled
    refresh()
    notice.show(enabled ? "AI enabled" : "AI disabled", "success")
  } catch (err) {
    notice.show(getApiErrorMessage(err, "Failed"), "error")
  }
}

async function resetCtx() {
  if (!selectedId.value) return
  try {
    await aiSessionsService.resetContext(selectedId.value)
    notice.show("Context reset", "success")
  } catch (err) {
    notice.show(getApiErrorMessage(err, "Failed"), "error")
  }
}
</script>
