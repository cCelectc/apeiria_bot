<script setup lang="ts">
import { reactive, ref, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import { ArrowUpCircle, Plus, RefreshCw, Settings2, Trash2, X } from "@lucide/vue";
import { toast } from "vue-sonner";
import ConfigEditor from "@/components/ConfigEditor.vue";
import ErrorState from "@/components/ErrorState.vue";
import InstallProgressDialog from "@/components/InstallProgressDialog.vue";
import PageHeader from "@/components/PageHeader.vue";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
  useAdapterConfigQuery,
  useAdapterMutations,
  useAdaptersQuery,
  useAdapterVersionsQuery,
  useSaveAdapterConfig,
} from "@/composables/useAdapters";
import type { UpdateInfo } from "@/types";
import { usePendingChanges } from "@/composables/usePendingChanges";

const { t } = useI18n();
const { pendingChanges, markChanged, clearChanges } = usePendingChanges();
const { data, isLoading, isError, error, refetch } = useAdaptersQuery();
void isLoading;
const { install, uninstall, setState, update, checkUpdates } = useAdapterMutations();

const updates = ref<Record<string, UpdateInfo>>({});
const updateOpen = ref(false);
const updateTarget = ref("");
const selectedVersion = ref("");
const { data: versionsData, isFetching: versionsLoading } = useAdapterVersionsQuery(
  computed(() => (updateOpen.value ? updateTarget.value : "")),
);

const installOpen = ref(false);
const installForm = reactive({ name: "", pkg: "", module_name: "" });
const progressOpen = ref(false);
const progressTaskId = ref<string | null>(null);
const progressTitle = ref("");

const uninstallOpen = ref(false);
const uninstallTarget = ref("");
const keepConfig = ref(false);

const configOpen = ref(false);
const configAdapter = ref("");
const { data: adapterConfigData } = useAdapterConfigQuery(
  computed(() => configAdapter.value),
);
const saveAdapterConfig = useSaveAdapterConfig();

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

function openConfig(name: string) {
  configAdapter.value = name;
  configOpen.value = true;
}

function submitInstall() {
  install.mutate(
    {
      name: installForm.name,
      pkg: installForm.pkg,
      module_name: installForm.module_name,
    },
    {
      onSuccess: (taskId: string) => {
        installOpen.value = false;
        progressTitle.value = `安装适配器: ${installForm.name}`;
        progressTaskId.value = taskId;
        progressOpen.value = true;
        installForm.name = "";
        installForm.pkg = "";
        installForm.module_name = "";
      },
      onError: (e: Error) => toast.error(e.message),
    },
  );
}

function onProgressClose() {
  progressOpen.value = false;
  progressTaskId.value = null;
  markChanged();
  refetch();
}

