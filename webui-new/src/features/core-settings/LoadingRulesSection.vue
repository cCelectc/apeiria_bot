<template>
  <Card>
    <CardHeader class="flex-row items-center justify-between">
      <div>
        <CardTitle>Plugin Loading Rules</CardTitle>
        <CardDescription>Configure which modules and directories to load at startup</CardDescription>
      </div>
      <Button variant="outline" size="sm" @click="refresh()">Refresh</Button>
    </CardHeader>
    <CardContent>
      <div class="grid gap-6 lg:grid-cols-2">
        <div>
          <div class="flex items-center justify-between mb-2">
            <h3 class="text-sm font-medium">Plugin Modules</h3>
            <Button variant="ghost" size="sm" @click="addModule"><Plus class="size-4" /> Add</Button>
          </div>
          <div class="flex flex-col gap-1">
            <div v-for="(m, i) in modules" :key="i" class="flex items-center justify-between rounded-md bg-muted px-3 py-1 text-sm">
              <span class="font-mono text-xs">{{ m }}</span>
              <Button variant="ghost" size="icon" class="size-6" @click="removeModule(i)"><X class="size-3" /></Button>
            </div>
            <EmptyState v-if="modules.length === 0" title="No modules" />
          </div>
        </div>
        <div>
          <div class="flex items-center justify-between mb-2">
            <h3 class="text-sm font-medium">Plugin Directories</h3>
            <Button variant="ghost" size="sm" @click="addDir"><Plus class="size-4" /> Add</Button>
          </div>
          <div class="flex flex-col gap-1">
            <div v-for="(d, i) in dirs" :key="i" class="flex items-center justify-between rounded-md bg-muted px-3 py-1 text-sm">
              <span class="font-mono text-xs truncate">{{ d }}</span>
              <Button variant="ghost" size="icon" class="size-6" @click="removeDir(i)"><X class="size-3" /></Button>
            </div>
            <EmptyState v-if="dirs.length === 0" title="No directories" />
          </div>
        </div>
      </div>
      <Button class="mt-4" @click="save">Save</Button>
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { Plus, X } from "@lucide/vue"
import { useRequest } from "@/composables/useRequest"
import client from "@/api/client"
import { useNoticeStore } from "@/stores/notice"
import { getApiErrorMessage } from "@/api/client"
import Button from "@/components/ui/button/Button.vue"
import Card from "@/components/ui/card/Card.vue"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import EmptyState from "@/components/EmptyState.vue"

const notice = useNoticeStore()
const modules = ref<string[]>([])
const dirs = ref<string[]>([])

const { refresh } = useRequest("plugin-sources", () =>
  client.get("/plugins/local-sources").then((r) => {
    modules.value = (r.data as Record<string, unknown>).modules as string[] ?? []
    dirs.value = (r.data as Record<string, unknown>).dirs as string[] ?? []
    return r.data
  }),
)

function addModule() { const m = prompt("Module name:"); if (m) modules.value.push(m) }
function removeModule(i: number) { modules.value.splice(i, 1) }
function addDir() { const d = prompt("Directory path:"); if (d) dirs.value.push(d) }
function removeDir(i: number) { dirs.value.splice(i, 1) }

async function save() {
  try {
    await client.patch("/plugins/local-sources", { modules: modules.value, dirs: dirs.value })
    notice.markRestartPending()
    notice.show("Loading rules saved. Restart required.", "info")
  } catch (err) { notice.show(getApiErrorMessage(err, "Failed"), "error") }
}
</script>
