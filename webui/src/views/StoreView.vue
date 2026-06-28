<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { refDebounced } from "@vueuse/core";
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Download,
  ExternalLink,
  Search,
} from "@lucide/vue";
import { toast } from "vue-sonner";
import ErrorState from "@/components/ErrorState.vue";
import InstallProgressDialog from "@/components/InstallProgressDialog.vue";
import PageHeader from "@/components/PageHeader.vue";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useAdapterMutations,
  useAdaptersQuery,
} from "@/composables/useAdapters";
import { usePluginMutations, usePluginsQuery } from "@/composables/usePlugins";
import { usePendingChanges } from "@/composables/usePendingChanges";
import {
  STORE_PAGE_SIZE,
  useStoreAdaptersQuery,
  useStorePluginsQuery,
} from "@/composables/useStore";
import type { StoreItem } from "@/types";

const query = ref("");
const debouncedQuery = refDebounced(query, 300);
const tab = ref<"plugins" | "adapters">("plugins");
const sort = ref("default");
const page = ref(1);
useI18n();

const isPlugins = computed(() => tab.value === "plugins");

watch([debouncedQuery, tab, sort], () => {
  page.value = 1;
});

const {
  data: pluginData,
  isFetching: pluginLoading,
  isError: pluginError,
  error: pluginErrorDetail,
  refetch: pluginRefetch,
} = useStorePluginsQuery(debouncedQuery, page, isPlugins, sort);
const {
  data: adapterData,
  isFetching: adapterLoading,
  isError: adapterError,
  error: adapterErrorDetail,
  refetch: adapterRefetch,
} = useStoreAdaptersQuery(
  debouncedQuery,
  page,
  computed(() => !isPlugins.value),
  sort,
);
const { install: installPlugin } = usePluginMutations();
const { install: installAdapter } = useAdapterMutations();
const { data: installedPlugins } = usePluginsQuery();
const { data: installedAdapters } = useAdaptersQuery();
const { pendingChanges, markChanged, clearChanges } = usePendingChanges();

const currentItems = computed<StoreItem[]>(
  () => (isPlugins.value ? pluginData.value : adapterData.value)?.results ?? [],
);
const currentLoading = computed(() =>
  isPlugins.value ? pluginLoading.value : adapterLoading.value,
);
const currentIsError = computed(() =>
  isPlugins.value ? pluginError.value : adapterError.value,
);
const currentErrorDetail = computed(
  () =>
    (isPlugins.value
      ? pluginErrorDetail.value
      : adapterErrorDetail.value) as Error | null,
);
const currentRefetch = computed(() =>
  isPlugins.value ? pluginRefetch : adapterRefetch,
);
const total = computed(
  () =>
    (isPlugins.value ? pluginData.value?.total : adapterData.value?.total) ?? 0,
);
const pageCount = computed(() =>
  Math.max(1, Math.ceil(total.value / STORE_PAGE_SIZE)),
);

const installedPluginKeys = computed(() => {
  const set = new Set<string>();
  for (const p of installedPlugins.value?.plugins ?? []) {
    set.add(p.path_or_module);
    set.add(p.name);
  }
  return set;
});
const installedAdapterKeys = computed(() => {
  const set = new Set<string>();
  for (const a of installedAdapters.value?.adapters ?? []) {
    set.add(a.module_name);
    set.add(a.name);
  }
  return set;
});

function isInstalled(item: StoreItem, forAdapter: boolean): boolean {
  const set = forAdapter
    ? installedAdapterKeys.value
    : installedPluginKeys.value;
  if (set.has(item.name) || set.has(item.pypi_name)) return true;
  return item.module_names.some((m) => set.has(m));
}

function installItem(item: StoreItem, forAdapter: boolean) {
  const opts = {
    onSuccess: (taskId: string) => {
      progressTitle.value = `安装: ${item.name}`;
      progressTaskId.value = taskId;
      progressOpen.value = true;
    },
    onError: (e: Error) => toast.error(e.message),
  };
  if (forAdapter) {
    installAdapter.mutate(
      {
        name: item.name,
        pkg: item.pypi_name,
        module_name: item.module_names[0] ?? "",
      },
      opts,
    );
  } else {
    installPlugin.mutate({ name: item.name, pkg: item.pypi_name }, opts);
  }
}

function onProgressClose() {
  progressOpen.value = false;
  progressTaskId.value = null;
  markChanged();
}

const detailOpen = ref(false);
const progressOpen = ref(false);
const progressTaskId = ref<string | null>(null);
const progressTitle = ref("");
const detailItem = ref<StoreItem | null>(null);
const detailIsAdapter = ref(false);

