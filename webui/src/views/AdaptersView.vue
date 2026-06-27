<script setup lang="ts">
import { reactive, ref, computed } from 'vue'
import { Plus, Settings2, Trash2, X } from '@lucide/vue'
import { toast } from 'vue-sonner'
import ConfigEditor from '@/components/ConfigEditor.vue'
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

const { data, isLoading } = useAdaptersQuery()
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
        toast.success('已安装')
        installOpen.value = false
      },
      onError: (e: Error) => toast.error(e.message),
    },
  )
}

function toggle(name: string, enabled: boolean) {
  setState.mutate({ name, enabled }, { onError: (e: Error) => toast.error(e.message) })
}

function remove(name: string) {
  uninstall.mutate(
    { name },
    {
      onSuccess: () => toast.success('已卸载'),
      onError: (e: Error) => toast.error(e.message),
    },
  )
}
</script>

<template>
  <div class="p-6 lg:p-8">
    <div class="mb-6 flex items-center justify-between gap-4">
      <div>
        <h1 class="text-2xl font-semibold tracking-tight">适配器管理</h1>
        <p class="mt-1 text-sm text-muted-foreground">安装、卸载、启停与配置</p>
      </div>
      <Button @click="installOpen = true">
        <Plus class="size-4" />
        安装适配器
      </Button>
    </div>

    <div class="rounded-xl border bg-card shadow-sm">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>名称</TableHead>
            <TableHead>模块</TableHead>
            <TableHead>来源</TableHead>
            <TableHead>启用</TableHead>
            <TableHead class="text-right">操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-if="isLoading">
            <TableCell colspan="5" class="text-center text-muted-foreground">
              加载中...
            </TableCell>
          </TableRow>
          <TableRow v-else-if="!data || !data.adapters.length">
            <TableCell colspan="5" class="text-center text-muted-foreground">
              暂无数据
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
          <DialogTitle>安装适配器</DialogTitle>
          <DialogDescription>填写名称、PyPI 包名与模块名</DialogDescription>
        </DialogHeader>
        <div class="space-y-4 py-2">
          <div class="space-y-2">
            <Label for="adapter-install-name">名称</Label>
            <Input id="adapter-install-name" v-model="installForm.name" />
          </div>
          <div class="space-y-2">
            <Label for="adapter-install-pkg">PyPI 包名</Label>
            <Input id="adapter-install-pkg" v-model="installForm.pkg" />
          </div>
          <div class="space-y-2">
            <Label for="adapter-install-module">模块名</Label>
            <Input id="adapter-install-module" v-model="installForm.module_name" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="installOpen = false">取消</Button>
          <Button :disabled="install.isPending.value" @click="submitInstall">安装</Button>
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
          <DialogTitle>{{ configAdapter }} 适配器配置</DialogTitle>
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
  </div>
</template>
