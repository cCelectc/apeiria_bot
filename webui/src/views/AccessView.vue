<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { useI18n } from "vue-i18n";
import {
  Check,
  ChevronsUpDown,
  GripVertical,
  Plus,
  Search,
  Trash2,
} from "@lucide/vue";
import { toast } from "vue-sonner";
import ErrorState from "@/components/ErrorState.vue";
import PageHeader from "@/components/PageHeader.vue";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
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
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
import { cn } from "@/lib/utils";
import {
  useAccessMutations,
  useAccessPreviewQuery,
  useAccessRulesQuery,
  usePluginNamesQuery,
} from "@/composables/useAccess";
import type { AccessRule } from "@/types";

const { t } = useI18n();
const { data, isLoading, isError, error, refetch } = useAccessRulesQuery();
const { create, update, remove, reorder } = useAccessMutations();
const { data: pluginNamesData } = usePluginNamesQuery();

const pluginNames = computed(() => pluginNamesData?.value?.names ?? []);

const rules = computed(() => data?.value?.rules ?? []);

const dialogOpen = ref(false);
const dialogMode = ref<"create" | "edit">("create");
const editingId = ref<number | null>(null);
const form = reactive({
  subject_type: "user" as "user" | "group",
  subject_id: "",
  plugin_name: "",
  action: "allow" as "allow" | "deny",
  priority: 0,
});

const deleteOpen = ref(false);
const deleteTarget = ref<AccessRule | null>(null);

const previewOpen = ref(false);
const previewForm = reactive({
  subject_type: "user" as "user" | "group",
  subject_id: "",
  plugin_name: "",
});
const previewParams = computed(() => {
  const f = previewForm;
  if (!f.subject_id || !f.plugin_name) return null;
  return {
    subject_type: f.subject_type,
    subject_id: f.subject_id,
    plugin_name: f.plugin_name,
  };
});
const { data: previewData } = useAccessPreviewQuery(previewParams);

function openCreate() {
  dialogMode.value = "create";
  editingId.value = null;
  form.subject_type = "user";
  form.subject_id = "";
  form.plugin_name = "";
  form.action = "allow";
  form.priority = 0;
  dialogOpen.value = true;
}

function openEdit(rule: AccessRule) {
  dialogMode.value = "edit";
  editingId.value = rule.id;
  form.subject_type = rule.subject_type;
  form.subject_id = rule.subject_id;
  form.plugin_name = rule.plugin_name ?? "";
  form.action = rule.action;
  form.priority = rule.priority;
  dialogOpen.value = true;
}

async function handleSave() {
  if (!form.subject_id.trim()) {
    toast.error(t("access.validationError"));
    return;
  }
  const payload = {
    subject_type: form.subject_type,
    subject_id: form.subject_id.trim(),
    plugin_name: form.plugin_name || null,
    action: form.action,
    priority: form.priority,
  };
  if (dialogMode.value === "create") {
    await create.mutateAsync(payload);
    toast.success(t("access.createSuccess"));
  } else if (editingId.value !== null) {
    await update.mutateAsync({ id: editingId.value, data: payload });
    toast.success(t("access.updateSuccess"));
  }
  dialogOpen.value = false;
}

function confirmDelete(rule: AccessRule) {
  deleteTarget.value = rule;
  deleteOpen.value = true;
}

async function handleDelete() {
  if (deleteTarget.value) {
    await remove.mutateAsync(deleteTarget.value.id);
    toast.success(t("access.deleteSuccess"));
    deleteOpen.value = false;
    deleteTarget.value = null;
  }
}

async function handleReorder(targetIndex: number, sourceIndex: number) {
  if (targetIndex === sourceIndex) return;
  const ids = rules.value.map((r) => r.id);
  const [moved] = ids.splice(sourceIndex, 1);
  ids.splice(targetIndex, 0, moved);
  await reorder.mutateAsync(ids);
  toast.success(t("access.reorderSuccess"));
}

function moveUp(index: number) {
  if (index <= 0) return;
  handleReorder(index - 1, index);
}

function moveDown(index: number) {
  if (index >= rules.value.length - 1) return;
  handleReorder(index + 1, index);
}

const actionBadgeVariant = (action: string) =>
  action === "allow" ? "default" : "destructive";
const typeLabel = (tval: string) => (tval === "user" ? t("access.user") : t("access.group"));

const pluginComboboxOpen = ref(false);
</script>

