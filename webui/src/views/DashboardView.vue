<script setup lang="ts">
import { computed, ref } from "vue";
import { Activity, Plug, Puzzle, RotateCw } from "@lucide/vue";
import { toast } from "vue-sonner";
import { api } from "@/lib/api";
import ErrorState from "@/components/ErrorState.vue";
import PageHeader from "@/components/PageHeader.vue";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useAdaptersQuery } from "@/composables/useAdapters";
import { usePluginsQuery } from "@/composables/usePlugins";
import { useStatusQuery } from "@/composables/useStatus";

const { data, isLoading, isError, error, refetch } = useStatusQuery();
const { data: installedPlugins } = usePluginsQuery();
const { data: installedAdapters } = useAdaptersQuery();

const restartOpen = ref(false);
const restarting = ref(false);

async function doRestart() {
  restarting.value = true;
  try {
    await api.status.restart();
    pollUntilUp();
  } catch {
    toast.error("重启请求失败");
    restarting.value = false;
    restartOpen.value = false;
  }
}

function pollUntilUp() {
  let attempts = 0;
  const max = 60;
  const interval = setInterval(async () => {
    attempts++;
    try {
      await api.status.get();
      clearInterval(interval);
      toast.success("Bot 已重启");
      restarting.value = false;
      restartOpen.value = false;
      refetch();
    } catch {
      if (attempts >= max) {
        clearInterval(interval);
        toast.error("重启超时，请手动刷新页面");
        restarting.value = false;
        restartOpen.value = false;
      }
    }
  }, 2000);
}

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
    >
      <template #actions>
        <Button
          variant="outline"
          size="sm"
          :disabled="isLoading || restarting"
          @click="restartOpen = true"
        >
          <RotateCw class="size-4" :class="{ 'animate-spin': restarting }" />
          {{ restarting ? $t("dashboard.restarting") : $t("dashboard.restart") }}
        </Button>
      </template>
    </PageHeader>

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

    <Dialog :open="restartOpen" @update:open="(v) => { if (!restarting) restartOpen = v }">
      <DialogContent :show-close-button="!restarting">
        <DialogHeader>
          <DialogTitle>{{ $t("dashboard.restartConfirmTitle") }}</DialogTitle>
          <DialogDescription>
            {{ $t("dashboard.restartConfirmDesc") }}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" :disabled="restarting" @click="restartOpen = false">
            {{ $t("common.cancel") }}
          </Button>
          <Button variant="destructive" :disabled="restarting" @click="doRestart">
            {{ restarting ? $t("dashboard.restarting") : $t("common.confirm") }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
