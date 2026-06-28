<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from "vue";
import { refDebounced } from "@vueuse/core";
import { ChevronLeft, ChevronRight, Pause, Play, Trash2 } from "@lucide/vue";
import ErrorState from "@/components/ErrorState.vue";
import PageHeader from "@/components/PageHeader.vue";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useLogHistoryQuery } from "@/composables/useLogs";
import { createSseClient } from "@/lib/sse";
import { useAuthStore } from "@/stores/auth";
import type { LogRecord } from "@/types";

const LEVELS = ["DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"];
const LEVEL_NO: Record<string, number> = {
  DEBUG: 10,
  INFO: 20,
  SUCCESS: 25,
  WARNING: 30,
  ERROR: 40,
  CRITICAL: 50,
};
const PAGE_SIZE = 100;
const MAX_LIVE = 1000;
const HOUR_MS = 3_600_000;

const auth = useAuthStore();
const tab = ref("live");

// ---- shared filters ----
const level = ref("all");
const keyword = ref("");
const source = ref("");
const debouncedKeyword = refDebounced(keyword, 500);
const debouncedSource = refDebounced(source, 500);

function levelClass(lvl: string): string {
  const map: Record<string, string> = {
    DEBUG: "text-log-debug",
    INFO: "text-log-info",
    SUCCESS: "text-log-success",
    WARNING: "text-log-warning",
    ERROR: "text-log-error",
    CRITICAL: "text-log-critical",
  };
  return map[lvl] ?? "text-muted-foreground";
}

function levelRank(lvl: string): number {
  return LEVEL_NO[lvl] ?? 0;
}

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