function checkUpdatesFn() {
  checkUpdates.mutate(undefined, {
    onSuccess: (res) => {
      updates.value = res.updates;
      const n = Object.values(res.updates).filter((u) => u.update_available).length;
      toast.success(n ? t("adapters.checkDone") : t("adapters.allLatest"));
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

function openUpdate(name: string) {
  updateTarget.value = name;
  selectedVersion.value = "";
  updateOpen.value = true;
}

watch(
  () => versionsData.value,
  (v) => {
    if (v && !selectedVersion.value) {
      selectedVersion.value =
        updates.value[updateTarget.value]?.latest ?? v.versions[0] ?? "";
    }
  },
);

function submitUpdate() {
  update.mutate(
    { name: updateTarget.value, version: selectedVersion.value || undefined },
    {
      onSuccess: (taskId: string) => {
        updateOpen.value = false;
        progressTitle.value = `更新适配器: ${updateTarget.value}`;
        progressTaskId.value = taskId;
        progressOpen.value = true;
      },
      onError: (e: Error) => toast.error(e.message),
    },
  );
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
  uninstallTarget.value = name;
  keepConfig.value = false;
  uninstallOpen.value = true;
}

function confirmUninstall() {
  const name = uninstallTarget.value;
  uninstallOpen.value = false;
  uninstall.mutate(
    { name, keep_config: keepConfig.value },
    {
      onSuccess: (taskId: string) => {
        progressTitle.value = `卸载适配器: ${name}`;
        progressTaskId.value = taskId;
        progressOpen.value = true;
      },
      onError: (e: Error) => toast.error(e.message),
    },
  );
}
</script>

<template>
  <div class="p-6 lg:p-8">
    <PageHeader
      :title="$t('adapters.title')"
      :subtitle="$t('adapters.subtitle')"
    >
      <template #actions>
        <Button
          variant="outline"
          :disabled="checkUpdates.isPending.value"
          @click="checkUpdatesFn"
        >
          <RefreshCw
            class="size-4"
            :class="{ 'animate-spin': checkUpdates.isPending.value }"
          />
          {{ $t("adapters.checkUpdates") }}
        </Button>
        <Button @click="installOpen = true">
          <Plus class="size-4" />
          {{ $t("adapters.installAdapter") }}
        </Button>
      </template>
    </PageHeader>

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
            <TableHead>{{ $t("adapters.name") }}</TableHead>
            <TableHead>{{ $t("adapters.moduleName") }}</TableHead>
            <TableHead>{{ $t("adapters.source") }}</TableHead>
            <TableHead>{{ $t("adapters.enabled") }}</TableHead>
            <TableHead class="text-right">{{
              $t("adapters.actions")
            }}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-if="isLoading">
            <TableCell colspan="5" class="text-center text-muted-foreground">
              {{ $t("adapters.loading") }}
            </TableCell>
          </TableRow>
          <TableRow v-else-if="!data || !data.adapters.length">
            <TableCell colspan="5" class="text-center text-muted-foreground">
              {{ $t("adapters.empty") }}
            </TableCell>
          </TableRow>
          <TableRow v-for="a in data?.adapters ?? []" :key="a.name">
            <TableCell>
              <div class="flex items-center gap-2">
                <span class="font-medium">{{ a.name }}</span>
                <Badge
                  v-if="updates[a.name]?.update_available"
                  variant="default"
                >
                  {{ $t("adapters.updateAvailable") }} → {{ updates[a.name].latest }}
                </Badge>
              </div>
            </TableCell>
            <TableCell class="font-mono text-xs text-muted-foreground">
              {{ a.module_name }}
            </TableCell>
            <TableCell>
              <Badge variant="secondary">{{ a.source }}</Badge>
            </TableCell>
            <TableCell>
              <Switch
                :model-value="a.enabled"
                @update:model-value="(v: boolean) => toggle(a.name, v)"
              />
            </TableCell>
            <TableCell class="text-right">
              <div class="flex items-center justify-end gap-0.5">
                <Button
                  variant="ghost"
                  size="icon"
                  :aria-label="`配置 ${a.name}`"
                  @click="openConfig(a.name)"
                >
                  <Settings2 class="size-4" aria-hidden="true" />
                </Button>
                <Button
                  v-if="a.source === 'pypi'"
                  variant="ghost"
                  size="icon"
                  :aria-label="`更新 ${a.name}`"
                  @click="openUpdate(a.name)"
                >
                  <ArrowUpCircle
                    class="size-4"
                    :class="{ 'text-primary': updates[a.name]?.update_available }"
                    aria-hidden="true"
                  />
                </Button>
                <Button
                  v-if="a.source !== 'builtin'"
                  variant="ghost"
                  size="icon"
                  :aria-label="`卸载 ${a.name}`"
                  @click="remove(a.name)"
                >
                  <Trash2 class="size-4 text-destructive" aria-hidden="true" />
                </Button>
              </div>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>

    <Dialog v-model:open="installOpen">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{{ $t("adapters.installAdapter") }}</DialogTitle>
          <DialogDescription>{{
            $t("adapters.installDescription")
          }}</DialogDescription>
        </DialogHeader>
        <div class="space-y-4 py-2">
          <div class="space-y-2">
            <Label for="adapter-install-name">{{ $t("adapters.name") }}</Label>
            <Input id="adapter-install-name" v-model="installForm.name" />
          </div>
          <div class="space-y-2">
            <Label for="adapter-install-pkg">{{
              $t("adapters.installAdapterPkg")
            }}</Label>
            <Input id="adapter-install-pkg" v-model="installForm.pkg" />
          </div>
          <div class="space-y-2">
            <Label for="adapter-install-module">{{
              $t("adapters.installAdapterModule")
            }}</Label>
            <Input
              id="adapter-install-module"
              v-model="installForm.module_name"
            />
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
            <DialogTitle>{{ $t("adapters.config") }}</DialogTitle>
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
            {{ configAdapter }}
          </p>
        </DialogHeader>
        <ConfigEditor
          v-if="adapterConfigData"
          ref="configEditorRef"
          :schema="adapterConfigData.schema"
          :model-value="adapterConfigData.values"
          section="adapters"
          :owner-id="configAdapter"
          :save-mutation="
            async (d: Record<string, unknown>) => {
              await saveAdapterConfig.mutateAsync({
                name: configAdapter,
                data: d,
              });
            }
          "
        />
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="uninstallOpen">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{{ $t("adapters.uninstallTitle") }}</DialogTitle>
          <DialogDescription>
            {{ $t("adapters.uninstallDesc", { name: uninstallTarget }) }}
          </DialogDescription>
        </DialogHeader>
        <div class="flex items-center gap-2 py-2">
          <Checkbox id="keep-config-adapter" v-model:checked="keepConfig" />
          <Label for="keep-config-adapter">{{ $t("adapters.keepConfig") }}</Label>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="uninstallOpen = false">
            {{ $t("common.cancel") }}
          </Button>
          <Button variant="destructive" @click="confirmUninstall">
            {{ $t("common.confirm") }}
          </Button>
        </DialogFooter>
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

    <InstallProgressDialog
      :open="progressOpen"
      :task-id="progressTaskId"
      :title="progressTitle"
      @close="onProgressClose"
    />

    <Dialog v-model:open="updateOpen">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{{ $t("adapters.updateTitle") }}</DialogTitle>
          <DialogDescription>
            {{ $t("adapters.updateDesc", { name: updateTarget }) }}
          </DialogDescription>
        </DialogHeader>
        <div class="space-y-2 py-2">
          <Label>{{ $t("adapters.version") }}</Label>
          <p v-if="versionsLoading" class="text-sm text-muted-foreground">
            {{ $t("adapters.loadingVersions") }}
          </p>
          <Select v-else v-model="selectedVersion">
            <SelectTrigger>
              <SelectValue :placeholder="$t('adapters.selectVersion')" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem
                v-for="v in versionsData?.versions ?? []"
                :key="v"
                :value="v"
              >
                {{ v }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="updateOpen = false">
            {{ $t("common.cancel") }}
          </Button>
          <Button
            :disabled="!selectedVersion || update.isPending.value"
            @click="submitUpdate"
          >
            {{ $t("adapters.doUpdate") }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
