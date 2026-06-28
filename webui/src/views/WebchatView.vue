<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { ImagePlus, Send, Trash2, X } from "@lucide/vue";
import PageHeader from "@/components/PageHeader.vue";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useWebchat } from "@/composables/useWebchat";
import { cn } from "@/lib/utils";

const {
  messages,
  connected,
  identity,
  send,
  clear,
  deleteMessage,
  setIdentity,
} = useWebchat();

const draft = ref("");
const pendingImage = ref<string | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
const scrollEl = ref<HTMLElement | null>(null);
const clearOpen = ref(false);

const sceneType = computed({
  get: () => identity.value.scene_type ?? "private",
  set: (v: string) =>
    setIdentity({ scene_type: v === "group" ? "group" : "private" }),
});
const userId = computed({
  get: () => identity.value.user_id ?? "",
  set: (v: string) => setIdentity({ user_id: v }),
});
const sceneId = computed({
  get: () => identity.value.scene_id ?? "",
  set: (v: string) => setIdentity({ scene_id: v }),
});

function scrollToBottom() {
  const el = scrollEl.value;
  if (el) el.scrollTop = el.scrollHeight;
}

watch(
  () => messages.value.length,
  () => void nextTick(scrollToBottom),
);

function onSend() {
  send(draft.value, pendingImage.value ?? undefined);
  draft.value = "";
  pendingImage.value = null;
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    onSend();
  }
}

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  if (file) {
    const reader = new FileReader();
    reader.onload = () => (pendingImage.value = reader.result as string);
    reader.readAsDataURL(file);
  }
  input.value = "";
}

function onClear() {
  clear();
  clearOpen.value = false;
}

function avatarText(role: string): string {
  return role === "user" ? "U" : "B";
}
</script>

<template>
  <div class="flex h-full flex-col p-6 lg:p-8">
    <PageHeader :title="$t('webchat.title')" :subtitle="$t('webchat.subtitle')">
      <template #actions>
        <div class="flex items-center gap-3">
          <span class="flex items-center gap-1.5 text-sm text-muted-foreground">
            <span
              :class="
                cn(
                  'size-2 rounded-full',
                  connected ? 'bg-success' : 'bg-destructive',
                )
              "
            />
            {{
              connected ? $t("webchat.connected") : $t("webchat.disconnected")
            }}
          </span>
          <Dialog v-model:open="clearOpen">
            <DialogTrigger as-child>
              <Button variant="outline" size="sm">
                <Trash2 class="size-4" />
                {{ $t("webchat.clear") }}
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{{ $t("webchat.clearConfirmTitle") }}</DialogTitle>
                <DialogDescription>
                  {{ $t("webchat.clearConfirmDesc") }}
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button variant="outline" @click="clearOpen = false">
                  {{ $t("common.cancel") }}
                </Button>
                <Button variant="destructive" @click="onClear">
                  {{ $t("common.confirm") }}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </template>
    </PageHeader>

    <div class="mb-3 flex flex-wrap items-center gap-2">
      <Select v-model="sceneType">
        <SelectTrigger class="w-32">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="private">
            {{ $t("webchat.scenePrivate") }}
          </SelectItem>
          <SelectItem value="group">{{ $t("webchat.sceneGroup") }}</SelectItem>
        </SelectContent>
      </Select>
      <Input
        v-model="userId"
        class="w-44"
        :placeholder="$t('webchat.userIdPlaceholder')"
        :aria-label="$t('webchat.userIdPlaceholder')"
      />
      <Input
        v-if="sceneType === 'group'"
        v-model="sceneId"
        class="w-44"
        :placeholder="$t('webchat.sceneIdPlaceholder')"
        :aria-label="$t('webchat.sceneIdPlaceholder')"
      />
    </div>

    <div
      ref="scrollEl"
      class="flex min-h-0 flex-1 flex-col gap-4 overflow-auto rounded-xl border bg-card p-4"
    >
      <p
        v-if="!messages.length"
        class="py-10 text-center text-sm text-muted-foreground"
      >
        {{ $t("webchat.empty") }}
      </p>
      <div
        v-for="m in messages"
        :key="m.id"
        :class="
          cn(
            'group flex items-end gap-2',
            m.role === 'user' ? 'flex-row-reverse' : 'flex-row',
          )
        "
      >
        <Avatar class="size-8 shrink-0">
          <AvatarFallback
            :class="
              m.role === 'user'
                ? 'bg-accent text-accent-foreground'
                : 'bg-primary/10 text-primary'
            "
          >
            {{ avatarText(m.role) }}
          </AvatarFallback>
        </Avatar>
        <div
          :class="
            cn(
              'flex max-w-[75%] flex-col gap-1',
              m.role === 'user' ? 'items-end' : 'items-start',
            )
          "
        >
          <div
            :class="
              cn(
                'rounded-lg px-3 py-2 text-sm break-words',
                m.role === 'user'
                  ? 'bg-accent text-accent-foreground'
                  : 'bg-secondary text-secondary-foreground',
              )
            "
          >
            <template v-for="(seg, i) in m.segments" :key="i">
              <span v-if="seg.type === 'text'" class="whitespace-pre-wrap">{{
                seg.text
              }}</span>
              <img
                v-else-if="seg.type === 'image'"
                :src="seg.url"
                alt=""
                class="max-h-60 max-w-full rounded-md"
              />
              <details v-else class="text-xs">
                <summary class="cursor-pointer">
                  <Badge variant="secondary">{{ seg.seg_type }}</Badge>
                </summary>
                <pre class="mt-1 overflow-auto">{{
                  JSON.stringify(seg.data, null, 2)
                }}</pre>
              </details>
            </template>
          </div>
          <div class="flex items-center gap-2 text-xs text-muted-foreground">
            <span>{{ m.time }}</span>
            <button
              type="button"
              class="opacity-0 transition-opacity group-hover:opacity-100"
              :aria-label="$t('webchat.deleteMessage')"
              @click="deleteMessage(m.id)"
            >
              <Trash2 class="size-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="mt-3 flex items-end gap-2">
      <input
        ref="fileInput"
        type="file"
        accept="image/*"
        class="hidden"
        @change="onFileChange"
      />
      <Button
        variant="outline"
        size="icon"
        :aria-label="$t('webchat.attachImage')"
        @click="fileInput?.click()"
      >
        <ImagePlus class="size-4" />
      </Button>
      <div class="flex-1">
        <div
          v-if="pendingImage"
          class="mb-2 inline-flex items-center gap-2 rounded-md border bg-muted p-1"
        >
          <img
            :src="pendingImage"
            alt=""
            class="size-12 rounded object-cover"
          />
          <Button
            variant="ghost"
            size="icon"
            :aria-label="$t('common.delete')"
            @click="pendingImage = null"
          >
            <X class="size-4" />
          </Button>
        </div>
        <Textarea
          v-model="draft"
          rows="1"
          :placeholder="$t('webchat.inputPlaceholder')"
          @keydown="onKeydown"
        />
      </div>
      <Button :disabled="!connected" @click="onSend">
        <Send class="size-4" />
        {{ $t("webchat.send") }}
      </Button>
    </div>
  </div>
</template>
