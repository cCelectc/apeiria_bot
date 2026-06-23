<template>
  <Card>
    <CardHeader>
      <CardTitle>Plugins</CardTitle>
      <CardDescription>Manage installed plugins</CardDescription>
    </CardHeader>
    <CardContent>
      <Skeleton v-if="loading" class="h-64 w-full" />
      <div v-else-if="plugins" class="flex flex-col gap-2">
        <div v-for="p in plugins" :key="p.module_name" class="flex items-center justify-between rounded-md border p-3">
          <div>
            <span class="font-medium">{{ p.name || p.module_name }}</span>
            <span class="ml-2 text-xs text-muted-foreground">v{{ p.version }}</span>
          </div>
          <div class="flex items-center gap-2">
            <Button variant="ghost" size="sm" @click="openSettings(p as unknown as Record<string,unknown>)">Settings</Button>
            <Button variant="ghost" size="sm" @click="openReadme(p as unknown as Record<string,unknown>)">README</Button>
            <Switch :checked="p.enabled" @update:checked="togglePlugin(p.module_name, $event)" />
            <StatusBadge :variant="p.enabled ? 'success' : 'default'">{{ p.enabled ? 'On' : 'Off' }}</StatusBadge>
          </div>
        </div>
      </div>
    </CardContent>
  </Card>

  <!-- Settings Dialog -->
  <Dialog :open="showSettings" @update:open="showSettings = $event">
    <DialogContent class="sm:max-w-lg">
      <DialogHeader><DialogTitle>{{ settingsPlugin?.module_name }} Settings</DialogTitle></DialogHeader>
      <Skeleton v-if="settingsLoading" class="h-48 w-full" />
      <div v-else class="flex flex-col gap-4">
        <MonacoEditor v-model="settingsRaw" language="toml" :style="{ height: '300px' }" />
        <Button @click="saveSettings">Save</Button>
      </div>
    </DialogContent>
  </Dialog>

  <!-- README Dialog -->
  <Dialog :open="showReadme" @update:open="showReadme = $event">
    <DialogContent class="sm:max-w-xl max-h-[80vh] overflow-auto">
      <DialogHeader><DialogTitle>{{ readmePlugin?.module_name }} README</DialogTitle></DialogHeader>
      <div v-if="readmeHtml" v-html="readmeHtml" class="prose prose-sm max-w-none" />
      <Skeleton v-else class="h-32 w-full" />
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { useRequest } from "@/composables/useRequest"
import { pluginsService } from "@/api/services/plugins"
import { getApiErrorMessage } from "@/api/client"
import { useNoticeStore } from "@/stores/notice"
import Button from "@/components/ui/button/Button.vue"
import Skeleton from "@/components/ui/skeleton/Skeleton.vue"
import Switch from "@/components/ui/switch/Switch.vue"
import Dialog from "@/components/ui/dialog/Dialog.vue"
import { DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import Card from "@/components/ui/card/Card.vue"
import { CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import StatusBadge from "@/components/StatusBadge.vue"
import MonacoEditor from "@/components/MonacoEditor.vue"

const notice = useNoticeStore()
const { data: plugins, loading, mutate } = useRequest("plugins-list", () => pluginsService.list())

async function togglePlugin(name: string, enabled: boolean) {
  try { await pluginsService.toggle(name, enabled); mutate((prev) => (prev ?? []).map(p => p.module_name === name ? { ...p, enabled } : p)); notice.markRestartPending(); notice.show(`${name} ${enabled ? 'enabled' : 'disabled'}`, "success") }
  catch (err) { notice.show(getApiErrorMessage(err, "Toggle failed"), "error") }
}

const showSettings = ref(false); const settingsPlugin = ref<Record<string,unknown>|null>(null); const settingsRaw = ref(""); const settingsLoading = ref(false)
const showReadme = ref(false); const readmePlugin = ref<Record<string,unknown>|null>(null); const readmeHtml = ref("")

async function openSettings(p: Record<string,unknown>) {
  settingsPlugin.value = p; showSettings.value = true; settingsLoading.value = true
  try { const res = await pluginsService.getSettings(p.module_name as string); settingsRaw.value = JSON.stringify(res, null, 2) }
  catch { settingsRaw.value = "# Failed to load" }
  finally { settingsLoading.value = false }
}
async function saveSettings() {
  if (!settingsPlugin.value) return
  try { await pluginsService.updateSettings(settingsPlugin.value.module_name as string, JSON.parse(settingsRaw.value)); showSettings.value = false; notice.markRestartPending(); notice.show("Settings saved", "success") }
  catch (err) { notice.show(getApiErrorMessage(err, "Failed"), "error") }
}
async function openReadme(p: Record<string,unknown>) {
  readmePlugin.value = p; showReadme.value = true; readmeHtml.value = ""
  try { const res = await pluginsService.getReadme(p.module_name as string); readmeHtml.value = (res as Record<string,unknown>).content as string ?? "<p>No README</p>" }
  catch { readmeHtml.value = "<p>Failed to load</p>" }
}
</script>
