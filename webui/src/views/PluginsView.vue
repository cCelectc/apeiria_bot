<script setup lang="ts">
import { reactive, ref, computed } from "vue";
import { useI18n } from "vue-i18n";
import { Info, Plus, Settings2, Trash2, X } from "@lucide/vue";
import { toast } from "vue-sonner";
import ConfigEditor from "@/components/ConfigEditor.vue";
import ErrorState from "@/components/ErrorState.vue";
import InstallProgressDialog from "@/components/InstallProgressDialog.vue";
import PageHeader from "@/components/PageHeader.vue";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  usePluginConfigQuery,
  usePluginMutations,
  usePluginsQuery,
  useSavePluginConfig,
} from "@/composables/usePlugins";
import type { Plugin } from "@/types";

const { t } = useI18n();
const { data, isLoading, isError, error, refetch } = usePluginsQuery();
void isLoading;
const { install, uninstall, setState } = usePluginMutations();

const installOpen = ref(false);
const installForm = reactive({ name: "", pkg: "" });
const progressOpen = ref(false);
const progressTaskId = ref<string | null>(null);
const progressTitle = ref("");

const configOpen = ref(false);
const configPlugin = ref("");
const { data: pluginConfigData } = usePluginConfigQuery(
  computed(() => configPlugin.value),
);
const savePluginConfig = useSavePluginConfig();

const configEditorRef = ref<InstanceType<typeof ConfigEditor>>();

const confirmOpen = ref(false);
const confirmMessage = ref("");
const confirmAction = ref<(() => void) | null>(null);

function askConfirm(msg: string, action: () => void) {
  confirmMessage.value = msg;
  confirmAction.value = action;
  confirmOpen.value = true;
}

function executeConfirm() {
  confirmAction.value?.();
  confirmOpen.value = false;
}

async function guardCloseConfig() {
  const ok = (await configEditorRef.value?.attemptClose()) ?? true;
  if (ok) configOpen.value = false;
}

const detailOpen = ref(false);
const detailPlugin = ref<Plugin | null>(null);

function openDetail(p: Plugin) {
  detailPlugin.value = p;
  detailOpen.value = true;
}

function openConfig(name: string) {
  configPlugin.value = name;
  configOpen.value = true;
}

function submitInstall() {
  install.mutate(
    { name: installForm.name, pkg: installForm.pkg },
    {
      onSuccess: (taskId: string) => {
        installOpen.value = false;
        progressTitle.value = `安装插件: ${installForm.name}`;
        progressTaskId.value = taskId;
        progressOpen.value = true;
        installForm.name = "";
        installForm.pkg = "";
      },
      onError: (e: Error) => toast.error(e.message),
    },
  );
}

function onProgressClose() {
  progressOpen.value = false;
  progressTaskId.value = null;
  refetch();
}

function toggle(name: string, enabled: boolean) {
  if (!enabled) {
    askConfirm(t("confirm.disableMessage", { name }), () => {
      setState.mutate(
        { name, enabled },
        { onError: (e: Error) => toast.error(e.message) },
      );
    });
    return;
  }
  setState.mutate(
    { name, enabled },
    { onError: (e: Error) => toast.error(e.message) },
  );
}

function remove(name: string) {
  askConfirm(t("confirm.uninstallMessage", { name }), () => {
    uninstall.mutate(
      { name },
      {
        onSuccess: () => toast.success(t("plugins.uninstalled")),
        onError: (e: Error) => toast.error(e.message),
      },
    );
  });
}
</script>

