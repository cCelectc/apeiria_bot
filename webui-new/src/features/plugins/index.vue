<template>
  <Card>
    <CardHeader>
      <CardTitle>Plugins</CardTitle>
      <CardDescription>Manage installed plugins</CardDescription>
    </CardHeader>
    <CardContent>
      <FeedbackAlert v-if="error" :message="error" variant="destructive" />
      <Skeleton v-if="loading" class="h-64 w-full" />
      <div v-else-if="plugins" class="flex flex-col gap-2">
        <div
          v-for="p in plugins"
          :key="p.module_name"
          class="flex items-center justify-between rounded-md border p-3"
        >
          <div>
            <span class="font-medium">{{ p.name || p.module_name }}</span>
            <span class="ml-2 text-xs text-muted-foreground">v{{ p.version }}</span>
          </div>
          <div class="flex items-center gap-2">
            <StatusBadge :variant="p.enabled ? 'success' : 'default'">
              {{ p.enabled ? 'Enabled' : 'Disabled' }}
            </StatusBadge>
            <Switch
              :checked="p.enabled"
              @update:checked="togglePlugin(p.module_name, $event)"
            />
          </div>
        </div>
      </div>
    </CardContent>
  </Card>
</template>

<script setup lang="ts">
import { useRequest } from "@/composables/useRequest"
import { pluginsService } from "@/api/services/plugins"
import { getApiErrorMessage } from "@/api/client"
import { useNoticeStore } from "@/stores/notice"
import Card from "@/components/ui/card/Card.vue"
import CardContent from "@/components/ui/card/CardContent.vue"
import CardDescription from "@/components/ui/card/CardDescription.vue"
import CardHeader from "@/components/ui/card/CardHeader.vue"
import CardTitle from "@/components/ui/card/CardTitle.vue"
import Skeleton from "@/components/ui/skeleton/Skeleton.vue"
import Switch from "@/components/ui/switch/Switch.vue"
import FeedbackAlert from "@/components/FeedbackAlert.vue"
import StatusBadge from "@/components/StatusBadge.vue"

const notice = useNoticeStore()
const { data: plugins, loading, error, mutate } = useRequest(
  "plugins-list",
  () => pluginsService.list(),
)

async function togglePlugin(name: string, enabled: boolean) {
  try {
    await pluginsService.toggle(name, enabled)
    mutate((prev) =>
      (prev ?? []).map((p) =>
        p.module_name === name ? { ...p, enabled } : p,
      ),
    )
    notice.markRestartPending()
    notice.show(enabled ? `${name} enabled` : `${name} disabled`, "success")
  } catch (err) {
    notice.show(getApiErrorMessage(err, "Toggle failed"), "error")
  }
}
</script>