function formatShortTime(ts: number): string {
  if (!ts) return "";
  const d = new Date(ts * 1000);
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function formatFullTime(ts: number): string {
  return ts ? new Date(ts * 1000).toLocaleString() : "";
}

interface Segment {
  text: string;
  match: boolean;
}

function highlightSegments(text: string, kw: string): Segment[] {
  if (!kw) return [{ text, match: false }];
  const lower = text.toLowerCase();
  const needle = kw.toLowerCase();
  const segments: Segment[] = [];
  let from = 0;
  let idx = lower.indexOf(needle);
  while (idx !== -1) {
    if (idx > from)
      segments.push({ text: text.slice(from, idx), match: false });
    segments.push({ text: text.slice(idx, idx + needle.length), match: true });
    from = idx + needle.length;
    idx = lower.indexOf(needle, from);
  }
  if (from < text.length)
    segments.push({ text: text.slice(from), match: false });
  return segments;
}

function matchesFilters(r: LogRecord, kw: string, src: string): boolean {
  const minRank = level.value === "all" ? 0 : levelRank(level.value);
  if (minRank && levelRank(r.level) < minRank) return false;
  if (
    kw &&
    !r.message.toLowerCase().includes(kw) &&
    !r.name.toLowerCase().includes(kw)
  ) {
    return false;
  }
  if (src && !r.name.toLowerCase().includes(src)) return false;
  return true;
}

// ---- live ----
const live = ref<LogRecord[]>([]);
const paused = ref(false);
const scrollEl = ref<HTMLElement | null>(null);
let sseClient: ReturnType<typeof createSseClient> | null = null;

const filteredLive = computed(() => {
  const kw = keyword.value.toLowerCase();
  const src = source.value.toLowerCase();
  return live.value.filter((r) => matchesFilters(r, kw, src));
});

function scrollToBottom() {
  const el = scrollEl.value;
  if (el) el.scrollTop = el.scrollHeight;
}

function connect() {
  disconnect();
  if (!auth.token) return;
  sseClient = createSseClient("/api/logs/stream", auth.token, (data) => {
    try {
      const rec = JSON.parse(data) as LogRecord;
      live.value.push(rec);
      if (live.value.length > MAX_LIVE) {
        live.value.splice(0, live.value.length - MAX_LIVE);
      }
      if (!paused.value) void nextTick(scrollToBottom);
    } catch {
      // ignore malformed lines
    }
  });
}

function disconnect() {
  sseClient?.close();
  sseClient = null;
}

function clearLive() {
  live.value = [];
}

watch(
  tab,
  (t) => {
    if (t === "live") connect();
    else disconnect();
  },
  { immediate: true },
);

onUnmounted(disconnect);

// ---- history ----
const page = ref(1);
const timePreset = ref("all");
const customFrom = ref("");
const customTo = ref("");

const timeRange = computed<{ since?: number; until?: number }>(() => {
  const now = Date.now();
  if (timePreset.value === "1h") return { since: (now - HOUR_MS) / 1000 };
  if (timePreset.value === "6h") return { since: (now - 6 * HOUR_MS) / 1000 };
  if (timePreset.value === "24h") return { since: (now - 24 * HOUR_MS) / 1000 };
  if (timePreset.value === "custom") {
    const range: { since?: number; until?: number } = {};
    if (customFrom.value) {
      range.since = new Date(customFrom.value).getTime() / 1000;
    }
    if (customTo.value) {
      range.until = new Date(customTo.value).getTime() / 1000;
    }
    return range;
  }
  return {};
});

const params = computed(() => ({
  level: level.value === "all" ? "" : level.value,
  q: debouncedKeyword.value,
  source: debouncedSource.value,
  since: timeRange.value.since,
  until: timeRange.value.until,
  page: page.value,
  size: PAGE_SIZE,
}));

const {
  data: history,
  isFetching,
  isError,
  error,
  refetch,
} = useLogHistoryQuery(params);

const totalPages = computed(() =>
  history.value ? Math.max(1, Math.ceil(history.value.total / PAGE_SIZE)) : 1,
);

watch(
  [level, debouncedKeyword, debouncedSource, timePreset, customFrom, customTo],
  () => {
    page.value = 1;
  },
);
</script>

<template>
  <div class="flex h-full flex-col p-6 lg:p-8">
    <PageHeader :title="$t('logs.title')" :subtitle="$t('logs.subtitle')" />

    <Tabs v-model="tab" class="flex min-h-0 flex-1 flex-col">
      <TabsList class="w-fit">
        <TabsTrigger value="live">{{ $t("logs.live") }}</TabsTrigger>
        <TabsTrigger value="history">{{ $t("logs.history") }}</TabsTrigger>
      </TabsList>

      <div class="my-2 flex flex-wrap items-center gap-2">
        <Select v-model="level">
          <SelectTrigger class="w-36">
            <SelectValue :placeholder="$t('logs.minLevel')" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{{ $t("logs.allLevels") }}</SelectItem>
            <SelectItem v-for="l in LEVELS" :key="l" :value="l">{{
              l
            }}</SelectItem>
          </SelectContent>
        </Select>
        <Input
          v-model="keyword"
          :placeholder="$t('logs.keywordPlaceholder')"
          :aria-label="$t('logs.keywordPlaceholder')"
          class="max-w-xs"
        />
        <Input
          v-model="source"
          :placeholder="$t('logs.sourcePlaceholder')"
          :aria-label="$t('logs.sourcePlaceholder')"
          class="max-w-xs"
        />
      </div>

      <TabsContent value="live" class="flex min-h-0 flex-1 flex-col">
        <div class="mb-2 flex items-center gap-2">
          <Button variant="outline" size="sm" @click="paused = !paused">
            <component :is="paused ? Play : Pause" class="size-4" />
            {{ paused ? $t("logs.resumeScroll") : $t("logs.pauseScroll") }}
          </Button>
          <Button variant="outline" size="sm" @click="clearLive">
            <Trash2 class="size-4" />
            {{ $t("logs.clear") }}
          </Button>
        </div>
        <div
          ref="scrollEl"
          class="flex-1 min-h-0 overflow-auto rounded-xl border bg-card p-3 font-mono text-xs"
        >
          <p
            v-if="!filteredLive.length"
            class="py-6 text-center text-muted-foreground"
          >
            {{ $t("logs.waiting") }}
          </p>
          <div
            v-for="(r, i) in filteredLive"
            :key="i"
            class="flex gap-2 py-0.5"
          >
            <span
              class="shrink-0 text-muted-foreground"
              :title="formatFullTime(r.ts)"
            >
              {{ formatShortTime(r.ts) }}
            </span>
            <span :class="['shrink-0 font-medium', levelClass(r.level)]">
              [{{ r.level }}]
            </span>
            <span class="shrink-0 text-muted-foreground">{{ r.name }}</span>
            <span class="shrink-0 text-muted-foreground">|</span>
            <span class="break-all">
              <template
                v-for="(seg, j) in highlightSegments(r.message, keyword)"
                :key="j"
              >
                <mark
                  v-if="seg.match"
                  class="rounded-sm bg-primary/20 text-inherit"
                  >{{ seg.text }}</mark
                >
                <template v-else>{{ seg.text }}</template>
              </template>
            </span>
          </div>
        </div>
      </TabsContent>

      <TabsContent value="history" class="flex min-h-0 flex-1 flex-col">
        <div class="mb-2 flex flex-wrap items-center gap-2">
          <Select v-model="timePreset">
            <SelectTrigger class="w-32">
              <SelectValue :placeholder="$t('logs.timeRange')" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{{ $t("logs.allTime") }}</SelectItem>
              <SelectItem value="1h">{{ $t("logs.last1h") }}</SelectItem>
              <SelectItem value="6h">{{ $t("logs.last6h") }}</SelectItem>
              <SelectItem value="24h">{{ $t("logs.last24h") }}</SelectItem>
              <SelectItem value="custom">{{
                $t("logs.customRange")
              }}</SelectItem>
            </SelectContent>
          </Select>
          <template v-if="timePreset === 'custom'">
            <input
              v-model="customFrom"
              type="datetime-local"
              :aria-label="$t('logs.from')"
              class="h-9 rounded-md border bg-transparent px-2 text-sm"
            />
            <span class="text-muted-foreground">–</span>
            <input
              v-model="customTo"
              type="datetime-local"
              :aria-label="$t('logs.to')"
              class="h-9 rounded-md border bg-transparent px-2 text-sm"
            />
          </template>
        </div>

        <div
          class="flex-1 min-h-0 overflow-auto rounded-xl border bg-card p-3 font-mono text-xs"
        >
          <ErrorState
            v-if="isError"
            class="mb-4"
            :message="(error as Error)?.message"
            @retry="() => refetch()"
          />
          <p
            v-else-if="isFetching"
            class="py-6 text-center text-muted-foreground"
          >
            {{ $t("logs.loading") }}
          </p>
          <p
            v-else-if="!history || !history.items.length"
            class="py-6 text-center text-muted-foreground"
          >
            {{ $t("logs.noLogs") }}
          </p>
          <div
            v-for="(r, i) in history?.items ?? []"
            :key="i"
            class="flex gap-2 py-0.5"
          >
            <span
              class="shrink-0 text-muted-foreground"
              :title="formatFullTime(r.ts)"
            >
              {{ formatShortTime(r.ts) }}
            </span>
            <span :class="['shrink-0 font-medium', levelClass(r.level)]">
              [{{ r.level }}]
            </span>
            <span class="shrink-0 text-muted-foreground">{{ r.name }}</span>
            <span class="shrink-0 text-muted-foreground">|</span>
            <span class="break-all">
              <template
                v-for="(seg, j) in highlightSegments(
                  r.message,
                  debouncedKeyword,
                )"
                :key="j"
              >
                <mark
                  v-if="seg.match"
                  class="rounded-sm bg-primary/20 text-inherit"
                  >{{ seg.text }}</mark
                >
                <template v-else>{{ seg.text }}</template>
              </template>
            </span>
          </div>
        </div>

        <div class="mt-2 flex items-center justify-end gap-2 text-sm">
          <span class="text-muted-foreground">
            {{
              $t("logs.pageInfo", {
                page,
                total: totalPages,
                count: history?.total ?? 0,
              })
            }}
          </span>
          <Button
            variant="outline"
            size="icon"
            :aria-label="$t('logs.prevPage')"
            :disabled="page <= 1"
            @click="page--"
          >
            <ChevronLeft class="size-4" aria-hidden="true" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            :aria-label="$t('logs.nextPage')"
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