<template>
  <div class="p-6 lg:p-8">
    <PageHeader :title="$t('plugins.title')" :subtitle="$t('plugins.subtitle')">
      <template #actions>
        <Button @click="installOpen = true">
          <Plus class="size-4" />
          {{ $t("plugins.installPlugin") }}
        </Button>
      </template>
    </PageHeader>

    <ErrorState
      v-if="isError"
      class="mb-4"
      :message="(error as Error)?.message"
      @retry="() => refetch()"
    />

    <div class="rounded-xl border bg-card shadow-sm">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{{ $t("plugins.name") }}</TableHead>
            <TableHead>{{ $t("plugins.description") }}</TableHead>
            <TableHead>{{ $t("plugins.type") }}</TableHead>
            <TableHead>{{ $t("plugins.source") }}</TableHead>
            <TableHead>{{ $t("plugins.enabled") }}</TableHead>
            <TableHead class="text-right">{{
              $t("plugins.actions")
            }}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-if="isLoading">
            <TableCell colspan="6" class="text-center text-muted-foreground">
              {{ $t("plugins.loading") }}
            </TableCell>
          </TableRow>
          <TableRow v-else-if="!data || !data.plugins.length">
            <TableCell colspan="6" class="text-center text-muted-foreground">
              {{ $t("plugins.empty") }}
            </TableCell>
          </TableRow>
          <TableRow v-for="p in data?.plugins ?? []" :key="p.name">
            <TableCell>
              <div class="font-medium">{{ p.display_name || p.name }}</div>
              <div
                v-if="p.module && p.module !== (p.display_name || p.name)"
                class="text-xs text-muted-foreground"
              >
                {{ p.module }}
              </div>
            </TableCell>
            <TableCell class="max-w-xs">
              <TooltipProvider :delay-duration="200">
                <Tooltip>
                  <TooltipTrigger as-child>
                    <span
                      class="line-clamp-1 text-sm text-muted-foreground cursor-default"
                    >
                      {{ p.description || "—" }}
                    </span>
                  </TooltipTrigger>
                  <TooltipContent v-if="p.description" class="max-w-xs">
                    <p>{{ p.description }}</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </TableCell>
            <TableCell>
              <Badge v-if="p.type" variant="outline">{{ p.type }}</Badge>
              <span v-else class="text-muted-foreground">—</span>
            </TableCell>
            <TableCell>
              <Badge variant="secondary">{{ p.source }}</Badge>
            </TableCell>
            <TableCell>
              <TooltipProvider v-if="!p.can_disable" :delay-duration="200">
                <Tooltip>
                  <TooltipTrigger as-child>
                    <span>
                      <Switch :model-value="p.enabled" disabled />
                    </span>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>{{ $t("plugins.cannotDisable") }}</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <Switch
                v-else
                :model-value="p.enabled"
                @update:model-value="(v: boolean) => toggle(p.name, v)"
              />
            </TableCell>
            <TableCell class="text-right">
              <div class="flex items-center justify-end gap-0.5">
                <Button
                  variant="ghost"
                  size="icon"
                  :aria-label="`查看 ${p.name} 详情`"
                  @click="openDetail(p)"
                >
                  <Info class="size-4" aria-hidden="true" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  :aria-label="`配置 ${p.name}`"
                  @click="openConfig(p.name)"
                >
                  <Settings2 class="size-4" aria-hidden="true" />
                </Button>
                <Button
                  v-if="p.can_uninstall"
                  variant="ghost"
                  size="icon"
                  :aria-label="`卸载 ${p.name}`"
                  @click="remove(p.name)"
                >
                  <Trash2 class="size-4 text-destructive" aria-hidden="true" />
                </Button>
              </div>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>

    <Sheet v-model:open="detailOpen">
      <SheetContent class="w-full overflow-y-auto sm:max-w-md">
        <SheetHeader>
          <SheetTitle>{{
            detailPlugin?.display_name || detailPlugin?.name
          }}</SheetTitle>
          <SheetDescription>{{
            detailPlugin?.description || $t("plugins.noDescription")
          }}</SheetDescription>
        </SheetHeader>

        <div v-if="detailPlugin" class="space-y-4 px-4 text-sm">
          <dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
            <dt class="text-muted-foreground">
              {{ $t("plugins.identifier") }}
            </dt>
            <dd class="break-all font-mono">{{ detailPlugin.name }}</dd>
            <dt class="text-muted-foreground">{{ $t("plugins.source") }}</dt>
            <dd>{{ detailPlugin.source }}</dd>
            <template v-if="detailPlugin.type">
              <dt class="text-muted-foreground">{{ $t("plugins.type") }}</dt>
              <dd>{{ detailPlugin.type }}</dd>
            </template>
            <dt class="text-muted-foreground">{{ $t("plugins.module") }}</dt>
            <dd class="break-all font-mono">
              {{ detailPlugin.path_or_module }}
            </dd>
          </dl>

          <div v-if="detailPlugin.supported_adapters?.length">
            <p class="mb-1 text-muted-foreground">
              {{ $t("plugins.supportedAdapters") }}
            </p>
            <div class="flex flex-wrap gap-1">
              <Badge
                v-for="a in detailPlugin.supported_adapters"
                :key="a"
                variant="outline"
              >
                {{ a }}
              </Badge>
            </div>
          </div>

          <div v-if="detailPlugin.usage">
            <p class="mb-1 text-muted-foreground">{{ $t("plugins.usage") }}</p>
            <pre class="whitespace-pre-wrap rounded-lg bg-muted p-3 text-xs">{{
              detailPlugin.usage
            }}</pre>
          </div>

          <a
            v-if="detailPlugin.homepage"
            :href="detailPlugin.homepage"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center gap-1 text-primary hover:underline"
          >
            {{ $t("plugins.homepage") }}
          </a>

          <div
            v-if="
              detailPlugin.depends_on.length || detailPlugin.depended_by.length
            "
          >
            <p class="mb-2 text-muted-foreground font-medium">
              {{ $t("plugins.dependency") }}
            </p>

            <div v-if="detailPlugin.depends_on.length" class="mb-2">
              <p class="text-xs text-muted-foreground mb-1">
                {{ $t("plugins.dependsOn") }}
              </p>
              <div class="flex flex-wrap gap-1">
                <Badge
                  v-for="d in detailPlugin.depends_on"
                  :key="d"
                  variant="secondary"
                >
                  {{ d }}
                </Badge>
              </div>
            </div>

            <div v-if="detailPlugin.depended_by.length">
              <p class="text-xs text-muted-foreground mb-1">
                {{ $t("plugins.dependedBy") }}
              </p>
              <div class="flex flex-wrap gap-1">
                <Badge
                  v-for="d in detailPlugin.depended_by"
                  :key="d"
                  variant="secondary"
                >
                  {{ d }}
                </Badge>
              </div>
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>

    <Dialog v-model:open="installOpen">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{{ $t("plugins.installPlugin") }}</DialogTitle>
          <DialogDescription>{{
            $t("plugins.installDescription")
          }}</DialogDescription>
        </DialogHeader>
        <div class="space-y-4 py-2">
          <div class="space-y-2">
            <Label for="plugin-install-name">{{ $t("plugins.name") }}</Label>
            <Input id="plugin-install-name" v-model="installForm.name" />
          </div>
          <div class="space-y-2">
            <Label for="plugin-install-pkg">{{ $t("plugins.pypiName") }}</Label>
            <Input id="plugin-install-pkg" v-model="installForm.pkg" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="installOpen = false">{{
            $t("common.cancel")
          }}</Button>
          <Button :disabled="install.isPending.value" @click="submitInstall">{{
            $t("store.install")
          }}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <InstallProgressDialog
      :open="progressOpen"
      :task-id="progressTaskId"
      :title="progressTitle"
      @close="onProgressClose"
    />

    <Dialog v-model:open="configOpen">
      <DialogContent
        class="max-w-2xl max-h-[85vh] flex flex-col overflow-hidden"
        :show-close-button="false"
        @escape-key-down="
          (e) => {
            e.preventDefault();
            guardCloseConfig();
          }
        "
        @interact-outside="
          (e) => {
            e.preventDefault();
            guardCloseConfig();
          }
        "
      >
        <DialogHeader class="space-y-1">
          <div class="flex flex-row items-center justify-between gap-2">
            <DialogTitle>{{ $t("plugins.config") }}</DialogTitle>
            <Button
              variant="ghost"
              size="icon"
              aria-label="关闭"
              @click="guardCloseConfig"
            >
              <X class="size-4" aria-hidden="true" />
            </Button>
          </div>
          <p class="font-mono text-xs text-muted-foreground">
            {{ configPlugin }}
          </p>
        </DialogHeader>
        <ConfigEditor
          v-if="pluginConfigData"
          ref="configEditorRef"
          :schema="pluginConfigData.schema"
          :model-value="pluginConfigData.values"
          section="plugins"
          :owner-id="configPlugin"
          :save-mutation="
            async (d: Record<string, unknown>) => {
              await savePluginConfig.mutateAsync({
                name: configPlugin,
                data: d,
              });
            }
          "
        />
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="confirmOpen">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{{ $t("confirm.title") }}</DialogTitle>
          <DialogDescription>{{ confirmMessage }}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" @click="confirmOpen = false">{{
            $t("confirm.cancel")
          }}</Button>
          <Button variant="destructive" @click="executeConfirm">{{
            $t("confirm.confirm")
          }}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
