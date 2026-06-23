<template>
  <Card>
    <CardHeader class="flex-row items-center justify-between">
      <div><CardTitle>Adapters</CardTitle><CardDescription>Communication adapter configuration</CardDescription></div>
      <Button variant="outline" size="sm" :disabled="loading" @click="refresh()">Refresh</Button>
    </CardHeader>
    <CardContent>
      <Skeleton v-if="loading" class="h-64 w-full" />
      <DataTable v-else-if="adapters && adapters.length > 0"
        :columns="[{key:'name',label:'Name'},{key:'type',label:'Type'},{key:'enabled',label:'Enabled'}]"
        :rows="adapters as unknown as Record<string,unknown>[]" />
      <EmptyState v-else title="No adapters" description="Enable adapters to connect bot to platforms." />
    </CardContent>
  </Card>
</template>
<script setup lang="ts">
import { useRequest } from "@/composables/useRequest"
import client from "@/api/client"
import Button from "@/components/ui/button/Button.vue"
import Skeleton from "@/components/ui/skeleton/Skeleton.vue"
import Card from "@/components/ui/card/Card.vue"
import {CardContent,CardDescription,CardHeader,CardTitle} from "@/components/ui/card"
import DataTable from "@/components/DataTable.vue"
import EmptyState from "@/components/EmptyState.vue"
const {data:adapters,loading,refresh}=useRequest("adapters",()=>client.get("/adapters/selection").then(r=>r.data))
</script>
