<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { toast } from "vue-sonner";
import {
  AlertTriangle,
  ArrowUpCircle,
  GitBranch,
  GitCommit,
  Loader2,
  Terminal,
} from "@lucide/vue";
import { api } from "@/lib/api";
import ErrorState from "@/components/ErrorState.vue";
import PageHeader from "@/components/PageHeader.vue";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuthStore } from "@/stores/auth";
import type {
  UpdateEvent,
  UpdatePreviewResponse,
  UpdateStatusResponse,
} from "@/types";

const { t } = useI18n();
const auth = useAuthStore();

const status = ref<UpdateStatusResponse | null>(null);
const statusLoading = ref(false);
const statusError = ref("");
const preview = ref<UpdatePreviewResponse | null>(null);
const previewLoading = ref(false);
const selectedBranch = ref("");
const executing = ref(false);
const terminalLines = ref<string[]>([]);
const stage = ref("");
const updateFailed = ref(false);
const updateDone = ref(false);
const rollbackOccurred = ref(false);
const polling = ref(false);
const terminalEl = ref<HTMLElement | null>(null);
let abortController: AbortController | null = null;

async function fetchStatus() {
  statusLoading.value = true;
  statusError.value = "";
  try {
    status.value = await api.update.status();
    if (!selectedBranch.value && status.value) {
      selectedBranch.value = status.value.branch;
    }
  } catch (err: unknown) {
    statusError.value = (err as Error).message;
  } finally {
    statusLoading.value = false;
  }
}

async function fetchPreview() {
  if (!selectedBranch.value) return;
  previewLoading.value = true;
  preview.value = null;
  try {
    preview.value = await api.update.preview(selectedBranch.value);
  } catch {
    preview.value = null;
  } finally {
    previewLoading.value = false;
  }
}

watch(selectedBranch, () => {
  fetchPreview();
});

const canExecute = computed(() => {
  if (!status.value) return false;
  return !status.value.is_dirty && !executing.value && !updateDone.value;
});

const dirtyFiles = computed(() => {
  if (!status.value?.dirty_files) return [];
  return status.value.dirty_files;
});

const terminals = computed(() => {
  if (executing.value && terminalLines.value.length === 0) {
    return [t("update.terminalPlaceholder")];
  }
  return terminalLines.value;
});

function stageLabel(s: string): string {
  const map: Record<string, string> = {
    checkout: t("update.checkout"),
    pull: t("update.pull"),
    sync: t("update.sync"),
    error: t("update.failed"),
    done: t("update.success"),
  };
  return map[s] ?? s;
}

async function scrollTerminal() {
  await nextTick();
  if (terminalEl.value) {
    terminalEl.value.scrollTop = terminalEl.value.scrollHeight;
  }
}

async function executeUpdate() {
  if (!selectedBranch.value || executing.value) return;
  executing.value = true;
  updateFailed.value = false;
  updateDone.value = false;
  rollbackOccurred.value = false;
  terminalLines.value = [];
  stage.value = "";

  abortController = new AbortController();

  try {
    const res = await api.update.execute(selectedBranch.value);
    if (!res.ok || !res.body) {
      throw new Error(`HTTP ${res.status}`);
    }

    const reader = res.body
      .pipeThrough(new TextDecoderStream())
      .getReader();

    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += value;
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const event: UpdateEvent = JSON.parse(line.slice(6));
          stage.value = event.stage;
          terminalLines.value.push(event.line);
          await scrollTerminal();

          if (event.stage === "error") {
            updateFailed.value = true;
            if (event.line.includes("回滚")) {
              rollbackOccurred.value = true;
            }
          }
          if (event.stage === "done") {
            updateDone.value = true;
            pollUntilUp();
          }
        } catch {
          // skip unparseable events
        }
      }
    }
  } catch (err: unknown) {
    const msg = (err as Error).message;
    if (msg !== "AbortError") {
      terminalLines.value.push(`Connection lost: ${msg}`);
      updateFailed.value = true;
    }
  } finally {
    executing.value = false;
    abortController = null;
  }
}

function pollUntilUp() {
  polling.value = true;
  let attempts = 0;
  const max = 60;
  const interval = setInterval(async () => {
    attempts++;
    try {
      await api.status.get();
      clearInterval(interval);
      toast.success(t("update.success"));
      polling.value = false;
      fetchStatus();
    } catch {
      if (attempts >= max) {
        clearInterval(interval);
        polling.value = false;
        toast.error(t("dashboard.restartTimeout"));
      }
    }
  }, 2000);
}

function cancelUpdate() {
  if (abortController) {
    abortController.abort();
    abortController = null;
  }
  executing.value = false;
}

onUnmounted(() => {
  cancelUpdate();
});

const commitsBehindText = computed(() => {
  if (!preview.value) return "";
  if (preview.value.commits_behind === 0) {
    return t("update.upToDate");
  }
  return t("update.commitsBehind", { count: preview.value.commits_behind });
});

const isBehind = computed(() => {
  return preview.value ? preview.value.commits_behind > 0 : false;
});