<template>
  <div class="flex flex-col gap-6 p-6">
    <PageHeader :title="t('access.title')" :subtitle="t('access.subtitle')">
      <template #actions>
        <div class="flex gap-2">
          <Button @click="previewOpen = true" variant="outline">
            <Search class="size-4" />
            {{ t("access.preview") }}
          </Button>
          <Button @click="openCreate">
            <Plus class="size-4" />
            {{ t("access.addRule") }}
          </Button>
        </div>
      </template>
    </PageHeader>

    <ErrorState v-if="isError" :message="String(error)" @retry="refetch()" />

    <div
      v-else
      class="rounded-xl border bg-card shadow-sm"
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead class="w-12" />
            <TableHead>{{ t("access.subjectType") }}</TableHead>
            <TableHead>{{ t("access.subjectId") }}</TableHead>
            <TableHead>{{ t("access.pluginName") }}</TableHead>
            <TableHead>{{ t("access.action") }}</TableHead>
            <TableHead class="w-24">{{ t("access.priority") }}</TableHead>
            <TableHead class="w-24">{{ t("plugins.actions") }}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-if="isLoading">
            <TableCell colspan="7" class="text-center text-muted-foreground py-8">
              {{ t("common.loading") }}
            </TableCell>
          </TableRow>
          <TableRow v-else-if="rules.length === 0">
            <TableCell colspan="7" class="text-center text-muted-foreground py-8">
              {{ t("access.noRules") }}
            </TableCell>
          </TableRow>
          <TableRow v-for="(rule, idx) in rules" :key="rule.id">
            <TableCell>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger as-child>
                    <div class="flex gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        class="size-7"
                        @click="moveUp(idx)"
                        :disabled="idx === 0"
                      >
                        <GripVertical class="size-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        class="size-7 rotate-180"
                        @click="moveDown(idx)"
                        :disabled="idx === rules.length - 1"
                      >
                        <GripVertical class="size-3.5" />
                      </Button>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent>{{ t("access.dragHint") }}</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </TableCell>
            <TableCell>
              <Badge variant="outline">{{ typeLabel(rule.subject_type) }}</Badge>
            </TableCell>
            <TableCell class="font-mono text-sm">{{ rule.subject_id }}</TableCell>
            <TableCell>
              <Badge variant="secondary" v-if="rule.plugin_name">{{ rule.plugin_name }}</Badge>
              <span v-else class="text-muted-foreground text-sm">{{ t("access.allPlugins") }}</span>
            </TableCell>
            <TableCell>
              <Badge :variant="actionBadgeVariant(rule.action)">
                {{ rule.action === "allow" ? t("access.allow") : t("access.deny") }}
              </Badge>
            </TableCell>
            <TableCell class="font-mono text-sm">{{ rule.priority }}</TableCell>
            <TableCell>
              <div class="flex gap-1">
                <Button variant="ghost" size="icon" class="size-8" @click="openEdit(rule)">
                  <Search class="size-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  class="size-8 text-destructive"
                  @click="confirmDelete(rule)"
                >
                  <Trash2 class="size-3.5" />
                </Button>
              </div>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>

    <!-- Create / Edit Dialog -->
    <Dialog :open="dialogOpen" @update:open="dialogOpen = $event">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {{ dialogMode === "create" ? t("access.addRule") : t("access.editRule") }}
          </DialogTitle>
          <DialogDescription />
        </DialogHeader>
        <div class="grid gap-4 py-2">
          <div class="grid gap-2">
            <Label>{{ t("access.subjectType") }}</Label>
            <Select v-model="form.subject_type">
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="user">{{ t("access.user") }}</SelectItem>
                <SelectItem value="group">{{ t("access.group") }}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div class="grid gap-2">
            <Label>{{ t("access.subjectId") }}</Label>
            <Input v-model="form.subject_id" placeholder="ID" />
          </div>
          <div class="grid gap-2">
            <Label>{{ t("access.pluginName") }}</Label>
            <Popover v-model:open="pluginComboboxOpen">
              <PopoverTrigger as-child>
                <Button
                  variant="outline"
                  role="combobox"
                  :aria-expanded="pluginComboboxOpen"
                  class="w-full justify-between font-normal"
                >
                  {{ form.plugin_name || t("access.allPlugins") }}
                  <ChevronsUpDown class="opacity-50" />
                </Button>
              </PopoverTrigger>
              <PopoverContent class="w-full p-0" align="start">
                <Command>
                  <CommandInput :placeholder="t('access.searchPlaceholder')" />
                  <CommandList>
                    <CommandEmpty>{{ t("access.noSubjects") }}</CommandEmpty>
                    <CommandGroup>
                      <CommandItem
                        v-for="name in pluginNames"
                        :key="name"
                        :value="name"
                        @select="() => {
                          form.plugin_name = name
                          pluginComboboxOpen = false
                        }"
                      >
                        <Check
                          :class="cn(
                            'mr-2 size-4',
                            form.plugin_name === name ? 'opacity-100' : 'opacity-0',
                          )"
                        />
                        {{ name }}
                      </CommandItem>
                    </CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
          </div>
          <div class="grid gap-2">
            <Label>{{ t("access.action") }}</Label>
            <Select v-model="form.action">
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="allow">{{ t("access.allow") }}</SelectItem>
                <SelectItem value="deny">{{ t("access.deny") }}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div class="grid gap-2">
            <Label>{{ t("access.priority") }}</Label>
            <Input v-model.number="form.priority" type="number" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="dialogOpen = false">{{ t("common.cancel") }}</Button>
          <Button @click="handleSave" :disabled="create.isPending || update.isPending">
            {{ t("common.save") }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- Delete Confirm Dialog -->
    <Dialog :open="deleteOpen" @update:open="deleteOpen = $event">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{{ t("access.deleteRule") }}</DialogTitle>
          <DialogDescription>{{ t("access.deleteConfirm") }}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" @click="deleteOpen = false">{{ t("common.cancel") }}</Button>
          <Button variant="destructive" @click="handleDelete" :disabled="remove.isPending">
            {{ t("common.delete") }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- Preview Dialog -->
    <Dialog :open="previewOpen" @update:open="previewOpen = $event">
      <DialogContent class="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{{ t("access.previewTitle") }}</DialogTitle>
          <DialogDescription>{{ t("access.previewDesc") }}</DialogDescription>
        </DialogHeader>
        <div class="grid gap-4 py-2">
          <div class="grid grid-cols-2 gap-3">
            <div class="grid gap-2">
              <Label>{{ t("access.subjectType") }}</Label>
              <Select v-model="previewForm.subject_type">
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="user">{{ t("access.user") }}</SelectItem>
                  <SelectItem value="group">{{ t("access.group") }}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div class="grid gap-2">
              <Label>{{ t("access.subjectId") }}</Label>
              <Input v-model="previewForm.subject_id" placeholder="ID" />
            </div>
          </div>
          <div class="grid gap-2">
            <Label>{{ t("access.pluginName") }}</Label>
            <Input
              v-model="previewForm.plugin_name"
              :placeholder="t('access.allPlugins')"
            />
          </div>

          <div
            v-if="previewData"
            class="rounded-lg border bg-muted/50 p-4 mt-2"
          >
            <div class="text-sm font-medium mb-2">{{ t("access.previewResult") }}</div>
            <div v-if="previewData.matched_rule" class="space-y-2">
              <div class="flex items-center gap-2">
                <Badge :variant="actionBadgeVariant(previewData.action)">
                  {{ previewData.action === "allow" ? t("access.allow") : t("access.deny") }}
                </Badge>
                <span class="text-sm text-muted-foreground">{{ t("access.matchedRule") }}</span>
              </div>
              <div class="text-sm space-y-1">
                <div class="flex gap-2">
                  <span class="text-muted-foreground">{{ t("access.subjectType") }}:</span>
                  <Badge variant="outline">{{ typeLabel(previewData.matched_rule.subject_type) }}</Badge>
                </div>
                <div class="flex gap-2">
                  <span class="text-muted-foreground">{{ t("access.subjectId") }}:</span>
                  <span class="font-mono">{{ previewData.matched_rule.subject_id }}</span>
                </div>
                <div class="flex gap-2">
                  <span class="text-muted-foreground">{{ t("access.pluginName") }}:</span>
                  <Badge variant="secondary" v-if="previewData.matched_rule.plugin_name">
                    {{ previewData.matched_rule.plugin_name }}
                  </Badge>
                  <span v-else>{{ t("access.allPlugins") }}</span>
                </div>
                <div class="flex gap-2">
                  <span class="text-muted-foreground">{{ t("access.priority") }}:</span>
                  <span class="font-mono">{{ previewData.matched_rule.priority }}</span>
                </div>
              </div>
            </div>
            <div v-else class="text-sm text-muted-foreground">
              {{ t("access.noMatch") }}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  </div>
</template>
