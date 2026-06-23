<template>
  <Tabs v-model="tab" class="w-full">
    <TabsList>
      <TabsTrigger value="traces">Traces</TabsTrigger>
      <TabsTrigger value="usage">Usage</TabsTrigger>
      <TabsTrigger value="tools">Tools & Skills</TabsTrigger>
    </TabsList>

    <TabsContent value="traces" class="mt-4">
      <Card>
        <CardHeader><CardTitle>Turn Traces</CardTitle></CardHeader>
        <CardContent>
          <Skeleton v-if="tracesLoading" class="h-64 w-full" />
          <DataTable v-else-if="traces && traces.length > 0"
            :columns="[{key:'id',label:'ID'},{key:'runtime_mode',label:'Mode'},{key:'status',label:'Status'}]"
            :rows="traces as unknown as Record<string,unknown>[]" />
          <EmptyState v-else title="No traces" />
        </CardContent>
      </Card>
    </TabsContent>

    <TabsContent value="usage" class="mt-4">
      <Card>
        <CardHeader><CardTitle>Usage Summary</CardTitle></CardHeader>
        <CardContent>
          <Skeleton v-if="usageLoading" class="h-64 w-full" />
          <EmptyState v-if="!usageLoading" title="Usage data" description="Model usage information" />
        </CardContent>
      </Card>
    </TabsContent>

    <TabsContent value="tools" class="mt-4">
      <div class="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader class="flex-row justify-between"><CardTitle>Tools</CardTitle><Button variant="outline" size="sm" @click="refreshTools">Refresh</Button></CardHeader>
          <CardContent>
            <div v-if="tools" class="flex flex-col gap-1">
              <div v-for="t in tools" :key="t.name" class="flex justify-between rounded-md border p-2 text-sm">
                <span class="font-medium">{{ t.name }}</span><span class="text-muted-foreground">{{ t.description }}</span>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader class="flex-row justify-between"><CardTitle>Skills</CardTitle><Button variant="outline" size="sm" @click="refreshSkills">Refresh</Button></CardHeader>
          <CardContent>
            <div v-if="skills" class="flex flex-col gap-2 text-sm">
              <div v-for="s in skills" :key="s.name" class="rounded-md border p-2">
                <span class="font-medium">{{ s.name }}</span>
                <p class="text-muted-foreground">{{ s.description }}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </TabsContent>
  </Tabs>
</template>
<script setup lang="ts">
import { ref } from "vue"
import { useRequest } from "@/composables/useRequest"
import { aiDebugService } from "@/api/services/ai-debug"
import Button from "@/components/ui/button/Button.vue"
import Skeleton from "@/components/ui/skeleton/Skeleton.vue"
import Tabs from "@/components/ui/tabs/Tabs.vue"
import {TabsContent,TabsList,TabsTrigger} from "@/components/ui/tabs"
import Card from "@/components/ui/card/Card.vue"
import {CardContent,CardHeader,CardTitle} from "@/components/ui/card"
import DataTable from "@/components/DataTable.vue"
import EmptyState from "@/components/EmptyState.vue"
const tab=ref("traces")
const {data:traces,loading:tracesLoading}=useRequest("ai-traces",()=>aiDebugService.getTraces())
const { loading: usageLoading } = useRequest("ai-usage", () => aiDebugService.getUsageSummary())
const {data:tools,refresh:refreshTools}=useRequest("ai-tools",()=>aiDebugService.getTools())
const {data:skills,refresh:refreshSkills}=useRequest("ai-skills",()=>aiDebugService.getSkills())
</script>
