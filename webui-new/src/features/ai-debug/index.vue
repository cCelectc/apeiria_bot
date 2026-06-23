<template>
  <Tabs v-model="tab" class="w-full">
    <TabsList>
      <TabsTrigger value="traces">Traces</TabsTrigger>
      <TabsTrigger value="usage">Usage</TabsTrigger>
      <TabsTrigger value="tools">Tools &amp; Skills</TabsTrigger>
    </TabsList>

    <TabsContent value="traces" class="mt-4">
      <Card>
        <CardHeader class="flex-row justify-between">
          <CardTitle>Turn Traces</CardTitle>
          <Button variant="outline" size="sm" @click="refreshTraces">Refresh</Button>
        </CardHeader>
        <CardContent>
          <Skeleton v-if="tracesLoading" class="h-64 w-full" />
          <div v-else-if="traces && traces.length > 0" class="flex flex-col gap-2">
            <div v-for="t in traces" :key="t.id" class="cursor-pointer rounded-md border p-3 text-sm hover:bg-muted/50" @click="selectTrace(t)">
              <div class="flex items-center justify-between">
                <span class="font-mono text-xs">{{ (t.id as string)?.slice(0, 12) }}</span>
                <div class="flex items-center gap-2">
                  <Badge variant="outline">{{ t.runtime_mode }}</Badge>
                  <Badge :variant="t.status === 'committed' ? 'default' : 'outline'">{{ t.status }}</Badge>
                </div>
              </div>
              <div v-if="t.session_id" class="mt-1 text-xs text-muted-foreground">Session: {{ t.session_id }}</div>
            </div>
          </div>
          <EmptyState v-else title="No traces" />
        </CardContent>
      </Card>

      <!-- Trace Detail -->
      <Dialog :open="showTrace" @update:open="showTrace = $event">
        <DialogContent class="sm:max-w-xl">
          <DialogHeader><DialogTitle>Trace Detail</DialogTitle></DialogHeader>
          <pre class="rounded-md bg-muted p-3 font-mono text-xs whitespace-pre-wrap overflow-auto max-h-96">{{ JSON.stringify(traceDetail, null, 2) }}</pre>
        </DialogContent>
      </Dialog>
    </TabsContent>

    <TabsContent value="usage" class="mt-4">
      <Card>
        <CardHeader class="flex-row justify-between">
          <CardTitle>Usage Summary</CardTitle>
          <Button variant="outline" size="sm" @click="refreshUsage">Refresh</Button>
        </CardHeader>
        <CardContent>
          <Skeleton v-if="usageLoading" class="h-32 w-full" />
          <DataTable v-else-if="usageItems && usageItems.length > 0"
            :columns="[{key:'model',label:'Model'},{key:'total_tokens',label:'Tokens'},{key:'request_count',label:'Requests'}]"
            :rows="usageItems as unknown as Record<string,unknown>[]" />
          <EmptyState v-else title="No usage data" />
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
import Badge from "@/components/ui/badge/Badge.vue"
import Tabs from "@/components/ui/tabs/Tabs.vue"
import { TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import Dialog from "@/components/ui/dialog/Dialog.vue"
import { DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import Card from "@/components/ui/card/Card.vue"
import { CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import DataTable from "@/components/DataTable.vue"
import EmptyState from "@/components/EmptyState.vue"

const tab = ref("traces")

const { data: traces, loading: tracesLoading, refresh: refreshTraces } = useRequest("ai-traces", () => aiDebugService.getTraces())
const { data: usageItems, loading: usageLoading, refresh: refreshUsage } = useRequest("ai-usage", () => aiDebugService.getUsageSummary())
const { data: tools, refresh: refreshTools } = useRequest("ai-tools", () => aiDebugService.getTools())
const { data: skills, refresh: refreshSkills } = useRequest("ai-skills", () => aiDebugService.getSkills())

const showTrace = ref(false)
const traceDetail = ref<unknown>(null)

function selectTrace(t: Record<string, unknown>) {
  traceDetail.value = t
  showTrace.value = true
}
</script>
