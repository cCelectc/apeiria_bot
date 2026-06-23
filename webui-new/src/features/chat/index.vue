<template>
  <div class="grid gap-6 lg:grid-cols-[280px_1fr]">
    <Card class="h-fit">
      <CardHeader class="flex-row items-center justify-between pb-2">
        <CardTitle>Sessions</CardTitle>
        <Button variant="ghost" size="icon" class="size-8" @click="createSession">
          <Plus class="size-4" />
        </Button>
      </CardHeader>
      <CardContent class="flex flex-col gap-1">
        <div v-if="sessions.length === 0" class="text-sm text-muted-foreground p-2">No sessions</div>
        <button
          v-for="s in sessions"
          :key="s.session.session_id"
          class="flex flex-col rounded-md p-2 text-left text-sm transition-colors hover:bg-muted"
          :class="{ 'bg-muted': activeId === s.session.session_id }"
          @click="selectSession(s.session.session_id)"
        >
          <span class="font-medium truncate">{{ s.session.session_id.slice(0, 12) }}</span>
          <span class="text-xs text-muted-foreground">{{ s.message_count }} msgs</span>
        </button>
      </CardContent>
    </Card>

    <div class="flex flex-col gap-0">
      <Card class="flex-1 flex flex-col rounded-b-none border-b-0">
        <CardHeader class="flex-row items-center justify-between pb-2">
          <div class="flex items-center gap-2">
            <StatusBadge :variant="connected ? 'success' : 'error'">
              {{ connected ? 'Connected' : 'Disconnected' }}
            </StatusBadge>
            <CardTitle v-if="activeId" class="text-sm font-mono">{{ activeId.slice(0, 16) }}</CardTitle>
            <CardTitle v-else class="text-sm">Select a session</CardTitle>
          </div>
          <Button v-if="activeId" variant="ghost" size="sm" @click="deleteSession">Delete</Button>
        </CardHeader>
        <CardContent class="flex-1 overflow-auto">
          <div ref="msgRef" class="flex flex-col gap-2">
            <div v-if="messages.length === 0 && activeId" class="text-center text-sm text-muted-foreground py-8">
              No messages yet. Type something below.
            </div>
            <div v-if="!activeId" class="text-center text-sm text-muted-foreground py-8">
              Create or select a session to start chatting.
            </div>
            <div
              v-for="msg in messages"
              :key="msg.message_id"
              class="flex"
              :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
            >
              <div
                class="max-w-[80%] rounded-lg px-3 py-2 text-sm"
                :class="msg.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted'"
              >
                <template v-for="(seg, j) in msg.segments" :key="j">
                  <span v-if="seg.type === 'text'">{{ seg.text }}</span>
                  <img
                    v-else-if="seg.type === 'image' && seg.url"
                    :src="seg.url"
                    class="max-w-[200px] rounded"
                  />
                </template>
                <div class="mt-1 text-[10px] opacity-60">{{ formatTime(msg.timestamp) }}</div>
              </div>
            </div>
            <div v-if="streaming" class="flex justify-start">
              <div class="max-w-[80%] rounded-lg bg-muted px-3 py-2 text-sm">
                {{ streamText }}<span class="animate-pulse">|</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <div class="flex items-center gap-2 rounded-b-lg border bg-background p-3">
        <Input
          v-model="inputText"
          placeholder="Type a message..."
          class="flex-1"
          :disabled="!activeId"
          @keydown.enter="doSend"
        />
        <Button size="icon" :disabled="!activeId || !inputText.trim()" @click="doSend">
          <Send class="size-4" />
        </Button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from "vue"
import { onMounted, onBeforeUnmount } from "vue"
import { Plus, Send } from "@lucide/vue"
import { useChatTransport } from "@/composables/chat/useChatTransport"
import type {
  SessionListItem,
  SessionSnapshotPayload,
  MessageReceivePayload,
  PartialReplyStartPayload,
  PartialReplyDeltaPayload,
  PartialReplyCompletePayload,
  TextSegment,
} from "@/types/chat"
import Button from "@/components/ui/button/Button.vue"
import Input from "@/components/ui/input/Input.vue"
import Card from "@/components/ui/card/Card.vue"
import CardContent from "@/components/ui/card/CardContent.vue"
import CardHeader from "@/components/ui/card/CardHeader.vue"
import CardTitle from "@/components/ui/card/CardTitle.vue"
import StatusBadge from "@/components/StatusBadge.vue"

const { connected, connect, disconnect, send, on } = useChatTransport()
const sessions = ref<SessionListItem[]>([])
const activeId = ref<string | null>(null)
const messages = ref<MessageReceivePayload[]>([])
const inputText = ref("")
const streaming = ref(false)
const streamText = ref("")
const msgRef = ref<HTMLElement>()

let streamId = ""

function formatTime(ts: string) {
  return new Date(ts).toLocaleTimeString()
}

function scrollBottom() {
  nextTick(() => {
    if (msgRef.value) msgRef.value.scrollTop = msgRef.value.scrollHeight
  })
}

on("session.snapshot", (p) => {
  const snap = p as SessionSnapshotPayload
  sessions.value = snap.sessions
  if (snap.active_session) {
    activeId.value = snap.active_session.session_id
    messages.value = snap.history
  }
  scrollBottom()
})

on("message.receive", (p) => {
  const msg = p as MessageReceivePayload
  messages.value.push(msg)
  scrollBottom()
})

on("reply.partial.start", (p) => {
  const start = p as PartialReplyStartPayload
  streaming.value = true
  streamText.value = ""
  streamId = start.stream_id
})

on("reply.partial.delta", (p) => {
  const d = p as PartialReplyDeltaPayload
  if (d.stream_id === streamId) streamText.value += d.content_delta
  scrollBottom()
})

on("reply.partial.complete", (p) => {
  const done = p as PartialReplyCompletePayload
  streaming.value = false
  streamText.value = ""
  if (done.message_id) send("session.list", {})
})

on("reply.partial.failed", () => {
  streaming.value = false
  streamText.value = ""
})

function createSession() {
  send("session.create", { target_user_id: "webui" })
}

function selectSession(id: string) {
  send("session.select", { session_id: id })
}

function doSend() {
  const text = inputText.value.trim()
  if (!text || !activeId.value) return
  const segment: TextSegment = { type: "text", text }
  send("message.send", {
    session_id: activeId.value,
    message_id: crypto.randomUUID(),
    segments: [segment],
  })
  inputText.value = ""
}

function deleteSession() {
  if (!activeId.value) return
  send("session.delete", { session_id: activeId.value })
}

onMounted(() => {
  const protocol = location.protocol === "https:" ? "wss" : "ws"
  connect(`${protocol}://${location.host}/api/chat/ws`)
})

onBeforeUnmount(() => disconnect())
</script>
