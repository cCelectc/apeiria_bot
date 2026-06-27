<script setup lang="ts">
import { computed } from "vue";
import { Activity, Plug, Puzzle } from "@lucide/vue";
import ErrorState from "@/components/ErrorState.vue";
import PageHeader from "@/components/PageHeader.vue";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAdaptersQuery } from "@/composables/useAdapters";
import { usePluginsQuery } from "@/composables/usePlugins";
import { useStatusQuery } from "@/composables/useStatus";

const { data, isLoading, isError, error, refetch } = useStatusQuery();
const { data: installedPlugins } = usePluginsQuery();
const { data: installedAdapters } = useAdaptersQuery();

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const parts: string[] = [];
  if (d) parts.push(`${d}天`);
  if (h) parts.push(`${h}小时`);
  parts.push(`${m}分`);
  return parts.join(" ");
}

const uptime = computed(() =>
  data.value ? formatUptime(data.value.uptime) : "—",
);
const loadedPlugins = computed(() => data.value?.plugin_count ?? 0);
const loadedAdapters = computed(() => data.value?.adapters ?? []);
const installedPluginCount = computed(
  () => installedPlugins.value?.plugins.length ?? 0,
);
const enabledPluginCount = computed(
  () => installedPlugins.value?.plugins.filter((p) => p.enabled).length ?? 0,
);
const installedAdapterCount = computed(
  () => installedAdapters.value?.adapters.length ?? 0,
);
</script>

<template>
  <div class="p-6 lg:p-8">
    <PageHeader
      :title="$t('dashboard.title')"
      :subtitle="$t('dashboard.subtitle')"
    />

    <ErrorState
      v-if="isError"
      class="mb-4"
      :message="(error as Error)?.message"
      @retry="() => refetch()"
    />

    <div v-else-if="isLoading" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <Skeleton v-for="i in 3" :key="i" class="h-32 rounded-xl" />
    </div>
    <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <Card>
        <CardContent>
          <div
            class="flex size-11 items-center justify-center rounded-xl bg-primary/10 text-primary"
          >
            <Activity class="size-6" />
          </div>
          <p class="mt-4 text-2xl font-bold">{{ uptime }}</p>
          <p class="mt-1 text-sm text-muted-foreground">
            {{ $t("dashboard.uptime") }}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <div class="flex items-center justify-between">
            <div
              class="flex size-11 items-center justify-center rounded-xl bg-primary/10 text-primary"
            >
              <Puzzle class="size-6" />
            </div>
            <span class="text-xs text-muted-foreground">{{
              $t("dashboard.installed", { count: installedPluginCount })
            }}</span>
          </div>
          <p class="mt-4 text-3xl font-bold">{{ loadedPlugins }}</p>
          <p class="mt-1 text-sm text-muted-foreground">
            {{ $t("dashboard.pluginCount") }} ·
            {{ $t("dashboard.enabled", { count: enabledPluginCount }) }}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <div class="flex items-center justify-between">
            <div
              class="flex size-11 items-center justify-center rounded-xl bg-chart-3/10 text-chart-3"
            >
              <Plug class="size-6" />
            </div>
            <span class="text-xs text-muted-foreground">{{
              $t("dashboard.installed", { count: installedAdapterCount })
            }}</span>
          </div>
          <p class="mt-4 text-3xl font-bold">{{ loadedAdapters.length }}</p>
          <p class="mt-1 text-sm text-muted-foreground">
            {{ $t("dashboard.adapterCount") }}
          </p>
        </CardContent>
      </Card>
    </div>

    <Card v-if="loadedAdapters.length" class="mt-4">
      <CardContent class="p-6">
        <p class="mb-3 text-sm font-medium">
          {{ $t("dashboard.adapterStatus") }}
        </p>
        <div class="flex flex-wrap gap-2">
          <span
            v-for="a in loadedAdapters"
            :key="a"
            class="inline-flex items-center gap-2 rounded-lg border bg-card px-3 py-1.5 text-sm"
          >
            <span class="size-2 rounded-full bg-emerald-500" />
            {{ a }}
          </span>
        </div>
      </CardContent>
    </Card>
  </div>
</template>
