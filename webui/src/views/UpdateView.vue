<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { toast } from "vue-sonner";
import {
  AlertTriangle,
  GitBranch,
  GitCommit as GitCommitIcon,
  Loader2,
  Tag,
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
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type {
  UpdateEvent,
  UpdatePreviewResponse,
  UpdateStatusResponse,
} from "@/types";

const { t } = useI18n();

const status = ref<UpdateStatusResponse | null>(null);
const statusLoading = ref(false);
const statusError = ref("");

const preview = ref<UpdatePreviewResponse | null>(null);
const previewLoading = ref(false);

const sourceType = ref<"branch" | "tag">("branch");
const selectedRef = ref("");

const executing = ref(false);
const terminalLines = ref<string[]>([]);
const stage = ref("");
const updateFailed = ref(false);
const updateDone = ref(false);
const polling = ref(false);
const terminalEl = ref<HTMLElement | null>(null);
let abortController: AbortController | null = null;

async function fetchStatus() {
  statusLoading.value = true;
  statusError.value = "";
  try {
    status.value = await api.update.status();
    if (!selectedRef.value && status.value) {
      selectedRef.value = status.value.branch;
    }
  } catch (err: unknown) {
    statusError.value = (err as Error).message;
  } finally {
    statusLoading.value = false;
  }
}

async function fetchPreview() {
  if (!selectedRef.value) return;
  previewLoading.value = true;
  preview.value = null;
  try {
    preview.value = await api.update.preview(
      selectedRef.value,
      sourceType.value,
    );
  } catch {
    preview.value = null;
  } finally {
    previewLoading.value = false;
  }
}

watch(selectedRef, () => fetchPreview());
watch(sourceType, () => {
  if (status.value) {
    if (sourceType.value === "branch" && status.value.available_branches.length > 0) {
      selectedRef.value = status.value.available_branches[0];
    } else if (sourceType.value === "tag" && status.value.available_tags.length > 0) {
      selectedRef.value = status.value.available_tags[0];
    }
  }
});

const dirtyFiles = computed(() => {
  if (!status.value?.dirty_files) return [];
  return status.value.dirty_files;
});

const sourceOptions = computed(() => {
  if (!status.value) return [];
  return sourceType.value === "branch"
    ? status.value.available_branches
    : status.value.available_tags;
});

function canExecuteRow(hash: string): boolean {
  return !!(
    status.value &&
    !status.value.is_dirty &&
    !executing.value &&
    !updateDone.value &&
    hash !== status.value.commit_hash
  );
}

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

async function executeUpdate(commit: string) {
  if (!selectedRef.value || executing.value) return;
  executing.value = true;
  updateFailed.value = false;
  updateDone.value = false;
  terminalLines.value = [];
  stage.value = "";

  abortController = new AbortController();

  try {
    const res = await api.update.execute(
      selectedRef.value,
      commit,
      sourceType.value,
    );
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
          }
          if (event.stage === "done") {
            updateDone.value = true;
            pollUntilUp();
          }
        } catch {
          // skip unparseable
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

function isCurrentCommit(hash: string): boolean {
  return status.value?.commit_hash === hash;
}

function formatDate(dateStr: string): string {
  if (!dateStr) return "";
  return dateStr.slice(0, 10) + " " + dateStr.slice(11, 16);
}

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
            <div class="flex flex-wrap items-center gap-2">
              <Badge variant="secondary">{{ status.branch }}</Badge>
              <GitCommitIcon class="size-3.5 text-muted-foreground" />
              <code class="text-sm text-muted-foreground">{{ status.commit_hash }}</code>
              <span class="text-sm text-muted-foreground truncate max-w-md">
                {{ status.commit_message }}
              </span>
            </div>

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

      <!-- Source Selector (Branch / Tag) -->
      <Card class="flex-none">
        <CardHeader class="pb-3">
          <Tabs
            :model-value="sourceType"
            @update:model-value="sourceType = $event as 'branch' | 'tag'"
          >
            <TabsList>
              <TabsTrigger value="branch" :disabled="executing">
                <GitBranch class="mr-1.5 size-3.5" />
                {{ t("update.branchTab") }}
              </TabsTrigger>
              <TabsTrigger
                value="tag"
                :disabled="executing || !status?.available_tags?.length"
              >
                <Tag class="mr-1.5 size-3.5" />
                {{ t("update.tagTab") }}
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </CardHeader>
        <CardContent class="space-y-4">
          <div class="flex items-center gap-3">
            <label class="text-sm font-medium text-muted-foreground shrink-0">
              {{ sourceType === "branch" ? t("update.selectBranch") : t("update.selectTag") }}:
            </label>
            <Select
              v-if="sourceOptions.length > 0"
              v-model="selectedRef"
              :disabled="status?.is_dirty || executing"
            >
              <SelectTrigger class="w-56">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem v-for="opt in sourceOptions" :key="opt" :value="opt">
                  {{ opt }}
                </SelectItem>
              </SelectContent>
            </Select>
            <p v-else class="text-sm text-muted-foreground">
              {{ t("update.noUpdate") }}
            </p>
          </div>

          <!-- Commit List Table -->
          <div v-if="previewLoading" class="space-y-2">
            <Skeleton class="h-4 w-full" />
            <Skeleton class="h-4 w-3/4" />
            <Skeleton class="h-4 w-5/6" />
          </div>
          <template v-else-if="preview && preview.commits.length > 0">
            <p class="text-sm font-medium text-muted-foreground">
              {{ t("update.selectCommit") }} ({{ preview.commits.length }})
            </p>
            <div class="max-h-80 overflow-auto rounded-md border">
              <table class="w-full text-xs">
                <thead class="sticky top-0 bg-muted/50">
                  <tr class="text-left text-muted-foreground">
                    <th class="px-3 py-2">Commit</th>
                    <th class="px-3 py-2">{{ t("update.commitMessage") }}</th>
                    <th class="hidden px-3 py-2 sm:table-cell">{{ t("update.commitAuthor") }}</th>
                    <th class="hidden px-3 py-2 sm:table-cell">{{ t("update.commitDate") }}</th>
                    <th class="w-24 px-3 py-2 text-center">{{ t("update.action") }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="c in preview.commits"
                    :key="c.hash"
                    :class="[
                      'border-t transition-colors',
                      isCurrentCommit(c.hash) ? 'bg-emerald-500/5' : 'hover:bg-muted/30',
                    ]"
                  >
                    <td class="whitespace-nowrap px-3 py-2 font-mono">
                      <code>{{ c.hash }}</code>
                      <Badge
                        v-if="isCurrentCommit(c.hash)"
                        variant="secondary"
                        class="ml-1 text-[0.6rem]"
                      >
                        {{ t("update.currentLabel") }}
                      </Badge>
                    </td>
                    <td class="max-w-64 truncate px-3 py-2">{{ c.message }}</td>
                    <td class="hidden px-3 py-2 text-muted-foreground sm:table-cell">
                      {{ c.author }}
                    </td>
                    <td class="hidden whitespace-nowrap px-3 py-2 text-muted-foreground sm:table-cell">
                      {{ formatDate(c.date) }}
                    </td>
                    <td class="px-2 py-1 text-center">
                      <Button
                        v-if="!isCurrentCommit(c.hash)"
                        size="sm"
                        variant="outline"
                        :disabled="!canExecuteRow(c.hash)"
                        @click.stop="executeUpdate(c.hash)"
                      >
                        {{ t("update.execute") }}
                      </Button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
          <p v-else-if="preview" class="text-sm text-muted-foreground">
            {{ t("update.noCommits") }}
          </p>
        </CardContent>
      </Card>

      <!-- Execute Controls -->
      <div class="flex-none">
        <Button
          v-if="executing"
          variant="destructive"
          @click="cancelUpdate()"
        >
          {{ $t("common.cancel") }}
        </Button>
        <Button v-else-if="polling" disabled>
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
            <template v-for="(line, i) in terminalLines" :key="i">
              <div class="text-zinc-300">{{ line }}</div>
            </template>
            <div
              v-if="executing && terminalLines.length > 0"
              class="mt-1 inline-block h-4 w-2 animate-pulse bg-emerald-400"
            />
          </div>
        </CardContent>
      </Card>

      <!-- Post-update -->
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
