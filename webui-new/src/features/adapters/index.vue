<template>
  <div class="flex flex-col gap-6">
    <div class="flex items-center justify-between">
      <div />
      <Button variant="outline" size="sm" :disabled="loading" @click="refresh()">
        <RotateCw class="size-4" /> Refresh
      </Button>
    </div>

    <Skeleton v-if="loading" class="h-64 w-full" />

    <div v-if="adapters && adapters.length > 0" class="flex flex-col gap-3">
      <Card v-for="a in adapters" :key="a.name">
        <CardHeader class="flex-row items-center justify-between pb-2">
          <div>
            <CardTitle class="text-base">{{ a.name }}</CardTitle>
            <CardDescription>{{ a.type }}</CardDescription>
          </div>
          <div class="flex items-center gap-2">
            <StatusBadge :variant="a.enabled ? 'success' : 'default'">
              {{ a.enabled ? 'Enabled' : 'Disabled' }}
            </StatusBadge>
            <Switch :checked="a.enabled" @update:checked="toggleAdapter(a.name, $event)" />
          </div>
        </CardHeader>
        <CardContent v-if="a.description">
          <p class="text-sm text-muted-foreground">{{ a.description }}</p>
        </CardContent>
      </Card>
    </div>

    <EmptyState v-else title="No adapters" description="Configure and enable adapters from the store." />

    <!-- Config Dialog -->
    <Dialog :open="showConfig" @update:open="showConfig = $event">
      <DialogContent class="sm:max-w-md">
        <DialogHeader><DialogTitle>Adapter Config</DialogTitle></DialogHeader>
        <CardContent>
          <p class="text-sm text-muted-foreground">Module configuration: {{ configText || 'No config loaded' }}</p>
        </CardContent>
        <DialogFooter>
          <Button variant="outline" @click="showConfig = false">Close</Button>
          <Button @click="saveConfig">Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { RotateCw } from "@lucide/vue"
import { useRequest } from "@/composables/useRequest"
import client from "@/api/client"
import { getApiErrorMessage } from "@/api/client"
import { useNoticeStore } from "@/stores/notice"
import Button from "@/components/ui/button/Button.vue"
import Skeleton from "@/components/ui/skeleton/Skeleton.vue"
import Switch from "@/components/ui/switch/Switch.vue"
import Dialog from "@/components/ui/dialog/Dialog.vue"
import DialogContent from "@/components/ui/dialog/DialogContent.vue"
import DialogFooter from "@/components/ui/dialog/DialogFooter.vue"
import DialogHeader from "@/components/ui/dialog/DialogHeader.vue"
import DialogTitle from "@/components/ui/dialog/DialogTitle.vue"
import Card from "@/components/ui/card/Card.vue"
import CardContent from "@/components/ui/card/CardContent.vue"
import CardDescription from "@/components/ui/card/CardDescription.vue"
import CardHeader from "@/components/ui/card/CardHeader.vue"
import CardTitle from "@/components/ui/card/CardTitle.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import EmptyState from "@/components/EmptyState.vue"

const notice = useNoticeStore()
const { data: adapters, loading, refresh } = useRequest("adapters", () =>
  client.get("/adapters/selection").then((r) => r.data),
)

async function toggleAdapter(name: string, enabled: boolean) {
  try {
    if (enabled) {
      await client.post("/adapters/selection/enable", { module_name: name })
    } else {
      await client.post("/adapters/selection/disable", { module_name: name })
    }
    refresh()
    notice.markRestartPending()
    notice.show(enabled ? `${name} enabled` : `${name} disabled`, "success")
  } catch (err) {
    notice.show(getApiErrorMessage(err, "Toggle failed"), "error")
  }
}

const showConfig = ref(false)
const configText = ref("")

async function saveConfig() { showConfig.value = false }
</script>
