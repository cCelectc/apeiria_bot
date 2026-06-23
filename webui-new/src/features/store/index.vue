<template>
  <Card>
    <CardHeader class="flex-row items-center justify-between">
      <div><CardTitle>Store</CardTitle><CardDescription>Plugin & adapter marketplace</CardDescription></div>
      <div class="flex items-center gap-2">
        <Input v-model="storeSearch" placeholder="Search..." class="w-48" @keydown.enter="searchStore" />
        <Button variant="outline" size="sm" @click="refreshStore">Refresh</Button>
      </div>
    </CardHeader>
    <CardContent>
      <Tabs v-model="storeTab">
        <TabsList><TabsTrigger value="plugins">Plugins</TabsTrigger><TabsTrigger value="adapters">Adapters</TabsTrigger></TabsList>
        <TabsContent value="plugins" class="mt-4">
          <Skeleton v-if="pluginItemsLoading" class="h-64 w-full" />
          <div v-else-if="pluginItems && pluginItems.length > 0" class="grid gap-3 sm:grid-cols-2">
            <Card v-for="item in pluginItems" :key="String((item as Record<string,unknown>).id)" class="p-4">
              <div class="flex items-center justify-between">
                <div>
                  <h4 class="font-medium text-sm">{{ item.name }}</h4>
                  <p class="text-xs text-muted-foreground mt-0.5">{{ String(item.description ?? "").slice(0, 80) }}</p>
                </div>
                <Button size="sm" variant="outline" @click="installPlugin(item)">Install</Button>
              </div>
            </Card>
          </div>
          <EmptyState v-else title="No plugins" description="Configure store sources to browse plugins." />
        </TabsContent>
        <TabsContent value="adapters" class="mt-4">
          <EmptyState title="Adapter Store" description="Browse available adapters." />
        </TabsContent>
      </Tabs>
    </CardContent>
  </Card>
</template>
<script setup lang="ts">
import { ref } from "vue"
import client from "@/api/client"
import { useNoticeStore } from "@/stores/notice"
import Button from "@/components/ui/button/Button.vue"
import Input from "@/components/ui/input/Input.vue"
import Skeleton from "@/components/ui/skeleton/Skeleton.vue"
import Tabs from "@/components/ui/tabs/Tabs.vue"
import { TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import Card from "@/components/ui/card/Card.vue"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import EmptyState from "@/components/EmptyState.vue"
const notice = useNoticeStore()
const storeTab = ref("plugins"); const storeSearch = ref("")
const pluginItems = ref<Record<string,unknown>[]>([]); const pluginItemsLoading = ref(false)
async function refreshStore() { pluginItemsLoading.value = true
  try { await client.post("/plugins/store/refresh"); const r = await client.get("/plugins/store/items"); pluginItems.value = (r.data as Record<string,unknown>).items as Record<string,unknown>[] ?? [] }
  finally { pluginItemsLoading.value = false }
}
async function searchStore() { pluginItemsLoading.value = true
  try { const r = await client.get("/plugins/store/items", { params: { search: storeSearch.value } }); pluginItems.value = (r.data as Record<string,unknown>).items as Record<string,unknown>[] ?? [] }
  finally { pluginItemsLoading.value = false }
}
async function installPlugin(_item: Record<string,unknown>) { notice.show("Install not yet implemented", "warning") }
</script>
