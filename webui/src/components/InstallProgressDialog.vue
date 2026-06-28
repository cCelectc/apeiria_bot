<script setup lang="ts">
import { ref, watch, onUnmounted } from "vue";
import { Loader, Terminal } from "@lucide/vue";
import { createSseClient } from "@/lib/sse";
import { useAuthStore } from "@/stores/auth";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { TaskEvent } from "@/types";

const props = defineProps<{
  open: boolean;
  taskId: string | null;
  title: string;
}>();

const emit = defineEmits<{
  (e: "close"): void;
}>();

const auth = useAuthStore();
const lines = ref<string[]>([]);
const status = ref<"running" | "done" | "error">("running");
const errorMsg = ref("");
let sse: ReturnType<typeof createSseClient> | null = null;

function startStream(taskId: string) {
  lines.value = [];
  status.value = "running";
  errorMsg.value = "";

  sse = createSseClient(
    `/api/tasks/${taskId}/stream`,
    auth.token ?? "",
    (data) => {
      try {
        const event: TaskEvent = JSON.parse(data);
        if (event.type === "output" && event.text !== undefined) {
          lines.value.push(event.text);
        } else if (event.type === "done") {
          status.value = "done";
        } else if (event.type === "error") {
          status.value = "error";
          errorMsg.value = event.message ?? "安装失败";
        }
      } catch {
        lines.value.push(data);
      }
    },
  );
}

function stopStream() {
  sse?.close();
  sse = null;
}

function handleClose() {
  stopStream();
  emit("close");
}

watch(
  () => props.taskId,
  (newId) => {
    stopStream();
    if (newId && props.open) {
      startStream(newId);
    }
  },
);

watch(
  () => props.open,
  (open) => {
    if (!open) {
      stopStream();
    } else if (props.taskId) {
      startStream(props.taskId);
    }
  },
);

onUnmounted(() => stopStream());
</script>

<template>
  <Dialog :open="open" @update:open="(v) => !v && handleClose()">
    <DialogContent
      class="max-w-lg max-h-[80vh] flex flex-col"
      :show-close-button="status === 'done' || status === 'error'"
    >
      <DialogHeader>
        <DialogTitle class="flex items-center gap-2">
          <Terminal class="size-4" />
          {{ title }}
        </DialogTitle>
        <DialogDescription v-if="status === 'running'">
          正在安装，请稍候...
        </DialogDescription>
        <DialogDescription v-else-if="status === 'done'">
          安装完成
        </DialogDescription>
        <DialogDescription v-else>
          安装失败
        </DialogDescription>
      </DialogHeader>

      <ScrollArea class="flex-1 min-h-[200px] max-h-[50vh] rounded-md border bg-black p-3">
        <pre
          class="font-mono text-xs text-green-400 whitespace-pre-wrap break-all leading-relaxed"
        ><template v-for="(line, i) in lines" :key="i">{{ line + '\n' }}</template><span
            v-if="status === 'running'"
            class="inline-block w-3 h-4 bg-green-400 animate-pulse align-middle ml-0.5"
          >&nbsp;</span><span v-if="status === 'error'" class="text-red-400">{{ errorMsg }}</span></pre>
      </ScrollArea>

      <DialogFooter>
        <div v-if="status === 'running'" class="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader class="size-4 animate-spin" />
          安装中...
        </div>
        <Button
          v-if="status === 'done' || status === 'error'"
          variant="outline"
          @click="handleClose"
        >
          {{ status === 'done' ? '完成' : '关闭' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
