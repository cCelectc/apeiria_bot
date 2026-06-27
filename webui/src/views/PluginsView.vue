<script setup lang="ts">
import { reactive, ref, computed } from 'vue'
import { Info, Plus, Settings2, Trash2 } from '@lucide/vue'
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
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
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
  usePluginConfigQuery,
  usePluginMutations,
  usePluginsQuery,
  useSavePluginConfig,
} from '@/composables/usePlugins'
import type { Plugin } from '@/types'

const { data, isLoading } = usePluginsQuery()
const { install, uninstall, setState } = usePluginMutations()

const installOpen = ref(false)
const installForm = reactive({ name: '', pkg: '' })

const configOpen = ref(false)
const configPlugin = ref('')
const { data: pluginConfigData } = usePluginConfigQuery(
  computed(() => configPlugin.value),
)
const savePluginConfig = useSavePluginConfig()

const detailOpen = ref(false)
const detailPlugin = ref<Plugin | null>(null)

function openDetail(p: Plugin) {
  detailPlugin.value = p
  detailOpen.value = true
}

function openConfig(name: string) {
  configPlugin.value = name
  configOpen.value = true
}

function submitInstall() {
  install.mutate(
    { name: installForm.name, pkg: installForm.pkg },
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
        <h1 class="text-2xl font-semibold tracking-tight">插件管理</h1>
        <p class="mt-1 text-sm text-muted-foreground">安装、卸载、启停与配置</p>
      </div>
      <Button @click="installOpen = true">
        <Plus class="size-4" />
        安装插件
      </Button>
    </div>

    <div class="rounded-xl border bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>名称</TableHead>
            <TableHead>描述</TableHead>
            <TableHead>类型</TableHead>
            <TableHead>来源</TableHead>
            <TableHead>启用</TableHead>
            <TableHead class="text-right">操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-if="isLoading">
            <TableCell colspan="6" class="text-center text-muted-foreground">
              加载中...
            </TableCell>
          </TableRow>
          <TableRow v-else-if="!data || !data.plugins.length">
            <TableCell colspan="6" class="text-center text-muted-foreground">
              暂无数据
            </TableCell>
          </TableRow>
          <TableRow v-for="p in data?.plugins ?? []" :key="p.name">
            <TableCell>
              <div class="font-medium">{{ p.display_name || p.name }}</div>
              <div
                v-if="p.display_name && p.display_name !== p.name"
                class="text-xs text-muted-foreground"
              >
                {{ p.name }}
              </div>
            </TableCell>
            <TableCell class="max-w-xs">
              <span class="line-clamp-1 text-sm text-muted-foreground">
                {{ p.description || '—' }}
              </span>
            </TableCell>
            <TableCell>
              <Badge v-if="p.type" variant="outline">{{ p.type }}</Badge>
              <span v-else class="text-muted-foreground">—</span>
            </TableCell>
            <TableCell>
              <Badge variant="secondary">{{ p.source }}</Badge>
            </TableCell>
            <TableCell>
              <Switch
                :model-value="p.enabled"
                @update:model-value="(v: boolean) => toggle(p.name, v)"
              />
            </TableCell>
            <TableCell class="text-right">
              <Button variant="ghost" size="icon" @click="openDetail(p)">
                <Info class="size-4" />
              </Button>
              <Button variant="ghost" size="icon" @click="openConfig(p.name)">
                <Settings2 class="size-4" />
              </Button>
              <Button variant="ghost" size="icon" @click="remove(p.name)">
                <Trash2 class="size-4 text-destructive" />
              </Button>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>

    <Sheet v-model:open="detailOpen">
      <SheetContent class="w-full overflow-y-auto sm:max-w-md">
        <SheetHeader>
          <SheetTitle>{{ detailPlugin?.display_name || detailPlugin?.name }}</SheetTitle>
          <SheetDescription>{{ detailPlugin?.description || '无描述' }}</SheetDescription>
        </SheetHeader>

        <div v-if="detailPlugin" class="space-y-4 px-4 text-sm">
          <div class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
            <span class="text-muted-foreground">标识</span>
            <span class="break-all font-mono">{{ detailPlugin.name }}</span>
            <span class="text-muted-foreground">来源</span>
            <span>{{ detailPlugin.source }}</span>
            <template v-if="detailPlugin.type">
              <span class="text-muted-foreground">类型</span>
              <span>{{ detailPlugin.type }}</span>
            </template>
            <span class="text-muted-foreground">模块</span>
            <span class="break-all font-mono">{{ detailPlugin.path_or_module }}</span>
          </div>

          <div v-if="detailPlugin.supported_adapters?.length">
            <p class="mb-1 text-muted-foreground">支持适配器</p>
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
            <p class="mb-1 text-muted-foreground">用法</p>
            <pre
              class="whitespace-pre-wrap rounded-lg bg-muted p-3 text-xs"
            >{{ detailPlugin.usage }}</pre>
          </div>

          <a
            v-if="detailPlugin.homepage"
            :href="detailPlugin.homepage"
            target="_blank"
            rel="noreferrer"
            class="inline-flex items-center gap-1 text-primary hover:underline"
          >
            项目主页
          </a>
        </div>
      </SheetContent>
    </Sheet>

    <Dialog v-model:open="installOpen">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>安装插件</DialogTitle>
          <DialogDescription>填写插件名称与 PyPI 包名</DialogDescription>
        </DialogHeader>
        <div class="space-y-4 py-2">
          <div class="space-y-2">
            <Label>名称</Label>
            <Input v-model="installForm.name" />
          </div>
          <div class="space-y-2">
            <Label>PyPI 包名</Label>
            <Input v-model="installForm.pkg" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="installOpen = false">取消</Button>
          <Button :disabled="install.isPending.value" @click="submitInstall">安装</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="configOpen">
      <DialogContent class="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{{ configPlugin }} 配置</DialogTitle>
        </DialogHeader>
        <ConfigEditor
          v-if="pluginConfigData"
          :schema="pluginConfigData.schema"
          :model-value="pluginConfigData.values"
          section="plugins"
          :owner-id="configPlugin"
          :save-mutation="
            async (d: Record<string, unknown>) => {
              await savePluginConfig.mutateAsync({ name: configPlugin, data: d })
            }
          "
        />
      </DialogContent>
    </Dialog>
  </div>
</template>