fetchStatus();
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col gap-6 p-6">
    <PageHeader
      :title="t('update.title')"
      :subtitle="t('update.subtitle')"
      class="flex-none"
    />

    <ErrorState
      v-if="statusError"
      :title="$t('error.loadFailed')"
      :description="statusError"
      @retry="fetchStatus()"
    />

    <template v-else>
      <!-- Status Card -->
      <Card class="flex-none">
        <CardHeader>
          <CardTitle class="flex items-center gap-2 text-base">
            <GitBranch class="size-4" />
            {{ t("update.currentBranch") }}
          </CardTitle>
        </CardHeader>
        <CardContent class="space-y-3">
          <div v-if="statusLoading" class="space-y-2">
            <Skeleton class="h-5 w-48" />
            <Skeleton class="h-4 w-96" />
          </div>
          <template v-else-if="status">
            <div class="flex items-center gap-2">
              <Badge variant="secondary">{{ status.branch }}</Badge>
              <GitCommit class="size-3.5 text-muted-foreground" />
              <code class="text-sm text-muted-foreground">{{ status.commit_hash }}</code>
              <span class="text-sm text-muted-foreground truncate">
                {{ status.commit_message }}
              </span>
            </div>

            <!-- Dirty Warning -->
            <div
              v-if="status.is_dirty"
              class="flex items-start gap-2 rounded-md border border-yellow-600/40 bg-yellow-600/10 p-3"
            >
              <AlertTriangle class="mt-0.5 size-4 shrink-0 text-yellow-500" />
              <div class="min-w-0 flex-1">
                <p class="text-sm font-medium text-yellow-500">
                  {{ t("update.dirtyWarning") }}
                </p>
                <p class="mt-1 text-xs font-medium text-yellow-400/80">
                  {{ t("update.dirtyFiles") }}:
                </p>
                <ul class="mt-1 list-inside list-disc space-y-0.5">
                  <li
                    v-for="f in dirtyFiles"
                    :key="f"
                    class="font-mono text-xs text-yellow-300/80 truncate"
                  >
                    {{ f }}
                  </li>
                </ul>
              </div>
            </div>
          </template>
        </CardContent>
      </Card>

      <!-- Branch Selector -->
      <Card class="flex-none">
        <CardHeader>
          <CardTitle class="flex items-center gap-2 text-base">
            <span>{{ t("update.selectBranch") }}</span>
          </CardTitle>
        </CardHeader>
        <CardContent class="space-y-3">
          <Select
            v-if="status && status.available_branches.length > 0"
            v-model="selectedBranch"
            :disabled="status.is_dirty || executing"
          >
            <SelectTrigger class="w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem
                v-for="b in status.available_branches"
                :key="b"
                :value="b"
              >
                {{ b }}
              </SelectItem>
            </SelectContent>
          </Select>
          <p v-else class="text-sm text-muted-foreground">
            {{ t("update.noUpdate") }}
          </p>

          <!-- Preview -->
          <div v-if="previewLoading" class="space-y-1">
            <Skeleton class="h-4 w-64" />
            <Skeleton class="h-4 w-48" />
          </div>
          <template v-else-if="preview">
            <div class="flex items-center gap-2 text-sm text-muted-foreground">
              <span>{{ t("update.remoteCommit") }}:</span>
              <code>{{ preview.remote_commit_hash }}</code>
              <span class="truncate">{{ preview.remote_commit_message }}</span>
            </div>
            <div class="flex items-center gap-2 text-sm">
              <Badge
                :variant="isBehind || selectedBranch !== status?.branch ? 'default' : 'secondary'"
              >
                {{ commitsBehindText }}
              </Badge>
              <Badge
                v-if="selectedBranch !== status?.branch"
                variant="outline"
              >
                {{ $t("update.selectBranch") }}
              </Badge>
            </div>
          </template>
        </CardContent>
      </Card>

      <!-- Execute -->
      <div class="flex-none">
        <Button
          v-if="!executing && !polling"
          :disabled="!canExecute"
          @click="executeUpdate()"
        >
          <ArrowUpCircle class="mr-1.5 size-4" />
          {{ t("update.execute") }}
        </Button>
        <Button
          v-else-if="executing"
          variant="destructive"
          @click="cancelUpdate()"
        >
          {{ $t("common.cancel") }}
        </Button>
        <Button v-else disabled>
          <Loader2 class="mr-1.5 size-4 animate-spin" />
          {{ t("update.reconnecting") }}
        </Button>
      </div>

      <!-- Terminal Output -->
      <Card
        v-if="executing || terminalLines.length > 0"
        class="flex min-h-0 flex-1 flex-col"
      >
        <CardHeader class="pb-2">
          <CardTitle class="flex items-center gap-2 text-base">
            <Terminal class="size-4" />
            <span v-if="stage">{{ stageLabel(stage) }}</span>
            <Loader2
              v-if="executing"
              class="size-4 animate-spin text-muted-foreground"
            />
          </CardTitle>
        </CardHeader>
        <CardContent class="min-h-0 flex-1 overflow-hidden p-0">
          <div
            ref="terminalEl"
            class="h-full overflow-auto rounded-b-lg bg-zinc-950 p-4 font-mono text-xs leading-relaxed"
          >
            <template v-for="(line, i) in terminals" :key="i">
              <div class="text-zinc-300">{{ line }}</div>
            </template>
            <div
              v-if="executing && terminalLines.length > 0"
              class="mt-1 inline-block h-4 w-2 animate-pulse bg-emerald-400"
            />
          </div>
        </CardContent>
      </Card>

      <!-- Post-update status -->
      <div
        v-if="updateDone"
        class="flex items-center gap-2 text-sm text-muted-foreground"
      >
        <Loader2 v-if="polling" class="size-4 animate-spin text-emerald-500" />
        <span v-if="polling">{{ t("update.reconnecting") }}</span>
        <span v-else class="text-emerald-500">{{ t("update.success") }}</span>
      </div>
    </template>
  </div>
</template>
