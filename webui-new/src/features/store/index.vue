<template>
  <Card>
    <CardHeader class="flex-row items-center justify-between">
      <div><CardTitle>Store</CardTitle><CardDescription>Plugin & adapter marketplace</CardDescription></div>
      <div class="flex items-center gap-2">
        <Input v-model="storeSearch" placeholder="Search..." class="w-48" />
        <Button variant="outline" size="sm" @click="refreshStore">Refresh</Button>
      </div>
    </CardHeader>
    <CardContent>
      <Tabs v-model="storeTab">
        <TabsList>
          <TabsTrigger value="plugins">Plugins</TabsTrigger>
          <TabsTrigger value="adapters">Adapters</TabsTrigger>
        </TabsList>
        <TabsContent value="plugins" class="mt-4">
          <Skeleton v-if="storeLoading" class="h-64 w-full" />
          <EmptyState v-else title="Plugin Store" description="Browse available plugins from configured sources." />
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
import Button from "@/components/ui/button/Button.vue"
import Input from "@/components/ui/input/Input.vue"
import Skeleton from "@/components/ui/skeleton/Skeleton.vue"
import Tabs from "@/components/ui/tabs/Tabs.vue"
import { TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import Card from "@/components/ui/card/Card.vue"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import EmptyState from "@/components/EmptyState.vue"

const storeTab = ref("plugins")
const storeSearch = ref("")
const storeLoading = ref(false)

async function refreshStore() {
  storeLoading.value = true
  try { await client.post("/plugins/store/refresh") } finally { storeLoading.value = false }
}
</script>
