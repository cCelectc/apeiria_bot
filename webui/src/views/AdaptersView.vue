<script setup lang="ts">
import { reactive, ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Plus, Settings2, Trash2, X } from '@lucide/vue'
import { toast } from 'vue-sonner'
import ConfigEditor from '@/components/ConfigEditor.vue'
import ErrorState from '@/components/ErrorState.vue'
import PageHeader from '@/components/PageHeader.vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  useAdapterConfigQuery,
  useAdapterMutations,
  useAdaptersQuery,
  useSaveAdapterConfig,
} from '@/composables/useAdapters'

const { t } = useI18n()
const { data, isLoading, isError, error, refetch } = useAdaptersQuery()
void isLoading
const { install, uninstall, setState } = useAdapterMutations()

const installOpen = ref(false)
const installForm = reactive({ name: '', pkg: '', module_name: '' })

const configOpen = ref(false)
const configAdapter = ref('')
const { data: adapterConfigData } = useAdapterConfigQuery(
  computed(() => configAdapter.value),
)
const saveAdapterConfig = useSaveAdapterConfig()

const configEditorRef = ref<InstanceType<typeof ConfigEditor>>()

const confirmOpen = ref(false)
const confirmMessage = ref('')
const confirmAction = ref<(() => void) | null>(null)

function askConfirm(msg: string, action: () => void) {
  confirmMessage.value = msg
  confirmAction.value = action
  confirmOpen.value = true
}

function executeConfirm() {
  confirmAction.value?.()
  confirmOpen.value = false
}

async function guardCloseConfig() {
  const ok = (await configEditorRef.value?.attemptClose()) ?? true
  if (ok) configOpen.value = false
}

function openConfig(name: string) {
  configAdapter.value = name
  configOpen.value = true
}

function submitInstall() {
  install.mutate(
    {
      name: installForm.name,
      pkg: installForm.pkg,
      module_name: installForm.module_name,
    },
    {
      onSuccess: () => {
        toast.success(t('adapters.installed'))
        installOpen.value = false
      },
      onError: (e: Error) => toast.error(e.message),
    },
  )
}

function toggle(name: string, enabled: boolean) {
  if (!enabled) {
    askConfirm(t('confirm.disableMessage', { name }), () => {
      setState.mutate({ name, enabled }, { onError: (e: Error) => toast.error(e.message) })
    })
    return
  }
  setState.mutate({ name, enabled }, { onError: (e: Error) => toast.error(e.message) })
}

function remove(name: string) {
  askConfirm(t('confirm.uninstallMessage', { name }), () => {
    uninstall.mutate(
      { name },
      {
        onSuccess: () => toast.success(t('adapters.uninstalled')),
        onError: (e: Error) => toast.error(e.message),
      },
    )
  })
}
</script>

<template>
  <div class="p-6 lg:p-8">
    <PageHeader :title="$t('adapters.title')" :subtitle="$t('adapters.subtitle')">
      <template #actions>
        <Button @click="installOpen = true">
          <Plus class="size-4" />
          {{ $t('adapters.installAdapter') }}
        </Button>
      </template>
    </PageHeader>

    <ErrorState v-if="isError" class="mb-4" :message="(error as Error)?.message" @retry="() => refetch()" />

    <div class="rounded-xl border bg-card shadow-sm">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{{ $t('adapters.name') }}</TableHead>
            <TableHead>{{ $t('adapters.moduleName') }}</TableHead>
            <TableHead>{{ $t('adapters.source') }}</TableHead>
            <TableHead>{{ $t('adapters.enabled') }}</TableHead>
            <TableHead class="text-right">{{ $t('adapters.actions') }}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-if="isLoading">
            <TableCell colspan="5" class="text-center text-muted-foreground">
              {{ $t('adapters.loading') }}
            </TableCell>
          </TableRow>
          <TableRow v-else-if="!data || !data.adapters.length">
            <TableCell colspan="5" class="text-center text-muted-foreground">
              {{ $t('adapters.empty') }}
            </TableCell>
          </TableRow>
          <TableRow v-for="a in data?.adapters ?? []" :key="a.name">
            <TableCell>
              <div class="font-medium">{{ a.name }}</div>
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
              <Button variant="ghost" size="icon" :aria-label="`配置 ${a.name}`" @click="openConfig(a.name)">
                <Settings2 class="size-4" aria-hidden="true" />
              </Button>
              <Button variant="ghost" size="icon" :aria-label="`卸载 ${a.name}`" @click="remove(a.name)">
                <Trash2 class="size-4 text-destructive" aria-hidden="true" />
              </Button>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>

    <Dialog v-model:open="installOpen">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{{ $t('adapters.installAdapter') }}</DialogTitle>
          <DialogDescription>{{ $t('adapters.installDescription') }}</DialogDescription>
        </DialogHeader>
        <div class="space-y-4 py-2">
          <div class="space-y-2">
            <Label for="adapter-install-name">{{ $t('adapters.name') }}</Label>
            <Input id="adapter-install-name" v-model="installForm.name" />
          </div>
          <div class="space-y-2">
            <Label for="adapter-install-pkg">{{ $t('adapters.installAdapterPkg') }}</Label>
            <Input id="adapter-install-pkg" v-model="installForm.pkg" />
          </div>
          <div class="space-y-2">
            <Label for="adapter-install-module">{{ $t('adapters.installAdapterModule') }}</Label>
            <Input id="adapter-install-module" v-model="installForm.module_name" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="installOpen = false">{{ $t('common.cancel') }}</Button>
          <Button :disabled="install.isPending.value" @click="submitInstall">{{ $t('store.install') }}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="configOpen">
      <DialogContent
        class="max-w-2xl max-h-[85vh] overflow-y-auto"
        :show-close-button="false"
        @escape-key-down="(e) => { e.preventDefault(); guardCloseConfig() }"
        @interact-outside="(e) => { e.preventDefault(); guardCloseConfig() }"
      >
        <DialogHeader class="flex flex-row items-center justify-between gap-2 space-y-0">
          <DialogTitle>{{ $t('adapters.config', { name: configAdapter }) }}</DialogTitle>
          <Button variant="ghost" size="icon" aria-label="关闭" @click="guardCloseConfig">
            <X class="size-4" aria-hidden="true" />
          </Button>
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
              await saveAdapterConfig.mutateAsync({ name: configAdapter, data: d })
            }
          "
        />
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="confirmOpen">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{{ $t('confirm.title') }}</DialogTitle>
          <DialogDescription>{{ confirmMessage }}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" @click="confirmOpen = false">{{ $t('confirm.cancel') }}</Button>
          <Button variant="destructive" @click="executeConfirm">{{ $t('confirm.confirm') }}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
