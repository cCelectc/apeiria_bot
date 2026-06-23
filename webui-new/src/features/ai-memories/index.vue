<template>
  <Card>
    <CardHeader class="flex-row items-center justify-between">
      <div><CardTitle>AI Memories</CardTitle><CardDescription>Fact memories stored by the bot</CardDescription></div>
      <div class="flex gap-2">
        <Input v-model="search" placeholder="Search..." class="w-48" />
        <Button variant="outline" size="sm" @click="searchMemories">Search</Button>
      </div>
    </CardHeader>
    <CardContent>
      <Skeleton v-if="loading" class="h-64 w-full" />
      <DataTable v-else-if="memories && memories.length > 0"
        :columns="[{key:'content',label:'Content'},{key:'layer',label:'Layer'},{key:'kind',label:'Kind'}]"
        :rows="memories as unknown as Record<string,unknown>[]" />
      <EmptyState v-else title="No memories" />
    </CardContent>
  </Card>
</template>
<script setup lang="ts">
import { ref } from "vue"
import { useRequest } from "@/composables/useRequest"
import { aiMemoriesService } from "@/api/services/ai-memories"
import Button from "@/components/ui/button/Button.vue"
import Input from "@/components/ui/input/Input.vue"
import Skeleton from "@/components/ui/skeleton/Skeleton.vue"
import Card from "@/components/ui/card/Card.vue"
import {CardContent,CardDescription,CardHeader,CardTitle} from "@/components/ui/card"
import DataTable from "@/components/DataTable.vue"
import EmptyState from "@/components/EmptyState.vue"
const search=ref("")
const {data:memories,loading,refresh}=useRequest("ai-memories",()=>aiMemoriesService.list())
async function searchMemories(){refresh()}
</script>