function openDetail(item: StoreItem) {
  detailItem.value = item;
  detailIsAdapter.value = !isPlugins.value;
  detailOpen.value = true;
}

function fmtTime(iso: string): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}
</script>

<template>
  <div class="p-6 lg:p-8">
    <PageHeader :title="$t('store.title')" :subtitle="$t('store.subtitle')" />

    <div
      v-if="pendingChanges"
      class="mb-4 flex items-center justify-between rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 dark:border-amber-800 dark:bg-amber-950"
    >
      <p class="text-sm text-amber-800 dark:text-amber-200">
        {{ $t("common.pendingChanges") }}
      </p>
      <div class="flex items-center gap-2">
        <Button variant="outline" size="sm" @click="clearChanges">
          {{ $t("common.dismiss") }}
        </Button>
      </div>
    </div>

    <div class="mb-4 flex flex-wrap items-center gap-3">
      <div class="relative w-full max-w-md">
        <Search
          class="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden="true"
        />
        <Input
          v-model="query"
          :placeholder="$t('store.searchPlaceholder')"
          aria-label="搜索插件与适配器"
          class="pl-9"
        />
      </div>
      <Tabs v-model="tab" class="shrink-0">
        <TabsList>
          <TabsTrigger value="plugins">{{ $t("store.plugins") }}</TabsTrigger>
          <TabsTrigger value="adapters">{{ $t("store.adapters") }}</TabsTrigger>
        </TabsList>
      </Tabs>
      <Select v-model="sort">
        <SelectTrigger class="w-36 shrink-0">
          <SelectValue :placeholder="$t('store.sortDefault')" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="default">{{ $t("store.sortDefault") }}</SelectItem>
          <SelectItem value="time_desc">{{ $t("store.sortTimeDesc") }}</SelectItem>
          <SelectItem value="name_asc">{{ $t("store.sortNameAsc") }}</SelectItem>
          <SelectItem value="name_desc">{{ $t("store.sortNameDesc") }}</SelectItem>
        </SelectContent>
      </Select>
    </div>

    <p v-if="!currentIsError" class="mb-4 text-xs text-muted-foreground">
      {{ $t("store.resultCount", { count: total }) }}
    </p>

    <div>
      <ErrorState
        v-if="currentIsError"
        class="mb-4"
        :message="(currentErrorDetail as Error)?.message"
        @retry="() => currentRefetch()"
      />
      <p
        v-else-if="currentLoading && !currentItems.length"
        class="py-12 text-center text-sm text-muted-foreground"
      >
        {{ $t("store.loading") }}
      </p>
      <p
        v-else-if="!currentItems.length"
        class="py-12 text-center text-sm text-muted-foreground"
      >
        {{ $t("store.noResults") }}
      </p>
      <div v-else class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Card
          v-for="item in currentItems"
          :key="item.pypi_name || item.name"
          class="flex flex-col"
        >
          <CardHeader class="pb-3">
            <div class="flex items-start justify-between gap-2">
              <Tooltip :delay-duration="600">
                <TooltipTrigger as-child>
                  <CardTitle class="truncate text-base leading-tight">{{
                    item.name
                  }}</CardTitle>
                </TooltipTrigger>
                <TooltipContent>{{ item.name }}</TooltipContent>
              </Tooltip>
              <Badge
                v-if="item.is_official"
                variant="secondary"
                class="shrink-0"
                >{{ $t("store.official") }}</Badge
              >
            </div>
            <Tooltip :delay-duration="600">
              <TooltipTrigger as-child>
                <p class="line-clamp-2 cursor-default text-sm text-muted-foreground">
                  {{ item.description }}
                </p>
              </TooltipTrigger>
              <TooltipContent class="max-w-xs">{{ item.description }}</TooltipContent>
            </Tooltip>
          </CardHeader>
          <CardContent class="mt-auto flex flex-col gap-3">
            <div v-if="item.tags.length" class="flex flex-wrap gap-1">
              <Tooltip v-for="t in item.tags.slice(0, 4)" :key="t.label">
                <TooltipTrigger as-child>
                  <span
                    class="rounded px-1.5 py-0.5 text-xs font-medium text-foreground/80"
                    :style="{ backgroundColor: t.color }"
                  >
                    {{ t.label }}
                  </span>
                </TooltipTrigger>
                <TooltipContent>{{ t.label }}</TooltipContent>
              </Tooltip>
              <span
                v-if="item.tags.length > 4"
                class="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground"
              >
                +{{ item.tags.length - 4 }}
              </span>
            </div>
            <div class="flex items-center justify-between gap-2">
              <div
                class="flex min-w-0 items-center gap-2 text-xs text-muted-foreground"
              >
                <Tooltip :delay-duration="600">
                  <TooltipTrigger as-child>
                    <span class="cursor-default truncate">{{ item.author }}</span>
                  </TooltipTrigger>
                  <TooltipContent>{{ item.author }}</TooltipContent>
                </Tooltip>
                <span v-if="item.version" class="shrink-0"
                  >v{{ item.version }}</span
                >
                <span v-if="item.time" class="shrink-0">{{ fmtTime(item.time) }}</span>
              </div>
              <div class="flex shrink-0 items-center gap-1">
                <Button variant="ghost" size="sm" @click="openDetail(item)">{{
                  $t("store.detail")
                }}</Button>
                <Button
                  v-if="isInstalled(item, !isPlugins)"
                  size="sm"
                  variant="secondary"
                  disabled
                >
                  <Check class="size-4" />
                  {{ $t("store.installed") }}
                </Button>
                <Button v-else size="sm" @click="installItem(item, !isPlugins)">
                  <Download class="size-4" />
                  {{ $t("store.install") }}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div
        v-if="pageCount > 1"
        class="mt-6 flex items-center justify-center gap-3"
      >
        <Button
          variant="outline"
          size="sm"
          :disabled="page <= 1"
          @click="page--"
        >
          <ChevronLeft class="size-4" />
          {{ $t("store.prevPage") }}
        </Button>
        <span class="text-sm text-muted-foreground"
          >{{ page }} / {{ pageCount }}</span
        >
        <Button
          variant="outline"
          size="sm"
          :disabled="page >= pageCount"
          @click="page++"
        >
          {{ $t("store.nextPage") }}
          <ChevronRight class="size-4" />
        </Button>
      </div>
    </div>

    <Sheet v-model:open="detailOpen">
      <SheetContent class="w-full overflow-y-auto sm:max-w-md">
        <SheetHeader>
          <SheetTitle class="flex items-center gap-2">
            {{ detailItem?.name }}
            <Badge v-if="detailItem?.is_official" variant="secondary">{{
              $t("store.official")
            }}</Badge>
          </SheetTitle>
          <SheetDescription>{{ detailItem?.description }}</SheetDescription>
        </SheetHeader>

        <div v-if="detailItem" class="space-y-4 px-4 text-sm">
          <div class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
            <span class="text-muted-foreground">{{ $t("store.pypi") }}</span>
            <span class="break-all font-mono">{{ detailItem.pypi_name }}</span>
            <span class="text-muted-foreground">{{ $t("store.author") }}</span>
            <span>{{ detailItem.author || "—" }}</span>
            <template v-if="detailItem.version">
              <span class="text-muted-foreground">{{
                $t("store.version")
              }}</span>
              <span>{{ detailItem.version }}</span>
            </template>
            <template v-if="detailItem.time">
              <span class="text-muted-foreground">{{ $t("store.updateTime") }}</span>
              <span>{{ fmtTime(detailItem.time) }}</span>
            </template>
            <template v-if="detailItem.type">
              <span class="text-muted-foreground">{{ $t("store.type") }}</span>
              <span>{{ detailItem.type }}</span>
            </template>
            <template v-if="detailItem.module_names.length">
              <span class="text-muted-foreground">{{
                $t("store.module")
              }}</span>
              <span class="break-all font-mono">{{
                detailItem.module_names.join(", ")
              }}</span>
            </template>
          </div>

          <div v-if="detailItem.supported_adapters?.length">
            <p class="mb-1 text-muted-foreground">
              {{ $t("store.supportedAdapters") }}
            </p>
            <div class="flex flex-wrap gap-1">
              <Badge
                v-for="a in detailItem.supported_adapters"
                :key="a"
                variant="outline"
              >
                {{ a }}
              </Badge>
            </div>
          </div>

          <a
            v-if="detailItem.homepage"
            :href="detailItem.homepage"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center gap-1 text-primary hover:underline"
          >
            <ExternalLink class="size-4" />
            {{ $t("store.homepage") }}
          </a>
        </div>

        <SheetFooter>
          <Button
            v-if="detailItem && isInstalled(detailItem, detailIsAdapter)"
            variant="secondary"
            disabled
          >
            <Check class="size-4" />
            {{ $t("store.installed") }}
          </Button>
          <Button
            v-else-if="detailItem"
            @click="
              () => {
                if (detailItem) installItem(detailItem, detailIsAdapter);
                detailOpen = false;
              }
            "
          >
            <Download class="size-4" />
            {{ $t("store.install") }}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>

    <InstallProgressDialog
      :open="progressOpen"
      :task-id="progressTaskId"
      :title="progressTitle"
      @close="onProgressClose"
    />
  </div>
</template>
