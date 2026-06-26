<script setup lang="ts">
import { ref } from 'vue'
import { Download, Search } from '@lucide/vue'
import { toast } from 'vue-sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useAdapterMutations } from '@/composables/useAdapters'
import { usePluginMutations } from '@/composables/usePlugins'
import { useStoreAdaptersQuery, useStorePluginsQuery } from '@/composables/useStore'
import type { StoreItem } from '@/types'

const query = ref('')
const tab = ref('plugins')

const { data: pluginData, isFetching: pluginLoading } = useStorePluginsQuery(query)
const { data: adapterData, isFetching: adapterLoading } = useStoreAdaptersQuery(query)
const { install: installPlugin } = usePluginMutations()
const { install: installAdapter } = useAdapterMutations()

function addPlugin(item: StoreItem) {
  installPlugin.mutate(
    { name: item.name, pkg: item.pypi_name },
    {
      onSuccess: () => toast.success(`已安装 ${item.name}`),
      onError: (e: Error) => toast.error(e.message),
    },
  )
}

function addAdapter(item: StoreItem) {
  installAdapter.mutate(
    { name: item.name, pkg: item.pypi_name, module_name: item.module_names[0] ?? '' },
    {
      onSuccess: () => toast.success(`已安装 ${item.name}`),
      onError: (e: Error) => toast.error(e.message),
    },
  )
}
</script>

<template>
  <div class="p-6 lg:p-8">
    <h1 class="text-2xl font-semibold tracking-tight">商店</h1>
    <p class="mb-6 mt-1 text-sm text-muted-foreground">搜索 NoneBot 官方插件与适配器</p>

    <div class="relative mb-6 max-w-md">
      <Search class="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
      <Input v-model="query" placeholder="输入关键词搜索…" class="pl-9" />
    </div>

    <Tabs v-model="tab">
      <TabsList>
        <TabsTrigger value="plugins">插件</TabsTrigger>
        <TabsTrigger value="adapters">适配器</TabsTrigger>
      </TabsList>

      <TabsContent value="plugins">
        <p v-if="!query.trim()" class="py-8 text-center text-sm text-muted-foreground">
          输入关键词以搜索插件
        </p>
        <p v-else-if="pluginLoading" class="py-8 text-center text-sm text-muted-foreground">
          搜索中…
        </p>
        <p
          v-else-if="!pluginData || !pluginData.results.length"
          class="py-8 text-center text-sm text-muted-foreground"
        >
          无匹配结果
        </p>
        <div v-else class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <Card v-for="item in pluginData.results" :key="item.pypi_name || item.name">
            <CardHeader>
              <CardTitle class="text-base">{{ item.name }}</CardTitle>
              <p class="line-clamp-2 text-sm text-muted-foreground">{{ item.description }}</p>
            </CardHeader>
            <CardContent class="flex items-center justify-between gap-2">
              <Badge variant="secondary">{{ item.author }}</Badge>
              <Button size="sm" @click="addPlugin(item)">
                <Download class="size-4" />
                安装
              </Button>
            </CardContent>
          </Card>
        </div>
      </TabsContent>

      <TabsContent value="adapters">
        <p v-if="!query.trim()" class="py-8 text-center text-sm text-muted-foreground">
          输入关键词以搜索适配器
        </p>
        <p v-else-if="adapterLoading" class="py-8 text-center text-sm text-muted-foreground">
          搜索中…
        </p>
        <p
          v-else-if="!adapterData || !adapterData.results.length"
          class="py-8 text-center text-sm text-muted-foreground"
        >
          无匹配结果
        </p>
        <div v-else class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <Card v-for="item in adapterData.results" :key="item.pypi_name || item.name">
            <CardHeader>
              <CardTitle class="text-base">{{ item.name }}</CardTitle>
              <p class="line-clamp-2 text-sm text-muted-foreground">{{ item.description }}</p>
            </CardHeader>
            <CardContent class="flex items-center justify-between gap-2">
              <Badge variant="secondary">{{ item.author }}</Badge>
              <Button size="sm" @click="addAdapter(item)">
                <Download class="size-4" />
                安装
              </Button>
            </CardContent>
          </Card>
        </div>
      </TabsContent>
    </Tabs>
  </div>
</template>
